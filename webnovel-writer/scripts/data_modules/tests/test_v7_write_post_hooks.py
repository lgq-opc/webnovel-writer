#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""settle 后置钩子（v8-gap-review 阶段三 P3-1）。

spec：docs/cursor/阶段三-settle后置钩子/2026-09-04-settle-post-hooks-spec.md
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from data_modules.tests.test_v7_write_gates import (
    _decision,
    _repo,
    _review,
    _settle,
)
from v7_write import GateRejected, settle


def _ls_files(repo: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotepath=false", "ls-files"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]


def _seed_bridge(repo: Path, entry_id: str) -> None:
    from data_modules.material_store import append_entries

    append_entries(
        repo,
        "桥段",
        [{"id": entry_id, "名称": "夜袭", "分类": "冲突", "核心摘要": "夜里偷袭", "状态": "active"}],
    )


def test_materials_logged_and_committed(tmp_path: Path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    _seed_bridge(repo, "Q-001")
    (repo / "大纲" / "章纲" / "0042.md").write_text(
        '---\n章号: 42\n素材引用: ["桥段:Q-001"]\n---\n',
        encoding="utf-8",
    )
    result = _settle(repo, _decision(), commit=True)
    assert result["post"]["materials"]["status"] == "ok"
    from data_modules.material_usage import read_trajectory

    rows = read_trajectory(repo, chapter=42)
    assert rows and rows[0]["条目id"] == "Q-001"
    tracked = _ls_files(repo)
    assert any(path.endswith("使用轨迹.jsonl") for path in tracked)


def test_fingerprint_written_and_committed(tmp_path: Path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    result = _settle(repo, _decision(), commit=True)
    assert result["post"]["style"]["status"] == "ok"
    assert result["post"]["style"]["recorded"] == 0
    assert (repo / "文风" / "指纹.yaml").is_file()
    assert any(path.endswith("指纹.yaml") for path in _ls_files(repo))


def test_reading_power_from_summary_front_matter(tmp_path: Path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    summary = "---\nhook_type: 悬念\nhook_strength: strong\n---\n夜未完。"
    result = settle(
        repo,
        _decision(),
        draft_path=repo / "工作区" / "草稿-0042.md",
        summary=summary,
        commit=False,
    )
    assert result["post"]["reading"]["status"] == "ok"
    from data_modules.config import DataModulesConfig
    from data_modules.index_manager import IndexManager

    row = IndexManager(DataModulesConfig.from_project_root(repo)).get_chapter_reading_power(42)
    assert row and row["hook_type"] == "悬念"


def test_reading_skipped_without_hook(tmp_path: Path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    result = _settle(repo, _decision())
    assert result["post"]["reading"]["status"] == "skipped"


def test_hook_error_does_not_block_settle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _repo(tmp_path)
    _review(repo, 0)
    import data_modules.material_usage as mu

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(mu, "log_chapter_materials", _boom)
    result = _settle(repo, _decision(), commit=True)
    assert list((repo / "定稿" / "正文").glob("0042-*"))
    assert result["post"]["materials"]["status"] == "error"


def test_gate_reject_skips_post_hooks(tmp_path: Path):
    repo = _repo(tmp_path)
    _review(repo, 1)
    with pytest.raises(GateRejected):
        _settle(repo, _decision(), commit=True)
    assert not (repo / "文风" / "指纹.yaml").exists()
