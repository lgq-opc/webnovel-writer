#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工坊同步执行器（v8-gap-review 阶段三 P3-2）。

spec：docs/cursor/阶段三-工坊同步执行器/2026-09-04-forge-sync-spec.md
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))

from test_setting_forge import _proposal_doc  # noqa: E402


@pytest.fixture()
def book(tmp_path: Path) -> Path:
    from data_modules.author_model import write_preferences
    from data_modules.domain_contract import init_domain_skeleton
    from data_modules.material_store import append_entries

    init_domain_skeleton(tmp_path)
    (tmp_path / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    (tmp_path / "定稿" / "设定").mkdir(parents=True, exist_ok=True)
    append_entries(tmp_path, "金手指零件", [{"id": "GF-001", "名称": "代价转化", "核心摘要": "吃灾转化"}])
    write_preferences(tmp_path, {"节奏": {"冲突前置": True}, "雷点": ["无代价金手指"], "审稿习惯": {}})
    return tmp_path


def _confirm(book: Path, tmp_path: Path, category: str) -> dict:
    from data_modules.setting_forge import forge_adopt, forge_confirm, forge_save

    proposal_file = tmp_path / f"{category}.md"
    proposal_file.write_text(_proposal_doc(category), encoding="utf-8")
    forge_save(book, category=category, file=proposal_file)
    adopt = forge_adopt(book, category=category, version=1, proposal=1)
    return forge_confirm(book, category=category, draft=adopt["draft"])


def _cli(book: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(_SCRIPTS / "webnovel.py"), "--project-root", str(book), "forge-sync", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_empty_journal_status_ok(book: Path):
    from data_modules.forge_sync import main

    assert main(["status", "--project-root", str(book), "--format", "json"]) == 0


def test_confirm_gongfa_lists_both_kinds(book: Path, tmp_path: Path, capsys):
    from data_modules.forge_sync import main

    _confirm(book, tmp_path, "功法")
    code = main(["status", "--project-root", str(book), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    kinds = {item["kind"] for item in payload["pending"]}
    assert code == 1 and payload["ok"] is False
    assert kinds == {"power_anchor_sync", "contract_rebuild"}
    joined = " ".join(payload["next"])
    assert "power validate" in joined and "master-outline-sync" in joined


def test_confirm_fabao_only_contract(book: Path, tmp_path: Path, capsys):
    from data_modules.forge_sync import main

    _confirm(book, tmp_path, "法宝")
    main(["status", "--project-root", str(book), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert {item["kind"] for item in payload["pending"]} == {"contract_rebuild"}


def test_status_does_not_write_journal(book: Path, tmp_path: Path):
    from data_modules.author_journal import read_journal
    from data_modules.forge_sync import main

    _confirm(book, tmp_path, "功法")
    before = read_journal(book)
    main(["status", "--project-root", str(book), "--format", "json"])
    assert read_journal(book) == before


def test_mark_cleared_all_after_gongfa(book: Path, tmp_path: Path, capsys):
    from data_modules.author_journal import read_journal
    from data_modules.forge_sync import main

    _confirm(book, tmp_path, "功法")
    assert main(["mark-cleared", "--kind", "all", "--project-root", str(book), "--format", "json"]) == 0
    impacts = [token for event in read_journal(book) for token in (event.get("impact") or [])]
    assert "power_anchor_sync:cleared" in impacts and "contract_rebuild:cleared" in impacts
    capsys.readouterr()
    assert main(["status", "--project-root", str(book), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True and payload["pending"] == []


def test_mark_cleared_rejects_when_empty(book: Path):
    from data_modules.author_journal import read_journal
    from data_modules.forge_sync import main

    before = read_journal(book)
    assert main(["mark-cleared", "--kind", "all", "--project-root", str(book)]) == 2
    assert read_journal(book) == before


def test_extra_cleared_does_not_swallow_later_required(book: Path, tmp_path: Path, capsys):
    from data_modules.author_journal import append_events
    from data_modules.forge_sync import main

    append_events(
        book,
        [{
            "actor": "author",
            "action": "edit",
            "domain": "设定",
            "path": "作者/journal.jsonl",
            "change_kind": "structure",
            "diff_stat": {"ins": 0, "del": 0},
            "summary": "历史脏 cleared",
            "impact": ["power_anchor_sync:cleared"],
        }],
    )
    _confirm(book, tmp_path, "功法")
    main(["status", "--project-root", str(book), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert "power_anchor_sync" in {item["kind"] for item in payload["pending"]}


def test_webnovel_cli_forge_sync(book: Path, tmp_path: Path):
    _confirm(book, tmp_path, "功法")
    proc = _cli(book, "--format", "json")
    assert proc.returncode == 1 and "power validate" in proc.stdout
    cleared = _cli(book, "mark-cleared", "--kind", "all", "--format", "json")
    assert cleared.returncode == 0
    again = _cli(book, "status", "--format", "json")
    assert again.returncode == 0
