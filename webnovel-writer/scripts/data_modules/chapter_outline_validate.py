"""章纲批一致性闸（v8-gap-review 阶段二 P2-1 / P2-2）。

error：承诺 ID 不存在、可解析的跨批时间倒流。
warning：标题不一致/缺大纲、时间不可解析、战力境界、人物未入册。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .continuity_shared import load_known_names, parse_anchor_day
from .outline_paths import extract_chapter_heading, resolve_detailed_outline
from .power_anchor import anchor_path, load_anchor
from .promise_ledger import load_entries


def finding(code: str, chapter: int, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "chapter": int(chapter), "message": message, "details": details}


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _promise_id(raw: str) -> str:
    text = str(raw).strip()
    head = text.split(":", 1)[0].strip()
    return head


def _chapter_int(card: dict[str, Any]) -> int:
    return int(card["章节号"])


def _check_titles(root: Path, cards: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    outlines: dict[int, str | None] = {}
    for card in cards:
        volume = int(card.get("卷") or 0) or 1
        if volume not in outlines:
            path = resolve_detailed_outline(root, volume)
            outlines[volume] = path.read_text(encoding="utf-8") if path and path.is_file() else None
        chapter = _chapter_int(card)
        text = outlines[volume]
        if text is None:
            warnings.append(finding("outline_missing", chapter, f"章{chapter} 缺详细大纲（卷{volume}）"))
            continue
        expected = extract_chapter_heading(text, chapter)
        actual = str(card.get("标题") or "").strip()
        if expected is None:
            warnings.append(finding("outline_heading_missing", chapter, f"章{chapter} 详细大纲中找不到本章标题"))
        elif expected != actual:
            warnings.append(
                finding(
                    "outline_title_mismatch",
                    chapter,
                    f"章{chapter} 标题与详细大纲不一致（期望 {expected}，实际 {actual}）",
                    expected=expected,
                    actual=actual,
                )
            )


def _check_promises(root: Path, cards: list[dict[str, Any]], errors: list[dict[str, Any]]) -> None:
    known = {str(entry.get("编号") or "") for entry in load_entries(root)}
    for card in cards:
        chapter = _chapter_int(card)
        for raw in _as_list(card.get("承诺推进")):
            entry_id = _promise_id(raw)
            if not entry_id:
                continue
            if entry_id not in known:
                errors.append(
                    finding("promise_not_found", chapter, f"章{chapter} 承诺 {entry_id} 不存在于账本", ref=entry_id)
                )


def _parse_simple_fields(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fields: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _max_prior_anchor_day(root: Path, before_chapter: int) -> int | None:
    """已 confirmed 章纲卡 + 更早定稿正文 书内时间 的最大可解析日。"""
    days: list[int] = []
    card_dir = root / "大纲" / "章纲"
    if card_dir.is_dir():
        for path in card_dir.glob("*.md"):
            fields = _parse_simple_fields(path.read_text(encoding="utf-8"))
            try:
                chapter = int(fields.get("章节号") or path.stem)
            except (TypeError, ValueError):
                continue
            if chapter >= before_chapter:
                continue
            if str(fields.get("状态") or "") != "confirmed":
                continue
            day = parse_anchor_day(str(fields.get("时间锚") or ""))
            if day is not None:
                days.append(day)
    body_dir = root / "定稿" / "正文"
    if body_dir.is_dir():
        for path in body_dir.glob("*.md"):
            match = re.match(r"^(\d{4})-", path.name)
            chapter = int(match.group(1)) if match else None
            text = path.read_text(encoding="utf-8")
            if chapter is None and text.startswith("---"):
                head = text.split("---", 2)[1] if text.count("---") >= 2 else ""
                for line in head.splitlines():
                    if line.startswith("章号:"):
                        try:
                            chapter = int(line.split(":", 1)[1].strip())
                        except ValueError:
                            chapter = None
            if chapter is None or chapter >= before_chapter:
                continue
            day = parse_anchor_day(text)
            if day is not None:
                days.append(day)
    return max(days) if days else None


def _check_time(root: Path, cards: list[dict[str, Any]], errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    before = min(_chapter_int(card) for card in cards)
    history_max = _max_prior_anchor_day(root, before)
    for card in cards:
        chapter = _chapter_int(card)
        anchor = str(card.get("时间锚") or "")
        day = parse_anchor_day(anchor)
        if day is None:
            if anchor.strip():
                warnings.append(finding("time_unparseable", chapter, f"章{chapter} 时间锚无法解析为第N天/日：{anchor}"))
            continue
        if history_max is not None and day < history_max:
            errors.append(
                finding(
                    "time_regression",
                    chapter,
                    f"章{chapter} 时间倒流（本章第{day}日 < 历史最大第{history_max}日）",
                    chapter_day=day,
                    history_max=history_max,
                )
            )


def _check_power(root: Path, cards: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    has_anchor = anchor_path(root).is_file()
    realms = [str(level.get("名") or "") for level in (load_anchor(root).get("境界链") or []) if level.get("名")]
    for card in cards:
        events = _as_list(card.get("战力事件"))
        if not events:
            continue
        chapter = _chapter_int(card)
        if not has_anchor:
            warnings.append(finding("power_anchor_missing", chapter, f"章{chapter} 含战力事件但缺少 设定/力量锚点.yaml"))
            continue
        for event in events:
            if not any(name and name in event for name in realms):
                warnings.append(
                    finding("unknown_realm", chapter, f"章{chapter} 战力事件未命中境界链：{event}", event=event)
                )


def _check_people(root: Path, cards: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    known = {item["name"] for item in load_known_names(root)}
    for card in cards:
        if "人物" not in card:
            continue
        chapter = _chapter_int(card)
        for name in _as_list(card.get("人物")):
            if name and name not in known:
                warnings.append(finding("unknown_character", chapter, f"章{chapter} 人物 {name} 不在名册", name=name))


def validate_chapter_batch(project_root: str | Path, cards: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    root = Path(project_root)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not cards:
        return {"errors": errors, "warnings": warnings}
    _check_titles(root, cards, warnings)
    _check_promises(root, cards, errors)
    _check_time(root, cards, errors, warnings)
    _check_power(root, cards, warnings)
    _check_people(root, cards, warnings)
    return {"errors": errors, "warnings": warnings}
