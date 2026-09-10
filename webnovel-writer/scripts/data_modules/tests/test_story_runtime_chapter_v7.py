"""F6 回归：纯 v7 书仓的"当前章"要从 `定稿/正文` 解析出来。

`story_runtime_health._resolve_chapter` 原先只看两处：`.story-system` 痕迹与
`.webnovel/state.json`。**纯 v7 仓按设计两者都没有**（v7 没有 v6 合同，新仓也可能
还没生成 state.json），于是解析出 `chapter = 0`，`build_story_runtime_health`
落进 `chapter_unspecified` 早返回分支。

实测（验证 F1 时构造）：一本 `book.yaml` + `定稿/正文/0001-起始.md` 的新 v7 仓，
doctor 报 `"chapter": 0, "fallback_sources": ["chapter_unspecified"]`。
`fantasy01-v2` 因留有迁移残留的 `.story-system/commits/` 而侥幸正常——缺陷只对
「干净的」新 v7 仓暴露。

修法：把 `定稿/正文` 的落定章并入候选，口径与 `story_runtime_sources._v7_fallback_sources`
一致（同用 `dual_format_guard.max_settled_chapter`，不另立一套定义）。
"""

from __future__ import annotations

import pytest

from data_modules.story_runtime_health import build_story_runtime_health


def _v7_book(root, chapters: list[int]):
    """最小纯 v7 仓：book.yaml + 定稿/正文（无 .story-system、无 state.json）。"""
    (root / "book.yaml").write_text('spec_version: "7.0"\n书名: 测试书\n', encoding="utf-8")
    final_dir = root / "定稿" / "正文"
    final_dir.mkdir(parents=True, exist_ok=True)
    for ch in chapters:
        (final_dir / f"{ch:04d}-标题.md").write_text("正文", encoding="utf-8")
    return root


def _v6_book(root, chapter: int = 3):
    """最小 v6 仓：state.json 记录当前章，无 book.yaml、无 定稿/正文。"""
    state = root / ".webnovel" / "state.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        '{"progress": {"current_chapter": %d}}' % chapter, encoding="utf-8"
    )
    return root


def test_pure_v7_repo_resolves_chapter_from_settled_finalized(tmp_path):
    """纯 v7 仓的当前章 = 定稿/正文里的最大章号。"""
    _v7_book(tmp_path, [1, 2, 3, 7])

    report = build_story_runtime_health(tmp_path)

    assert report["chapter"] == 7, f"实际 {report}"
    assert "chapter_unspecified" not in report["fallback_sources"]


def test_pure_v7_repo_without_finalized_still_reports_unspecified(tmp_path):
    """一本还没落定任何章的 v7 仓，仍应如实报"章号未定"（别把未知说成 0 号章）。"""
    _v7_book(tmp_path, [])

    report = build_story_runtime_health(tmp_path)

    assert report["chapter"] == 0
    assert "chapter_unspecified" in report["fallback_sources"]


def test_explicit_chapter_argument_still_wins(tmp_path):
    """显式传入章号时不受影响——调用方说了算。"""
    _v7_book(tmp_path, [1, 2, 3])

    report = build_story_runtime_health(tmp_path, chapter=9)

    assert report["chapter"] == 9


def test_v6_repo_chapter_resolution_unchanged(tmp_path):
    """守住反向：v6 仓仍按 state.json 解析，定稿目录不参与。"""
    _v6_book(tmp_path, chapter=3)

    report = build_story_runtime_health(tmp_path)

    assert report["chapter"] == 3


def test_v6_repo_is_not_inflated_by_stray_finalized_dir(tmp_path):
    """v6 仓即便意外存在 定稿/正文，也不该被它抬高章号（形态闸保持有效）。"""
    _v6_book(tmp_path, chapter=3)
    final_dir = tmp_path / "定稿" / "正文"
    final_dir.mkdir(parents=True)
    (final_dir / "0099-杂项.md").write_text("正文", encoding="utf-8")

    report = build_story_runtime_health(tmp_path)

    assert report["chapter"] == 3, f"被 定稿/正文 抬高了章号：{report}"
