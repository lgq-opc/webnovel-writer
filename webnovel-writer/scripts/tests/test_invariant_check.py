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
    assert report["summary"] == {"pass": 4, "fail": 0, "warn": 0, "skip": 2}
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


def _write_anchor(book: Path, *, chain: list[dict] | None = None, battles: list[dict] | None = None) -> None:
    from data_modules.power_anchor import write_anchor

    write_anchor(
        book,
        {
            "境界链": chain
            or [
                {"序": 1, "名": "聚气"},
                {"序": 2, "名": "凝罡"},
            ],
            "越级规则": {},
            "战例账本": battles or [],
            "通胀记录": [],
        },
    )


def _settled_chapter(book: Path, chapter: int) -> None:
    path = book / "定稿" / "正文" / f"{chapter:04d}-战例.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("正文\n", encoding="utf-8")


def _rewrite_entry(path: str, **fields) -> None:
    text = Path(path).read_text(encoding="utf-8")
    head, _, body = text.partition("\n---\n")
    lines = ["---"]
    seen: set[str] = set()
    for line in head.splitlines()[1:]:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key in fields:
            lines.append(f"{key}: {fields[key]}")
            seen.add(key)
        else:
            lines.append(line)
    for key, value in fields.items():
        if key not in seen:
            lines.append(f"{key}: {value}")
    Path(path).write_text("\n".join(lines) + "\n---\n" + body.lstrip("\n"), encoding="utf-8")


class TestPowerInvariant:
    def test_missing_anchor_skips(self, book: Path):
        item = _check(book, "inv-3-power")
        assert item["status"] == "skip"

    def test_battle_with_settled_chapter_passes(self, book: Path):
        _write_anchor(book, battles=[{"章": 37, "胜负": "胜"}])
        _settled_chapter(book, 37)
        item = _check(book, "inv-3-power")
        assert item["status"] == "pass"

    def test_battle_missing_settled_chapter_fails(self, book: Path):
        _write_anchor(book, battles=[{"章": 37, "胜负": "胜"}])
        item = _check(book, "inv-3-power")
        assert item["status"] == "fail"
        assert "missing_settled_chapter" in _codes(item)

    def test_duplicate_realm_name_fails(self, book: Path):
        _write_anchor(
            book,
            chain=[{"序": 1, "名": "聚气"}, {"序": 2, "名": "聚气"}],
        )
        item = _check(book, "inv-3-power")
        assert item["status"] == "fail"
        assert "chain_invalid" in _codes(item)

    def test_non_integer_battle_chapter_fails(self, book: Path):
        _write_anchor(book, battles=[{"章": "abc", "胜负": "胜"}])
        item = _check(book, "inv-3-power")
        assert item["status"] == "fail"
        assert "invalid_battle_chapter" in _codes(item)


class TestPromiseInvariant:
    def test_no_entries_passes(self, book: Path):
        item = _check(book, "inv-4-promises")
        assert item["status"] == "pass"

    def test_recovered_without_or_before_planted_fails(self, book: Path):
        from data_modules.promise_ledger import create_entry

        created = create_entry(book, kind="伏笔", name="缺回收章", planted_chapter=20, due_chapter=80)
        _rewrite_entry(created["path"], 状态="已回收", 回收章=0)
        item = _check(book, "inv-4-promises")
        assert item["status"] == "fail"
        assert "recovered_without_chapter" in _codes(item)

        _rewrite_entry(created["path"], 状态="已回收", 回收章=10)
        item = _check(book, "inv-4-promises")
        assert item["status"] == "fail"
        assert "recovered_before_planted" in _codes(item)

    def test_open_with_recovered_chapter_fails(self, book: Path):
        from data_modules.promise_ledger import create_entry

        created = create_entry(book, kind="伏笔", name="open带回收", planted_chapter=12, due_chapter=80)
        _rewrite_entry(created["path"], 回收章=40)
        item = _check(book, "inv-4-promises")
        assert item["status"] == "fail"
        assert "open_with_recovered_chapter" in _codes(item)

    def test_voided_needs_journal_and_evolution_retcon(self, book: Path):
        from data_modules.author_journal import append_events
        from data_modules.promise_ledger import create_entry, update_status

        created = create_entry(book, kind="伏笔", name="作废线", planted_chapter=12, due_chapter=80)
        update_status(book, entry_id=created["id"], status="作废")
        item = _check(book, "inv-4-promises")
        assert item["status"] == "fail"

        append_events(
            book,
            [
                {
                    "actor": "author",
                    "action": "retcon",
                    "domain": "设定",
                    "path": "素材/定版/v01",
                    "change_kind": "structure",
                    "diff_stat": {"ins": 0, "del": 0},
                    "summary": "卷1 retcon",
                    "impact": [],
                }
            ],
        )
        item = _check(book, "inv-4-promises")
        assert item["status"] == "fail"
        assert "voided_missing_evolution_retcon" in _codes(item)

        evo = book / "演化"
        evo.mkdir(parents=True, exist_ok=True)
        (evo / "retcon-v01-test.json").write_text("{}", encoding="utf-8")
        item = _check(book, "inv-4-promises")
        assert item["status"] == "pass"

    def test_voided_missing_journal_retcon_fails(self, book: Path):
        from data_modules.promise_ledger import create_entry, update_status

        created = create_entry(book, kind="伏笔", name="缺journal", planted_chapter=12, due_chapter=80)
        update_status(book, entry_id=created["id"], status="作废")
        evo = book / "演化"
        evo.mkdir(parents=True, exist_ok=True)
        (evo / "retcon-v01-only.json").write_text("{}", encoding="utf-8")
        item = _check(book, "inv-4-promises")
        assert item["status"] == "fail"
        assert "voided_missing_journal_retcon" in _codes(item)


def _write_stale_fixture(root: Path, items: list[dict]) -> None:
    path = root / ".webnovel" / "stale.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": "stale/1", "items": items}, ensure_ascii=False),
        encoding="utf-8",
    )


class TestStaleAgeInvariant:
    def test_old_stale_without_since_chapter_is_warn(self, tmp_path: Path):
        import data_modules.invariant_check as invariant_check

        _write_stale_fixture(
            tmp_path,
            [{"target": "x", "since": "2026-09-01T00:00:00+08:00", "consumed": False}],
        )
        assert invariant_check.check_stale_age(tmp_path)["status"] == "warn"
        assert "unknown_stale_age" in _codes(invariant_check.check_stale_age(tmp_path))

    def test_stale_older_than_one_volume_fails(self, tmp_path: Path):
        import data_modules.invariant_check as invariant_check

        (tmp_path / "book.yaml").write_text("卷规模: 40\n", encoding="utf-8")
        _settled_chapter(tmp_path, 82)
        _write_stale_fixture(tmp_path, [{"target": "x", "since_chapter": 41, "consumed": False}])
        report = invariant_check.check_stale_age(tmp_path)
        assert report["status"] == "fail"
        assert report["findings"][0]["code"] == "stale_over_one_volume"

    def test_consumed_and_within_volume_pass(self, tmp_path: Path):
        import data_modules.invariant_check as invariant_check

        (tmp_path / "book.yaml").write_text("卷规模: 40\n", encoding="utf-8")
        _settled_chapter(tmp_path, 82)
        _write_stale_fixture(
            tmp_path,
            [
                {"target": "old", "since_chapter": 1, "consumed": True},
                {"target": "fresh", "since_chapter": 42, "consumed": False},
            ],
        )
        assert invariant_check.check_stale_age(tmp_path)["status"] == "pass"
