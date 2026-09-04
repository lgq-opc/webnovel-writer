# doctor 治理检查组 实施计划

> **执行者注意：** 按任务逐个实施。步骤用 checkbox 跟踪，完成即勾选。
>
> 我在用 writing-plans 技能写实施计划。

**目标：** doctor 在已解析项目根时恒发出 8 条 `gov.*` 治理检查。
**架构：** 六项映射 `run_invariants`；素材健康调 `review_stats`；画廊扫两处 regen。fail/warn → doctor warning，不当 blocker。
**技术栈：** Python 3.10+、pytest。
**Spec：** `docs/cursor/阶段四-doctor治理检查/2026-09-04-doctor-governance-spec.md`

## 全局约束

- 不实现 git dirty vs journal 未留账。
- 不改 P2-3 六项语义与 `invariants` CLI 退出码。
- 治理组不得 `severity=blocker`。
- 不自动修复、不删画廊、不写素材。
- Windows：`python -X utf8`；覆盖率不低于 80%。

## 执行总览

| 序号 | 任务名 | 依赖 | 验证方式 |
|---|---|---|---|
| 1 | 失败测试：8 组 id / 映射 / 素材 / 画廊 / 非 blocker | — | `test_doctor.py` 新例 RED |
| 2 | `_governance_checks` + 接入 `build_doctor_report` | 依赖 Task 1 | 定点 GREEN |
| 3 | 提交实现（不含 spec/plan） | 依赖 Task 2 | `feat(doctor): 接入八组治理体检` |

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `webnovel-writer/scripts/data_modules/tests/test_doctor.py` | 修改 | 治理组用例 |
| `webnovel-writer/scripts/data_modules/doctor.py` | 修改 | `_governance_checks` 与接线 |

README / 交接留收尾。

---

## Task 1：失败测试

**文件：** `test_doctor.py`

复用 `_make_v7_repo`。

- [x] 增加：

```python
_GOV_IDS = (
    "gov.inv-1-journal",
    "gov.inv-2-material-trajectory",
    "gov.inv-3-power",
    "gov.inv-4-promises",
    "gov.inv-5-contracts",
    "gov.inv-6-stale-age",
    "gov.materials.health",
    "gov.gallery.backlog",
)


def test_doctor_v7_emits_eight_governance_checks(tmp_path, monkeypatch):
    _make_v7_repo(tmp_path)
    monkeypatch.setattr(doctor_module, "_python_checks", lambda: [])
    report = doctor_module.build_doctor_report(tmp_path)
    ids = [c["id"] for c in report["checks"]]
    for gov_id in _GOV_IDS:
        assert gov_id in ids
    gov = [c for c in report["checks"] if str(c["id"]).startswith("gov.")]
    assert not [c for c in gov if c.get("severity") == "blocker"]
    assert report["ok"] is True


def test_doctor_maps_invariant_fail_to_warning_not_blocker(tmp_path, monkeypatch):
    from data_modules.author_journal import append_events

    _make_v7_repo(tmp_path)
    append_events(
        tmp_path,
        [{
            "actor": "author",
            "action": "edit",
            "domain": "其他",
            "path": "工作区/散落.md",
            "change_kind": "content",
            "diff_stat": {"ins": 1, "del": 0},
            "summary": "散落",
            "impact": [],
        }],
    )
    monkeypatch.setattr(doctor_module, "_python_checks", lambda: [])
    report = doctor_module.build_doctor_report(tmp_path)
    match = [c for c in report["checks"] if c["id"] == "gov.inv-1-journal"]
    assert match and match[0]["status"] == doctor_module.CHECK_WARNING
    assert match[0]["severity"] == "warning"
    assert report["ok"] is True


def test_doctor_materials_health_warns_on_decayed_active(tmp_path, monkeypatch):
    _make_v7_repo(tmp_path, settled="0150-远征.md")
    (tmp_path / "book.yaml").write_text("书名: 测试\n卷规模: 50\n", encoding="utf-8")
    live = tmp_path / "素材" / "活"
    live.mkdir(parents=True)
    (live / "桥段.csv").write_text(
        "id,名称,来源,状态\nTR-001,旧桥,原创,active\n", encoding="utf-8"
    )
    monkeypatch.setattr(doctor_module, "_python_checks", lambda: [])
    report = doctor_module.build_doctor_report(tmp_path)
    match = [c for c in report["checks"] if c["id"] == "gov.materials.health"]
    assert match and match[0]["status"] == doctor_module.CHECK_WARNING


def test_doctor_gallery_backlog_warns_after_two_volumes(tmp_path, monkeypatch):
    _make_v7_repo(tmp_path, settled="0150-远征.md")
    (tmp_path / "book.yaml").write_text("书名: 测试\n卷规模: 50\n", encoding="utf-8")
    gallery = tmp_path / "大纲" / "regen" / "总纲"
    gallery.mkdir(parents=True)
    (gallery / "v1.md").write_text("旧稿\n", encoding="utf-8")
    monkeypatch.setattr(doctor_module, "_python_checks", lambda: [])
    report = doctor_module.build_doctor_report(tmp_path)
    match = [c for c in report["checks"] if c["id"] == "gov.gallery.backlog"]
    assert match and match[0]["status"] == doctor_module.CHECK_WARNING


def test_doctor_gallery_and_materials_skip_when_absent(tmp_path, monkeypatch):
    _make_v7_repo(tmp_path)
    monkeypatch.setattr(doctor_module, "_python_checks", lambda: [])
    report = doctor_module.build_doctor_report(tmp_path)
    mats = [c for c in report["checks"] if c["id"] == "gov.materials.health"]
    gal = [c for c in report["checks"] if c["id"] == "gov.gallery.backlog"]
    assert mats and mats[0]["status"] == doctor_module.CHECK_SKIPPED
    assert gal and gal[0]["status"] == doctor_module.CHECK_SKIPPED
```

journal 夹具用 `append_events`（与 `test_invariant_check.py` 同字段）。`素材/活/桥段.csv` 表名来自 `MATERIAL_TABLES`（「桥段」）。

- [x] RED：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_doctor.py -q --no-cov -p no:cacheprovider -k "governance or materials_health or gallery_backlog"
```

---

## Task 2：实现并接线

**文件：** `doctor.py`

- [x] 增加 `_inv_status_to_doctor(status: str) -> tuple[str, str]`：`fail|warn` → `(CHECK_WARNING, "warning")`；`skip` → `(CHECK_SKIPPED, "info")`；其余 → `(CHECK_OK, "info")`。

- [x] `_governance_checks(project_root: Path) -> list[dict]`：

```python
from .invariant_check import run_invariants, volume_of_chapter, volume_size
from .dual_format_guard import max_settled_chapter
from .material_review import review_stats

def _current_volume(root: Path) -> int:
    size = volume_size(root)
    chapter = max(1, max_settled_chapter(root))
    return volume_of_chapter(chapter, size)
```

六项：`run_invariants(root)` 后对每个 `invariants[]` 发 `_check(f"gov.{item['id']}", ...)`。

素材：`stats = review_stats(root, current_volume=_current_volume(root))`；`total==0` skip；`sum(e["decayed"] and e.get("状态")=="active" for e in entries)` > 0 则 warning。

画廊：收集 spec §4.4 三类文件；产物卷规则按 spec；`current_volume - produced >= 2` 计入积压。

- [x] `build_doctor_report` 在 `domains.contract` 块之后：

```python
        try:
            checks.extend(_governance_checks(root))
        except Exception as exc:
            checks.append(_check(
                "gov.suite",
                status=CHECK_WARNING,
                severity="warning",
                message="governance checks failed",
                actual=str(exc),
                impact="治理组（不变量/素材/画廊）本次未跑完。",
                repair="检查 invariant_check / 素材 CSV / 画廊目录可读性。",
            ))
```

- [x] GREEN：Task 1 命令去掉 RED 预期，再跑全部 `test_doctor.py` 与 `scripts/tests/test_invariant_check.py`。

- [x] 提交（实现 + 测试）：

```text
feat(doctor): 接入八组治理体检
```

---

## 完成定义（实现期）

- [x] 新测试全绿；既有 doctor / invariant 全绿。
- [x] tmp v7 恒有 8 个 `gov.*`；治理组无 blocker。
- [x] journal `domain=其他` → `gov.inv-1-journal` warning 且 `ok is True`。
- [x] 全量回归与 README W1 留收尾。

实现提交：`c0c5981`。Task 1–3 合并为一次提交。CLI 外置化适配（`test_doctor_cli_reports_missing_init_file` 认 `EXTERNALIZED` dump）同 commit。
