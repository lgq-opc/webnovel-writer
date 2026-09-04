#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段二 P2-3 数据不变量校验器。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
_WEBNOVEL = _SCRIPTS / "webnovel.py"


def test_empty_v7_book_always_returns_six_results(tmp_path: Path):
    import data_modules.invariant_check as invariant_check

    (tmp_path / "book.yaml").write_text("书名: 测试\n", encoding="utf-8")
    report = invariant_check.run_invariants(tmp_path)
    assert report["schema_version"] == "invariants/1"
    assert [item["id"] for item in report["invariants"]] == [
        "inv-1-journal",
        "inv-2-material-trajectory",
        "inv-3-power",
        "inv-4-promises",
        "inv-5-contracts",
        "inv-6-stale-age",
    ]
    assert report["summary"] == {"pass": 5, "fail": 0, "warn": 0, "skip": 1}
    assert report["ok"] is True


def test_summary_fails_only_on_fail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import data_modules.invariant_check as invariant_check

    monkeypatch.setattr(
        invariant_check,
        "CHECKS",
        (
            ("a", lambda _root: invariant_check.result("a", "A", "warn")),
            ("b", lambda _root: invariant_check.result("b", "B", "skip")),
            ("c", lambda _root: invariant_check.result("c", "C", "fail")),
        ),
    )
    report = invariant_check.run_invariants(tmp_path)
    assert report["ok"] is False
    assert report["summary"] == {"pass": 0, "fail": 1, "warn": 1, "skip": 1}


def test_only_filters_and_rejects_unknown_id(tmp_path: Path):
    import data_modules.invariant_check as invariant_check

    assert len(invariant_check.run_invariants(tmp_path, only=["inv-1-journal"])["invariants"]) == 1
    with pytest.raises(ValueError, match="unknown invariant"):
        invariant_check.run_invariants(tmp_path, only=["inv-999"])


def test_cli_json_empty_v7_exits_zero(tmp_path: Path):
    (tmp_path / "book.yaml").write_text("书名: 测试\n", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(_WEBNOVEL),
            "--project-root",
            str(tmp_path),
            "invariants",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["schema_version"] == "invariants/1"
    assert len(report["invariants"]) == 6
    assert report["ok"] is True


def test_text_format_ok_line():
    import data_modules.invariant_check as invariant_check

    report = {
        "ok": True,
        "summary": {"pass": 5, "fail": 0, "warn": 0, "skip": 1},
        "invariants": [
            invariant_check.result("inv-1-journal", "journal", "pass"),
            invariant_check.result("inv-5-contracts", "contracts", "skip"),
        ],
    }
    text = invariant_check.format_text(report)
    assert text.startswith("OK invariants: 2 checked")
    assert "inv-1-journal" in text and "pass" in text
