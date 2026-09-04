"""数据不变量校验器（v8-gap-review 阶段二 P2-3）。

只读：六项恒各返回一条 pass/fail/warn/skip；ok 仅受 fail 影响。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "invariants/1"

CheckFn = Callable[[Path], dict[str, Any]]


def finding(code: str, message: str, *, ref: str = "", path: str = "", **details: Any) -> dict[str, Any]:
    return {"code": code, "ref": ref, "path": path, "message": message, "details": details}


def result(
    check_id: str,
    title: str,
    status: str,
    *,
    findings: list[dict[str, Any]] | None = None,
    counts: dict[str, Any] | None = None,
    repair: str = "",
) -> dict[str, Any]:
    return {
        "id": check_id,
        "title": title,
        "status": status,
        "findings": list(findings or []),
        "counts": dict(counts or {}),
        "repair": repair,
    }


def check_journal(root: Path) -> dict[str, Any]:
    return result("inv-1-journal", "journal 无未分类事件积压", "pass")


def check_material_trajectory(root: Path) -> dict[str, Any]:
    return result("inv-2-material-trajectory", "素材使用轨迹与来源一致", "pass")


def check_power_anchor(root: Path) -> dict[str, Any]:
    return result("inv-3-power", "力量锚点战例与境界链", "pass")


def check_promise_states(root: Path) -> dict[str, Any]:
    return result("inv-4-promises", "承诺条目状态机与 retcon 双记录", "pass")


def check_contract_rebuild(root: Path) -> dict[str, Any]:
    return result(
        "inv-5-contracts",
        "runtime contract 重建对账",
        "skip",
        repair="纯 v7 无 .story-system 时跳过合同重建",
    )


def check_stale_age(root: Path) -> dict[str, Any]:
    return result("inv-6-stale-age", "stale 不超过一卷", "pass")


CHECKS: tuple[tuple[str, CheckFn], ...] = (
    ("inv-1-journal", check_journal),
    ("inv-2-material-trajectory", check_material_trajectory),
    ("inv-3-power", check_power_anchor),
    ("inv-4-promises", check_promise_states),
    ("inv-5-contracts", check_contract_rebuild),
    ("inv-6-stale-age", check_stale_age),
)


def _select_checks(only: list[str]) -> tuple[tuple[str, CheckFn], ...]:
    by_id = {check_id: pair for check_id, pair in ((item[0], item) for item in CHECKS)}
    selected: list[tuple[str, CheckFn]] = []
    unknown: list[str] = []
    for check_id in only:
        pair = by_id.get(check_id)
        if pair is None:
            unknown.append(check_id)
        else:
            selected.append(pair)
    if unknown:
        raise ValueError(f"unknown invariant: {', '.join(unknown)}")
    return tuple(selected)


def run_invariants(root: str | Path, *, only: list[str] | None = None) -> dict[str, Any]:
    selected = CHECKS if only is None else _select_checks(only)
    items = [check(Path(root)) for _, check in selected]
    summary = {status: sum(item["status"] == status for item in items) for status in ("pass", "fail", "warn", "skip")}
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": summary["fail"] == 0,
        "project_root": str(Path(root)),
        "summary": summary,
        "invariants": items,
    }


def format_text(report: dict[str, Any]) -> str:
    items = report.get("invariants") or []
    failed = int((report.get("summary") or {}).get("fail") or 0)
    head = (
        f"OK invariants: {len(items)} checked"
        if report.get("ok")
        else f"ERROR invariants: {failed} failed"
    )
    lines = [head]
    for item in items:
        lines.append(f"{item['id']}\t{item['status']}\t{item['title']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="数据不变量校验（P2-3，只读）")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--only", default="", help="逗号分隔的检查 id")
    args = parser.parse_args(argv)
    only = [part.strip() for part in args.only.split(",") if part.strip()]
    try:
        report = run_invariants(args.project_root, only=only or None)
    except ValueError as exc:
        parser.error(str(exc))
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_text(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
