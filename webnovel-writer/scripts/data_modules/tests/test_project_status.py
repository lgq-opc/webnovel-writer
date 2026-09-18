#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path

from .test_project_phase import _make_contracts, _make_init_ready


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


_ensure_scripts_on_path()

from data_modules.project_status import (  # noqa: E402
    SCHEMA_VERSION,
    build_project_status,
    format_project_status,
)


def test_project_status_json_shape(tmp_path):
    _make_init_ready(tmp_path)
    _make_contracts(tmp_path, chapter=1)

    report = build_project_status(tmp_path)

    assert report["schema_version"] == SCHEMA_VERSION
    assert report["project"] == "测试书"
    assert report["phase"] == "chapter_contract_ready"
    assert report["target_chapter"] == 1
    assert report["next_action"] == "run /webnovel-write 1"
    assert report["quality_trend"]["available"] is False
    assert report["quality_trend"]["reason"] == "no_index_db"
    assert not (tmp_path / ".webnovel" / "index.db").exists()


def test_project_status_summary_is_short_and_machine_source_is_json(tmp_path):
    _make_init_ready(tmp_path)
    report = build_project_status(tmp_path)

    summary = format_project_status(report, "summary")
    payload = json.loads(format_project_status(report, "json"))

    assert "phase: init_ready" in summary
    assert "quality_trend: unavailable (no_index_db)" in summary
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["quality_trend"]["available"] is False


def test_project_status_handles_no_project():
    report = build_project_status(None)

    assert report["phase"] == "no_project"
    assert report["blocking"]
    assert report["quality_trend"]["available"] is False
    assert report["quality_trend"]["reason"] == "no_project"


def test_project_status_quality_trend_line_when_metrics_exist(tmp_path):
    from data_modules.config import DataModulesConfig
    from data_modules.index_manager import IndexManager, ReviewMetrics

    _make_init_ready(tmp_path)
    manager = IndexManager(DataModulesConfig.from_project_root(tmp_path))
    manager.save_review_metrics(
        ReviewMetrics(start_chapter=1, end_chapter=1, overall_score=80.0)
    )
    manager.save_review_metrics(
        ReviewMetrics(start_chapter=2, end_chapter=2, overall_score=70.0)
    )

    report = build_project_status(tmp_path)
    trend = report["quality_trend"]
    summary = format_project_status(report, "summary")

    assert trend["available"] is True
    assert trend["count"] == 2
    assert trend["latest_score"] == 70.0
    assert "quality_trend: 近2次审查均分" in summary
