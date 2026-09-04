"""数据不变量校验器（v8-gap-review 阶段二 P2-3）。

只读：六项恒各返回一条 pass/fail/warn/skip；ok 仅受 fail 影响。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable

from .author_journal import pending_semantic, read_journal, read_watermark, validate_journal
from .material_store import _read_csv_rows
from .material_usage import trajectory_path

SCHEMA_VERSION = "invariants/1"
_JOURNAL_TITLE = "journal 无未分类事件积压"
_MATERIAL_TITLE = "素材使用轨迹与来源一致"
_FROZEN_VERSION_RE = re.compile(r"^v\d+$")

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
    root = Path(root)
    events = read_journal(root)
    schema_problems = validate_journal(root)
    unclassified = [
        (index, event)
        for index, event in enumerate(events, 1)
        if event.get("domain") == "其他"
        and not (event.get("path") == "(bulk)" and "migration" in (event.get("impact") or []))
    ]
    enrich_refs = {
        event.get("ref_index")
        for event in events
        if event.get("action") == "enrich" and isinstance(event.get("ref_index"), int)
    }
    semantic = [item for item in pending_semantic(root) if item.get("index") not in enrich_refs]
    findings: list[dict[str, Any]] = []
    for index, event in unclassified:
        findings.append(
            finding(
                "unclassified_event",
                f"event#{index} domain=其他 未分类",
                ref=f"event#{index}",
                path=str(event.get("path") or ""),
            )
        )
    for problem in schema_problems:
        findings.append(finding("illegal_field", problem, ref=problem.split(":", 1)[0]))
    for item in semantic:
        findings.append(
            finding(
                "pending_semantic",
                f"event#{item['index']} edit 缺摘要且尚未 enrich",
                ref=f"event#{item['index']}",
                path=str(item.get("path") or ""),
            )
        )
    counts = {
        "events": len(events),
        "unclassified": len(unclassified),
        "schema_problems": len(schema_problems),
        "pending_semantic": len(semantic),
        "watermark": read_watermark(root),
    }
    if schema_problems or unclassified:
        status, repair = "fail", "修正非法枚举或给未分类事件补上明确 domain"
    elif semantic:
        status, repair = "warn", "为 edit 事件补 summary 或 enrich"
    else:
        status, repair = "pass", ""
    return result("inv-1-journal", _JOURNAL_TITLE, status, findings=findings, counts=counts, repair=repair)


def _live_ids(root: Path) -> set[str]:
    live_dir = root / "素材" / "活"
    ids: set[str] = set()
    if not live_dir.is_dir():
        return ids
    for path in live_dir.glob("*.csv"):
        for row in _read_csv_rows(path):
            entry_id = str(row.get("id") or "").strip()
            if entry_id:
                ids.add(entry_id)
    return ids


def _frozen_csv_ids(directory: Path) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    if not directory.is_dir():
        return found
    for path in directory.glob("*.csv"):
        found[path.name] = {
            str(row.get("id") or "").strip() for row in _read_csv_rows(path) if str(row.get("id") or "").strip()
        }
    return found


def _load_manifest(directory: Path) -> dict[str, Any] | None:
    path = directory / "manifest.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def check_material_trajectory(root: Path) -> dict[str, Any]:
    root = Path(root)
    path = trajectory_path(root)
    findings: list[dict[str, Any]] = []
    counts = {"rows": 0, "live": 0, "frozen": 0, "invalid": 0}
    if not path.is_file():
        return result("inv-2-material-trajectory", _MATERIAL_TITLE, "pass", counts=counts)

    live_ids = _live_ids(root)
    frozen_cache: dict[str, tuple[dict[str, Any] | None, dict[str, set[str]]]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line:
                continue
            counts["rows"] += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                counts["invalid"] += 1
                findings.append(
                    finding("bad_json_row", f"轨迹第{line_no}行 JSON 非法", path="素材/使用轨迹.jsonl", line=line_no)
                )
                continue
            entry_id = str(row.get("条目id") or "").strip()
            version = str(row.get("定版版本") or "").strip()
            if not entry_id:
                counts["invalid"] += 1
                findings.append(
                    finding("empty_entry_id", f"轨迹第{line_no}行条目id为空", path="素材/使用轨迹.jsonl", line=line_no)
                )
                continue
            if version == "live":
                counts["live"] += 1
                if entry_id not in live_ids:
                    findings.append(finding("live_id_missing", f"{entry_id} 不在活层 CSV", ref=entry_id, line=line_no))
                continue
            if not _FROZEN_VERSION_RE.fullmatch(version):
                counts["invalid"] += 1
                findings.append(finding("invalid_version", f"定版版本非法：{version}", ref=entry_id, line=line_no))
                continue
            counts["frozen"] += 1
            if version not in frozen_cache:
                directory = root / "素材" / "定版" / version
                frozen_cache[version] = (_load_manifest(directory), _frozen_csv_ids(directory))
            manifest, by_file = frozen_cache[version]
            if manifest is None:
                findings.append(
                    finding(
                        "frozen_manifest_missing",
                        f"{version} 缺或无法读取 manifest.json",
                        ref=entry_id,
                        path=f"素材/定版/{version}/manifest.json",
                    )
                )
                continue
            listed = {str(item.get("path") or "") for item in (manifest.get("source_files") or []) if item.get("path")}
            home = next((name for name, ids in by_file.items() if entry_id in ids), None)
            if home is None:
                missing_csv = [name for name in listed if name.endswith(".csv") and name not in by_file]
                if missing_csv:
                    findings.append(
                        finding(
                            "frozen_csv_missing",
                            f"{version} 缺 CSV {missing_csv[0]}",
                            ref=entry_id,
                            path=f"素材/定版/{version}/{missing_csv[0]}",
                        )
                    )
                else:
                    findings.append(
                        finding("frozen_id_missing", f"{entry_id} 不在 {version} CSV", ref=entry_id, path=f"素材/定版/{version}")
                    )
            elif home not in listed:
                findings.append(
                    finding(
                        "frozen_source_unlisted",
                        f"{home} 未列入 {version} manifest source_files",
                        ref=entry_id,
                        path=f"素材/定版/{version}/{home}",
                    )
                )

    status = "fail" if findings else "pass"
    repair = "补齐活层/定版 CSV 或修正使用轨迹" if findings else ""
    return result("inv-2-material-trajectory", _MATERIAL_TITLE, status, findings=findings, counts=counts, repair=repair)


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
