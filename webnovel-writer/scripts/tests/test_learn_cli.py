#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""learn CLI 默认 action（v8-gap-review 阶段三 P3-3 / N9）。

spec：docs/cursor/阶段三-写回播种与CLI/2026-09-04-writeback-seed-spec.md
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent


@pytest.fixture()
def book(tmp_path: Path) -> Path:
    from data_modules.author_journal import append_events
    from data_modules.domain_contract import init_domain_skeleton

    init_domain_skeleton(tmp_path)
    (tmp_path / "book.yaml").write_text('spec_version: "7.0"\n卷规模: 40\n', encoding="utf-8")
    append_events(
        tmp_path,
        [
            {
                "actor": "author", "action": "edit", "domain": "章纲",
                "path": "大纲/章纲/0001.md", "change_kind": "content",
                "diff_stat": {"ins": 1, "del": 0}, "summary": "对峙提前", "impact": [],
            }
        ],
    )
    return tmp_path


def _cli(book: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(_SCRIPTS / "webnovel.py"), "--project-root", str(book), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_learn_from_journal_without_nested_action(book: Path):
    proc = _cli(book, "learn", "--from-journal", "--format", "json")
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert payload["ok"] is True
    assert (book / "作者" / "author_model-建议.md").is_file()


def test_learn_learn_from_journal_still_works(book: Path):
    proc = _cli(book, "learn", "learn", "--from-journal", "--format", "json")
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["ok"] is True


def test_learn_without_from_journal_still_errors(book: Path):
    proc = _cli(book, "learn", "--format", "json")
    assert proc.returncode != 0


def test_learn_apply_still_requires_explicit_action(book: Path):
    proc = _cli(book, "learn", "apply", "--format", "json")
    payload = json.loads(proc.stdout or "{}") if proc.stdout.strip().startswith("{") else {}
    assert proc.returncode != 0 or payload.get("ok") is False
