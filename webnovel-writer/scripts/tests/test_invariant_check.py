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


def _event(**overrides) -> dict:
    base = {
        "actor": "author",
        "action": "edit",
        "domain": "章纲",
        "path": "大纲/章纲/0039.md",
        "change_kind": "content",
        "diff_stat": {"ins": 1, "del": 0},
        "summary": "改了一处钩子",
        "impact": [],
    }
    base.update(overrides)
    return base


def _check(root: Path, check_id: str) -> dict:
    import data_modules.invariant_check as invariant_check

    report = invariant_check.run_invariants(root, only=[check_id])
    return report["invariants"][0]


def _codes(item: dict) -> set[str]:
    return {finding["code"] for finding in item.get("findings") or []}


@pytest.fixture()
def book(tmp_path: Path) -> Path:
    from data_modules.domain_contract import init_domain_skeleton

    init_domain_skeleton(tmp_path)
    return tmp_path


class TestJournalInvariant:
    def test_legal_journal_passes(self, book: Path):
        from data_modules.author_journal import append_events

        append_events(book, [_event()])
        item = _check(book, "inv-1-journal")
        assert item["status"] == "pass"

    def test_unclassified_domain_fails(self, book: Path):
        from data_modules.author_journal import append_events

        append_events(book, [_event(domain="其他", path="工作区/散落.md")])
        item = _check(book, "inv-1-journal")
        assert item["status"] == "fail"
        assert "unclassified_event" in _codes(item)

    def test_migration_bulk_is_exempt(self, book: Path):
        from data_modules.author_journal import append_events

        append_events(book, [_event(domain="其他", path="(bulk)", impact=["migration"])])
        item = _check(book, "inv-1-journal")
        assert item["status"] == "pass"

    def test_empty_summary_edit_warns(self, book: Path):
        from data_modules.author_journal import append_events

        append_events(book, [_event(summary="")])
        item = _check(book, "inv-1-journal")
        assert item["status"] == "warn"
        assert "pending_semantic" in _codes(item)

    def test_illegal_enum_fails(self, book: Path):
        from data_modules.author_journal import append_events

        append_events(book, [_event(actor="unknown")])
        item = _check(book, "inv-1-journal")
        assert item["status"] == "fail"
        assert "illegal_field" in _codes(item)


def _seed_live(book: Path, table: str, entry_id: str) -> None:
    from data_modules.material_store import append_entries

    append_entries(book, table, [{"id": entry_id, "名称": entry_id, "核心摘要": "摘要"}])


class TestMaterialTrajectoryInvariant:
    def test_no_trajectory_passes(self, book: Path):
        item = _check(book, "inv-2-material-trajectory")
        assert item["status"] == "pass"
        assert item["counts"].get("rows", 0) == 0

    def test_live_id_present_then_missing(self, book: Path):
        from data_modules.material_usage import append_usage

        _seed_live(book, "桥段", "TR-001")
        append_usage(book, 39, [{"条目id": "TR-001", "定版版本": "live"}])
        assert _check(book, "inv-2-material-trajectory")["status"] == "pass"

        live_csv = book / "素材" / "活" / "桥段.csv"
        lines = live_csv.read_text(encoding="utf-8-sig").splitlines()
        live_csv.write_text("\n".join(line for line in lines if "TR-001" not in line) + "\n", encoding="utf-8")
        item = _check(book, "inv-2-material-trajectory")
        assert item["status"] == "fail"
        assert "live_id_missing" in _codes(item)

    def test_frozen_v01_complete_passes(self, book: Path):
        from data_modules.freeze_manager import freeze_volume
        from data_modules.material_usage import append_usage

        _seed_live(book, "桥段", "TR-001")
        freeze_volume(book, volume=1)
        append_usage(book, 39, [{"条目id": "TR-001", "定版版本": "v01"}])
        item = _check(book, "inv-2-material-trajectory")
        assert item["status"] == "pass"

    def test_frozen_missing_manifest_fails(self, book: Path):
        from data_modules.freeze_manager import freeze_volume
        from data_modules.material_usage import append_usage

        _seed_live(book, "桥段", "TR-001")
        freeze_volume(book, volume=1)
        append_usage(book, 39, [{"条目id": "TR-001", "定版版本": "v01"}])
        (book / "素材" / "定版" / "v01" / "manifest.json").unlink()
        item = _check(book, "inv-2-material-trajectory")
        assert item["status"] == "fail"
        assert "frozen_manifest_missing" in _codes(item)

    def test_frozen_missing_csv_fails(self, book: Path):
        from data_modules.freeze_manager import freeze_volume
        from data_modules.material_usage import append_usage

        _seed_live(book, "桥段", "TR-001")
        freeze_volume(book, volume=1)
        append_usage(book, 39, [{"条目id": "TR-001", "定版版本": "v01"}])
        (book / "素材" / "定版" / "v01" / "桥段.csv").unlink()
        item = _check(book, "inv-2-material-trajectory")
        assert item["status"] == "fail"
        assert "frozen_id_missing" in _codes(item) or "frozen_csv_missing" in _codes(item)

    def test_frozen_source_unlisted_fails(self, book: Path):
        from data_modules.freeze_manager import freeze_volume
        from data_modules.material_usage import append_usage

        _seed_live(book, "桥段", "TR-001")
        freeze_volume(book, volume=1)
        append_usage(book, 39, [{"条目id": "TR-001", "定版版本": "v01"}])
        manifest_path = book / "素材" / "定版" / "v01" / "manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["source_files"] = [item for item in payload["source_files"] if item.get("path") != "桥段.csv"]
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        item = _check(book, "inv-2-material-trajectory")
        assert item["status"] == "fail"
        assert "frozen_source_unlisted" in _codes(item)

    def test_frozen_id_removed_from_csv_fails(self, book: Path):
        from data_modules.freeze_manager import freeze_volume
        from data_modules.material_usage import append_usage

        _seed_live(book, "桥段", "TR-001")
        freeze_volume(book, volume=1)
        append_usage(book, 39, [{"条目id": "TR-001", "定版版本": "v01"}])
        csv_path = book / "素材" / "定版" / "v01" / "桥段.csv"
        lines = csv_path.read_text(encoding="utf-8-sig").splitlines()
        csv_path.write_text("\n".join(line for line in lines if "TR-001" not in line) + "\n", encoding="utf-8")
        item = _check(book, "inv-2-material-trajectory")
        assert item["status"] == "fail"
        assert "frozen_id_missing" in _codes(item)

    def test_bad_json_and_empty_id_fail(self, book: Path):
        from data_modules.material_usage import append_usage, trajectory_path

        _seed_live(book, "桥段", "TR-001")
        append_usage(book, 39, [{"条目id": "", "定版版本": "live"}])
        with trajectory_path(book).open("a", encoding="utf-8") as handle:
            handle.write("{not-json\n")
        item = _check(book, "inv-2-material-trajectory")
        assert item["status"] == "fail"
        assert "empty_entry_id" in _codes(item)
        assert "bad_json_row" in _codes(item)
