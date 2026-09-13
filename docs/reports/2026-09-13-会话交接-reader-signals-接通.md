# 会话交接（W4）— reader_signals 在 v7 接通

> ⚠️ **本文件已过期**：它是 2026-09-13 会话**中途**写的，此后同一会话又落了 20 个提交
> （D-2 乙 裁决落地、死引用根因修复、6 项缺陷修复、9 条待办结案）。
> **请改读全场交接：`docs/reports/2026-09-13-会话交接-缺陷修复与口径收口.md`。**
> 本文件保留是因为它对 reader_signals 那一段的记录仍准确，可作该主题的细节补充。

> 会话：2026-09-13（Claude Code 宿主，分支 `v8-author`）
> 曾要求下会话开局读本文件，再读 `docs/reports/2026-09-13-会话交接-v7路径收口.md`（前一轮）。
> 红线：左栏每个事实必须附出处；写不出出处的放右栏当假设。

---

## 一、已验证事实（附出处）

### 起点与终点

| 事实 | 出处 |
|---|---|
| 会话起点：`t-20260913-6202` 定性的「reader_signals 换落点」——方案写「v7 生产 / v6 存储，**只需换落点，不需补生产**」 | `docs/reports/2026-09-12-需求与设计对账.md` §D-2 乙 原条目 |
| **该前提被实测证伪**：生产端在 v7 上是死的 | ① 钩子字段只从摘要 front matter 提取（`reading_power_projection.py:28` 的 `summary.startswith("---")`）② 真实流程传纯文本（`skills/webnovel-write/SKILL.md:177`）③ v7 写链无 data-agent 步骤（该 SKILL 全文无匹配）④ 章纲卡模板与真书都无 `钩子类型`/`钩子强度`（真书 `fantasy01-pov` 第 41/42 章 directive 探针 `hook_type=None`） |
| 会话终点：链路端到端打通，退出码 0 | 见下方「端到端探针」 |
| `.cache/index.db` 原只有 4 张表，`_cache_intact` 只查「四表齐备」 | `v7_cache.py`（会话起点时的 `:206`）；本会话改为同时校验 `meta.schema_version` |

### 本会话的提交（`v8-author`，**均未 push**）

| 提交 | 内容 |
|---|---|
| `ca7417d` | spec + plan（含 5 个被否方案的逐个证伪） |
| `1a080a5` | Task 1：`.cache` 新增 `chapter_reading_power` 表（schema v2 + 版本化） |
| `9b0e0b8` | 计划回改：Task 1 测试改为扩展既有文件（W12） |
| `9e84b4d` | Task 2+3：settle 落正文 front matter + `run_checks` 钩子硬闸 |
| `445c526` | 计划回改：Task 6 断言改走旁路 settle（W12） |
| `7a060a5` | Task 4：追读力写盘退役，`_SETTLE_ADD_PATHS` 去掉 `.webnovel/index.db` |
| `2e43209` | Task 5：消费侧按形态分叉 + `index get-reader-signals` v7 派发 |
| `04737ec` | Task 6：冒烟断言非空 + 三处文档回改 |

### 端到端探针（`.tmp/probe-reader-signals-e2e.py`，会话内实跑）

```
1. check                      OK
2. settle                     OK
3. 正文 front matter           钩子类型: 危机钩 ／ 钩子强度: strong（决策卡写「强」，已归一）
4. index get-reader-signals   [{"chapter":42,"hook_type":"危机钩","hook_strength":"strong"}]
                              hook_type_usage: {"危机钩":1}
5. v7-cache verify            OK equal=True（删缓存→重建→快照等价）
6. 删掉 .cache 后再查          仍读得到（派生物可丢弃，按需重建）
7. .webnovel/index.db 存在？   False（v6 域副作用消失）
```

### 关键实现位置（下会话可能要动）

| 关注点 | 位置 |
|---|---|
| 钩子机检闸 | `v7_write.py` `run_checks`：`hook_ok = bool(hook_type) or bool(hook_waiver)` |
| 钩子落盘 | `v7_write.py` `settle` 的 front matter 构造段（`书内时间` 之后） |
| 追读力表 | `v7_cache.py`：`_iter_reading_power` / `get_recent_reading_power` / `get_hook_type_usage` / `_CACHE_SCHEMA_VERSION` |
| 消费侧分叉 | `data_modules/reader_signal_builder.py`：`_is_v7_repo` / `_v7_signal` / `_v6_signal` |
| CLI 派发 | `data_modules/webnovel.py`：`index get-reader-signals` 的 v7 分支（在 `if tool == "index"` 之前） |
| 冒烟轮 C | `webnovel-writer/scripts/smoke_v7_newbook.py`：`_run_assert` / `_reading_power_non_empty` |

### 验证证据（会话末）

| 项 | 结果 |
|---|---|
| 全量 pytest | **EXIT=0**，覆盖率 82.64%（≥80 闸） |
| 冒烟 | **PASS 19 ｜ BREAK 0 ｜ BIZ 2**，退出码 0 |
| 四校验 | `sync_plugin_version --check` / `validate_release_notes` / `validate_plugin_package` / `validate_reference_wiring` **全 EXIT=0** |
| CI | ✅ **已跑且双平台绿**：run `34747226885` @ `dff8ea0` —— `tests-windows` ✓ 2m13s、`tests`（ubuntu）✓ 1m14s |

> **冒烟基线变了**：`PASS 18` → `PASS 19`。原因是 `reader-signals` 移出「8 只读工具面」
> 通用循环（−1）并新增轮 C 的 C1/C2 两步（+2）。**不是新缺陷被修**，是步骤重排。

---

## 二、假设 / 待确认

- ~~**假设**：CI 双平台会绿。~~ → ✅ **2026-09-13 已验证为事实**：push 后 run `34747226885`
  双 job 全绿（见上表）。本会话涉及的是纯 Python/sqlite 改动 + 冒烟步骤重排，无平台敏感项，
  与结果一致。
- **假设**：存量 v6 书仓的读者信号行为未变。已加反向守住用例
  （`test_v6_repo_still_reads_webnovel_index_db`：构造有 `state.json` 的仓并真写
  `chapter_reading_power` 行，断言仍读 `.webnovel/index.db`），但**未在真实 v6 书仓上跑过**。
- **未做**：存量章（40+）钩子回填——不回溯，已登记 `t-20260913-25f8`。
- **未做**：`review_trend` 在 v7 仍恒为空（无生产者），已登记 `t-20260913-3e39`，
  与 D-2 乙剩余决策一并裁决。

---

## 三、本轮踩到的坑（怎么发现的、怎么绕开）

1. **前提证伪比实现更值钱**：本条原定性是「只需换落点」，我按方案勘察时才发现生产端是死的。
   **教训：接到「方案已定、可直接做」的条目，仍要独立验一遍它的前提**——否则会把一个死路径搬家。
2. **加闸必须查全部调用点**：钩子硬闸加上后，波及 3 处（两个测试夹具、冒烟决策卡、CLI 转发用例），
   其中**冒烟那处不改会让 CI 直接红**。用 grep 逐个查 `run_checks(` / `settle(` / `_decision(` 才找全。
3. **Edit 锚点不要用类内方法名**：给 `test_v7_write.py` 插新测试类时，我以类内某方法名为锚，
   结果把新类插进旧类中间并重复了类头——Python 允许重定义，**前一个类被静默覆盖、丢两条既有测试**。
   读回文件时发现。**教训：插类要锚定文件尾或类边界。**
4. **直接跑代码胜过读代码**：本次多个结论（章纲卡无钩子字段、`book-init` 真建 git 仓、
   冒烟书仓是 `--no-git` 建的）都是**跑探针/跑真命令**得出的，读代码只给了假设。
5. **断言必须先见红**：轮 C 的「reader-signals 非空」断言首轮真的报了
   `断言失败：…` 并判 BREAK（退出码 1），修好数据源才转 PASS——**这才证明断言会咬**，
   而不是恰好通过。

---

## 四、交接给下一会话

- **进行到**：`t-20260913-6202` 已结（范围重新定性后全部落地）。v6 线退役 Phase 3 的
  `reader_signals` 一项从「待做」推进到「已接通且有端到端守护」。
- **下一步（建议顺序）**：
  1. ~~**push 并确认 CI 双平台绿**~~ → ✅ **已完成**（2026-09-13，Human 授权后推送；
     `8b3bfb8..dff8ea0`，CI run `34747226885` 双 job 绿）。**注意**：本次推送一并带上了
     上会话遗留的 3 个 OpenCode 文档提交（`63da9af` / `6b03d20` / `492c68d`），它们是快进，
     非本会话产物。
  2. **D-2 乙 剩余决策**（P1，需 Human 拍板）：`rag_search` / `knowledge` 真砍 vs 在 v7 写链补生产者，
     外加 `meter` 去留；定了才能同步 README/AGENTS/commands.md 的「14 只读工具」承诺数。
  3. **`t-20260913-1072` 的另一半**：`pack` 副作用建 `style_samples.db`（本轮已消解
     `index.db 被 settle 加入 git` 那一半）。
  4. `t-20260913-a126`（本轮新登记）：`book-init --no-git` 的仓走 settle 默认路径必失败，
     报错不指向根因。**本轮的冒烟只因为它先被 prose 门禁拒才没暴露。**
- **本轮的元教训**：与上一轮同一句话——**已知的每个缺陷都是「撞见」的**。
  本轮新增的两个手段（端到端探针 + 冒烟断言先红后绿）确实把「撞见」变成了「查出来」，
  但 `t-20260913-a126` 仍然是撞见的（在给轮 C 调 `--no-commit` 时才看到根因）。
