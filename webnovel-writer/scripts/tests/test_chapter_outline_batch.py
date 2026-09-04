#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T8（M1）章纲批量生成测试。

对应方案：06 §2（章纲卡 front matter）、07 F-04、08 T8、02 P7（一次确认一批）。
契约：一批 ≤8 张；必填字段校验；批内自检（节点非空/字数范围/承诺格式）；
写入 状态: draft；confirm 翻转为 confirmed 并留 journal。
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def book(tmp_path: Path) -> Path:
    from data_modules.domain_contract import init_domain_skeleton

    init_domain_skeleton(tmp_path)
    return tmp_path


def _card(chapter: int, **over) -> dict:
    base = {
        "章节号": chapter,
        "标题": f"第{chapter}章标题",
        "卷": 2,
        "时间锚": f"第{chapter}日·夜",
        "节点": [f"CBN: 推进{chapter}", f"CEN: 钩子{chapter}"],
        "禁区": ["主角不得暴露金手指"],
        "承诺推进": [],
        "战力事件": [],
        "素材引用": ["桥段:TR-012"],
        "字数目标": 2400,
        "正文": f"# 第 {chapter} 章 章纲正文",
    }
    base.update(over)
    return base


def _write_outline(book: Path, body: str, volume: int = 2) -> None:
    path = book / "大纲" / "卷纲" / f"第{volume:02d}卷-详细大纲.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _seed_promise(book: Path, entry_id: str, name: str = "测试伏笔") -> None:
    from data_modules.promise_ledger import create_entry

    create_entry(book, kind="伏笔", name=name, planted_chapter=1, due_chapter=80, entry_id=entry_id)


def _seed_roster(book: Path, name: str, aliases: list[str] | None = None) -> None:
    path = book / "定稿" / "设定" / "名册" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    alias_json = __import__("json").dumps(aliases or [], ensure_ascii=False)
    path.write_text(f"---\n正名: {name}\n别名: {alias_json}\n类型: 角色\n---\n", encoding="utf-8")


def _write_confirmed_card(book: Path, chapter: int, *, title: str, anchor: str) -> None:
    path = book / "大纲" / "章纲" / f"{chapter:04d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\n章节号: {chapter}\n标题: {title}\n卷: 2\n状态: confirmed\n时间锚: {anchor}\n节点: [\"CBN\"]\n字数目标: 2000\n---\n",
        encoding="utf-8",
    )


class TestCreateBatch:
    def test_creates_draft_cards_with_front_matter(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch, parse_chapter_card

        report = create_chapter_batch(book, [_card(39), _card(40), _card(41)])

        assert report["ok"] is True
        assert report["written"] == [39, 40, 41]
        fields, body = parse_chapter_card((book / "大纲" / "章纲" / "0039.md").read_text(encoding="utf-8"))
        assert fields["章节号"] == "39"
        assert fields["状态"] == "draft"
        assert fields["字数目标"] == "2400"
        assert "章纲正文" in body

    def test_batch_over_eight_rejected(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        report = create_chapter_batch(book, [_card(100 + i) for i in range(9)])

        assert report["ok"] is False
        assert report["error"] == "batch_too_large"

    def test_duplicate_chapter_rejected(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        report = create_chapter_batch(book, [_card(39), _card(39, 标题="另一标题")])

        assert report["ok"] is False
        assert report["error"] == "duplicate_chapter"

    def test_missing_required_field_rejected(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        bad = _card(39)
        del bad["标题"]
        report = create_chapter_batch(book, [bad])

        assert report["ok"] is False
        assert report["error"] == "missing_field"

    def test_list_fields_round_trip(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch, parse_chapter_card

        _seed_promise(book, "F-039")
        create_chapter_batch(book, [_card(39, 承诺推进=["F-039: 揭示部分真相"])])
        fields, _ = parse_chapter_card((book / "大纲" / "章纲" / "0039.md").read_text(encoding="utf-8"))

        assert fields["节点"] == ["CBN: 推进39", "CEN: 钩子39"]
        assert fields["承诺推进"] == ["F-039: 揭示部分真相"]


class TestSelfCheck:
    def test_empty_nodes_flagged(self, book: Path):
        from data_modules.chapter_outline_batch import self_check_batch

        problems = self_check_batch([_card(39, 节点=[])])

        assert any("节点" in p for p in problems)

    def test_word_target_out_of_range_flagged(self, book: Path):
        from data_modules.chapter_outline_batch import self_check_batch

        problems = self_check_batch([_card(39, 字数目标=50)])

        assert any("字数" in p for p in problems)

    def test_promise_format_flagged(self, book: Path):
        from data_modules.chapter_outline_batch import self_check_batch

        problems = self_check_batch([_card(39, 承诺推进=["没有前缀的承诺"])])

        assert any("承诺" in p for p in problems)

    def test_clean_card_no_problems(self, book: Path):
        from data_modules.chapter_outline_batch import self_check_batch

        assert self_check_batch([_card(39)]) == []

    def test_create_reports_self_check(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        report = create_chapter_batch(book, [_card(39, 字数目标=50)])

        assert report["ok"] is True, "自检问题为 warning，不阻断创建"
        assert report["checks"], "自检问题应在报告中透出"


class TestConfirm:
    def test_confirm_flips_status_and_leaves_trail(self, book: Path):
        from data_modules.author_journal import read_journal
        from data_modules.chapter_outline_batch import confirm_chapter_batch, create_chapter_batch, parse_chapter_card

        create_chapter_batch(book, [_card(39), _card(40)])
        report = confirm_chapter_batch(book, [39, 40])

        assert report["ok"] is True
        for chapter in (39, 40):
            fields, _ = parse_chapter_card((book / "大纲" / "章纲" / f"{chapter:04d}.md").read_text(encoding="utf-8"))
            assert fields["状态"] == "confirmed"
        assert "adopt" in [e["action"] for e in read_journal(book)]

    def test_confirm_missing_chapter_fails(self, book: Path):
        from data_modules.chapter_outline_batch import confirm_chapter_batch

        report = confirm_chapter_batch(book, [99])
        assert report["ok"] is False


class TestConsistencyGate:
    def test_title_mismatch_is_warning_but_card_is_written(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        _write_outline(book, "## 第43章：夜袭\n目标")
        report = create_chapter_batch(book, [_card(43, 标题="错名", 人物=["苏小白"])])

        assert report["ok"] is True
        assert any(item["code"] == "outline_title_mismatch" for item in report["warnings"])
        assert (book / "大纲" / "章纲" / "0043.md").is_file()

    def test_matching_outline_title_has_no_title_warning(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        _write_outline(book, "## 第43章：夜袭\n目标")
        report = create_chapter_batch(book, [_card(43, 标题="夜袭")])

        assert report["ok"] is True
        assert not any(item["code"] == "outline_title_mismatch" for item in report.get("warnings") or [])

    def test_missing_promise_is_error_with_zero_side_effects(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        journal = book / "作者" / "journal.jsonl"
        before = journal.read_text(encoding="utf-8") if journal.is_file() else ""
        report = create_chapter_batch(book, [_card(43, 承诺推进=["F-999: 推进"])])

        assert report["ok"] is False and report["error"] == "consistency_gate"
        assert any(item["code"] == "promise_not_found" for item in report["errors"])
        assert not (book / "大纲" / "章纲" / "0043.md").exists()
        assert (journal.read_text(encoding="utf-8") if journal.is_file() else "") == before

    def test_people_round_trip_as_json_list(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch, parse_chapter_card

        _seed_roster(book, "苏小白")
        _seed_roster(book, "林知夏")
        report = create_chapter_batch(book, [_card(43, 人物=["苏小白", "林知夏"])])

        assert report["ok"] is True
        fields, _ = parse_chapter_card((book / "大纲" / "章纲" / "0043.md").read_text(encoding="utf-8"))
        assert fields["人物"] == ["苏小白", "林知夏"]

    def test_time_regression_from_confirmed_card_is_error(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        _write_confirmed_card(book, 42, title="前夜", anchor="第42日·夜")
        report = create_chapter_batch(book, [_card(43, 时间锚="第41日·晨")])

        assert report["ok"] is False and report["error"] == "consistency_gate"
        assert any(item["code"] == "time_regression" for item in report["errors"])
        assert not (book / "大纲" / "章纲" / "0043.md").exists()

    def test_time_regression_from_settled_front_matter(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        path = book / "定稿" / "正文" / "0041-旧章.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n章号: 41\n书内时间: 末世第42天\n---\n正文\n", encoding="utf-8")
        report = create_chapter_batch(book, [_card(43, 时间锚="第41日·晨")])

        assert report["ok"] is False
        assert any(item["code"] == "time_regression" for item in report["errors"])

    def test_unparseable_time_is_warning_and_writes(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        report = create_chapter_batch(book, [_card(43, 时间锚="灾变后第三周")])

        assert report["ok"] is True
        assert any(item["code"] == "time_unparseable" for item in report["warnings"])
        assert (book / "大纲" / "章纲" / "0043.md").is_file()

    def test_unknown_realm_is_warning(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch
        from data_modules.power_anchor import write_anchor

        write_anchor(book, {
            "spec": "power-anchor/1",
            "境界链": [{"序": 1, "名": "聚气"}, {"序": 2, "名": "凝罡"}],
            "越级规则": {},
            "战例账本": [],
            "通胀记录": [],
        })
        report = create_chapter_batch(book, [_card(43, 战力事件=["筑基突破"])])

        assert report["ok"] is True
        assert any(item["code"] == "unknown_realm" for item in report["warnings"])

    def test_missing_power_anchor_with_events_is_warning(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        report = create_chapter_batch(book, [_card(43, 战力事件=["聚气对决"])])

        assert report["ok"] is True
        assert any(item["code"] == "power_anchor_missing" for item in report["warnings"])

    def test_unknown_character_is_warning(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        _seed_roster(book, "苏小白")
        report = create_chapter_batch(book, [_card(43, 人物=["苏小白", "林知夏"])])

        assert report["ok"] is True
        codes = [item["code"] for item in report["warnings"] if item.get("chapter") == 43]
        assert "unknown_character" in codes
        assert not any(item["code"] == "unknown_character" and "苏小白" in item["message"] for item in report["warnings"])

    def test_missing_people_field_is_compatible(self, book: Path):
        from data_modules.chapter_outline_batch import create_chapter_batch

        report = create_chapter_batch(book, [_card(43)])

        assert report["ok"] is True
        assert not any(item["code"] == "unknown_character" for item in report.get("warnings") or [])

