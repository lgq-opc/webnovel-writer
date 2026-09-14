"""连贯性共享函数：时间锚/年龄推演与名册加载（v6 线退役方案 §1.5 B 类拆分产物）。

本模块是 `continuity_check` 中**被 v7 侧长期依赖**的那部分函数（2026-09-14 逐字迁出）：

- 时间线年龄推演：`parse_anchor_day` / `_book_age_base` / `build_age_columns`
  —— 消费者 `timeline_view.py`（卷纲时间线视图追加主角年龄/修龄列）；
- 名册加载：`load_known_names` —— 消费者 `chapter_outline_validate.py`（章纲「人物未入册」校验）。

迁出原因：`continuity_check` 整体属 v6 连续性检查，按退役方案「冻结而非删除」口径处理；
但上述函数被 v7 写链/治理链引用，**不能随 v6 一起退役**，故独立成本模块长期保留。
`continuity_check.py` 的其余部分（命名冲突、浮动名扫描、CLI）保持原位不动。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_ANCHOR_DAY_RE = re.compile(r"第\s*(\d{1,5})\s*[天日]")
_NAME_RE = re.compile(r"[\u4e00-\u9fa5A-Za-z0-9]{2,8}")


def parse_anchor_day(anchor: str) -> int | None:
    """时间锚 → 故事内天数（「第N天/日」；解析失败 None）。"""
    match = _ANCHOR_DAY_RE.search(str(anchor or ""))
    return int(match.group(1)) if match else None


def _book_age_base(project_root: Path) -> dict[str, int] | None:
    book_yaml = project_root / "book.yaml"
    if not book_yaml.is_file():
        return None
    text = book_yaml.read_text(encoding="utf-8")
    age_match = re.search(r"^主角年龄:\s*(\d+)", text, re.MULTILINE)
    if not age_match:
        return None
    day_match = re.search(r"^觉醒日:\s*(\d+)", text, re.MULTILINE)
    return {"base_age": int(age_match.group(1)), "base_day": int(day_match.group(1)) if day_match else 1}


def build_age_columns(rows: list[tuple[int, str]], base: dict[str, int]) -> list[dict[str, Any]]:
    """核心推演：[(章, 时间锚)] → [{章, 年龄, 修龄}]（锚不可解析为「—」）。"""
    columns: list[dict[str, Any]] = []
    for chapter, anchor in rows:
        day = parse_anchor_day(anchor)
        if day is None:
            columns.append({"章": int(chapter), "年龄": "—", "修龄": "—"})
            continue
        age = base["base_age"] + max(0, day - base["base_day"]) // 365
        cultivation_age = max(0, day - base["base_day"])
        columns.append({"章": int(chapter), "年龄": age, "修龄": cultivation_age})
    return columns


def load_known_names(project_root: str | Path) -> list[dict[str, str]]:
    """已知名字池：v7 名册 front matter（正名+别名 JSON）+ 名册.md 总表（中文名单元格）。"""
    root = Path(project_root)
    known: list[dict[str, str]] = []
    roster_dir = root / "定稿" / "设定" / "名册"
    if roster_dir.is_dir():
        for path in sorted(roster_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            head = text.split("---", 2)
            if len(head) < 3:
                continue
            canonical = ""
            aliases: list[str] = []
            for line in head[1].splitlines():
                if line.startswith("正名:"):
                    canonical = line.partition(":")[2].strip()
                elif line.startswith("别名:"):
                    raw = line.partition(":")[2].strip()
                    try:
                        aliases = [str(a) for a in json.loads(raw)] if raw else []
                    except json.JSONDecodeError:
                        aliases = [raw.strip("[]\" ")] if raw else []
            if canonical:
                known.append({"name": canonical, "alias": "", "source": path.name})
            for alias in aliases:
                if alias:
                    known.append({"name": alias, "alias": canonical, "source": path.name})
    # 名册.md 总表（历史形态：列对齐不稳，直接取行内的中文名单元格）
    roster_md = root / "定稿" / "设定" / "名册.md"
    if roster_md.is_file():
        seen = {k["name"] for k in known}
        for line in roster_md.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line.startswith("|") or set(line) <= {"|", "-", " ", ":"}:
                continue
            for cell in line.strip("|").split("|"):
                cell = cell.strip()
                if cell and _NAME_RE.fullmatch(cell) and cell not in seen and cell not in ("正名", "别名", "首现章"):
                    known.append({"name": cell, "alias": "", "source": "名册.md"})
                    seen.add(cell)
    return known
