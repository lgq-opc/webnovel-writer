# v7 settle 后置钩子 实施计划

> **执行者注意：** 按任务逐个实施。步骤用 checkbox 跟踪，完成即勾选。
>
> 我在用 writing-plans 技能写实施计划。

**目标：** settle 成功后自动落账素材轨迹、文风指纹、追读力，失败不阻断，后置文件与定稿同一次 git commit。
**架构：** `v7_write._run_post_hooks` 依次调用已有 `log_chapter_materials` / `settle_style_domain` 与新增 `settle_reading_power`；git add 候选路径在 commit 前执行。
**技术栈：** Python 3.10+、pytest、git CLI。
**Spec：** `docs/cursor/阶段三-settle后置钩子/2026-09-04-settle-post-hooks-spec.md`

**执行记录（2026-09-04，Cursor）**：Task 1–3 完成。实现 commit `6ed016f`；spec/plan `c1c8267`。无 ledger（未走 SDD）。定点 `test_v7_write_post_hooks.py` + gates + `test_v7_write.py`。全量 `1550 passed` / cov 82.85%。fantasy01 只读副本 ch43 `--no-commit`：`post=materials:ok/2 style:fp=42,samples=0 reading:ok`。

## 全局约束

- 后置在定稿写盘之后、`git add`/`commit` 之前。
- 各自 try/except，不回滚定稿，不改变退出码。
- git add 仅：`定稿`、`素材/使用轨迹.jsonl`、`文风/指纹.yaml`、`作者/journal.jsonl`、`.webnovel/index.db`（存在且未被 ignore）。
- 不改 v6 `chapter_commit.py` / write-gate / `context_manager`。
- Windows 命令统一 `python -X utf8`；覆盖率不低于 80%。

## 执行总览

| 序号 | 任务名 | 依赖 | 验证方式 |
|---|---|---|---|
| 1 | 失败测试：三钩子、git add、不阻断、CLI 一行 | — | `test_v7_write_post_hooks.py` RED |
| 2 | `_run_post_hooks` + `settle_reading_power` + git add 扩展 | 依赖 Task 1 | 定点测试 GREEN |
| 3 | CLI `post=` 行 + 既有门禁测试回归 | 依赖 Task 2 | gates + post_hooks + CLI |

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `webnovel-writer/scripts/data_modules/reading_power_projection.py` | 修改 | 新增 `settle_reading_power` |
| `webnovel-writer/scripts/v7_write.py` | 修改 | `_run_post_hooks`、`_git_add_settle_paths`、settle 顺序、CLI 一行 |
| `webnovel-writer/scripts/data_modules/tests/test_v7_write_post_hooks.py` | 新增 | P3-1 行为测试 |
| `webnovel-writer/scripts/data_modules/tests/test_v7_write_gates.py` | 修改 | CLI 断言含 `post=` |

---

## Task 1：失败测试

**文件：** 新增 `test_v7_write_post_hooks.py`；修改 `test_v7_write_gates.py` CLI 断言。

- [x] 写失败测试（夹具复用 gates 的 `_repo` / `_review` / `_decision` / CLEAN_BODY 模式，本文件自备以免循环导入）：

```python
def test_materials_logged_and_committed(tmp_path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    _seed_bridge(repo, "Q-001")
    (repo / "大纲" / "章纲" / "0042.md").write_text(
        '---\n章号: 42\n素材引用: ["桥段:Q-001"]\n---\n', encoding="utf-8"
    )
    result = _settle(repo, _decision(), commit=True)
    assert result["post"]["materials"]["status"] == "ok"
    rows = read_trajectory(repo, chapter=42)
    assert rows and rows[0]["条目id"] == "Q-001"
    tracked = _ls_files(repo)
    assert any(p.endswith("使用轨迹.jsonl") for p in tracked)


def test_fingerprint_written_and_committed(tmp_path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    result = _settle(repo, _decision(), commit=True)
    assert result["post"]["style"]["status"] == "ok"
    assert result["post"]["style"]["recorded"] == 0
    assert (repo / "文风" / "指纹.yaml").is_file()
    assert any(p.endswith("指纹.yaml") for p in _ls_files(repo))


def test_reading_power_from_summary_front_matter(tmp_path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    summary = "---\nhook_type: 悬念\nhook_strength: strong\n---\n夜未完。"
    result = settle(repo, _decision(), draft_path=repo / "工作区" / "草稿-0042.md", summary=summary, commit=False)
    assert result["post"]["reading"]["status"] == "ok"
    from data_modules.config import DataModulesConfig
    from data_modules.index_manager import IndexManager
    row = IndexManager(DataModulesConfig.from_project_root(repo)).get_chapter_reading_power(42)
    assert row and row["hook_type"] == "悬念"


def test_reading_skipped_without_hook(tmp_path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    result = _settle(repo, _decision())
    assert result["post"]["reading"]["status"] == "skipped"


def test_hook_error_does_not_block_settle(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    _review(repo, 0)
    import data_modules.material_usage as mu
    monkeypatch.setattr(mu, "log_chapter_materials", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))
    result = _settle(repo, _decision(), commit=True)
    assert list((repo / "定稿" / "正文").glob("0042-*"))
    assert result["post"]["materials"]["status"] == "error"


def test_gate_reject_skips_post_hooks(tmp_path):
    repo = _repo(tmp_path)
    _review(repo, 1)
    with pytest.raises(GateRejected):
        _settle(repo, _decision(), commit=True)
    assert not (repo / "文风" / "指纹.yaml").exists()
```

CLI：`test_exit_0_with_bypass` 增加 `assert "post=" in proc.stdout`。

- [x] 运行 RED：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_v7_write_post_hooks.py webnovel-writer/scripts/data_modules/tests/test_v7_write_gates.py::TestSettleCli -q --no-cov -p no:cacheprovider
```

---

## Task 2：实现后置与 git add

**文件：** `reading_power_projection.py`、`v7_write.py`

- [x] `settle_reading_power(root, chapter, summary_text) -> dict`：`extract_hook_fields`；无 `hook_type` 再读章摘要文件；仍无则 `skipped`；否则 `IndexManager.save_chapter_reading_power`。
- [x] `_run_post_hooks(repo, chapter, summary_text)` 按 spec §4.2。
- [x] `_git_add_settle_paths(repo)`：对候选路径 `exists` 且 `git check-ignore -q` 非 0 则 `git add -- <rel>`。
- [x] `settle`：写盘 + 绕过 journal 之后调用后置，再 add+commit。`result["post"] = ...`
- [x] 运行定点 GREEN。

- [x] 提交：

```text
feat(settle): 成功后落账轨迹、指纹与追读力
```

---

## Task 3：CLI 一行与回归

- [x] `main` settle 成功打印含 `post=_format_post(result["post"])`。
- [x] 运行：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_v7_write_post_hooks.py webnovel-writer/scripts/data_modules/tests/test_v7_write_gates.py webnovel-writer/scripts/data_modules/tests/test_v7_write.py -q --no-cov -p no:cacheprovider
```

- [x] 若 CLI 断言已在 Task 1 文件中，本任务只补 `_format_post` 与打印。
