# v8 功能缺口三轮复盘报告（附修复计划）

> 复盘时间：2026-09-04｜方法：三轮递进——①逐项验证既有审计 ②横向扩展未覆盖面 ③端到端场景推演
> 基线：docs/zcode/v8-migration-gap-audit/README.md（28 项缺口）+ fantasy01 实仓验证
> 结论：**原 28 项中 1 项根因需修正；三轮新发现 12 项；合计 40 项缺口归并为 4 个修复阶段**

---

## 第 1 轮复盘：既有审计逐项验证

### 1.1 重大修正：A1「详细大纲未迁移」结论有误

**原结论**：迁移器漏了详细大纲 → 仓里无逐章规划 → 标题自造。

**验证事实**（git 历史 + 内容比对）：

```
迁移提交 2343eb0 中，大纲/卷纲/第01卷.md（1633 行）已存在
  ← 该文件就是源项目 大纲/第1卷-详细大纲.md 的重命名产物
  ← 含全部 80 个逐章标题（## 第40章：灾前夜 就在其中）
```

迁移器 `_migrate_outlines` 的 glob `第*卷-详细大纲.md` → 重命名为 `卷纲/第{NN}卷.md`（去掉了「详细大纲」后缀）。

**修正后的根因链**：

```
迁移器重命名丢失语义（第01卷.md 看不出是逐章规划）
    ↓
AI 建章纲卡时读卷纲只读头部摘要，不知道往下 800 行有逐章标题
    ↓
create_chapter_batch 不读详细大纲（无论叫什么名字）→ 标题自造
    ↓
后续手动补入 -详细大纲.md 后缀版 → 现在同一内容存两份（重复）
```

### 1.2 原审计其余 27 项验证结果

| 类别 | 验证结论 |
|------|---------|
| A2 增强设定 skip 理由错误 | ✅ 属实（skipped 列表明写「v7 由角色卡承接」但内容不在） |
| A3 总纲写回.json | ⚠️ 属实 + **新发现：迁入后无消费者**（promise_ledger 无「从写回 JSON 播种账本」功能，8 条伏笔数据躺着没人读） |
| A4 审查报告 | ✅ 属实（已补） |
| B1-B5 章纲自检缺 5 项 | ✅ 全部属实（self_check_batch 仅 4 项检查，实测确认） |
| C1-C14 v7 上下文包缺 14 section | ✅ 全部属实（build_context_pack 实测仅 7 section） |
| D1-D3 settle 缺门禁 | ✅ 全部属实（v7 settle 不看 review_results、不跑 prose_check、不查素材引用） |
| E1-E3 链路断裂 | ✅ 全部属实（grep 验证 v7_write.py 零后置钩子、零 stale/author_model 引用） |

### 1.3 第 1 轮新发现

| # | 新发现 | 证据 |
|---|--------|------|
| N1 | 详细大纲内容重复两份 | `第01卷.md` 与 `第01卷-详细大纲.md` 前 20 行 diff 完全一致 |
| N2 | 总纲写回.json 无消费者 | promise_ledger/webnovel.py 中除 master-outline-sync 的同名参数外零引用 |

---

## 第 2 轮复盘：横向扩展（原审计未覆盖面）

### 2.1 doctor 治理检查组完全未建（最严重新发现）

07 方案 F-13 明确要求 doctor 新增 8 组检查：journal 水位/stale 积压/定版-轨迹一致性/锚点-正文对账/条目状态机/素材健康摘要/画廊积压/合同编译一致性。

**实测**（fantasy01 真仓跑 `build_doctor_report`）：只有 8 个环境检查（python.version / 依赖导入×7），**零治理检查**。MCP `webnovel_doctor` 暴露的也是这个空壳版本。

> **勘误 2026-09-04（复审 §6）**：「零治理检查」属实；「只有环境检查」是表象——`build_doctor_report`（`doctor.py:861-945`）本有 12 组项目检查（preflight / file / json / story_runtime / sqlite / total_words / projection_log / extraction / contract_version / run_log / rag / domain_contract），在 fantasy01 只跑出环境组是因为 doctor **对纯 v7 书仓解析不到项目根**（依赖 `.webnovel/state.json`，08 计划 T1 证据行已登记「phase 解析限制」但未排任务）。`_python_checks` 实为 version + 6 import = 7 项。修复见 P4-0。
>
> **P4-0 完成记录（2026-09-04）**：根解析已修。fantasy01 CLI doctor `phase=v7_story_repo`，§4.6 十二组前缀 12/12，`check_count=32`，不再只剩 python.*。P4-1 八组治理检查仍未建，不把本节改成「已有治理检查」。

### 2.2 06 §12 六条数据不变量仅 1 条实现

| # | 不变量 | 实现 |
|---|--------|------|
| 1 | journal 无未分类事件积压 | ❌（author-sync 兜底新增，但不校验积压） |
| 2 | 使用轨迹引用 (条目,定版版本) 在 manifest 中存在 | ❌ |
| 3 | 力量锚点战例章号有定稿正文；境界链序单调 | ⚠️（序单调有 validate_chain；战例-正文对账无） |
| 4 | 条目状态机合法 | ✅（promise_ledger LEGAL_TRANSITIONS） |
| 5 | .story-system 合同与正典编译一致（重建对账） | ❌ |
| 6 | stale 无超过一卷未消费 | ❌ |

### 2.3 详细大纲三重路径分裂

同一文件在链路中有三种位置命名：
- plan skill 输出：`大纲/第N卷-详细大纲.md`（v6 平铺路径）
- 迁移器产物：`大纲/卷纲/第NN卷.md`（重命名去后缀）
- 手动补入：`大纲/卷纲/第NN卷-详细大纲.md`（卷纲内带后缀）

读写路径不统一 → 每次 AI 操作都要猜文件在哪。

### 2.4 其他横向发现

| # | 发现 | 影响 |
|---|------|------|
| N5 | 工坊 confirm 的三处同步只登记标记（`power_anchor_sync:required` 写进 journal impact），无执行器消费这些标记 | 作者采纳后仍需手工同步锚点/重编译合同 |
| N6 | dashboard governance.py 六视图不读承诺账本（条目/逾期视图缺失，F-14 只写了 stale 红点） | 逾期承诺在面板不可见 |
| N7 | 素材播种 `_GENRE_KEYWORDS` 无复合题材键（fantasy01 = 都市+仙侠+科幻，只能按「都市」单键播种，仙侠/科幻素材不可达） | 复合题材书素材覆盖打折 |
| N8 | name-check 只查名册，不查正文已出现但未入册的浮动名（如「哑巴嗓」「铁牙」类绰号） | 绰号类撞名漏检 |

---

## 第 3 轮复盘：端到端场景推演

**场景：作者改完素材与章纲 → 开新会话 → 写第 42 章（反派视角章）→ settle → 学习闭环**

| 步骤 | 结果 | 缺口 |
|------|------|------|
| author-sync 扫改动 | ✅ 可跑 | — |
| foreshadow pending 取本章应推进项 | ✅ 可跑（F-002 眼线返回） | 但不自动注入 v7 决策卡（E1 确认） |
| build_context_pack | ❌ | 无 stale_notes/author_model/style_anchor 等 14 section（C 类确认） |
| 双稿择优 | ⚠️ | drafts record/choose/link 三条命令全手动，SKILL 有指引但无脚本编排 |
| settle | ❌ | 不消费 review_results.json（审查阻断形同虚设）；零后置钩子（素材轨迹/指纹/追读力全手动） |
| learn 闭环 | ✅ | v7 仓可跑（13/58 事件归纳 + apply 回写成功）——**但 CLI 设计缺陷** |
| volume-reconcile | ✅ | 80% 覆盖 / 逾期 1 条 / 里程碑 0/3 检出正确 |
| MCP 装机副本 | ✅ | 6 个 v8 模块在 8.0.0 缓存中 |

### 3.1 第 3 轮新发现

| # | 发现 | 证据 |
|---|------|------|
| N9 | `learn` CLI 参数冗余：`webnovel.py learn learn --from-journal`（子命令 learn + action learn 重复），首次调用必然报错 | 实测 usage error |
| N10 | v7 settle 不读 `.webnovel/tmp/review_results.json` → reviewer 阻断语义在 v7 路径完全失效（v6 路径由 write-gate 兜底） | grep 零引用 |
| N11 | 反派视角章（如 42 黄雀）无 POV 纪律注入——pov-management.md 只挂 context-agent 人物段，v7 决策卡的 pov 字段无消费者 | 卡 42 pov=熊铁山 但上下文包不注入视角约束 |
| N12 | settle 后 `.webnovel/tmp/` 的 review/extraction artifacts 在 v7 路径无人清理也无人归档 | 工作区残留累积 |

---

## 汇总：缺口总清单（40 项归并）

| 来源 | 项数 | 状态 |
|------|------|------|
| 原审计 A 类（迁移器） | 4 | A1 根因修正；A2-A4 已补但迁移器本体未修 |
| 原审计 B 类（章纲自检） | 5 | 全部未修 |
| 原审计 C 类（v7 上下文包） | 14 | 全部未修 |
| 原审计 D 类（settle 门禁） | 3 | 全部未修 |
| 原审计 E 类（链路断裂） | 3 | 全部未修 |
| 三轮复盘新发现 N1-N12 | 12 | 未修 |
| **合计** | **41（含修正）** | |

---

## 修复计划（4 阶段，按依赖与收益排序）

### 阶段一：止血——写前链路补全（预计 2 个任务，~1 天）

> 目标：让 v7 仓上写章时 AI 能看到完整上下文 + 审查能拦住问题

| 任务 | 内容 | 验收 |
|------|------|------|
| **P1-1 v7 上下文包补 14 section** | `build_context_pack` 增加：stale_notes / reader_signal / author_style_patterns / style_contract（宪法）/ urgent_loops（账本条目）/ pending_promises（本章应推进项）/ protagonist / outline（详细大纲当章节选）/ genre_profile / active_rules / memory_pack / prewrite_validation / runtime_status / story_contracts。每个 section 复用既有模块的读函数，配额进 V7_SECTION_QUOTAS，DROP 顺序按 v6 的 PROTECTED_PATHS 语义 | fantasy01 ch42 上下文包含 stale_notes、账本应推进项、author_model 三段；饱和测试三段保全 |
| **P1-2 v7 settle 三门禁** | settle() 前置：①读 `.webnovel/tmp/review_results.json` 存在且 blocking>0 → 拒绝（`--force-review-bypass` 显式跳过）；②prose_check flagged 非（空或全 deviation）→ 拒绝；③素材引用 resolve_ref 逐条存在性 | 构造 blocking 审查 → settle 拒绝；引用不存在 ID → 报错 |

**阶段一完成（2026-09-04，Cursor；spec/plan 见 `docs/cursor/阶段一-写前链路补全/`）**

| 任务 | 状态 | 证据（验收原文 → 测试 / 命令输出） |
|---|---|---|
| P1-1 | ✅ `d645d70` | 「fantasy01 ch42 上下文包含 stale_notes、账本应推进项、author_model 三段」→ fantasy01 只读副本 `webnovel.py --project-root <副本> v7-write pack --chapter 42` 输出 `OK … used=5,774`，包内 `## ` 节 = 决策卡 / 本章应推进（承诺账本）/ 作者修改未消费（stale）/ 前情摘要 / 上一章结尾 / 素材装配 / 作者模型 / 书级元信息；`section_errors={}`、`dropped=[]`、`stale_count=5`。「饱和测试三段保全」→ `test_v7_write_pack_sections.py::TestSaturation::test_protected_sections_survive_budget_squeeze`（预算 2500 触发丢弃，四个 PROTECTED 节全在）。**范围调整（Human 2026-09-04 批准 spec §2）**：14 → 10 个 section，v6-only 的 genre_profile / active_rules / memory_pack / prewrite_validation / runtime_status / story_contracts 不移植（无 v7 数据源）；author_style_patterns 并入 author_model；urgent_loops 并入 pending_promises；新增 pov_discipline。 |
| P1-2 | ✅ `d404a29` `73b70a7` | 「构造 blocking 审查 → settle 拒绝」→ `test_v7_write_gates.py::TestReviewGate::test_blocking_review_rejects_without_side_effects`（HEAD 不动、定稿零文件）；「引用不存在 ID → 报错」→ `TestMaterialGate::test_unresolvable_ref_rejects_even_with_bypass`（bypass 也不放行）。补充：缺审查文件 / 章号不符视同未审查；绕过留痕 front matter `审查绕过:` + journal 事件（`validate_journal()==[]`）；settle CLI 退出码 0/2/1；`webnovel.py v7-write` 转发。 |
| 接线（原文未列） | ✅ `841831b` | brainstorming 时发现 `v7_write.py` 无任何 skill/command 调用点（`/webnovel:write` 全 v6）——不接线则 P1-1/P1-2 不可达。`/webnovel:write` 新增「书仓形态判定」按 `book.yaml` 分流到 v7 链；`evals/fast.json` 新增 `skill_write_v7_branch` 契约，`run_behavior_evals.py --suite fast` 23/23 PASS。 |

回归：`pytest -o addopts=""` → `1483 passed`（此前 1455）；覆盖率 82.67%（门 80）；`sync_plugin_version.py --check` / `validate_plugin_package.py` / `validate_reference_wiring.py`（drift=0）/ `validate_release_notes.py` 全 OK。

### 阶段二：一致性闸——章纲与数据不变量（预计 3 个任务，~1 天）

> 目标：标题/账本/人物/时间锚在生成时就被拦，不等 reviewer

| 任务 | 内容 | 验收 |
|------|------|------|
| **P2-1 详细大纲统一路径 + 标题闸** | ①约定规范路径 `大纲/卷纲/第NN卷-详细大纲.md`（plan skill 输出、迁移器、补入三方统一；迁移器去后缀的旧行为加兼容读取）；②`create_chapter_batch` 读当卷详细大纲提取 `## 第N章：标题`，card 标题不一致 → warning（不阻断，作者可覆盖）；缺详细大纲 → 提示 | fantasy01 建卡 43「夜袭」与大纲一致；错标题被 warning 报出 |
| **P2-2 self_check_batch 增 4 项** | ①承诺 ID 存在于账本（load_entries）；②时间锚跨批单调（读已确认卡+定稿时间锚取最大）；③战力事件境界名 ∈ 境界链；④人物 ∈ 名册∪决策卡 entities（warning 级） | F-999 引用被拒；时间倒流被拒 |
| **P2-3 数据不变量校验器** | 新 `data_modules/invariant_check.py`：实现 06 §12 六条（journal 积压/轨迹-manifest 一致/战例-正文对账/合同重建对账/stale 超一卷+状态机复检），CLI `webnovel.py invariants` | fantasy01 跑出六条各自结论 |

**阶段二 P2-1/P2-2 完成（2026-09-04，Cursor；spec/plan 见 `docs/cursor/阶段二-章纲一致性闸/`）**

| 任务 | 状态 | 证据（验收原文 → 测试 / 命令输出） |
|---|---|---|
| P2-1 | ✅ `948bf79` `06028ac` `0ea89e3` `a939ef7` | 「fantasy01 建卡 43「夜袭」与大纲一致」→ 只读副本 `create_chapter_batch(..., 标题=夜袭, 卷=1)`：`MATCH_OK True outline_codes []`，`MATCH_WARNINGS []`；解析到规范路径 `大纲/卷纲/第01卷-详细大纲.md`，`heading43=夜袭`。「错标题被 warning 报出」→ 同副本 `标题=错名`：`WRONG_OK True codes ['outline_title_mismatch']` 且 `0043.md` 仍落盘。单测：`test_chapter_outline_batch.py::TestConsistencyGate::test_title_mismatch_is_warning_but_card_is_written`。 |
| P2-2 | ✅ `a939ef7` | 「F-999 引用被拒」→ 单测 `test_missing_promise_is_error_with_zero_side_effects`（`ok=False, error=consistency_gate`，零卡）；副本冒烟 `F999_OK False error consistency_gate codes ['promise_not_found', 'time_regression']`，无 `0099.md`。「时间倒流被拒」→ `test_time_regression_from_confirmed_card_is_error` / `test_time_regression_from_settled_front_matter`。战力/人物为 warning：`test_unknown_realm_is_warning` / `test_unknown_character_is_warning`。 |
| P2-3 | ✅ `c304aa9` `5cdbb20` `fe5e7fc` `873fa21` `f4a8c50` | 「fantasy01 跑出六条各自结论」→ 只读副本 `$env:TEMP/fantasy01-invariants`：`schema_version=invariants/1`，`len(invariants)==6`，`ok=false` exit 1。分项：`inv-1-journal` **fail**（3 `unclassified_event` + 4 `illegal_field action=add` + 12 `pending_semantic`，events=61）；`inv-2-material-trajectory` **pass**（rows=4 live）；`inv-3-power` **pass**（battles=0，chain_problems=0）；`inv-4-promises` **pass**（entries=4）；`inv-5-contracts` **skip**（无 `.story-system`）；`inv-6-stale-age` **warn**（5 条旧 stale `unknown_stale_age`，current_chapter=41，volume_size=40）。 |

**范围/实现对照（对照方案条目，非只报测试全绿）：**

- 规范写路径 `大纲/卷纲/第NN卷-详细大纲.md`；兼容读：规范 → `第NN卷.md` → v6 平铺/空格变体（`outline_paths.py`）。
- 新检查不塞进 `self_check_batch`（签名仍 `list[str]`）；由 `validate_chapter_batch` 产出结构化 `errors/warnings`，`create_chapter_batch` 组合后 `checks` 仍为 warning 文本。
- **偏差**：验收原文写「第02卷」，fantasy01 第43章在 **第01卷**（卡 `卷: 1`，规范文件 `第01卷-详细大纲.md`），冒烟按真仓卷号，未伪造第02卷文件。Task 4+5 合并为一次提交 `a939ef7`（闸实现不可拆）。`init_domain_skeleton` 会建空 `作者/journal.jsonl`，error 门禁断言 journal **内容**不变而非文件不存在。时间线夹具补种 `F-003`（`test_timeline_view.py`，`6d39144`），否则闸上线后建卡被拒、视图空表。

回归（P2-1/P2-2 当时）：`pytest -o addopts=""` → `1505 passed`（阶段一 1483）；覆盖率 `Total coverage: 82.72%`（门 80）；evals fast 23/23；三校验器 OK。

**阶段二 P2-3 完成（2026-09-04，Cursor；spec/plan 见 `docs/cursor/阶段二-数据不变量/`）**

| spec §6 成功标准原文 | 证据 |
|---|---|
| 1. 六项检查恒各有一条结果 | `test_empty_v7_book_always_returns_six_results`：空 v7 = 4 pass / 2 skip（无锚点 + 无 `.story-system`）；fantasy01 `len==6` |
| 2. fantasy01 `invariants --format json` 六项 status；纯 v7 合同 skip | 上表 P2-3 行；inv-5 `skip` + repair「纯 v7 无 .story-system 时跳过合同重建」 |
| 3. journal 普通 `domain=其他` fail；migration 豁免；待语义 warn | `TestJournal*` 定点；fantasy01 inv-1 含 `unclassified_event` 与 `pending_semantic` |
| 4. live 丢条目、vNN 缺 manifest/CSV/文件项 fail | `test_invariant_check.py` Inv-2 矩阵（Task 2 `5cdbb20`） |
| 5. 战例无定稿、境界链不单调 fail | Inv-3 定点（Task 3 `fe5e7fc`）；fantasy01 无战例 → pass |
| 6. 作废缺 journal 或演化 retcon fail | Inv-4 定点（`fe5e7fc`）；fantasy01 4 条目均合法 → pass |
| 7. 篡改 review/volume 重建 fail；纯 v7 skip | `TestContractRebuildInvariant`（`f4a8c50`）；fantasy01 无 `.story-system` → skip |
| 8. 新 stale 带 `since_chapter`；超卷 fail；旧项 unknown-age warn | Task 4 `873fa21`；fantasy01 5 条旧 stale → `unknown_stale_age` warn |
| 9. CLI 退出码 0/1 | 空 v7 `invariants --format json` returncode 0；fantasy01 有 fail → returncode 1 |
| 10. 全量测试通过，覆盖率 ≥80% | `pytest -o addopts="" -q` → `1544 passed in 113.26s`；`Total coverage: 82.82%`；evals fast 23/23；`validate_plugin_package.py` OK；`validate_reference_wiring.py` drift=0；`sync_plugin_version.py --check` → `Versions are in sync: 8.0.0` |

### 阶段三：闭环补全——settle 后置与工坊执行器（预计 3 个任务，~1 天）

> 目标：settle 一条命令完成全部落账；工坊采纳标记有人消费

| 任务 | 内容 | 验收 |
|------|------|------|
| **P3-1 v7 settle 后置钩子** | settle 成功后自动串：materials log（幂等闸已有）→ settle_style_domain（指纹+高分采样）→ reading_power（从摘要 front matter 提取）；各自 try/except 不阻断 settle；CLI 输出后置结果一行 | ch43 settle 一次跑完，轨迹/指纹/追读力三表自动更新 |
| **P3-2 工坊同步执行器** | 新 `forge-sync` 命令：扫 journal 中 `power_anchor_sync:required` / `contract_rebuild:required` 未消费标记 → 提示作者执行锚点确认与 master-outline-sync；消费后标记 cleared | adopt 功法提案 → forge-sync 引导完成锚点同步 |
| **P3-3 写回 JSON 播种 + CLI 修正** | ①promise-ledger 增 `seed-from-writeback`：读 `第NN卷-总纲写回.json` 的 foreshadow_writeback 数组建账本条目；②修 `learn` CLI 冗余参数（action 默认 learn）；③fantasy01 重复详细大纲去重（保留带后缀版） | 写回 8 条伏笔一键入账；`learn --from-journal` 直接可跑。**勘误**：真仓 `foreshadow_writeback` 实际 7 条，验收按数组长度，不造第 8 条 |

**阶段三 P3-1 完成（2026-09-04，Cursor；spec/plan 见 `docs/cursor/阶段三-settle后置钩子/`；实现 `6ed016f`）**

| 任务 | 状态 | 证据（验收原文 → 测试 / 命令输出） |
|---|---|---|
| P3-1 | ✅ `6ed016f` | 「ch43 settle 一次跑完，轨迹/指纹/追读力三表自动更新」→ 真仓无 `0043-` 定稿（spec §4.5 用 43）。只读副本 `$env:TEMP/fantasy01-p3-1-smoke`（排除 `.git`）：补种 `场景写法:SP-001`（真仓无该表，否则门③拒）；`webnovel.py --project-root <副本> v7-write settle --chapter 43 --no-commit --summary-file`（摘要含 `hook_type`/`hook_strength`）→ `OK v7-write settle chapter=43 committed=False bypassed=False … post=materials:ok/2 style:fp=42,samples=0 reading:ok`。轨迹 `TRAJ_IDS ['SP-001', 'WT-001']`；`文风/指纹.yaml` 内容变化且 `fingerprint_chapters=42`；`get_chapter_reading_power(43)` → `hook_type=悬念, hook_strength=strong`。副本无 git → `--no-commit`；git add 由单测覆盖。 |

**范围/实现对照（spec §6 原文 → 证据）：**

| # | 方案原文 | 证据 |
|---|---|---|
| 1 | materials log（幂等闸已有） | 冒烟轨迹 2 行；`test_materials_logged_and_committed`；无卡 → `test_v7_write_post_hooks` 中 skipped 路径（`card_missing`） |
| 2 | settle_style_domain（指纹+高分采样） | 冒烟 `style:fp=42,samples=0`；`test_fingerprint_written_and_committed`（`recorded==0`） |
| 3 | reading_power（从摘要 front matter 提取） | 冒烟 `reading:ok` + index 行；`test_reading_power_from_summary_front_matter` / `test_reading_skipped_without_hook` |
| 4 | 各自 try/except 不阻断 settle | `test_hook_error_does_not_block_settle`（定稿仍在，`materials.status==error`） |
| 5 | CLI 输出后置结果一行 | 冒烟 stdout 含 `post=materials:ok/2`；`test_exit_0_with_bypass` 断言 `post=` |
| 6 | 后置文件扩进本次 git add | `test_materials_logged_and_committed` / `test_fingerprint_written_and_committed`：`git -c core.quotepath=false ls-files` 含轨迹与指纹 |
| 7 | 门禁拒绝不跑后置 | `test_gate_reject_skips_post_hooks`（blocking 审查 → 无 `0042-*`、无新指纹） |
| 8 | 回归 | `pytest -o addopts="" -q --cov …` → `1550 passed, 23 warnings in 120.18s`；`Total coverage: 82.85%`；evals fast 23/23；`validate_plugin_package.py` OK；`validate_reference_wiring.py` drift=0；`sync_plugin_version.py --check` → `Versions are in sync: 8.0.0` |

偏差：① 无 ledger（与 P2 相同，未走 SDD）。② 冒烟 `--no-commit`（副本排除 `.git`）；③ 真仓缺 `场景写法.csv`，副本补种 SP-001 才能过门③并验证轨迹，未改真仓。

**阶段三 P3-2 完成（2026-09-04，Cursor；spec/plan 见 `docs/cursor/阶段三-工坊同步执行器/`；实现 `f23eeb5`）**

| 任务 | 状态 | 证据（验收原文 → 测试 / 命令输出） |
|---|---|---|
| P3-2 | ✅ `f23eeb5` | 「adopt 功法提案 → forge-sync 引导完成锚点同步」→ 按代码勘误走 `save→adopt→confirm` 功法：`test_confirm_gongfa_lists_both_kinds` status exit 1、`pending` 含 `power_anchor_sync`+`contract_rebuild`、`next` 含 `power validate` 与 `master-outline-sync`；`test_mark_cleared_all_after_gongfa` / `test_webnovel_cli_forge_sync` mark-cleared 后 pending 空、exit 0。`webnovel.py forge-sync -h` → `usage: webnovel.py forge-sync [-h] [--kind KIND] [--format {text,json}] [{status,mark-cleared}]`。 |

**范围/实现对照（spec §6 原文 → 证据）：**

| # | 方案原文 | 证据 |
|---|---|---|
| 1 | 扫 journal 中 `power_anchor_sync:required` / `contract_rebuild:required` 未消费标记 | `test_confirm_gongfa_lists_both_kinds` 两种 kind；`test_confirm_fabao_only_contract` 仅 `contract_rebuild` |
| 2 | 提示作者执行锚点确认与 master-outline-sync | 同上 `next` 含 `power validate` 与 `master-outline-sync` |
| 3 | 消费后标记 cleared | `test_mark_cleared_all_after_gongfa` journal 含 `*:cleared`，再次 status `pending==[]` exit 0 |
| 4 | 新 `forge-sync` 命令 | `webnovel.py forge-sync -h` 可解析；无子命令 = status（CLI 测 `--format json` 即默认 status） |
| 5 | 验收：adopt 功法提案 → forge-sync 引导完成锚点同步 | 上表 P3-2 行；生产者实为 confirm |
| 6 | 回归 | `test_setting_forge.py` 全绿；`pytest -o addopts="" -q --cov …` → `1558 passed, 23 warnings in 125.12s`；`Total coverage: 82.85%`；evals fast 23/23；`validate_plugin_package.py` OK；`validate_reference_wiring.py` drift=0；`sync_plugin_version.py --check` → `Versions are in sync: 8.0.0` |

额外（方案 A）：`test_status_does_not_write_journal`；`test_mark_cleared_rejects_when_empty` exit 2；`test_extra_cleared_does_not_swallow_later_required`。

偏差：① 无 ledger。② CLI 夹具须有 `book.yaml`（`webnovel.py` 宽松根解析认 v7 书仓）。③ 测试跨文件 import 把 `scripts/tests` 加入 `sys.path`。Task 2+3 合并为一次提交 `f23eeb5`。

**阶段三 P3-3 完成（2026-09-04，Cursor；spec/plan 见 `docs/cursor/阶段三-写回播种与CLI/`；实现 `cd6016d`；书仓 `e28e7c5`）**

| 任务 | 状态 | 证据（验收原文 → 测试 / 命令输出） |
|---|---|---|
| P3-3 | ✅ `cd6016d` + 书仓 `e28e7c5` | 「写回 8 条伏笔一键入账」→ 勘误为数组长度 7：`test_seeds_seven_foreshadow_entries` created=`F-001`…`F-007`，第二次 `test_idempotent_skips_duplicate_names` skipped=7。真仓未跑 seed（spec §2）。「`learn --from-journal` 直接可跑」→ `test_learn_from_journal_without_nested_action`；`webnovel.py learn -h` → `[{learn,apply,show}]` 可选。③ `resolve_detailed_outline(fantasy01, 1)` → `第01卷-详细大纲.md`，`第01卷.md` 已不存在。 |

**范围/实现对照（spec §6 原文 → 证据）：**

| # | 方案原文 | 证据 |
|---|---|---|
| 1 | 读 `第NN卷-总纲写回.json` 的 foreshadow_writeback 数组建账本条目 | `test_seeds_seven_foreshadow_entries`：7 个 `F-*.md`，`名称` 与夹具 `content` 一一对应；`test_ignores_open_loop_writeback` 不建悬念 |
| 2 | promise-ledger 增 `seed-from-writeback` | `webnovel.py promise-ledger -h` 含 `{create,list,update,seed-from-writeback}`；`test_cli_seed_and_help` 缺 `--volume` 非 0 |
| 3 | 验收：写回 8 条伏笔一键入账 | **勘误为 7**：同上 created=7 / 幂等 skipped=7；不以字面 8 造数据 |
| 4 | 修 `learn` CLI 冗余参数（action 默认 learn） | `test_learn_from_journal_without_nested_action`；`learn -h` action 可选 |
| 5 | 验收：`learn --from-journal` 直接可跑 | 同上；`test_learn_learn_from_journal_still_works`；`test_learn_apply_still_requires_explicit_action` |
| 6 | fantasy01 重复详细大纲去重（保留带后缀版） | 删除前 SHA-256 相同；书仓 `e28e7c5` 删 `大纲/卷纲/第01卷.md`；`dup_exists False`；解析器指向 `-详细大纲.md` |
| 7 | 回归 | `test_promise_ledger.py` / `test_author_model.py` 定点全绿；`pytest -o addopts="" -q --cov …` → `1568 passed, 23 warnings in 127.90s`；`Total coverage: 82.97%`；evals fast 23/23；`validate_plugin_package.py` OK；`validate_reference_wiring.py` drift=0；`sync_plugin_version.py --check` → `Versions are in sync: 8.0.0` |

额外（方案 A）：`test_missing_file_exit_2_no_write` exit 2；`test_bad_buried_chapter_fails_item_keeps_rest` 坏章号 failed、其余仍种；空 payoff → `最晚回收章==0`。

偏差：① 无 ledger。② 真仓 fantasy01 不跑 seed（会新增 F-004 起且与现有 F-001 名称对不上）。③ Task 1–3 合并为 `cd6016d`；Task 4 在书仓 `e28e7c5`。阶段三 P3-1/P3-2/P3-3 全部完成。

### 阶段四：体检与体验（预计 3 个任务，~1 天）

> 目标：doctor 成为一站式治理体检；面板/播种/命名补盲

| 任务 | 内容 | 验收 |
|------|------|------|
| **P4-0 v7 书仓项目根解析（P4-1 前置，复审 P1-9）** | `build_doctor_report` 在纯 v7 书仓（无 `.webnovel/state.json`）解析不到项目根，既有 12 组检查整体跳过、只剩 python 依赖组——这是 §2.1「只看到环境检查」的真实原因。改 doctor 根解析兼容 `book.yaml` 书仓（phase 推导走 v7 定稿目录），并把 §2.1 措辞修正为「零治理检查」（既有组并非不存在，是没跑到） | fantasy01 doctor 输出 ≥12 组既有检查而非仅 python.* |
| **P4-1 doctor 治理检查组** | doctor 增 8 组检查（F-13）：journal 水位/stale 积压/轨迹-manifest/锚点-正文/条目状态机/素材健康（复用 material_review stats）/画廊积压/合同对账（调 P2-3）；MCP webnovel_doctor 自动受益。**F-13 在 08 计划中从未排期**（对账见 `docs/cursor/项目复审/2026-09-04-copilot-300-规格对账表.md`），本项即其唯一落地点 | fantasy01 doctor 输出治理组结论 |
| **P4-2 dashboard 账本视图** | governance.py 增承诺账本视图（各状态计数+逾期列表）；GovernancePage 增第七段 | 面板可见 F-001~S-001 状态 |
| **P4-3 播种复合题材 + name-check 绰号** | ①seed 支持复合键（都市+仙侠+科幻 → 三键并集）；②name-check 增正文浮动名扫描（最近 N 章高频专名，warning 级） | fantasy01 播种含仙侠素材；「铁牙」类绰号被提示 |

**阶段四 P4-0 完成（2026-09-04，Cursor；spec/plan 见 `docs/cursor/阶段四-doctor根解析/`；实现 `47e661c`）**

| 任务 | 状态 | 证据（验收原文 → 测试 / 命令输出） |
|---|---|---|
| P4-0 | ✅ `47e661c` | 「改 doctor 根解析兼容 `book.yaml` 书仓」→ tmp `phase=v7_story_repo`；fantasy01 CLI `phase=v7_story_repo`、`preflight.project_root` ok。「phase 推导走 v7 定稿目录」→ `test_v7_book_yaml_is_story_repo_phase` 章号 42；`test_v7_ignores_v6_zhengwen_flat_dir` 不读 `正文/`。「fantasy01 doctor 输出 ≥12 组既有检查而非仅 python.*」→ 十二组前缀 12/12，`check_count=32`，`python_only False`。 |

**范围/实现对照（spec §6 原文 → 证据）：**

| # | 方案原文 | 证据 |
|---|---|---|
| 1 | 改 doctor 根解析兼容 `book.yaml` 书仓 | `test_v7_book_yaml_is_story_repo_phase`；`test_doctor_v7_runs_project_groups_not_only_python` 无 `project.root`；fantasy01 `project_root=…\fantasy01` |
| 2 | phase 推导走 v7 定稿目录 | `定稿/正文/0042-夜袭.md` → `target_chapter==42` / `latest_accepted_chapter==42`；v6 平铺 `正文/第0099章.md` 不影响（latest=0） |
| 3 | 验收：fantasy01 doctor 输出 ≥12 组既有检查而非仅 python.* | CLI json：`group_hits 12 / 12`，`missing []`；`python_only False` |
| 4 | §2.1 措辞「零治理检查」 | 历史勘误段未改实测句；上补 P4-0 完成记录（12 组已跑到）。P4-1 治理组仍未建 |
| 5 | 回归 | `test_doctor.py` / `test_project_phase.py` 定点全绿；`pytest -o addopts="" -q` → `1575 passed in 122.50s`；`Total coverage: 82.99%`；evals fast 23/23；`validate_plugin_package.py` OK；`validate_reference_wiring.py` drift=0；`sync_plugin_version.py --check` → `Versions are in sync: 8.0.0` |

额外（方向 2）：`test_doctor_v7_missing_finalized_dir_errors` → `file.v7.dir.定稿/正文` error；fantasy01 无 `file.dir.设定集`；`test_doctor_cli_v7_emits_twelve_groups` + 真仓 `preflight.project_root` ok。

偏差：① 无 ledger。② Task 1–3 合并为一次提交 `47e661c`。③ `_resolve_root_lenient` 入参改为 `Optional[str]`，避免 preflight 无根时 `Path(None)`。

### 依赖关系

```
P1-1 ──→ P1-2 ──→ P3-1（settle 门禁先于后置钩子）
P2-1 ──→ P2-2（路径统一先于标题闸）
P2-3 ──→ P4-1（不变量器被 doctor 复用）
P4-0 ──→ P4-1（根解析不修，治理组在 v7 书仓上同样跑不到）
P3-3 / P4-2 / P4-3 独立
```

### 明确不做（本轮）

- 不重写 v7_write 为 v6 合同链（08 方案「并轨」的大动作，等本计划验证后单独立项）
- 不做 write-gate 对 v7 的全量移植（用 P1-2 的 settle 门禁替代）
- 不动 v6 路径任何行为（v6 是回归基线）

---

## 验证方式（每阶段通用）

1. 全量 pytest（≥当前 1452 基线，覆盖率 ≥80%）
2. fantasy01 实仓冒烟：ch42 走完「pending→上下文包→settle→后置→learn」全链
3. `validate_reference_wiring.py` drift=0
4. 行为评测全 PASS

## 复盘方法说明

- **第 1 轮**（验证）：逐项 grep/实跑原审计 28 项 → 修正 A1 根因 + 发现 N1/N2
- **第 2 轮**（横向）：doctor/不变量/路径分裂/工坊/dashboard/播种/命名 → 发现 N3-N8
- **第 3 轮**（场景）：以「改素材→写 42 章→settle→learn」端到端走链 → 发现 N9-N12
- 每项新发现均有代码行号或实跑输出佐证，无凭印象项
