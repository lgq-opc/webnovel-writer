"""数据不变量校验器（v8-gap-review 阶段二 P2-3）。

只读：六项恒各返回一条 pass/fail/warn/skip；ok 仅受 fail 影响。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable

from chapter_outline_loader import volume_num_for_chapter_from_state

from .author_journal import pending_semantic, read_journal, read_stale, read_watermark, validate_journal
from .dual_format_guard import has_v7_settled_chapter, max_settled_chapter
from .material_store import _read_csv_rows
from .material_usage import trajectory_path
from .power_anchor import anchor_path, load_anchor, validate_chain
from .promise_ledger import STATUS_VALUES, load_entries
from .runtime_contract_builder import RuntimeContractBuilder
from .story_contract_schema import ChapterBrief, MasterSetting
from .story_contracts import StoryContractPaths, read_json_if_exists

SCHEMA_VERSION = "invariants/1"
_JOURNAL_TITLE = "journal 无未分类事件积压"
_MATERIAL_TITLE = "素材使用轨迹与来源一致"
_POWER_TITLE = "力量锚点战例与境界链"
_PROMISE_TITLE = "承诺条目状态机与 retcon 双记录"
_CONTRACT_TITLE = "runtime contract 重建对账"
_REVIEW_NAME_RE = re.compile(r"^chapter_(\d+)\.review\.json$")
_CONTRACT_WARN_CODES = frozenset({"no_review_sample"})
_FROZEN_VERSION_RE = re.compile(r"^v\d+$")
_RETCON_VOL_RE = re.compile(r"v(\d+)")
_EVO_RETCON_RE = re.compile(r"^retcon-v(\d+)-")
_DEFAULT_VOLUME_SIZE = 50

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
    root = Path(root)
    path = anchor_path(root)
    if not path.is_file():
        return result("inv-3-power", _POWER_TITLE, "skip", repair="先运行 power extract --apply")
    findings: list[dict[str, Any]] = []
    for problem in validate_chain(root):
        findings.append(finding("chain_invalid", problem, path="设定/力量锚点.yaml"))
    battles = load_anchor(root).get("战例账本") or []
    for battle in battles:
        raw = battle.get("章")
        try:
            chapter = int(raw)
        except (TypeError, ValueError):
            findings.append(finding("invalid_battle_chapter", f"战例章号非整数：{raw}", ref=str(raw)))
            continue
        if not has_v7_settled_chapter(root, chapter):
            findings.append(
                finding(
                    "missing_settled_chapter",
                    f"战例章 {chapter} 无定稿正文",
                    ref=str(chapter),
                    path=f"定稿/正文/{chapter:04d}-*.md",
                )
            )
    status = "fail" if findings else "pass"
    repair = "补定稿正文或修正境界链/战例章号" if findings else ""
    return result(
        "inv-3-power",
        _POWER_TITLE,
        status,
        findings=findings,
        counts={"battles": len(battles), "chain_problems": sum(1 for item in findings if item["code"] == "chain_invalid")},
        repair=repair,
    )


def volume_size(root: Path) -> int:
    path = Path(root) / "book.yaml"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("卷规模:"):
                try:
                    value = int(line.split(":", 1)[1].strip())
                except ValueError:
                    break
                if value > 0:
                    return value
    return _DEFAULT_VOLUME_SIZE


def volume_of_chapter(chapter: int, size: int) -> int:
    return (int(chapter) - 1) // int(size) + 1


def _journal_retcon_volumes(root: Path) -> set[int]:
    volumes: set[int] = set()
    for event in read_journal(root):
        if event.get("action") != "retcon":
            continue
        match = _RETCON_VOL_RE.search(str(event.get("path") or ""))
        if match:
            volumes.add(int(match.group(1)))
    return volumes


def _evolution_retcon_volumes(root: Path) -> set[int]:
    volumes: set[int] = set()
    directory = Path(root) / "演化"
    if not directory.is_dir():
        return volumes
    for path in directory.glob("retcon-v*.json"):
        match = _EVO_RETCON_RE.match(path.name)
        if match:
            volumes.add(int(match.group(1)))
    return volumes


def check_promise_states(root: Path) -> dict[str, Any]:
    root = Path(root)
    entries = load_entries(root)
    findings: list[dict[str, Any]] = []
    size = volume_size(root)
    journal_vols = _journal_retcon_volumes(root)
    evo_vols = _evolution_retcon_volumes(root)
    for entry in entries:
        entry_id = str(entry.get("编号") or "")
        status = str(entry.get("状态") or "")
        planted = int(entry.get("埋设章") or 0)
        recovered = int(entry.get("回收章") or 0)
        path = str(entry.get("path") or "")
        if status not in STATUS_VALUES:
            findings.append(finding("invalid_status", f"{entry_id} 状态非法：{status}", ref=entry_id, path=path))
            continue
        if status == "已回收":
            if recovered <= 0:
                findings.append(finding("recovered_without_chapter", f"{entry_id} 已回收但缺回收章", ref=entry_id, path=path))
            elif recovered < planted:
                findings.append(
                    finding(
                        "recovered_before_planted",
                        f"{entry_id} 回收章 {recovered} 早于埋设章 {planted}",
                        ref=entry_id,
                        path=path,
                    )
                )
            continue
        if status in ("open", "推进中", "逾期") and recovered:
            findings.append(
                finding("open_with_recovered_chapter", f"{entry_id} {status} 不应带回收章 {recovered}", ref=entry_id, path=path)
            )
            continue
        if status == "作废":
            volume = volume_of_chapter(planted or 1, size)
            if volume not in journal_vols:
                findings.append(
                    finding(
                        "voided_missing_journal_retcon",
                        f"{entry_id} 作废缺卷{volume} journal retcon",
                        ref=entry_id,
                        path=path,
                    )
                )
            if volume not in evo_vols:
                findings.append(
                    finding(
                        "voided_missing_evolution_retcon",
                        f"{entry_id} 作废缺卷{volume} 演化 retcon",
                        ref=entry_id,
                        path=path,
                    )
                )
    result_status = "fail" if findings else "pass"
    repair = "补回收章约束或同卷 journal+演化 retcon 双记录" if findings else ""
    return result(
        "inv-4-promises",
        _PROMISE_TITLE,
        result_status,
        findings=findings,
        counts={"entries": len(entries)},
        repair=repair,
    )

def _rel_to_root(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _normalized_json(payload: Any) -> Any:
    return json.loads(json.dumps(payload, ensure_ascii=False))


def check_contract_rebuild(root: Path) -> dict[str, Any]:
    root = Path(root)
    try:
        return _check_contract_rebuild_inner(root)
    except Exception as exc:
        return result(
            "inv-5-contracts",
            _CONTRACT_TITLE,
            "fail",
            findings=[finding("contract_check_error", str(exc))],
            repair="修正 .story-system JSON/schema 后重跑 invariants",
        )


def _check_contract_rebuild_inner(root: Path) -> dict[str, Any]:
    paths = StoryContractPaths.from_project_root(root)
    if not paths.root.is_dir():
        return result(
            "inv-5-contracts",
            _CONTRACT_TITLE,
            "skip",
            repair="纯 v7 无 .story-system 时跳过合同重建",
        )

    findings: list[dict[str, Any]] = []
    seed_checked = 0
    master_rel = ".story-system/MASTER_SETTING.json"
    try:
        master_raw = read_json_if_exists(paths.master_json)
    except Exception as exc:
        findings.append(finding("bad_master_setting", str(exc), path=master_rel))
        master_raw = None
    if master_raw is None and not any(item["code"] == "bad_master_setting" for item in findings):
        findings.append(finding("missing_master_setting", "缺 MASTER_SETTING.json", path=master_rel))
    elif master_raw is not None:
        try:
            MasterSetting.model_validate(master_raw)
            seed_checked += 1
        except Exception as exc:
            findings.append(finding("bad_master_setting", str(exc), path=master_rel))

    if paths.anti_patterns_json.is_file():
        anti_rel = ".story-system/anti_patterns.json"
        try:
            anti_raw = read_json_if_exists(paths.anti_patterns_json)
            if not isinstance(anti_raw, list):
                findings.append(finding("bad_anti_patterns", "anti_patterns 必须是 JSON 数组", path=anti_rel))
            else:
                seed_checked += 1
        except Exception as exc:
            findings.append(finding("bad_anti_patterns", str(exc), path=anti_rel))

    if paths.chapters_dir.is_dir():
        for chapter_path in sorted(paths.chapters_dir.glob("chapter_*.json")):
            rel = _rel_to_root(root, chapter_path)
            try:
                brief_raw = read_json_if_exists(chapter_path)
                if brief_raw is None:
                    continue
                ChapterBrief.model_validate(brief_raw)
                seed_checked += 1
            except Exception as exc:
                findings.append(finding("bad_chapter_brief", str(exc), path=rel))

    reviews: list[tuple[int, Path]] = []
    if paths.reviews_dir.is_dir():
        for review_path in sorted(paths.reviews_dir.glob("chapter_*.review.json")):
            match = _REVIEW_NAME_RE.match(review_path.name)
            if match:
                reviews.append((int(match.group(1)), review_path))

    if not reviews:
        findings.append(
            finding(
                "no_review_sample",
                "有 .story-system 但无可重建 review 样本",
                path=".story-system/reviews",
            )
        )

    volume_last: dict[int, tuple[int, Any]] = {}
    for chapter, review_path in reviews:
        rel = _rel_to_root(root, review_path)
        try:
            rebuilt_volume, rebuilt_review = RuntimeContractBuilder(root).build_for_chapter(chapter)
        except Exception as exc:
            findings.append(
                finding("rebuild_failed", str(exc), ref=str(chapter), path=rel, chapter=chapter)
            )
            continue
        try:
            disk_review = read_json_if_exists(review_path)
        except Exception as exc:
            findings.append(
                finding("bad_review_json", str(exc), ref=str(chapter), path=rel, chapter=chapter)
            )
            continue
        if _normalized_json(disk_review) != _normalized_json(rebuilt_review):
            findings.append(
                finding(
                    "review_mismatch",
                    f"章{chapter} review 与重建不一致",
                    ref=str(chapter),
                    path=rel,
                    chapter=chapter,
                )
            )
        volume = volume_num_for_chapter_from_state(root, chapter) or 1
        volume_last[volume] = (chapter, rebuilt_volume)

    for volume, (chapter, rebuilt_volume) in volume_last.items():
        vol_path = paths.volume_json(volume)
        rel = _rel_to_root(root, vol_path)
        try:
            disk_volume = read_json_if_exists(vol_path)
        except Exception as exc:
            findings.append(
                finding(
                    "bad_volume_json",
                    str(exc),
                    ref=str(volume),
                    path=rel,
                    chapter=chapter,
                    volume=volume,
                )
            )
            continue
        if disk_volume is None:
            findings.append(
                finding(
                    "missing_volume",
                    f"缺 volume_{volume:03d}.json",
                    ref=str(volume),
                    path=rel,
                    chapter=chapter,
                    volume=volume,
                )
            )
        elif _normalized_json(disk_volume) != _normalized_json(rebuilt_volume):
            findings.append(
                finding(
                    "volume_mismatch",
                    f"卷{volume} volume 与章{chapter}重建不一致",
                    ref=str(volume),
                    path=rel,
                    chapter=chapter,
                    volume=volume,
                )
            )

    has_fail = any(item["code"] not in _CONTRACT_WARN_CODES for item in findings)
    has_warn = any(item["code"] in _CONTRACT_WARN_CODES for item in findings)
    status = "fail" if has_fail else ("warn" if has_warn else "pass")
    if status == "fail":
        repair = "重新生成 runtime contracts 或修正 MASTER_SETTING/磁盘合同"
    elif status == "warn":
        repair = "生成至少一份 review runtime contract 后再对账"
    else:
        repair = ""
    return result(
        "inv-5-contracts",
        _CONTRACT_TITLE,
        status,
        findings=findings,
        counts={
            "reviews": len(reviews),
            "volumes": len(volume_last),
            "seed_schema_checked": seed_checked,
        },
        repair=repair,
    )


def check_stale_age(root: Path) -> dict[str, Any]:
    root = Path(root)
    items = [item for item in read_stale(root) if not item.get("consumed")]
    findings: list[dict[str, Any]] = []
    current = max_settled_chapter(root)
    size = volume_size(root)
    for item in items:
        target = str(item.get("target") or "")
        if "since_chapter" not in item:
            findings.append(finding("unknown_stale_age", f"{target} 缺 since_chapter，无法换算卷龄", ref=target))
            continue
        try:
            since_chapter = int(item.get("since_chapter"))
        except (TypeError, ValueError):
            findings.append(finding("unknown_stale_age", f"{target} since_chapter 无法解析", ref=target))
            continue
        age = current - since_chapter
        if age > size:
            findings.append(
                finding(
                    "stale_over_one_volume",
                    f"{target} 未消费已超一卷（当前章 {current} - 起始章 {since_chapter} = {age} > 卷规模 {size}）",
                    ref=target,
                    current_chapter=current,
                    since_chapter=since_chapter,
                    volume_size=size,
                )
            )
    fail = any(item["code"] == "stale_over_one_volume" for item in findings)
    warn = any(item["code"] == "unknown_stale_age" for item in findings)
    status = "fail" if fail else ("warn" if warn else "pass")
    repair = "消费或推进超龄 stale；旧项补 since_chapter 后重标" if findings else ""
    return result(
        "inv-6-stale-age",
        "stale 不超过一卷",
        status,
        findings=findings,
        counts={"unconsumed": len(items), "current_chapter": current, "volume_size": size},
        repair=repair,
    )

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
