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


def test_reading_reported_from_decision_card(tmp_path: Path):
    """Task 4：追读力写盘退役——钩子来自决策卡，落 canonical 后由缓存重建承载。

    此前该用例走的是「摘要 front matter + 写 v6 .webnovel/index.db」，那条路径在
    真实流程下恒 skipped（摘要传纯文本）且污染 v6 域，均已退役。
    """
    repo = _repo(tmp_path)
    _review(repo, 0)
    result = settle(
        repo,
        _decision(hook_type="悬念", hook_strength="strong"),
        draft_path=repo / "工作区" / "草稿-0042.md",
        summary="夜未完。",
        commit=False,
    )
    assert result["post"]["reading"]["status"] == "ok"
    assert result["post"]["reading"]["hook_type"] == "悬念"
    assert not (repo / ".webnovel" / "index.db").exists()  # 不再落 v6 域
    assert result["cache_rebuilt"] is True
    from v7_cache import get_recent_reading_power

    assert get_recent_reading_power(repo, limit=5) == [
        {"chapter": 42, "hook_type": "悬念", "hook_strength": "strong"}
    ]


def test_reading_skipped_when_waived(tmp_path: Path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    result = _settle(repo, _decision(hook_type="", hook_waiver="过渡章，本章无钩子"))
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
