# Spec：v7 settle 后置钩子（v8-gap-review 阶段三 P3-1）

> 档位：Architectural（改 `settle` 成功路径与 git add 范围）
> 状态：**已批准**（Human 2026-09-04；方案 A；git 默认改为后置文件扩进本次 `git add`）
> 上游：`docs/zcode/v8-gap-review-3rounds/README.md` 阶段三 P3-1；阶段一 spec §8「P3-1 会再改 settle」
> 下游：同目录 `2026-09-04-settle-post-hooks-plan.md` → TDD → 收尾

## 1. 背景与目标

`v7_write.settle` 在 P1-2 后已有三门禁与原子落定（正文 / 章摘要 / 新实体 + `git add 定稿`），但成功后不写素材轨迹、文风指纹、追读力表。v6 `chapter_commit.py` 已按 try/except 调用 `settle_materials_for_chapter` 与 `settle_style_domain`。阶段一 spec 预留的 `_run_post_hooks()` 空壳未落地。

**目标：** settle 一条命令在成功落定后自动串三条后置，失败不回滚、不改退出码；后置产物与定稿进入同一次 git commit。

**成功标准（抄 gap-review 阶段三 P3-1 原文）：**

> settle 成功后自动串：materials log（幂等闸已有）→ settle_style_domain（指纹+高分采样）→ reading_power（从摘要 front matter 提取）；各自 try/except 不阻断 settle；CLI 输出后置结果一行
>
> 验收：ch43 settle 一次跑完，轨迹/指纹/追读力三表自动更新

## 2. 非目标

- 不实现 P3-2 工坊执行器、P3-3 写回播种 / learn CLI / 重复大纲去重。
- 不清理 `.webnovel/tmp/`（N12，未排进 P3-1）。
- 不改 v6 `chapter_commit.py` / write-gate / `context_manager`。
- 不把 v7 settle 接进 `.story-system` chapter-commit 投影链。
- 不在本任务给摘要强行补钩子字段；无 `hook_type` 则追读力 skip。
- 不降低文风采样门槛（仍 ≥85 且无 blocking issue）；v7 审查文件无 `overall_score` 时只更新指纹、不高分采样。

## 3. 方案与裁决

| 方案 | 内容 | 裁决 |
|---|---|---|
| **A（采纳）** | `settle` 事务写盘成功后 `_run_post_hooks` 调三个既有域函数；CLI 一行；后置文件并入本次 git add | 对齐原文「一条命令」；与 v6 落账同函数 |
| B | 另做 `v7-write post`，skill 再调一次 | 否决：易漏，对不上「一条命令」 |
| C | v7 settle 走 v6 chapter-commit 投影链 | 否决：绑 `.story-system` commit，违反「不重写为 v6 合同链」 |

**Git（Human 2026-09-04 改默认）：** 后置文件扩进本次 `git add`，与 `定稿` 同一次 commit。因此后置必须在 `git add` / `commit` **之前**运行（仍在门禁通过且定稿已写盘之后）。`--no-commit` 仍跑后置，不 git。

被 gitignore 的路径（如测试夹具忽略整个 `.webnovel/`）不 `add -f`；磁盘仍更新。

## 4. 设计

### 4.1 调用顺序

```
门禁通过 → 写 定稿/正文 + 章摘要 + 新实体
         → 审查绕过 journal（若有）
         → _run_post_hooks（材料 → 文风 → 追读力；各自 try/except）
         → git add 定稿 + 存在且未被 ignore 的后置路径
         → git commit
         → rebuild_cache（仍 best-effort，不进本次 add）
```

门禁拒绝 / 机检失败 / 唯一写入路径拒绝：不跑后置、不 git。

后置失败：写入 `result["post"][*].status=error`，**不**回滚定稿，退出码仍 0。

### 4.2 三条钩子（只调已有实现）

| 顺序 | 调用 | 成功时磁盘 | status |
|---|---|---|---|
| 1 | `log_chapter_materials(root, chapter)` | `素材/使用轨迹.jsonl` + journal `domain=素材` | `ok` / `already_logged` / `skipped`（无章纲卡） |
| 2 | `settle_style_domain(root, chapter, review_file=…/review_results.json, extraction_file=可选)` | `文风/指纹.yaml`；高分时 style_samples | `ok`（指纹写入即 ok）；采样数记 `recorded` |
| 3 | `settle_reading_power(root, chapter, summary_text)`（本任务新增薄封装） | `.webnovel/index.db` 表 `chapter_reading_power` | `ok` 或 `skipped`（无 hook_type） |

`settle_reading_power` 用已有 `extract_hook_fields({"summary_text": …})`，再 `IndexManager.save_chapter_reading_power`。不要求 `.story-system` commit payload。先看 settle 传入的摘要文本，空则读 `定稿/记忆/章摘要/{NNNN}.md`。

审查文件路径固定 `.webnovel/tmp/review_results.json`；extraction 仅当 `.webnovel/tmp/extraction_result.json` 存在时传入。

### 4.3 git add 路径

固定候选（存在才 add）：

```
定稿
素材/使用轨迹.jsonl
文风/指纹.yaml
作者/journal.jsonl
.webnovel/index.db
```

`git check-ignore` 退出 0 的路径跳过。不 `git add -A`。

### 4.4 返回值与 CLI

`settle()` 增加 `post`：

```json
{
  "materials": {"status": "ok", "logged": 1},
  "style": {"status": "ok", "recorded": 0, "fingerprint_chapters": 2},
  "reading": {"status": "skipped", "reason": "not_required"}
}
```

CLI 在现有 OK 行末追加 `post=`：

```text
OK v7-write settle chapter=42 committed=True bypassed=False file=... post=materials:ok/1 style:fp=2,samples=0 reading:skipped
```

退出码仍只由门禁 / 机检 / 落盘 / git 决定。

### 4.5 验收章号

原文「ch43」。单测用 tmp 书仓任意未 settle 章。fantasy01 冒烟：若 43 已有 `0043-` 定稿，改用**尚未 settle** 的最小章号，并在 README 记录实际章号，不删真仓正文。

## 5. 数据与兼容

- 不改轨迹 / 指纹 / `chapter_reading_power` schema。
- 不改门禁语义与 `GateRejected` 退出码 2。
- 现有只 `git add 定稿` 的测试：多 add 的后置文件不改变定稿回滚范围（回滚仍只 unlink 本次新建的定稿文件）。

## 6. 验收清单（W1：引用方案原文）

| # | 方案原文 | 验证 |
|---|---|---|
| 1 | materials log（幂等闸已有） | 章纲卡有可解析 `素材引用` → 轨迹出现该章行；再 settle 同章被唯一路径拦住。无卡 → materials skipped，settle 仍成功 |
| 2 | settle_style_domain（指纹+高分采样） | 成功后存在 `文风/指纹.yaml`；无 overall_score 时 `recorded=0` |
| 3 | reading_power（从摘要 front matter 提取） | 摘要含 `hook_type`/`hook_strength` → `get_chapter_reading_power(章)` 有行；无字段 → skipped |
| 4 | 各自 try/except 不阻断 settle | monkeypatch 一条钩子抛错 → 定稿仍在，exit 0，该条 status=error |
| 5 | CLI 输出后置结果一行 | stdout 含 `post=materials:` |
| 6 | 后置文件扩进本次 git add | `commit=True` 后 `git ls-files` 含轨迹与指纹（未被 ignore 时） |
| 7 | 门禁拒绝不跑后置 | blocking 审查 → 无 `0042-*`、无新指纹 |
| 8 | 回归 | 既有 `test_v7_write_gates.py` 全绿；全量 pytest；cov ≥80 |

## 7. 约束

- TDD：先失败测试再实现。
- 不修改 `context_manager.py`、`write_gates/*`、v6 `chapter_commit.py`。
- Windows：`python -X utf8`。
- 提交：spec/plan 与实现分开 commit。
