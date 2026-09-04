# dashboard 承诺账本视图 实施计划

> **执行者注意：** 按任务逐个实施。步骤用 checkbox 跟踪，完成即勾选。
>
> 我在用 writing-plans 技能写实施计划。

**目标：** 治理快照增加 `ledger`（状态计数+全量条目+逾期列表）；GovernancePage 增加第七段。
**架构：** `_ledger_view` 调 `load_entries` + `foreshadow_scan(apply=False)`；当前章 `max_settled_chapter`；只读。
**技术栈：** Python 3.10+、pytest、React 19 / Vite 6。
**Spec：** `docs/cursor/阶段四-dashboard账本视图/2026-09-04-dashboard-ledger-spec.md`

## 全局约束

- `foreshadow_scan(..., apply=False)`，不把条目标逾期、不写 journal。
- 不改 ForeshadowingPage / 不新开 `/api/ledger`。
- 不改 doctor、P2-3、v6 写链、MCP 签名。
- schema 仍为 `governance-snapshot/1`（只加键）。
- Windows：`python -X utf8`；覆盖率不低于 80%。

## 执行总览

| 序号 | 任务名 | 依赖 | 验证方式 |
|---|---|---|---|
| 1 | 失败测试：ledger 键 / 计数 / 逾期只读 / 空账本 / 第七段文案 | — | `test_dashboard_app.py` 新例 RED |
| 2 | `_ledger_view` + ⑥ 章号同源 + GovernancePage ⑦ + dist | 依赖 Task 1 | 定点 GREEN；`npm run build` |
| 3 | 提交实现（不含 spec/plan） | 依赖 Task 2 | `feat(dashboard): 治理面板增加承诺账本视图` |

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `webnovel-writer/scripts/data_modules/tests/test_dashboard_app.py` | 修改 | ledger / 只读 / 空账本 / JSX 文案 |
| `webnovel-writer/dashboard/governance.py` | 修改 | `_ledger_view`；⑥ 用 `max_settled_chapter` |
| `webnovel-writer/dashboard/frontend/src/pages/GovernancePage.jsx` | 修改 | 第七段 |
| `webnovel-writer/dashboard/frontend/dist/**` | 重建 | 面板实际产物 |
| `webnovel-writer/dashboard/app.py` | 可选 | 注释「六视图」→「七视图」 |

README / 交接留收尾。

---

## Task 1：失败测试

**文件：** `test_dashboard_app.py`

在 `test_dashboard_governance_snapshot_endpoint` 的六键元组末尾加上 `"ledger"`。

再增加：

```python
def _plant_settled(project_root: Path, name: str = "0042-夜袭.md") -> None:
    body = project_root / "定稿" / "正文"
    body.mkdir(parents=True, exist_ok=True)
    (body / name).write_text("正文\n", encoding="utf-8")


def test_governance_ledger_counts_and_overdue_without_writing(monkeypatch, tmp_path):
    from data_modules.promise_ledger import create_entry, load_entries, update_status

    project_root = tmp_path / "book"
    _build_project_data(project_root)
    _plant_settled(project_root)
    create_entry(
        project_root,
        kind="伏笔",
        name="熔炉残响",
        planted_chapter=12,
        due_chapter=10,
        entry_id="F-001",
    )
    create_entry(
        project_root,
        kind="悬念",
        name="天裂来历",
        planted_chapter=1,
        due_chapter=300,
        entry_id="S-001",
    )
    update_status(project_root, entry_id="S-001", status="已回收", chapter=40)
    client = _create_dashboard_client(monkeypatch, project_root)

    payload = client.get("/api/governance").json()
    ledger = payload["ledger"]
    assert ledger["current_chapter"] == 42
    assert ledger["counts"]["open"] == 1
    assert ledger["counts"]["已回收"] == 1
    ids = [e["编号"] for e in ledger["entries"]]
    assert ids == ["F-001", "S-001"]
    overdue_ids = [e["编号"] for e in ledger["overdue"]]
    assert overdue_ids == ["F-001"]
    assert payload["alerts"]["overdue"][0]["编号"] == "F-001"
    still = {e["编号"]: e["状态"] for e in load_entries(project_root)}
    assert still["F-001"] == "open"
    assert still["S-001"] == "已回收"


def test_governance_empty_ledger_is_empty_structure(monkeypatch, tmp_path):
    project_root = tmp_path / "book"
    _build_project_data(project_root)
    client = _create_dashboard_client(monkeypatch, project_root)
    ledger = client.get("/api/governance").json()["ledger"]
    assert ledger["entries"] == []
    assert ledger["overdue"] == []
    assert ledger["counts"]["open"] == 0
    assert set(ledger["counts"]) >= {"open", "推进中", "已回收", "作废", "逾期"}


def test_governance_page_has_seventh_ledger_section():
    page = (
        Path(__file__).resolve().parents[3]
        / "dashboard"
        / "frontend"
        / "src"
        / "pages"
        / "GovernancePage.jsx"
    )
    text = page.read_text(encoding="utf-8")
    assert "⑦ 承诺账本" in text
```

`create_entry` 会写 journal（`action=add`）；本切片不断言 journal。F-001 `due=10` < 定稿 42 → 逾期；S-001 先建再 `已回收`，扫描器跳过已回收。

- [x] RED：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_dashboard_app.py -q --no-cov -p no:cacheprovider -k "governance"
```

预期：既有六键测因缺 `ledger` 失败；两例新测失败；JSX 文案测失败。

---

## Task 2：实现并接线

**文件：** `governance.py`、`GovernancePage.jsx`、可选 `app.py` 注释、`frontend/dist`

- [x] `governance.py` 增加 `_ledger_view`，接入 `build_governance_snapshot`：

```python
def _ledger_view(root: Path) -> dict[str, Any]:
    empty_counts = {"open": 0, "推进中": 0, "已回收": 0, "作废": 0, "逾期": 0}
    empty = {
        "current_chapter": 0,
        "counts": dict(empty_counts),
        "entries": [],
        "overdue": [],
    }
    try:
        from data_modules.dual_format_guard import max_settled_chapter
        from data_modules.promise_ledger import STATUS_VALUES, foreshadow_scan, load_entries

        chapter = max(1, max_settled_chapter(root))
        entries = load_entries(root)
        scan = foreshadow_scan(root, current_chapter=chapter, apply=False)
        counts = {key: 0 for key in STATUS_VALUES}
        for entry in entries:
            status = str(entry.get("状态") or "")
            if status in counts:
                counts[status] += 1
        return {
            "current_chapter": chapter,
            "counts": counts,
            "entries": [
                {
                    "编号": entry["编号"],
                    "类型": entry["类型"],
                    "名称": entry["名称"],
                    "状态": entry["状态"],
                    "埋设章": entry["埋设章"],
                    "最晚回收章": entry["最晚回收章"],
                    "回收章": entry["回收章"],
                }
                for entry in entries
            ],
            "overdue": [
                {
                    "编号": item["编号"],
                    "名称": item["名称"],
                    "最晚回收章": item["最晚回收章"],
                    "状态": item["状态"],
                }
                for item in scan.get("overdue") or []
            ],
        }
    except Exception:
        return empty
```

`build_governance_snapshot` 增加 `"ledger": _ledger_view(root)`。

- [x] `_alerts` 的 `latest` 改为 `max(1, max_settled_chapter(root))`（与 ledger 同源）。若 `_latest_chapter_hint` 无其它调用则删除。

- [x] `GovernancePage.jsx`：读 `snapshot.ledger`；⑥ 后增加第七段（计数一行、逾期、全量表、空态「无承诺账本条目」）。标题必须含原文 `⑦ 承诺账本`。

- [x] 可选：`app.py` 中 `/api/governance` 注释「六视图」改为「七视图」。

- [x] GREEN：Task 1 命令去掉 RED 预期。

- [x] 前端产物：

```powershell
Set-Location webnovel-writer/dashboard/frontend
npm run build
```

**验证/MCP：** 若本机可启 dashboard，用 Playwright 打开 `/governance`，断言可见「⑦ 承诺账本」及夹具编号；启不了则 fantasy01 收尾时用 `build_governance_snapshot` JSON 对账 F-001~S-001。

---

## Task 3：提交实现

- [x] 只 stage 实现 + 测试 + dist（不含 spec/plan）：

```text
feat(dashboard): 治理面板增加承诺账本视图
```

`git add` 须包含 `frontend/dist` 新建 hashed 文件；旧 hash 由 vite 删掉的要一并 `git add`。

---

## 完成定义（实现期）

- [x] 新测试全绿；既有 `test_dashboard_app.py` / governance 端点全绿。
- [x] tmp 仓 `ledger` 有计数与逾期；扫描后 F-001 仍为 `open`。
- [x] 空账本不报错。
- [x] JSX / dist 含「⑦ 承诺账本」。
- [x] 全量回归与 README W1 留收尾。

实现提交：`0f399fe`。Task 1–3 合并为一次提交。Playwright MCP 本轮不可用，真仓用 `GET /api/governance` + dist 文案对账。
