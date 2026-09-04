# Spec：doctor 治理检查组（v8-gap-review 阶段四 P4-1 / F-13）

> 档位：Architectural（doctor 增 8 组治理检查；复用 P2-3 不变量器）
> 状态：**已批准**（Human 2026-09-04 确认方案 A；严重度与画廊范围用当时捆绑默认）
> 上游：`docs/zcode/v8-gap-review-3rounds/README.md` 阶段四 P4-1；`07-feature-flows.md` F-13；P2-3 `invariant_check.py`
> 下游：同目录 `2026-09-04-doctor-governance-plan.md` → TDD → 收尾

## 1. 背景与目标

F-13 要求 doctor 增加 8 组治理体检。08 计划从未排期。P4-0 已让纯 v7 书仓跑完既有 12 组；P2-3 已提供六项只读 `run_invariants`，并写明「为 P4-1 直接复用」。缺的是素材健康摘要与画廊积压。MCP `webnovel_doctor` 已转 `doctor --format json`，接上即受益。

F-13 原文「journal 水位 vs git 状态（未留账告警）」**不是** Inv-1（Inv-1 查 `domain=其他`；watermark 滞后只记 counts）。本切片按方案 A **不实现 git 未留账**。

**目标：** `build_doctor_report` 在已解析到项目根时恒发出 8 条 `gov.*` 检查；六项映射 P2-3，两项新查素材健康与画廊积压。fantasy01 能打出治理组结论。

**成功标准（抄 gap-review 阶段四 P4-1 原文）：**

> doctor 增 8 组检查（F-13）：journal 水位/stale 积压/轨迹-manifest/锚点-正文/条目状态机/素材健康（复用 material_review stats）/画廊积压/合同对账（调 P2-3）；MCP webnovel_doctor 自动受益。
>
> 验收：fantasy01 doctor 输出治理组结论

## 2. 非目标

- 不实现 git dirty vs journal/watermark 未留账（F-13 字面；方案 A 明确不做）。
- 不改 P2-3 六项语义、不改 `invariants` CLI 退出码。
- 不自动修复、不删画廊、不改素材 CSV / stale / 账本。
- 不把治理 fail 升级为 doctor blocker / 写前闸。
- 不实现 P4-2 / P4-3。
- 不改 v6 写链；不改 MCP 工具签名（`webnovel_doctor` 无需新参数）。

## 3. 方案与裁决

| 方案 | 内容 | 裁决 |
|---|---|---|
| **A（采纳，Human 2026-09-04）** | 六项映射 `run_invariants`；另加素材健康、画廊积压。journal 组 = Inv-1 | 复用 P2-3；八组都能打出结论 |
| B | A + journal 组加 git dirty vs watermark | 否决：真仓脏文件会误红；本切片不做 |
| C | 八组在 doctor 重写、不调 P2-3 | 否决：违反 P2-3 spec「P4-1 直接复用」 |

捆绑默认（同批批准）：

1. **严重度：** inv `fail`/`warn` → doctor `warning`（`severity=warning`，**不是** blocker）。`pass`→`ok`，`skip`→`skipped`。fantasy01 Inv-1 现为 fail，doctor 仍可 `ok=True`，治理组可见。
2. **画廊：** 扫 `大纲/regen/**` 与 `设定/regen/工坊/**`；规则见 §4.4。

## 4. 设计

### 4.1 接线

在 `build_doctor_report` 已解析到根的分支里，于 `_rag_checks` / `domains.contract` 之后、`_python_checks` 之前调用 `_governance_checks(root)`。整组 `try/except`：异常时发一条 `gov.suite` warning，不拖垮 doctor（与 `domains.contract` 相同策略）。正常路径恒 8 条 `gov.*`。

`no_project` 早退路径不发治理组。

### 4.2 八组 id 与数据源

| id | F-13 / P4-1 名称 | 数据源 |
|---|---|---|
| `gov.inv-1-journal` | journal 水位 | `check_journal`（Inv-1，非 git） |
| `gov.inv-2-material-trajectory` | 定版-轨迹 / 轨迹-manifest | `check_material_trajectory` |
| `gov.inv-3-power` | 锚点-正文 | `check_power_anchor` |
| `gov.inv-4-promises` | 条目状态机 | `check_promise_states` |
| `gov.inv-5-contracts` | 合同对账 | `check_contract_rebuild` |
| `gov.inv-6-stale-age` | stale 积压 | `check_stale_age` |
| `gov.materials.health` | 素材健康摘要 | `material_review.review_stats` |
| `gov.gallery.backlog` | 画廊积压 | 扫两处 regen 目录 |

一次 `run_invariants(root)` 取六项，按上表映射，不改不变量器。

映射字段：`message` = inv `title`；`actual` = `status=<pass|fail|warn|skip>` 加 `counts` 摘要；`repair` = inv `repair`；`path` 空即可。

### 4.3 素材健康

`current_chapter = max_settled_chapter(root)`；`size = volume_size(root)`（P2-3 已有，默认 50）；`current_volume = volume_of_chapter(max(1, current_chapter), size)`。

调用 `review_stats(root, current_volume=current_volume)`（衰减窗口用模块默认 `decay_volumes=1`）。

| 条件 | status |
|---|---|
| `total==0`（无活层行） | skipped |
| `decayed` 且 `状态=active` 的条数 > 0 | warning |
| 其余 | ok |

`actual` 含 `total` / `decayed` / `current_volume`；decayed id 最多列 5 个。不跑 LLM、不调用 `apply_rulings`。

### 4.4 画廊积压

扫描：

- regen：`大纲/regen/**/v*.md`
- 工坊：`设定/regen/工坊/{类}-v*.md` 与 `设定/regen/工坊/*-草案.md`

采纳/confirm **不自动删文件**，积压看盘上是否还留着超过两卷。

**当前卷：** 同 §4.3 `current_volume`。无定稿时为 1。

**产物卷：**

- 路径含 `大纲/regen/章纲/<key>/` 且 `<key>` 能解析出十进制章号（允许 `0043`）→ `volume_of_chapter(章号, size)`
- 其余（总纲、工坊）→ 产物卷 = 1

**计入积压：** `current_volume - 产物卷 >= 2`。

| 条件 | status |
|---|---|
| 扫描范围内 0 个版本/草案文件 | skipped |
| 有文件但计入积压 0 | ok |
| 计入积压 ≥ 1 | warning |

`actual` 含积压条数与最多 5 条相对路径。不删文件。

### 4.5 doctor.ok

治理组 **不得** 使用 `severity=blocker`。`fail` 只升 warning，不把 `ok` 打成 False。既有 file/json blocker 行为不变。

text 格式已打印非 ok 行，治理 warning 会自动出现。

### 4.6 代码落点

| 文件 | 动作 |
|---|---|
| `webnovel-writer/scripts/data_modules/doctor.py` | `_governance_checks`；接入 `build_doctor_report` |
| `webnovel-writer/scripts/data_modules/tests/test_doctor.py` | 八组出现、inv 映射、素材衰减 warning、画廊积压、无组时 skip、不当 blocker |

不新增 MCP 文件。可选把画廊枚举抽到 doctor 内私有函数，不新模块，除非函数明显过长。

## 5. 数据与兼容

- v6（有 `state.json`）同样跑 8 组；Inv-5 有 `.story-system` 时按 P2-3 对账。
- 纯 v7：Inv-5 多为 skip；fantasy01 Inv-1 现为 fail → doctor warning。
- 不写盘。

## 6. 验收清单（W1：引用方案原文）

| # | 方案原文 | 验证 |
|---|---|---|
| 1 | journal 水位 | `gov.inv-1-journal` 存在；映射 Inv-1 status；**不**跑 git status |
| 2 | stale 积压 | `gov.inv-6-stale-age` 映射 Inv-6 |
| 3 | 轨迹-manifest | `gov.inv-2-material-trajectory` 映射 Inv-2 |
| 4 | 锚点-正文 | `gov.inv-3-power` 映射 Inv-3 |
| 5 | 条目状态机 | `gov.inv-4-promises` 映射 Inv-4 |
| 6 | 素材健康（复用 material_review stats） | 衰减 active → `gov.materials.health` warning；无活层 → skipped |
| 7 | 画廊积压 | 当前卷−产物卷≥2 的未清理文件 → `gov.gallery.backlog` warning；无画廊文件 → skipped |
| 8 | 合同对账（调 P2-3） | `gov.inv-5-contracts` 映射 Inv-5 |
| 9 | 验收：fantasy01 doctor 输出治理组结论 | CLI json：8 个 `gov.*` id 均出现；Inv-1 fail 时该条为 warning；`ok` 不因治理组变 False |
| 10 | MCP webnovel_doctor 自动受益 | 无新工具；`webnovel_doctor` 仍调 `doctor --format json`（既有 wiring 测覆盖即可） |
| 11 | 回归 | `test_doctor.py` / `test_invariant_check.py` 全绿；全量 pytest；cov ≥80 |

## 7. 约束

- TDD：先失败测试再实现。
- Windows：`python -X utf8`。
- 提交：spec/plan 与实现分开；中文 message 走 UTF-8 文件 + `git commit -F`。
- 无 ledger，除非改走 SDD。
- 不 push，除非 Human 再批。
