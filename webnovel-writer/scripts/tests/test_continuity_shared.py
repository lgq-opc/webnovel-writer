#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""continuity_shared 共享函数测试（v6 线退役方案 §1.5 B 类拆分留存）。

对应方案：docs/plans/2026-09-10-v6线退役方案.md §1.5 B（`continuity_check` 拆出
`load_known_names` / `parse_anchor_day` / `build_age_columns` / `_book_age_base`，
v7 章纲校验与时间线视图在用）与 §1.6 增量记录。

契约：这 4 个函数被 v7 侧长期引用，拆分后必须独立有测试守护（「不允许拆完没守护」）——
故本文件**直接**覆盖它们，而不是只经由 continuity_check 的集成路径间接覆盖。
"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)


def test_parse_anchor_day_parses_day_and_days_forms():
    from data_modules.continuity_shared import parse_anchor_day

    assert parse_anchor_day("末世第370天") == 370
    assert parse_anchor_day("第 12 日") == 12
    assert parse_anchor_day("某个雨夜") is None
    assert parse_anchor_day("") is None
    assert parse_anchor_day(None) is None


def test_book_age_base_reads_book_yaml(tmp_path: Path):
    from data_modules.continuity_shared import _book_age_base

    assert _book_age_base(tmp_path) is None, "无 book.yaml → None"

    (tmp_path / "book.yaml").write_text("书名: 测试\n主角年龄: 24\n觉醒日: 3\n", encoding="utf-8")
    assert _book_age_base(tmp_path) == {"base_age": 24, "base_day": 3}

    (tmp_path / "book.yaml").write_text("书名: 测试\n主角年龄: 24\n", encoding="utf-8")
    assert _book_age_base(tmp_path) == {"base_age": 24, "base_day": 1}, "觉醒日缺省为 1"

    (tmp_path / "book.yaml").write_text("书名: 测试\n", encoding="utf-8")
    assert _book_age_base(tmp_path) is None, "无主角年龄 → None"


def test_build_age_columns_crosses_year_and_dashes_unparsable():
    from data_modules.continuity_shared import build_age_columns

    columns = build_age_columns(
        [(1, "末世第1天"), (2, "末世第370天"), (3, "某个雨夜")],
        {"base_age": 24, "base_day": 1},
    )

    assert columns == [
        {"章": 1, "年龄": 24, "修龄": 0},
        {"章": 2, "年龄": 25, "修龄": 369},
        {"章": 3, "年龄": "—", "修龄": "—"},
    ]


def test_load_known_names_reads_roster_frontmatter_and_table(tmp_path: Path):
    from data_modules.continuity_shared import load_known_names

    roster = tmp_path / "定稿" / "设定" / "名册"
    roster.mkdir(parents=True, exist_ok=True)
    (roster / "苏小白.md").write_text(
        '---\n正名: 苏小白\n别名: ["苏哥", "小白"]\n类型: 角色\n首现章: 1\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "定稿" / "设定" / "名册.md").write_text(
        "| 正名 | 别名 | 首现章 |\n|---|---|---|\n| 王铁柱 | 柱哥 | 5 |\n",
        encoding="utf-8",
    )

    known = load_known_names(tmp_path)
    names = {item["name"] for item in known}

    assert {"苏小白", "苏哥", "小白", "王铁柱", "柱哥"} <= names
    assert next(i for i in known if i["name"] == "苏哥")["alias"] == "苏小白"
    assert next(i for i in known if i["name"] == "王铁柱")["source"] == "名册.md"
    assert "正名" not in names and "首现章" not in names, "表头不入池"
