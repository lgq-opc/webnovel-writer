# doctor v7 书仓根解析 实施计划

> **执行者注意：** 按任务逐个实施。步骤用 checkbox 跟踪，完成即勾选。
>
> 我在用 writing-plans 技能写实施计划。

**目标：** 纯 v7 书仓（`book.yaml`）能解析到项目根，doctor 跑完 12 组既有检查；file 组按 v7 路径验存在性。
**架构：** `resolve_project_phase` 无 state.json 时认 `book.yaml` → `v7_story_repo`，章号复用 `max_settled_chapter`；doctor file 组分相；preflight 改 `_resolve_root_lenient`。
**技术栈：** Python 3.10+、pytest。
**Spec：** `docs/cursor/阶段四-doctor根解析/2026-09-04-doctor-root-spec.md`

## 全局约束

- 有 `state.json` → v6 状态机与 INIT 清单一字不改。
- 同时有 state 与 `book.yaml` → state 优先（v6）。
- v7 file 只查 `book.yaml` / `定稿/正文` / `大纲` / `作者`；不输出 v6 INIT 行。
- 不强制 `.story-system`；不实现 P4-1。
- 不改 `project_locator.resolve_project_root` 默认严格语义。
- Windows：`python -X utf8`；覆盖率不低于 80%。

## 执行总览

| 序号 | 任务名 | 依赖 | 验证方式 |
|---|---|---|---|
| 1 | 失败测试：v7 phase + doctor file/12 组 + preflight | — | `test_project_phase.py` / `test_doctor.py` 新例 RED |
| 2 | `resolve_project_phase` + doctor 分相 + total_words skip | 依赖 Task 1 | 定点 GREEN（除 CLI preflight 若仍红） |
| 3 | `_build_preflight_report` 宽松根 | 依赖 Task 2 | CLI `doctor --format json` 12 组前缀；v6 回归全绿 |

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `webnovel-writer/scripts/data_modules/tests/test_project_phase.py` | 修改 | v7 phase / 定稿章号 / state 优先 |
| `webnovel-writer/scripts/data_modules/tests/test_doctor.py` | 修改 | v7 12 组、缺定稿 error、无设定集、CLI preflight |
| `webnovel-writer/scripts/data_modules/project_phase.py` | 修改 | `PHASE_V7_STORY_REPO` |
| `webnovel-writer/scripts/data_modules/doctor.py` | 修改 | `_v7_file_checks`、profile、total_words skip、早退文案 |
| `webnovel-writer/scripts/data_modules/webnovel.py` | 修改 | `_build_preflight_report` 用 `_resolve_root_lenient` |

README P4-0 勾选留收尾。

---

## Task 1：失败测试

**文件：** `test_project_phase.py`、`test_doctor.py`

- [x] 在 `test_project_phase.py` 增加（文件顶部 import `PHASE_NO_PROJECT`、`PHASE_V7_STORY_REPO`）：

```python
def _make_v7_repo(root: Path, *, settled: str | None = "0042-夜袭.md") -> Path:
    (root / "book.yaml").write_text("书名: 测试\n", encoding="utf-8")
    for rel in ("定稿/正文", "大纲", "作者"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    if settled:
        (root / "定稿" / "正文" / settled).write_text("正文\n", encoding="utf-8")
    return root


def test_v7_book_yaml_is_story_repo_phase(tmp_path):
    _make_v7_repo(tmp_path)
    snapshot = resolve_project_phase(tmp_path)
    assert snapshot.phase == PHASE_V7_STORY_REPO
    assert snapshot.project_root
    assert snapshot.latest_accepted_chapter == 42
    assert snapshot.target_chapter == 42


def test_v7_ignores_v6_zhengwen_flat_dir(tmp_path):
    _make_v7_repo(tmp_path, settled=None)
    (tmp_path / "正文").mkdir()
    (tmp_path / "正文" / "第0099章.md").write_text("旧\n", encoding="utf-8")
    snapshot = resolve_project_phase(tmp_path)
    assert snapshot.phase == PHASE_V7_STORY_REPO
    assert snapshot.latest_accepted_chapter == 0


def test_state_json_wins_over_book_yaml(tmp_path):
    _make_init_ready(tmp_path)
    (tmp_path / "book.yaml").write_text("书名: 混\n", encoding="utf-8")
    snapshot = resolve_project_phase(tmp_path)
    assert snapshot.phase == PHASE_INIT_READY


def test_empty_dir_without_state_or_yaml_is_no_project(tmp_path):
    snapshot = resolve_project_phase(tmp_path)
    assert snapshot.phase == PHASE_NO_PROJECT
```

- [x] 在 `test_doctor.py` 增加（可把 `_make_v7_repo` 放本文件或从 phase 测试导入）：

```python
_SCRIPTS = Path(__file__).resolve().parents[2]
_GROUP_PREFIXES = (
    "preflight.",
    "file.",
    "json.",
    "story_runtime.",
    "sqlite.",
    "state.total_words_reconcile",
    "projection_log.",
    "commit.extraction_warnings",
    "contract.schema_version",
    "run_log.",
    "rag.",
    "domains.contract",
)


def _group_hits(checks: list[dict]) -> set[str]:
    ids = [str(item.get("id") or "") for item in checks]
    return {prefix for prefix in _GROUP_PREFIXES if any(i == prefix or i.startswith(prefix) for i in ids)}


def test_doctor_v7_runs_project_groups_not_only_python(tmp_path, monkeypatch):
    from test_project_phase import _make_v7_repo
    _make_v7_repo(tmp_path)
    monkeypatch.setattr(doctor_module, "_python_checks", lambda: [])
    report = doctor_module.build_doctor_report(tmp_path)
    assert report["phase"] == "v7_story_repo"
    ids = [c["id"] for c in report["checks"]]
    assert "project.root" not in ids
    assert any(i.startswith("file.v7.") for i in ids)
    assert not any(i.startswith("file.dir.设定集") or i.startswith("file.required.设定集") for i in ids)
    tw = [c for c in report["checks"] if c["id"] == "state.total_words_reconcile"]
    assert tw and tw[0]["status"] == doctor_module.CHECK_SKIPPED


def test_doctor_v7_missing_finalized_dir_errors(tmp_path, monkeypatch):
    from test_project_phase import _make_v7_repo
    _make_v7_repo(tmp_path, settled=None)
    import shutil
    shutil.rmtree(tmp_path / "定稿" / "正文")
    monkeypatch.setattr(doctor_module, "_python_checks", lambda: [])
    report = doctor_module.build_doctor_report(tmp_path)
    match = [c for c in report["checks"] if c["id"] == "file.v7.dir.定稿/正文"]
    assert match and match[0]["status"] == doctor_module.CHECK_ERROR
    assert report["ok"] is False


def test_doctor_cli_v7_emits_twelve_groups(tmp_path):
    from test_project_phase import _make_v7_repo
    import json
    import subprocess
    import sys
    _make_v7_repo(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(_SCRIPTS / "webnovel.py"),
         "--project-root", str(tmp_path), "doctor", "--format", "json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    payload = json.loads(proc.stdout)
    hits = _group_hits(payload["checks"])
    assert hits == set(_GROUP_PREFIXES)
    pre = [c for c in payload["checks"] if c["id"] == "preflight.project_root"]
    assert pre and pre[0]["status"] == doctor_module.CHECK_OK
```

跨文件 import：`test_doctor.py` 与 `test_project_phase.py` 同目录，pytest 收集时通常可 `from .test_project_phase import _make_v7_repo` 或同包相对导入。若失败，把 `_make_v7_repo` 复制进 `test_doctor.py`。

- [x] RED：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_project_phase.py webnovel-writer/scripts/data_modules/tests/test_doctor.py -q --no-cov -p no:cacheprovider -k "v7 or empty_dir_without or state_json_wins or twelve_groups or missing_finalized"
```

---

## Task 2：phase + doctor

**文件：** `project_phase.py`、`doctor.py`

- [x] `PHASE_V7_STORY_REPO = "v7_story_repo"` 加入 `PHASES`。

- [x] `resolve_project_phase` 在 `if not state_path.is_file()` 分支：

```python
    if not state_path.is_file():
        from .domain_contract import is_story_repo
        from .dual_format_guard import max_settled_chapter

        if is_story_repo(root):
            latest = max_settled_chapter(root)
            if chapter is not None:
                try:
                    target = max(0, int(chapter))
                except (TypeError, ValueError):
                    target = latest
            else:
                target = latest
            return ProjectPhaseSnapshot(
                project_root=str(root),
                phase=PHASE_V7_STORY_REPO,
                target_chapter=target,
                latest_accepted_chapter=latest,
            )
        return ProjectPhaseSnapshot(
            project_root=str(root),
            phase=PHASE_NO_PROJECT,
            target_chapter=0,
            latest_accepted_chapter=0,
            blocking=("missing .webnovel/state.json",),
        )
```

- [x] `doctor.py` import `PHASE_V7_STORY_REPO`。早退 `project.root` 的 `expected` 改为 `book.yaml or .webnovel/state.json`。

- [x] `_expected_profile`：若 `snapshot.phase == PHASE_V7_STORY_REPO`，files=`["book.yaml"]`，dirs=`["定稿/正文","大纲","作者"]`，return。

- [x] `_file_checks` 开头：v7 phase 只跑：

```python
V7_FILE_CHECKS = (
    ("file.v7.book.yaml", "book.yaml", True),
    ("file.v7.dir.定稿/正文", "定稿/正文", False),
    ("file.v7.dir.大纲", "大纲", False),
    ("file.v7.dir.作者", "作者", False),
)

def _v7_file_checks(project_root: Path) -> list[dict[str, Any]]:
    checks = []
    for check_id, rel, is_file in V7_FILE_CHECKS:
        path = project_root / rel
        exists = path.is_file() if is_file else path.is_dir()
        checks.append(_check(
            check_id,
            status=CHECK_OK if exists else CHECK_ERROR,
            severity="info" if exists else "blocker",
            message=f"v7 required {'file' if is_file else 'directory'} {rel}",
            path=str(path),
            expected="exists",
            actual="exists" if exists else "missing",
            impact="" if exists else "v7 书仓骨架不完整。",
            repair="" if exists else f"补齐 {rel}",
        ))
    return checks
```

- [x] `_total_words_reconcile_check`：读 state 失败（缺文件）时改为一条 skipped，不要 `return []`。其它早退（无漂移、无 index）保持 `return []`。

- [x] GREEN（可先不含 CLI 若 preflight 仍红）：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_project_phase.py webnovel-writer/scripts/data_modules/tests/test_doctor.py -q --no-cov -p no:cacheprovider
```

---

## Task 3：preflight 宽松根

**文件：** `webnovel.py`

- [x] `_build_preflight_report` 把 `_resolve_root(explicit_project_root)` 换成 `_resolve_root_lenient(explicit_project_root)`。`_resolve_root_lenient` 已先严格再认 `is_story_repo`。

- [x] GREEN 含 `test_doctor_cli_v7_emits_twelve_groups` 与全部 doctor / project_phase。

- [x] 提交（实现 + 测试，不含 spec/plan）：

```text
feat(doctor): 纯 v7 书仓解析项目根并按定稿体检
```

Task 2+3 可合成一次提交。

---

## 完成定义（实现期）

- [x] 新测试全绿；既有 doctor / project_phase 全绿。
- [x] tmp v7 CLI json 具备 spec §4.6 十二组前缀；`preflight.project_root` ok。
- [x] 缺 `定稿/正文` error；无 `file.dir.设定集` error。
- [x] 全量回归与 README W1（收尾提交）。

实现提交：`47e661c`。Task 2+3 合并为一次提交。
