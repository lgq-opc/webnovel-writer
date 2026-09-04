#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工坊同步执行器（v8-gap-review 阶段三 P3-2）。

扫 journal impact 中 power_anchor_sync / contract_rebuild 的 required/cleared，
FIFO 配对 pending；status 只读；mark-cleared 追加 edit 事件。
"""
from __future__ import annotations

import argparse
import json
import re
from collections import deque
from pathlib import Path
from typing import Any

from .author_journal import append_events, read_journal

SCHEMA_VERSION = "forge-sync/1"
KINDS = ("power_anchor_sync", "contract_rebuild")
_IMPACT_RE = re.compile(r"^(power_anchor_sync|contract_rebuild)\s*:\s*(required|cleared)$")
_VOLUME_PLACEHOLDER = "<已完成规划的卷号>"


def _tokens(event: dict[str, Any]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for raw in event.get("impact") or []:
        match = _IMPACT_RE.match(str(raw).strip())
        if match:
            found.append((match.group(1), match.group(2)))
    return found


def scan_pending(project_root: str | Path) -> list[dict[str, Any]]:
    queues: dict[str, deque] = {kind: deque() for kind in KINDS}
    for index, event in enumerate(read_journal(project_root), start=1):
        for kind, state in _tokens(event):
            if state == "required":
                queues[kind].append(
                    {
                        "kind": kind,
                        "index": index,
                        "path": str(event.get("path") or ""),
                        "ts": str(event.get("ts") or ""),
                        "summary": str(event.get("summary") or ""),
                    }
                )
            elif queues[kind]:
                queues[kind].popleft()
    pending: list[dict[str, Any]] = []
    for kind in KINDS:
        pending.extend(queues[kind])
    return pending


def _next_steps(project_root: Path, pending: list[dict[str, Any]]) -> list[str]:
    root = str(project_root)
    steps: list[str] = []
    kinds = {item["kind"] for item in pending}
    if "power_anchor_sync" in kinds:
        steps.append(f"手改力量锚点后：python -X utf8 webnovel.py --project-root {root} power validate")
    if "contract_rebuild" in kinds:
        steps.append(
            f"python -X utf8 webnovel.py --project-root {root} master-outline-sync --volume {_VOLUME_PLACEHOLDER}"
        )
    if pending:
        steps.append(f"python -X utf8 webnovel.py --project-root {root} forge-sync mark-cleared --kind all")
    return steps


def status_report(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root)
    pending = scan_pending(root)
    return {
        "ok": not pending,
        "schema_version": SCHEMA_VERSION,
        "pending": pending,
        "next": _next_steps(root, pending),
    }


def format_status_text(report: dict[str, Any]) -> str:
    pending = report.get("pending") or []
    lines = [f"PENDING forge-sync n={len(pending)}"]
    if not pending:
        lines.append("  (无未消费标记)")
    for item in pending:
        lines.append(f"  {item['kind']}  journal#{item['index']}  {item.get('path') or '-'}")
    nxt = report.get("next") or []
    if nxt:
        lines.append("NEXT")
        for index, step in enumerate(nxt, start=1):
            lines.append(f"  {index}. {step}")
    return "\n".join(lines)


def mark_cleared(project_root: str | Path, kind: str) -> dict[str, Any]:
    root = Path(project_root)
    kind = (kind or "").strip()
    if kind not in (*KINDS, "all"):
        return {"ok": False, "error": "invalid_kind", "kind": kind}
    pending = scan_pending(root)
    if kind == "all":
        requested = [k for k in KINDS if any(item["kind"] == k for item in pending)]
    else:
        requested = [kind] if any(item["kind"] == kind for item in pending) else []
    if not requested:
        return {"ok": False, "error": "nothing_pending"}
    heads = []
    for current in requested:
        heads.append(next(item for item in pending if item["kind"] == current))
    path = heads[0].get("path") or "作者/journal.jsonl"
    impact = [f"{current}:cleared" for current in requested]
    append_events(
        root,
        [
            {
                "actor": "author",
                "action": "edit",
                "domain": "设定",
                "path": path,
                "change_kind": "structure",
                "diff_stat": {"ins": 0, "del": 0},
                "summary": "forge-sync 消费 " + ",".join(requested),
                "impact": impact,
            }
        ],
    )
    return {"ok": True, "cleared": requested, "schema_version": SCHEMA_VERSION}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="工坊同步执行器（P3-2）：status / mark-cleared")
    parser.add_argument("action", nargs="?", default="status", choices=["status", "mark-cleared"])
    parser.add_argument("--kind", default="", help="mark-cleared：power_anchor_sync / contract_rebuild / all")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    root = Path(args.project_root)
    if args.action == "mark-cleared":
        if not str(args.kind).strip():
            report = {"ok": False, "error": "missing_kind"}
            print(json.dumps(report, ensure_ascii=False) if args.format == "json" else "ERROR missing --kind")
            return 2
        report = mark_cleared(root, args.kind)
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False))
        else:
            print(
                "OK forge-sync cleared " + ",".join(report.get("cleared") or [])
                if report.get("ok")
                else f"ERROR {report.get('error')}"
            )
        return 0 if report.get("ok") else 2
    report = status_report(root)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(format_status_text(report))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
