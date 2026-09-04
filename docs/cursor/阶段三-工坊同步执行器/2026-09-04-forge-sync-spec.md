# Spec：工坊同步执行器（v8-gap-review 阶段三 P3-2）

> 档位：Architectural（新 CLI + journal 消费协议）
> 状态：**已批准**（Human 2026-09-04 确认书面稿）
> 上游：`docs/zcode/v8-gap-review-3rounds/README.md` 阶段三 P3-2；N5；`setting_forge.forge_confirm`
> 下游：同目录 `2026-09-04-forge-sync-plan.md` → TDD → 收尾

## 1. 背景与目标

`forge confirm` 把 `contract_rebuild:required` 与（境界/功法）`power_anchor_sync:required` 写入 journal `impact`，但不消费。作者采纳后仍须手工改锚点、跑 `master-outline-sync`，没有命令扫未消费标记。

生产者是 **`forge confirm`**，不是 `adopt`（`adopt` 只出画廊草案）。gap-review 验收原文写「adopt 功法提案」——本 spec 按代码勘误为 **confirm 功法**，冒烟/单测走 `save → adopt → confirm`。

**目标：** 新增顶层 `forge-sync`，只读扫 pending、打印下一步命令；作者确认做完后显式 `--mark-cleared` 追加 `*:cleared`。不自动改锚点表，不代跑 `power validate` / `master-outline-sync`。

**成功标准（抄 gap-review 阶段三 P3-2 原文）：**

> 新 `forge-sync` 命令：扫 journal 中 `power_anchor_sync:required` / `contract_rebuild:required` 未消费标记 → 提示作者执行锚点确认与 master-outline-sync；消费后标记 cleared
>
> 验收：adopt 功法提案 → forge-sync 引导完成锚点同步

（验收路径按上款勘误：confirm 功法后 `forge-sync` 列出 `power_anchor_sync` pending 与引导命令，`--mark-cleared` 后 pending 为空。）

## 2. 非目标

- 不实现 P3-3（写回播种 / learn CLI / 重复大纲去重）。
- 不改 `forge_confirm` 语义（仍不自动改作者锚点表）。
- 不代跑 `power validate` / `master-outline-sync`，不改写 `设定/力量锚点.yaml` 或合同产物。
- 不新增 VALID_ACTIONS / 不改 journal schema（cleared 用既有 `action=edit`）。
- 不新增 skill / 斜杠命令文件；只在 `docs/guides/commands.md` 补一行。
- 不改 v6 `chapter_commit.py` / write-gate / `context_manager`。

## 3. 方案与裁决

| 方案 | 内容 | 裁决 |
|---|---|---|
| **A（采纳，Human 2026-09-04）** | 顶层 `webnovel.py forge-sync`：默认 status；引导命令；显式 `mark-cleared` | 对齐原文「引导」；不绑卷收尾写回 JSON |
| B | 命令内调用 `power validate` + `master-outline-sync`，成功才 cleared | 否决：`master-outline-sync` 要当前卷规划产物与写回 JSON，功法 confirm 当时通常没有 |
| C | 同步塞进 `forge confirm` | 否决：违反 confirm「不自动改锚点」；原文要独立命令 |

**默认（随方案 A）：** 命令名为顶层 `forge-sync`（不是 `forge sync` 子动作）；cleared 必须显式 `mark-cleared`，status 绝不写 journal。

## 4. 设计

### 4.1 标记词

只认 journal 事件 `impact` 列表里的字符串。允许冒号两侧可选空白，大小写敏感：

```
^(power_anchor_sync|contract_rebuild)\s*:\s*(required|cleared)$
```

`forge_confirm` 实际写入无空格（`power_anchor_sync:required`）。其它 impact 忽略。一条事件可同时带两种 `required`（功法/境界 confirm）。

法宝/命名 confirm 只有 `contract_rebuild:required`。

### 4.2 pending（FIFO，按 kind 独立）

按 journal 顺序扫描。每种 kind 一个队列：

- 见到 `kind:required` → 入队 `{index, path, ts, summary}`（`index` 为 1-based 行号）
- 见到 `kind:cleared` → 若队列非空则弹出队头；若队列已空则**忽略该 cleared**（不产生负余额，避免历史脏 cleared 吞掉未来的 required）

pending = 两队列剩余项。不修改历史行。

### 4.3 CLI

```
webnovel.py [--project-root ROOT] forge-sync [--format text|json]
webnovel.py [--project-root ROOT] forge-sync status [--format text|json]
webnovel.py [--project-root ROOT] forge-sync mark-cleared --kind {power_anchor_sync|contract_rebuild|all} [--format text|json]
```

无子命令 = `status`。`--format` 默认 `text`。

**status 退出码：** pending 空 → 0；有 pending → 1。

**mark-cleared：** 对每个请求的 kind，若该 kind 队列非空，追加一条 journal 事件（见 §4.5）弹出队头语义。`--kind all` **只请求当前队列非空的 kind**（法宝-only pending 时 `all` 只清 `contract_rebuild`）；两种队列都空、或显式 `--kind power_anchor_sync`/`contract_rebuild` 而该队列空、或缺少 `--kind` → 整次拒绝、不写 journal、退出码 2。成功退出码 0。一次成功写入一行事件，`impact` 可含多个 `*:cleared`。

不把 `forge-sync` 做成 `forge` 的第五个 action（避免与 `prepare/save/adopt/confirm/list` 混名）。

### 4.4 引导文案（status）

有 `power_anchor_sync` pending 时打印：

1. 作者按工坊登记稿手改力量锚点（路径提示 `设定/力量锚点.yaml` 或书仓既有锚点文件；**不代改**）
2. 然后：`python -X utf8 webnovel.py --project-root <root> power validate`

有 `contract_rebuild` pending 时打印：

3. `python -X utf8 webnovel.py --project-root <root> master-outline-sync --volume <已完成规划的卷号>`

`book.yaml` 无当前卷字段（fantasy01 亦无）→ 卷号保持占位，不猜。

有 pending 时追加：做完后 `forge-sync mark-cleared --kind …`。

text 示例：

```text
PENDING forge-sync n=2
  power_anchor_sync  journal#12  定稿/设定/工坊-功法-v1-提案2-草案.md
  contract_rebuild   journal#12  定稿/设定/工坊-功法-v1-提案2-草案.md
NEXT
  1. 手改力量锚点后：python -X utf8 webnovel.py --project-root <root> power validate
  2. python -X utf8 webnovel.py --project-root <root> master-outline-sync --volume <已完成规划的卷号>
  3. python -X utf8 webnovel.py --project-root <root> forge-sync mark-cleared --kind all
```

json 含 `ok`（pending 空为 true）、`pending` 列表、`next` 字符串列表。`ok` 与退出码一致：有 pending 时 `ok=false` 且 exit 1。

### 4.5 cleared 事件（不扩 journal 枚举）

```json
{
  "actor": "author",
  "action": "edit",
  "domain": "设定",
  "path": "<队头 path，缺则 作者/journal.jsonl>",
  "change_kind": "structure",
  "diff_stat": {"ins": 0, "del": 0},
  "summary": "forge-sync 消费 power_anchor_sync,contract_rebuild",
  "impact": ["power_anchor_sync:cleared", "contract_rebuild:cleared"]
}
```

`summary` 必非空（避免 Inv-1 `pending_semantic`）。`action=edit` 已在 `VALID_ACTIONS`。`--kind` 只含一种时 `impact` 只一项。

### 4.6 代码落点

| 文件 | 动作 |
|---|---|
| `webnovel-writer/scripts/data_modules/forge_sync.py` | 新增：扫描、status、mark-cleared、`main` |
| `webnovel-writer/scripts/data_modules/webnovel.py` | `cmd_forge_sync` + `forge-sync` 子解析器 |
| `webnovel-writer/scripts/tests/test_forge_sync.py` | 新增行为测试 |
| `docs/guides/commands.md` | `forge-sync` 一行 |

不改 `setting_forge.py`。

## 5. 数据与兼容

- journal 仍 append-only；不改 `forge_confirm` 写入格式。
- 空 journal / 无匹配 impact → pending 空，status exit 0。
- 既有 `test_setting_forge.py` 全绿。

## 6. 验收清单（W1：引用方案原文）

| # | 方案原文 | 验证 |
|---|---|---|
| 1 | 扫 journal 中 `power_anchor_sync:required` / `contract_rebuild:required` 未消费标记 | confirm 功法后 status json `pending` 含两种 kind；法宝 confirm 只有 `contract_rebuild` |
| 2 | 提示作者执行锚点确认与 master-outline-sync | status stdout / `next` 含 `power validate` 与 `master-outline-sync` |
| 3 | 消费后标记 cleared | `mark-cleared --kind all` 后 journal 出现 `*:cleared`，再次 status pending 空、exit 0 |
| 4 | 新 `forge-sync` 命令 | `webnovel.py forge-sync -h` 可解析；无子命令 = status |
| 5 | 验收：adopt 功法提案 → forge-sync 引导完成锚点同步 | 夹具 `save→adopt→confirm` 功法后 status exit 1 且引导含锚点；mark-cleared 后 exit 0 |
| 6 | 回归 | 既有 `test_setting_forge.py` 全绿；全量 pytest；cov ≥80 |

额外（方案 A 默认，非原文但必测）：status 不写 journal；无 pending 时 `mark-cleared` 拒写且 exit 2；多余 `cleared` 不吞后续 `required`。

## 7. 约束

- TDD：先失败测试再实现。
- Windows：`python -X utf8`。
- 提交：spec/plan 与实现分开 commit。
- 无 ledger，除非本任务改走 SDD。
