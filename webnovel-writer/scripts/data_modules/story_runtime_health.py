#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .domain_contract import resolve_write_mode
from .domain_contract import resolve_write_mode
from .story_runtime_sources import load_runtime_sources


_CHAPTER_FILE_RE = re.compile(r"chapter_(\d{3,4})")


def _extract_chapter_from_name(path: Path) -> int:
    match = _CHAPTER_FILE_RE.search(path.name)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return 0


def _latest_story_system_chapter(project_root: Path) -> int:
    story_root = project_root / ".story-system"
    if not story_root.is_dir():
        return 0

    candidates = []
    for pattern in (
        "chapters/chapter_*.json",
        "reviews/chapter_*.review.json",
        "commits/chapter_*.commit.json",
    ):
        for path in story_root.glob(pattern):
            candidates.append(_extract_chapter_from_name(path))
    return max(candidates or [0])


def _latest_settled_chapter(project_root: Path) -> int:
    """v7 语境的「当前章」来源：`定稿/正文` 的落定章。

    口径与 `story_runtime_sources._v7_fallback_sources` 一致——同用
    `dual_format_guard.max_settled_chapter`，不另立一套"落定"定义。
    """
    from .dual_format_guard import max_settled_chapter

    return max_settled_chapter(project_root)


def _resolve_chapter(project_root: Path, chapter: int | None) -> int:
    if chapter is not None:
        try:
            return max(0, int(chapter))
        except (TypeError, ValueError):
            return 0

    # F6：纯 v7 仓按设计既没有 .story-system 痕迹，新仓也可能还没生成
    # .webnovel/state.json——两者都没有时，原先会解析出 0 并落进
    # chapter_unspecified 分支（实测：book.yaml + 定稿/正文 的干净新仓报 chapter=0）。
    # 这类仓的"当前章"只能从 定稿/正文 来。
    # **仅对 v7 生效**：v6 仓即便意外存在 定稿/正文，也不该被它抬高章号。
    settled_chapter = _latest_settled_chapter(project_root) if resolve_write_mode(project_root) == "v7" else 0
    base_chapter = max(_latest_story_system_chapter(project_root), settled_chapter)

    state_path = project_root / ".webnovel" / "state.json"
    if not state_path.is_file():
        return base_chapter

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return base_chapter

    try:
        state_chapter = max(0, int(((state.get("progress") or {}).get("current_chapter") or 0)))
    except (TypeError, ValueError):
        state_chapter = 0
    return max(state_chapter, base_chapter)


def build_story_runtime_health(project_root: Path, chapter: int | None = None) -> dict[str, Any]:
    project_root = Path(project_root)
    write_mode = resolve_write_mode(project_root)
    current_chapter = _resolve_chapter(project_root, chapter)
    if current_chapter <= 0:
        return {
            "chapter": 0,
            "mainline_ready": False,
            "fallback_sources": ["chapter_unspecified"],
            "latest_commit_status": "missing",
            "primary_write_source": "chapter_commit",
            "write_mode": write_mode,
        }

    snapshot = load_runtime_sources(project_root, current_chapter)
    latest_commit = snapshot.latest_commit or {}
    return {
        "chapter": current_chapter,
        "mainline_ready": not snapshot.fallback_sources,
        "fallback_sources": list(snapshot.fallback_sources),
        "latest_commit_status": (latest_commit.get("meta") or {}).get("status", "missing"),
        "primary_write_source": snapshot.primary_write_source,
        "write_mode": snapshot.write_mode,
    }
