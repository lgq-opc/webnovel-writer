#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .project_phase import (
    PHASE_CHAPTER_CONTRACT_READY,
    PHASE_CHAPTER_COMMITTED,
    PHASE_DRAFT_IN_PROGRESS,
    PHASE_INIT_READY,
    PHASE_INIT_SCAFFOLDED,
    PHASE_NO_PROJECT,
    PHASE_PLAN_IN_PROGRESS,
    PHASE_PROJECTION_FAILED,
    PHASE_READY_TO_COMMIT,
    ProjectPhaseSnapshot,
    resolve_project_phase,
)


SCHEMA_VERSION = "webnovel-project-status/v1"


def _project_title(project_root: Path) -> str:
    state_path = project_root / ".webnovel" / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(state, dict):
        return ""
    project_info = state.get("project_info") if isinstance(state.get("project_info"), dict) else {}
    project = state.get("project") if isinstance(state.get("project"), dict) else {}
    return str(project_info.get("title") or project.get("title") or "").strip()


def next_action_for_phase(snapshot: ProjectPhaseSnapshot) -> str:
    phase = snapshot.phase
    target = snapshot.target_chapter
    if phase == PHASE_NO_PROJECT:
        return "run /webnovel-init or webnovel.py use <project_root>"
    if phase == PHASE_INIT_SCAFFOLDED:
        return "run webnovel.py doctor --format text and fix missing init files"
    if phase == PHASE_INIT_READY:
        return "run /webnovel-plan or refresh Story System contracts"
    if phase == PHASE_PLAN_IN_PROGRESS:
        return f"finish planning and emit runtime contracts for chapter {target}"
    if phase == PHASE_CHAPTER_CONTRACT_READY:
        return f"run /webnovel-write {target}"
    if phase == PHASE_DRAFT_IN_PROGRESS:
        return f"finish review/data artifacts for chapter {target}"
    if phase == PHASE_READY_TO_COMMIT:
        # v6 写链已退役（`chapter-commit` CLI 已撤，走它会 rc=2 invalid choice）；
        # 该相位只对含 .webnovel/state.json 的 v6 书仓可达，唯一在役路径是先迁移到
        # v7 书仓，再用 v7 写链 settle 落定（见 skills/webnovel-write/SKILL.md）。
        return f"v6 write chain retired; migrate with migrate_v6_to_v7.py, then webnovel.py v7-write settle --chapter {target}"
    if phase == PHASE_CHAPTER_COMMITTED:
        return f"continue with chapter {snapshot.latest_accepted_chapter + 1}"
    if phase == PHASE_PROJECTION_FAILED:
        return "inspect projection_log / projection_status and repair failed or pending projection"
    return "run webnovel.py doctor --format text"


def _quality_trend_snapshot(root: Path | None) -> dict[str, Any]:
    """R17：短状态附带近 10 次审查趋势。无 index.db 时不可用，且不得建库。"""
    empty = {"available": False, "reason": "no_project", "window": 10, "line": ""}
    if root is None:
        return empty
    try:
        from quality_trend_report import summarize_quality_trend

        return summarize_quality_trend(root, last_n=10)
    except Exception:
        return {"available": False, "reason": "trend_unavailable", "window": 10, "line": ""}


def build_project_status(project_root: str | Path | None, chapter: int | None = None) -> dict[str, Any]:
    snapshot = resolve_project_phase(project_root, chapter=chapter)
    root = Path(snapshot.project_root) if snapshot.project_root else None
    return {
        "schema_version": SCHEMA_VERSION,
        "project_root": snapshot.project_root,
        "project": _project_title(root) if root else "",
        "latest_accepted_chapter": snapshot.latest_accepted_chapter,
        "target_chapter": snapshot.target_chapter,
        "phase": snapshot.phase,
        "blocking": list(snapshot.blocking),
        "warnings": list(snapshot.warnings),
        "next_action": next_action_for_phase(snapshot),
        "quality_trend": _quality_trend_snapshot(root),
        "evidence": snapshot.to_dict(),
    }


def format_project_status(report: dict[str, Any], output_format: str = "summary") -> str:
    if output_format == "json":
        return json.dumps(report, ensure_ascii=False, indent=2)

    project = report.get("project") or "(未命名项目)"
    root = report.get("project_root") or "(未解析)"
    lines = [
        f"project: {project}",
        f"root: {root}",
        f"phase: {report.get('phase')}",
        f"latest_accepted_chapter: {report.get('latest_accepted_chapter')}",
        f"target_chapter: {report.get('target_chapter')}",
        f"next_action: {report.get('next_action')}",
    ]
    trend = report.get("quality_trend") or {}
    if trend.get("available") and trend.get("line"):
        lines.append(f"quality_trend: {trend['line']}")
    else:
        reason = trend.get("reason") or "unknown"
        lines.append(f"quality_trend: unavailable ({reason})")
    blocking = report.get("blocking") or []
    warnings = report.get("warnings") or []
    if blocking:
        lines.append("blocking:")
        lines.extend(f"- {item}" for item in blocking)
    if warnings:
        lines.append("warnings:")
        lines.extend(f"- {item}" for item in warnings)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build short machine-readable webnovel project status")
    parser.add_argument("--project-root", default="", help="书项目根目录")
    parser.add_argument("--chapter", type=int, default=None, help="目标章节号")
    parser.add_argument("--format", choices=["summary", "json"], default="summary")
    args = parser.parse_args()

    report = build_project_status(args.project_root or None, chapter=args.chapter)
    print(format_project_status(report, args.format))
    raise SystemExit(0)


if __name__ == "__main__":
    main()
