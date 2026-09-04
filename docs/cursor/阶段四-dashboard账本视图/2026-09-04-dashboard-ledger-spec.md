# Spec：dashboard 承诺账本视图（v8-gap-review 阶段四 P4-2 / N6）

> 档位：Architectural（治理快照增 `ledger` 键；GovernancePage 增第七段；重编 dist）
> 状态：**已批准**（Human 2026-09-04 确认方案 A 及捆绑默认）
> 上游：`docs/zcode/v8-gap-review-3rounds/README.md` 阶段四 P4-2、§2.4 N6；`07-feature-flows.md` F-14；`promise_ledger.py`
> 下游：同目录 `2026-09-04-dashboard-ledger-plan.md` → TDD → 收尾

## 1. 背景与目标

F-14 治理面板是六组只读视图；⑥ 红点已用 `foreshadow_scan(apply=False)` 列出逾期，但**没有全量账本**（各状态计数 + 每条编号/状态）。N6 说「F-14 只写了 stale 红点」——逾期列表后来补上了，缺口变成：非逾期条目在治理页不可见。

fantasy01 现有 F-001 / F-002 / F-003 / S-001，全是 `open`，当前定稿约 41 章，**无逾期**，⑥ 上看不到这四条。侧栏「伏笔追踪」读 v6 `state.json` 的 `plot_threads.foreshadowing`，不是 `大纲/条目`。

**目标：** `build_governance_snapshot` 增加 `ledger` 视图；GovernancePage 增加第七段；面板能看到 F-001~S-001 的状态。

**成功标准（抄 gap-review 阶段四 P4-2 原文）：**

> governance.py 增承诺账本视图（各状态计数+逾期列表）；GovernancePage 增第七段
>
> 验收：面板可见 F-001~S-001 状态

## 2. 非目标

- 不改 ForeshadowingPage / `lib/foreshadowing.js`（仍读 v6 `plot_threads`）。
- 不把 `foreshadow_scan(..., apply=True)` 接到 dashboard（禁止写盘、禁止把条目标成「逾期」）。
- 不改 doctor、P2-3 不变量、`invariants` CLI、v6 写链、MCP 签名。
- 不新开 `/api/ledger`。
- 不实现 P4-3。

## 3. 方案与裁决

| 方案 | 内容 | 裁决 |
|---|---|---|
| **A（采纳，Human 2026-09-04）** | 快照加 `ledger`；页面加 ⑦。`load_entries` + `foreshadow_scan(apply=False)` | 对准 P4-2 原文；⑥ 红点保留 |
| B | 计数和全表塞进 ⑥ | 否决：不增加第七段 |
| C | 另开 `/api/ledger` | 否决：多一个 GET 面，快照已能装下 |

捆绑默认（同批批准）：

1. **payload：** `counts` 按 `open / 推进中 / 已回收 / 作废 / 逾期`；`entries` 全量；`overdue` 与 ⑥ 同源；`current_chapter` 用 `max_settled_chapter`。无条目则空结构，不报错。
2. **不写盘：** `apply=False`；该视图失败返回空结构，不拖垮快照。
3. **schema：** 只加键，仍用 `governance-snapshot/1`。
4. **⑥：** 保留；逾期章号改走同一 `max_settled_chapter`；删除仅此使用的 `_latest_chapter_hint`。
5. **前端：** 改 `GovernancePage.jsx` 后 rebuild 并提交 `frontend/dist`。

## 4. 设计

### 4.1 接线

`build_governance_snapshot` 增加键 `ledger`，值由 `_ledger_view(root)` 返回。整函数 `try/except`：异常 → 空结构（counts 全 0、entries/overdue 空列表、`current_chapter` 为 `max(1, max_settled_chapter)` 或 0 若连章号也失败）。

`GET /api/governance` 仍只调 `build_governance_snapshot`，无新路由、无 POST。

### 4.2 `ledger` 形状

```text
ledger.current_chapter: int          # max(1, max_settled_chapter(root))
ledger.counts: {open, 推进中, 已回收, 作废, 逾期}  # 键集 = promise_ledger.STATUS_VALUES
ledger.entries: [{编号, 类型, 名称, 状态, 埋设章, 最晚回收章, 回收章}, ...]  # load_entries 全量，按编号
ledger.overdue: [{编号, 名称, 最晚回收章, 状态}, ...]  # foreshadow_scan(..., apply=False)["overdue"]
```

不返回 `path` / 正文。未知 `状态` 不计入 `counts` 任一键（仍出现在 `entries`）。

⑥ `alerts.overdue` 继续用同一扫描（`apply=False`、同一 `current_chapter`），字段保持现有 `编号/名称/最晚回收章`。

### 4.3 当前章

与 P4-1 同源：`data_modules.dual_format_guard.max_settled_chapter`（`定稿/正文/NNNN-*.md`）。无定稿时扫描用 `max(1, 0) = 1`。不再用 `_latest_chapter_hint`。

### 4.4 前端第七段

`GovernancePage.jsx` 在 ⑥ 之后增加：

- 标题：`⑦ 承诺账本`
- 一行计数：五个状态 + `current_chapter`
- 逾期列表（可与 ⑥ 重复，⑦ 以账本为主）
- 全量表：编号、类型、名称、状态、最晚回收章
- 无条目：Empty「无承诺账本条目」

只读展示，无按钮写盘。

改完后在 `webnovel-writer/dashboard/frontend` 执行 `npm run build`，提交 `dist/`（面板实际吃 dist）。

### 4.5 代码落点

| 文件 | 动作 |
|---|---|
| `webnovel-writer/dashboard/governance.py` | `_ledger_view`；接入 snapshot；⑥ 章号同源 |
| `webnovel-writer/scripts/data_modules/tests/test_dashboard_app.py` | ledger 键、计数、逾期只读、空账本 |
| `webnovel-writer/dashboard/frontend/src/pages/GovernancePage.jsx` | 第七段 |
| `webnovel-writer/dashboard/frontend/dist/**` | rebuild |

不新增 MCP 文件。不改 `dashboard/app.py` 路由签名（注释可改为「七视图」）。

## 5. 数据与兼容

- v6（有 `state.json`）若同时有 `大纲/条目` 则 ⑦ 有数据；仅有 `plot_threads.foreshadowing` 不够。
- 纯 v7 / fantasy01：四条 open，⑦ 可见 F-001~S-001。
- 不写盘。既有六键仍在。

## 6. 验收清单（W1：引用方案原文）

| # | 方案原文 | 验证 |
|---|---|---|
| 1 | governance.py 增承诺账本视图（各状态计数+逾期列表） | snapshot 含 `ledger`；`counts` 五键；逾期列表与 `foreshadow_scan(apply=False)` 一致；扫描后条目状态仍为扫描前（未写盘） |
| 2 | GovernancePage 增第七段 | JSX 含 `⑦ 承诺账本`；dist 构建产物含该文案 |
| 3 | 面板可见 F-001~S-001 状态 | fantasy01 快照 `entries` 含这四个编号及其 `状态`；浏览器 `/governance` 第七段可见 |
| 4 | 回归 | `test_dashboard_app.py` 定点全绿；全量 pytest；cov ≥80；evals fast 23/23；三校验器 OK |

## 7. 约束

- TDD：先失败测试再实现。
- Windows：`python -X utf8`。
- 提交：spec/plan 与实现分开；中文 message 走 UTF-8 文件 + `git commit -F`。
- 无 ledger（ruling），除非改走 SDD。
- 不 push，除非 Human 再批。
