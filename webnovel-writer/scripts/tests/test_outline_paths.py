#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段二 P2-1：详细大纲规范路径与章节标题/节选解析。"""
from __future__ import annotations

from pathlib import Path

from data_modules.outline_paths import (
    canonical_detailed_outline_path,
    extract_chapter_heading,
    extract_chapter_section,
    resolve_detailed_outline,
)


def test_canonical_path_is_zero_padded(tmp_path: Path):
    assert canonical_detailed_outline_path(tmp_path, 2) == tmp_path / "大纲" / "卷纲" / "第02卷-详细大纲.md"


def test_resolver_prefers_canonical_then_legacy_nested_then_v6_flat(tmp_path: Path):
    canonical = tmp_path / "大纲" / "卷纲" / "第01卷-详细大纲.md"
    nested = tmp_path / "大纲" / "卷纲" / "第01卷.md"
    flat = tmp_path / "大纲" / "第1卷-详细大纲.md"
    for path in (flat, nested, canonical):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.name, encoding="utf-8")
    assert resolve_detailed_outline(tmp_path, 1) == canonical
    canonical.unlink()
    assert resolve_detailed_outline(tmp_path, 1) == nested
    nested.unlink()
    assert resolve_detailed_outline(tmp_path, 1) == flat


def test_heading_compatibility_matrix():
    cases = [
        ("## 第43章：夜袭", 43, "夜袭"),
        ("### 第43章: 夜袭", 43, "夜袭"),
        ("## 第43章 夜袭", 43, "夜袭"),
        ("### 第四十三章：夜袭", 43, "夜袭"),
        ("## 第九十九章：收束", 99, "收束"),
        ("## 第一章：开端", 1, "开端"),
    ]
    for text, chapter, expected in cases:
        assert extract_chapter_heading(text, chapter) == expected, text


def test_extract_section_stops_at_same_or_higher_heading():
    text = "# 卷二\n\n## 第42章：前夜\n旧\n\n## 第43章：夜袭\n目标段\n\n### 场景\n细节\n\n## 第44章：余波\n不应包含"
    section = extract_chapter_section(text, 43)
    assert section is not None
    assert "目标段" in section and "### 场景" in section
    assert "第44章" not in section


def test_missing_volume_returns_none(tmp_path: Path):
    assert resolve_detailed_outline(tmp_path, 1) is None
    assert extract_chapter_heading("## 第1章：别的", 43) is None
    assert extract_chapter_section("## 第1章：别的\n正文", 43) is None
