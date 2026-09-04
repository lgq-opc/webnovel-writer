"""详细大纲路径与章节标题/节选解析（v8-gap-review 阶段二 P2-1）。

规范写路径：大纲/卷纲/第NN卷-详细大纲.md
兼容读顺序：规范路径 → 迁移器旧产物 第NN卷.md → v6 平铺路径及空格变体。
新写标题固定 ## 第N章：标题；读取兼容 H2/H3、阿拉伯/中文章号、全角/半角冒号与空格。
"""
from __future__ import annotations

import re
from pathlib import Path

_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_HEADING_RE = re.compile(
    r"^(#{2,3})\s*第\s*([0-9零一二三四五六七八九十百]+)\s*章(?:\s*[：:]\s*|\s+)(.+?)\s*$",
    re.M,
)


def _cn_number(raw: str) -> int | None:
    if raw.isdigit():
        return int(raw)
    total, current = 0, 0
    for char in raw:
        if char in _CN_DIGITS:
            current = _CN_DIGITS[char]
        elif char == "十":
            total += (current or 1) * 10
            current = 0
        elif char == "百":
            total += (current or 1) * 100
            current = 0
        else:
            return None
    return total + current


def canonical_detailed_outline_path(root: str | Path, volume: int) -> Path:
    return Path(root) / "大纲" / "卷纲" / f"第{int(volume):02d}卷-详细大纲.md"


def detailed_outline_candidates(root: str | Path, volume: int) -> list[Path]:
    root, volume = Path(root), int(volume)
    return [
        canonical_detailed_outline_path(root, volume),
        root / "大纲" / "卷纲" / f"第{volume:02d}卷.md",
        root / "大纲" / f"第{volume}卷-详细大纲.md",
        root / "大纲" / f"第{volume}卷 - 详细大纲.md",
        root / "大纲" / f"第{volume}卷 详细大纲.md",
    ]


def resolve_detailed_outline(root: str | Path, volume: int) -> Path | None:
    return next((path for path in detailed_outline_candidates(root, volume) if path.is_file()), None)


def _match(text: str, chapter: int):
    return next((m for m in _HEADING_RE.finditer(text) if _cn_number(m.group(2)) == int(chapter)), None)


def extract_chapter_heading(text: str, chapter: int) -> str | None:
    match = _match(text, chapter)
    return match.group(3).strip() if match else None


def extract_chapter_section(text: str, chapter: int) -> str | None:
    match = _match(text, chapter)
    if not match:
        return None
    level = len(match.group(1))
    rest = text[match.end():]
    stop = re.search(rf"^#{{1,{level}}}\s", rest, re.M)
    return (match.group(0) + (rest[: stop.start()] if stop else rest)).strip()
