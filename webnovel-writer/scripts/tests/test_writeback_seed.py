#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写回 JSON 播种承诺账本（v8-gap-review 阶段三 P3-3）。

spec：docs/cursor/阶段三-写回播种与CLI/2026-09-04-writeback-seed-spec.md
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent

FORESHADOW = [
    {"content": "江岸仓库地底上古遗迹与妖王颈上铁链（有人把妖王拴在灾源旁，链连石门）", "buried_chapter": "第17章", "payoff_chapter": "", "level": "核心"},
    {"content": "熔炉残响说出'天劫'：灾难是人引来的，三百年前他们成功过一次", "buried_chapter": "第76章", "payoff_chapter": "", "level": "核心"},
    {"content": "林知夏家族身世（家族式管理熟悉/市政图纸/儿时见过大阵仗）", "buried_chapter": "第19章", "payoff_chapter": "", "level": "卷级"},
    {"content": "新安城觊觎吞灾能力，程卫东将亲自来", "buried_chapter": "第79章", "payoff_chapter": "", "level": "卷级"},
    {"content": "熊铁山败逃被新安城收留", "buried_chapter": "第79章", "payoff_chapter": "", "level": "卷级"},
    {"content": "苏小白丹田内的未知之物（灾源残留，熔炉回避不答）", "buried_chapter": "第80章", "payoff_chapter": "", "level": "核心"},
    {"content": "铁门青光与敲击声实为灾源脉动", "buried_chapter": "第32章", "payoff_chapter": "第60章", "level": "卷级"},
]
OPEN_LOOP = [
    {"content": "三百年前上一次灵气潮汐与引劫真相", "buried_chapter": "第18章", "payoff_chapter": "", "level": "持续开放环"},
]


def _writeback(book: Path, items: list[dict], extra: dict | None = None) -> Path:
    payload = {"foreshadow_writeback": items, "open_loop_writeback": OPEN_LOOP}
    if extra:
        payload.update(extra)
    path = book / "大纲" / "卷纲" / "第01卷-总纲写回.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@pytest.fixture()
def book(tmp_path: Path) -> Path:
    from data_modules.domain_contract import init_domain_skeleton

    init_domain_skeleton(tmp_path)
    (tmp_path / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    _writeback(tmp_path, FORESHADOW)
    return tmp_path


def _cli(book: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(_SCRIPTS / "webnovel.py"), "--project-root", str(book), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_seeds_seven_foreshadow_entries(book: Path):
    from data_modules.promise_ledger import load_entries, seed_from_writeback

    report = seed_from_writeback(book, volume=1)
    entries = load_entries(book, kind="伏笔")
    names = [e["名称"] for e in entries]
    assert report["ok"] is True and report.get("exit", 0) == 0
    assert report["created"] == [f"F-{i:03d}" for i in range(1, 8)]
    assert names == [item["content"] for item in FORESHADOW]
    assert entries[0]["最晚回收章"] == 0
    assert entries[-1]["最晚回收章"] == 60
    assert entries[0]["埋设章"] == 17
    assert "level: 核心" in entries[0]["正文"]
    assert load_entries(book, kind="悬念") == []


def test_idempotent_skips_duplicate_names(book: Path):
    from data_modules.promise_ledger import seed_from_writeback

    first = seed_from_writeback(book, volume=1)
    second = seed_from_writeback(book, volume=1)
    assert first["created"] and not second["created"]
    assert len(second["skipped"]) == 7
    assert all(s["reason"] == "duplicate_name" for s in second["skipped"])
    assert second.get("exit", 0) == 0


def test_ignores_open_loop_writeback(book: Path):
    from data_modules.promise_ledger import load_entries, seed_from_writeback

    seed_from_writeback(book, volume=1)
    assert [e["名称"] for e in load_entries(book, kind="悬念")] == []
    assert len(load_entries(book, kind="伏笔")) == 7


def test_bad_buried_chapter_fails_item_keeps_rest(book: Path):
    from data_modules.promise_ledger import load_entries, seed_from_writeback

    _writeback(book, [
        {"content": "好伏笔", "buried_chapter": "第10章", "payoff_chapter": "", "level": "卷级"},
        {"content": "坏伏笔", "buried_chapter": "不明", "payoff_chapter": "", "level": "卷级"},
        {"content": "另一条", "buried_chapter": "第12章", "payoff_chapter": "", "level": "卷级"},
    ])
    report = seed_from_writeback(book, volume=1)
    assert report["ok"] is False and report.get("exit") == 1
    assert len(report["created"]) == 2 and len(report["failed"]) == 1
    assert report["failed"][0]["error"] == "unparseable_buried_chapter"
    assert [e["名称"] for e in load_entries(book, kind="伏笔")] == ["好伏笔", "另一条"]


def test_missing_file_exit_2_no_write(book: Path):
    from data_modules.promise_ledger import load_entries, seed_from_writeback

    report = seed_from_writeback(book, volume=9)
    assert report["ok"] is False and report.get("exit") == 2
    assert report["error"] == "missing_file"
    assert load_entries(book, kind="伏笔") == []


def test_cli_seed_and_help(book: Path):
    help_proc = _cli(book, "promise-ledger", "-h")
    assert help_proc.returncode == 0 and "seed-from-writeback" in help_proc.stdout
    missing = _cli(book, "promise-ledger", "seed-from-writeback", "--format", "json")
    assert missing.returncode != 0
    proc = _cli(book, "promise-ledger", "seed-from-writeback", "--volume", "1", "--format", "json")
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0 and len(payload["created"]) == 7
