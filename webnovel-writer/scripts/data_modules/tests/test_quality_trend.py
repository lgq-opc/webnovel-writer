#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R17：quality_trend 短摘要不得在无库时建 index.db。"""

from data_modules.config import DataModulesConfig
from data_modules.index_manager import IndexManager, ReviewMetrics
from quality_trend_report import summarize_quality_trend


def test_summarize_quality_trend_without_db(tmp_path):
    trend = summarize_quality_trend(tmp_path)
    assert trend["available"] is False
    assert trend["reason"] == "no_index_db"
    assert not (tmp_path / ".webnovel" / "index.db").exists()


def test_summarize_quality_trend_with_two_scores(tmp_path):
    cfg = DataModulesConfig.from_project_root(tmp_path)
    manager = IndexManager(cfg)
    manager.save_review_metrics(ReviewMetrics(start_chapter=1, end_chapter=1, overall_score=88.0))
    manager.save_review_metrics(ReviewMetrics(start_chapter=2, end_chapter=2, overall_score=78.0))

    trend = summarize_quality_trend(tmp_path, last_n=10)
    assert trend["available"] is True
    assert trend["count"] == 2
    assert trend["latest_score"] == 78.0
    assert trend["delta"] == -10.0
    assert "近2次审查均分" in trend["line"]
    assert "最新 78.0" in trend["line"]
