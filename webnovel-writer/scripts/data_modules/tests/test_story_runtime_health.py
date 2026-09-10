#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from data_modules.story_runtime_health import build_story_runtime_health


def _make_v7_repo(root, *, settled: str | None = "0040-收势.md"):
    """纯 v7 书仓：book.yaml + 定稿/正文（无 .story-system 合同链、无 .webnovel/state.json）。"""
    (root / "book.yaml").write_text('spec_version: "7.0"\n书名: 测试\n', encoding="utf-8")
    (root / "定稿" / "正文").mkdir(parents=True, exist_ok=True)
    if settled:
        (root / "定稿" / "正文" / settled).write_text("正文\n", encoding="utf-8")


def _make_v6_repo(root, chapter: int = 3):
    """v6 形态：.webnovel/state.json 生命周期锚 + 仅有 commit（合同链缺失）。"""
    webnovel_dir = root / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)
    (webnovel_dir / "state.json").write_text(
        json.dumps({"progress": {"current_chapter": chapter}}, ensure_ascii=False),
        encoding="utf-8",
    )
    commits_dir = root / ".story-system" / "commits"
    commits_dir.mkdir(parents=True, exist_ok=True)
    (commits_dir / f"chapter_{chapter:03d}.commit.json").write_text(
        json.dumps({"meta": {"chapter": chapter, "status": "accepted"}}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_story_runtime_health_reports_missing_commit_as_not_ready(tmp_path):
    report = build_story_runtime_health(tmp_path, chapter=3)

    assert report["mainline_ready"] is False
    assert "missing_accepted_commit" in report["fallback_sources"]


def test_story_runtime_health_prefers_latest_story_system_chapter_over_state_projection(tmp_path):
    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir(parents=True, exist_ok=True)
    (webnovel_dir / "state.json").write_text(
        json.dumps({"progress": {"current_chapter": 2}}, ensure_ascii=False),
        encoding="utf-8",
    )

    story_root = tmp_path / ".story-system"
    (story_root / "chapters").mkdir(parents=True, exist_ok=True)
    (story_root / "reviews").mkdir(parents=True, exist_ok=True)
    (story_root / "commits").mkdir(parents=True, exist_ok=True)
    (story_root / "MASTER_SETTING.json").write_text(
        json.dumps({"meta": {"contract_type": "MASTER_SETTING"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (story_root / "chapters" / "chapter_003.json").write_text(
        json.dumps({"meta": {"contract_type": "CHAPTER_BRIEF", "chapter": 3}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (story_root / "reviews" / "chapter_003.review.json").write_text(
        json.dumps({"meta": {"contract_type": "REVIEW_CONTRACT", "chapter": 3}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (story_root / "commits" / "chapter_002.commit.json").write_text(
        json.dumps({"meta": {"chapter": 2, "status": "accepted"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (story_root / "commits" / "chapter_003.commit.json").write_text(
        json.dumps({"meta": {"chapter": 3, "status": "rejected"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    report = build_story_runtime_health(tmp_path)

    assert report["chapter"] == 3
    assert report["latest_commit_status"] == "rejected"
    assert report["write_mode"] == "v6"


def test_pure_v7_repo_does_not_treat_missing_v6_contracts_as_fallback(tmp_path):
    """F1：纯 v7 书仓缺 .story-system 四合同，不是它的运行时缺陷。"""
    _make_v7_repo(tmp_path)

    report = build_story_runtime_health(tmp_path, chapter=41)

    assert report["write_mode"] == "v7"
    assert report["fallback_sources"] == []
    assert report["mainline_ready"] is True


def test_pure_v7_repo_without_settled_chapter_uses_v7_fallback(tmp_path):
    """v7 语境下的 fallback 应指向 v7 落定（定稿/正文），而非 v6 合同/commit。"""
    _make_v7_repo(tmp_path, settled=None)

    report = build_story_runtime_health(tmp_path, chapter=1)

    assert report["write_mode"] == "v7"
    assert report["fallback_sources"] == ["missing_settled_chapter"]
    assert report["mainline_ready"] is False


def test_v7_repo_with_residual_story_system_commits_stays_v7(tmp_path):
    """迁移残留：.story-system 只剩 commits（无合同链）时仍按 v7 判，不算合同缺失。"""
    _make_v7_repo(tmp_path, settled="0040-收势.md")
    commits_dir = tmp_path / ".story-system" / "commits"
    commits_dir.mkdir(parents=True, exist_ok=True)
    (commits_dir / "chapter_040.commit.json").write_text(
        json.dumps({"meta": {"chapter": 40, "status": "accepted"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    report = build_story_runtime_health(tmp_path)

    assert report["chapter"] == 40
    assert report["write_mode"] == "v7"
    assert report["fallback_sources"] == []
    assert report["mainline_ready"] is True


def test_v6_repo_keeps_contract_fallbacks(tmp_path):
    """闸门不削弱：v6 形态（state.json 生命周期锚）缺合同照旧报 fallback。"""
    _make_v6_repo(tmp_path, chapter=3)

    report = build_story_runtime_health(tmp_path, chapter=3)

    assert report["write_mode"] == "v6"
    assert report["mainline_ready"] is False
    assert "missing_master_contract" in report["fallback_sources"]
    assert "missing_accepted_commit" not in report["fallback_sources"]
