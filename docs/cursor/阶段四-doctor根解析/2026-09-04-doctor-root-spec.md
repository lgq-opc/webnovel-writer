# Spec：doctor v7 书仓根解析（v8-gap-review 阶段四 P4-0）

> 档位：Architectural（改 `resolve_project_phase` + doctor file 清单 + CLI preflight 根解析）
> 状态：**已批准**（Human 2026-09-04 确认书面稿；方案 A + 方向 2）
> 上游：`docs/zcode/v8-gap-review-3rounds/README.md` 阶段四 P4-0；复审 P1-9；§2.1 勘误
> 下游：同目录 `2026-09-04-doctor-root-plan.md` → TDD → 收尾

## 1. 背景与目标

`build_doctor_report` 本有 12 组项目检查，但 `resolve_project_phase` 在缺少 `.webnovel/state.json` 时一律 `no_project`，doctor 早退，只剩 `_python_checks`。纯 v7 书仓（`book.yaml`、无 state.json）在 fantasy01 上因此只看到环境组。CLI `_build_preflight_report` 走严格 `_resolve_root`（同样要 state.json），`preflight.project_root` 在 v7 仓会失败。

`is_story_repo`（认 `book.yaml`）已存在，doctor / phase 未用。`_latest_draft_chapter` 扫的是 v6 `正文/`，不是 `定稿/正文`。

**目标：** v7 书仓能解析到项目根并跑完既有 12 组；file 组按 v7 路径验存在性，不再用 v6 必选清单刷红。

**成功标准（抄 gap-review 阶段四 P4-0 原文）：**

> 改 doctor 根解析兼容 `book.yaml` 书仓（phase 推导走 v7 定稿目录），并把 §2.1 措辞修正为「零治理检查」（既有组并非不存在，是没跑到）
>
> 验收：fantasy01 doctor 输出 ≥12 组既有检查而非仅 python.*

§2.1 勘误段（「零治理检查」属实 / 12 组没跑到）已在 README，本任务收尾只补「P4-0 完成后 12 组已跑到」的完成记录，不改历史实测句。

## 2. 非目标

- 不实现 P4-1 八组治理检查（journal 水位 / stale / 轨迹-manifest 等）。
- 不实现 P4-2 / P4-3。
- 不改 v6 写链（`chapter_commit.py` / write-gate / `context_manager`）。
- 不改 `project_locator.resolve_project_root` 的默认严格语义（其它仍依赖 state.json 的命令不在本任务全盘放宽）。
- 不强制纯 v7 具备 `.story-system`；合同组保持 skip。
- 不查详细大纲文件名、章号连续性、账本条目内容（P2 / P4-1）。
- 不在真仓补 `.webnovel/state.json`。

## 3. 方案与裁决

| 方案 | 内容 | 裁决 |
|---|---|---|
| **A + 方向 2（采纳，Human 2026-09-04）** | `resolve_project_phase` 认 `book.yaml`，phase=`v7_story_repo`，目标章从 `定稿/正文` 推；doctor 跑 12 组；v6 INIT 清单对 v7 **不发出**；file 组改查 v7 路径 | 根解析收口；空壳 v7（无定稿目录）能被抓住 |
| B | 只放宽 doctor 早退，file 仍用 v6 清单 | 否决：fantasy01 会被 `设定集/` `正文/` 刷成 blocker |
| C | 只改 `cmd_doctor` 绕过 phase | 否决：MCP / 直调 `build_doctor_report` 仍坏 |
| 方向 1 | skip v6 但不补 v7 file 清单 | 否决：删掉 `定稿/正文` 时 doctor 仍可显示正常 |

## 4. 设计

### 4.1 根与 phase

`resolve_project_phase(root)`：

1. `root is None` → 仍 `no_project`（`project_root=""`）。
2. 存在 `.webnovel/state.json` → **现有 v6 状态机一字不改**（含测试 `_make_init_ready`）。
3. 否则若 `book.yaml` 存在（`is_story_repo`）→ `phase=v7_story_repo`，`project_root=str(root)`；`target_chapter` / `latest_accepted_chapter` 从 `定稿/正文/` 文件名解析最大章号（`NNNN-*.md` 或 `第N章`，取能解析的十进制章号；目录空或不存在 → 0）。不读 `正文/`（v6 平铺）。不要求 `.story-system`。
4. 否则 → 现有 `no_project` + `missing .webnovel/state.json`。

`PHASES` 增加 `v7_story_repo`。`project-status` 若只打印 snapshot.phase，自动受益，不另做 UI。

### 4.2 CLI preflight

`_build_preflight_report` 解析根改为 `_resolve_root_lenient`（先严格 state.json，失败再认 `book.yaml` 目录）。`cmd_preflight` 与 `cmd_doctor` 共用，故 `webnovel.py --project-root <v7> preflight` / `doctor` 的 `preflight.project_root` 在 fantasy01 为 ok。

不把全仓 `PASSTHROUGH_TOOLS` 改为宽松。

### 4.3 doctor 早退

仅当 `phase==no_project` 或 `project_root` 空时早退（现逻辑保留）。`v7_story_repo` 走 12 组。

`project.root` 的 `expected` 在 v7 语境改为 `book.yaml or .webnovel/state.json`（仅早退那条 error 文案；成功路径不发这条）。

### 4.4 file 组（方向 2）

**v6 phase**（有 state.json）：`_file_checks` 仍用 `INIT_REQUIRED_DIRS/FILES` + 合同文件规则，行为与现在一致。

**`v7_story_repo`：** 不遍历 v6 INIT 清单（不输出那批 skip/error 行）。只查：

| 路径 | 类型 | 缺时 |
|---|---|---|
| `book.yaml` | 文件 | error / blocker |
| `定稿/正文` | 目录 | error / blocker |
| `大纲` | 目录 | error / blocker |
| `作者` | 目录 | error / blocker |

目录存在即为 ok（允许空目录，新书尚未 settle）。不要求 `大纲/卷纲`、不要求至少一篇正文。`作者/` 与 `domains.contract` 重叠可接受。id 建议：`file.v7.book.yaml`、`file.v7.dir.定稿/正文`、`file.v7.dir.大纲`、`file.v7.dir.作者`。

`_expected_profile`：v7 phase 的 files/dirs 用上表，不含 v6 INIT、不含 `.story-system` 合同路径。

### 4.5 其余 11 组

逻辑不改语义。纯 v7 上：json / story_runtime / projection / extraction / contract / run_log 按现有缺文件 skip 或 warning。sqlite / rag 有库则查。`domains.contract` 仍查六域。

**`_total_words_reconcile_check`：** 无 `state.json` 时现在 `return []`（组消失）。改为发一条 `state.total_words_reconcile`，`status=skipped`，message 表明 v7 无 state 不对账。有 state 但无漂移仍可 `return []`（v6 行为不变）。

### 4.6 「≥12 组」计数

12 组 = README 所列：preflight / file / json / story_runtime / sqlite / total_words / projection_log / extraction / contract_version / run_log / rag / domain_contract。不含 python 环境组。

验收用 CLI：`webnovel.py --project-root <fantasy01> doctor --format json`（或只读副本）。断言上述 12 个组在 `checks[].id` 前缀中均至少一条（file=`file.`，total_words=`state.total_words_reconcile`，extraction=`commit.extraction_warnings`，domain=`domains.contract`）。`python.*` 仍在，但不作为「只有环境组」的唯一输出。

### 4.7 代码落点

| 文件 | 动作 |
|---|---|
| `webnovel-writer/scripts/data_modules/project_phase.py` | `PHASE_V7_STORY_REPO`；无 state 时认 book.yaml；定稿章号 |
| `webnovel-writer/scripts/data_modules/doctor.py` | `_file_checks` / `_expected_profile` 分相；total_words 无 state 发 skip |
| `webnovel-writer/scripts/data_modules/webnovel.py` | `_build_preflight_report` 用 `_resolve_root_lenient` |
| `webnovel-writer/scripts/data_modules/tests/test_project_phase.py` | v7 phase 用例 |
| `webnovel-writer/scripts/data_modules/tests/test_doctor.py` | v7 跑满组 / 缺定稿目录 error / v6 回归 |

MCP `webnovel_doctor` 调 `build_doctor_report`，无单独改动。

## 5. 数据与兼容

- 有 `state.json` 的夹具与 v6 书仓：phase 与 file 清单与现在相同。
- 同时有 `state.json` 与 `book.yaml`：走 v6 分支（state 优先）。
- 空目录、无 yaml 无 state：仍 `no_project`。

## 6. 验收清单（W1：引用方案原文）

| # | 方案原文 | 验证 |
|---|---|---|
| 1 | 改 doctor 根解析兼容 `book.yaml` 书仓 | tmp 仅 `book.yaml`+v7 四路径 → `phase=v7_story_repo`，`project_root` 非空，不早退 |
| 2 | phase 推导走 v7 定稿目录 | `定稿/正文/0042-x.md` → `target_chapter>=42`；无 `正文/` 平铺不影响 |
| 3 | 验收：fantasy01 doctor 输出 ≥12 组既有检查而非仅 python.* | CLI json：§4.6 十二组前缀均出现；`python.*` 不是唯一非空组 |
| 4 | §2.1 措辞「零治理检查」 | 历史勘误已在 README；收尾加 P4-0 完成记录（12 组已跑到）。P4-1 治理组仍未建，不把 §2.1 改成「已有治理检查」 |
| 5 | 回归 | 既有 `test_doctor.py` / `test_project_phase.py` 全绿；全量 pytest；cov ≥80 |

额外（方向 2，必测）：缺 `定稿/正文` → `file.v7.dir.定稿/正文` error；缺 `设定集/` 不出现 v6 `file.dir.设定集` error；`preflight.project_root` 在 v7 CLI 为 ok。

## 7. 约束

- TDD：先失败测试再实现。
- Windows：`python -X utf8`。
- 提交：spec/plan 与实现分开；中文 message 走 UTF-8 文件 + `git commit -F`。
- 无 ledger，除非改走 SDD。
- 不 push，除非 Human 再批。
