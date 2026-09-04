# Spec：写回播种 + learn CLI + 重复大纲去重（v8-gap-review 阶段三 P3-3）

> 档位：Architectural（新账本动作 + CLI 合同 + 跨仓去重）
> 状态：**已批准**（Human 2026-09-04 确认书面稿）
> 上游：`docs/zcode/v8-gap-review-3rounds/README.md` 阶段三 P3-3；N1 / N2 / N9
> 下游：同目录 `2026-09-04-writeback-seed-plan.md` → TDD → 收尾

## 1. 背景与目标

总纲写回 JSON（`大纲/卷纲/第NN卷-总纲写回.json`）迁入后无消费者：`foreshadow_writeback` 躺在文件里，`promise-ledger` 不会建账。`learn` 把子命令与 action 都叫 `learn`，首次调用必须写成 `learn learn --from-journal`，否则 usage error（N9）。fantasy01 详细大纲有两份字节级相同副本（N1）：迁移器产物 `第01卷.md` 与补入的 `第01卷-详细大纲.md`。

**目标：** ① 一键把写回数组种进承诺账本；② `learn --from-journal` 可直接跑；③ 删无后缀副本，只留带后缀规范路径。

**成功标准（抄 gap-review 阶段三 P3-3 原文）：**

> ①promise-ledger 增 `seed-from-writeback`：读 `第NN卷-总纲写回.json` 的 foreshadow_writeback 数组建账本条目；②修 `learn` CLI 冗余参数（action 默认 learn）；③fantasy01 重复详细大纲去重（保留带后缀版）
>
> 验收：写回 8 条伏笔一键入账；`learn --from-journal` 直接可跑

**勘误（以真仓 JSON 为准，不造第 8 条）：** `projects/loom-books/fantasy01/大纲/卷纲/第01卷-总纲写回.json` 的 `foreshadow_writeback` **实际 7 条**。验收条数 = 该数组长度，不是字面「8」。W1 收尾时同步改 README 原文旁注。

## 2. 非目标

- 不实现 P4-x（doctor 治理组等）。
- 不播种 `open_loop_writeback`（5 条开放环；原文只提伏笔）。
- 不在本任务对 **真仓** fantasy01 跑 `seed-from-writeback`（会新增 F-00x 并再写 `action=add` journal；现有 F-001～F-003 名称与写回 `content` 不同，不会幂等跳过）。入账验收用 tmp 书仓 + 真 JSON 副本。
- 不改 `create_entry` 的 `action=add`（Inv-1 历史债，P2-3 已登记不自动修）。
- 不改 CLI `create` 的「`--due-chapter` 必非 0」；播种走 Python API，允许 `due_chapter=0`。
- 不改 v6 `context_manager` / write-gate / `chapter_commit.py`。
- 不新增 skill / 斜杠命令文件；`docs/guides/commands.md` 改 learn 一行、promise-ledger 一行。
- 不去重除 fantasy01 第 01 卷以外的书仓；哈希不同则拒绝删除、不停手改内容。

## 3. 方案与裁决

| 方案 | 内容 | 裁决 |
|---|---|---|
| **A（采纳，Human 2026-09-04）** | ① `seed-from-writeback --volume N` 只读 `foreshadow_writeback`，空 payoff→due=0，按 `名称=content` 幂等跳过；② `learn` action `nargs=?` 默认 `learn`；③ SHA-256 相同后删 `第01卷.md` | 对齐原文三款；不把开放环塞进伏笔账本 |
| B | 同时播种 `open_loop_writeback` 为悬念 | 否决：超出「伏笔入账」口径 |
| C | ① 只 dry-run 打印 | 否决：对不上「一键入账」 |

**默认（随方案 A）：** 空 `payoff_chapter` → `due_chapter=0`；不猜「埋设+10」。名称用 `content` 全文。`level` 写入条目正文 note。③ 只动 `loom-books/fantasy01`，与插件仓分开 commit。

## 4. 设计

### 4.1 写回文件

路径（与现有卷纲命名一致，两位零填充）：

```
大纲/卷纲/第{volume:02d}卷-总纲写回.json
```

只读顶层数组 `foreshadow_writeback`。每条字段：

| JSON | 账本 |
|---|---|
| `content` | `名称`（全文，strip） |
| `buried_chapter` | `埋设章`（见 §4.2） |
| `payoff_chapter` | `最晚回收章`（空/缺 → 0） |
| `level` | 正文 note 一行 `level: {level}` |

`kind` 固定 `伏笔`。忽略同文件其它键（含 `open_loop_writeback`、`next_volume_anchor`）。

### 4.2 章号解析

接受 `第17章`、`第17 章`、纯数字 `17`。正则抽出第一个十进制整数。

- `buried_chapter` 解析失败或结果 `< 1` → 该条 `failed`，不建文件。
- `payoff_chapter` 空白 → `0`；非空但解析失败 → 该条 `failed`。
- `content` 空白 → 该条 `failed`（`missing_name`）。

一批内先处理的成功条目占用下一个 `F-###`；失败条不占号。

### 4.3 幂等

播种前 `load_entries(root, kind="伏笔")`。若已有条目 `名称` 与 `content` **完全相等**（strip 后），该条 `skipped`，`reason=duplicate_name`，带已有 `id`。不做模糊合并（真仓 F-001「熔炉残响与引劫人」≠ 写回「熔炉残响说出'天劫'…」）。

第二次对同一 JSON 再跑：`created` 空，`skipped` = 数组长度，exit 0。

### 4.4 `create_entry` 复用

每条新建调用现有 `create_entry(...)`（自动递增 `F-###`、写 md、journal `action=add`）。不新造编号规则。允许 `due_chapter=0`。

### 4.5 CLI：`seed-from-writeback`

```
webnovel.py [--project-root ROOT] promise-ledger seed-from-writeback --volume N [--format text|json]
```

`--volume` 必填。`create` / `list` / `update` 行为不变。

**退出码：**

| 条件 | 码 |
|---|---|
| 缺文件 / JSON 非法 / 根对象非 dict / `foreshadow_writeback` 缺或非 list | 2，不写账本 |
| 有 `failed` 条（其余仍尽量写入） | 1 |
| 否则（含数组空、全 skip） | 0 |

text 示例：

```text
OK seed-from-writeback volume=1 created=7 skipped=0 failed=0
  F-001「江岸仓库地底上古遗迹与妖王颈上铁链（有人把妖王拴在灾源旁，链连石门）」
  …
```

json：`ok`（exit 0 为 true）、`volume`、`source`、`created`（id 列表）、`skipped`、`failed`。`ok=false` 当 exit≠0。

### 4.6 learn CLI（N9）

`webnovel.py learn` 与 `author_model.main` 的 `action` 均改为 `nargs="?"`、`default="learn"`、`choices=["learn","apply","show"]`。

| 调用 | 结果 |
|---|---|
| `learn --from-journal` | 归纳（本任务验收） |
| `learn learn --from-journal` | 仍可跑（显式） |
| `learn apply` / `learn show` | 仍须显式 action |
| `learn` 无 `--from-journal` | 保持现有：learn 动作仍要求 `--from-journal`（error） |

不删 `apply`/`show`。不改 `learn_from_journal` 算法。

### 4.7 重复大纲（N1，书仓）

真仓（2026-09-04 已测）：

- `大纲/卷纲/第01卷-详细大纲.md` 与 `大纲/卷纲/第01卷.md` 大小均为 101722 字节，SHA-256 相同（`48e52806…` 前缀）。
- P2-1 `resolve_detailed_outline` 已优先规范路径，再回退 `第NN卷.md`。

本任务：再算一次整文件哈希；**相同**则删除 `第01卷.md`，只留 `-详细大纲.md`；在 **`projects/loom-books/fantasy01` 仓**单独 commit。哈希不同则停止、不删、不改内容。

插件仓：不提交该书文件；可加回归：仅有规范路径时 `resolve_detailed_outline(..., 1)` 仍指向 `-详细大纲.md`（P2-1 已有则不重复造套）。

### 4.8 代码落点

| 位置 | 动作 |
|---|---|
| `webnovel-writer/scripts/data_modules/promise_ledger.py` | `seed_from_writeback` + `crud_main` 增 action |
| `webnovel-writer/scripts/data_modules/webnovel.py` | `promise-ledger` choices 含 `seed-from-writeback`；转发 `--volume`；`learn` action 可选 |
| `webnovel-writer/scripts/data_modules/author_model.py` | `action` 同样可选，默认 `learn` |
| `webnovel-writer/scripts/tests/test_writeback_seed.py` | 播种行为（含 7 条夹具 / 幂等 / 坏章号 / 缺文件） |
| `webnovel-writer/scripts/tests/test_learn_cli.py` | `learn --from-journal` 可解析并进入 learn 路径（夹具 journal 可最小） |
| `docs/guides/commands.md` | learn 去掉 N9 警告；promise-ledger 补 seed |
| `projects/loom-books/fantasy01/大纲/卷纲/第01卷.md` | 哈希确认后删除（书仓 commit） |
| `docs/zcode/v8-gap-review-3rounds/README.md` | 收尾 W1：P3-3 勾选 +「8 条」旁注 7 |

不改 `outline_paths.py` 读序（删副本后回退路径仍合法，只是文件不在）。

## 5. 数据与兼容

- 账本 schema 不变；新建条目 `状态=open`。
- 既有 `create`/`list`/`update` 与 foreshadow-scan 全绿。
- 真仓三份已有伏笔条目不改、不删。
- `learn apply` / `show` 回归保持。

## 6. 验收清单（W1：引用方案原文）

| # | 方案原文 | 验证 |
|---|---|---|
| 1 | 读 `第NN卷-总纲写回.json` 的 foreshadow_writeback 数组建账本条目 | tmp 书仓放入与真仓同结构的 7 条 JSON；`seed-from-writeback --volume 1` 后 `大纲/条目/伏笔/` 新增 7 个 `F-*.md`，`名称` 与 `content` 一一对应 |
| 2 | promise-ledger 增 `seed-from-writeback` | `webnovel.py promise-ledger -h` 含该 action；缺 `--volume` usage error |
| 3 | 验收：写回 8 条伏笔一键入账 | **勘误为数组长度**：夹具 7 条 → created=7；第二次 created=0 skipped=7。不以字面 8 造数据 |
| 4 | 修 `learn` CLI 冗余参数（action 默认 learn） | `webnovel.py learn --from-journal` 不再 usage error（夹具可跑通 learn 或至少进入 `learn_from_journal`） |
| 5 | 验收：`learn --from-journal` 直接可跑 | 同上；`learn apply` 仍需显式 apply |
| 6 | fantasy01 重复详细大纲去重（保留带后缀版） | 删除前 SHA-256 相等；删后仅存 `第01卷-详细大纲.md`；`resolve_detailed_outline(root, 1)` 指向该文件 |
| 7 | 回归 | 既有账本/learn 相关测试全绿；全量 pytest；cov ≥80 |

额外（方案 A 默认，非原文但必测）：不读 `open_loop_writeback`；空 payoff → 最晚回收章 0；缺写回文件 exit 2 不写盘；`buried_chapter` 无法解析则该条 failed、其余仍种。

## 7. 约束

- TDD：先失败测试再实现。
- Windows：`python -X utf8`。
- 提交：spec/plan 与实现分开；插件仓与 fantasy01 仓分开；中文 message 走 UTF-8 文件 + `git commit -F`。
- 无 ledger，除非本任务改走 SDD。
- 不 push，除非 Human 再批。
