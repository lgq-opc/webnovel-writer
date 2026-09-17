#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯 v7 书仓启动 Dashboard 必须明示不支持（2026-09-18 §3.1 第 1 条）。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _import_refuse():
    plugin_root = _plugin_root()
    if str(plugin_root) not in sys.path:
        sys.path.insert(0, str(plugin_root))
    from dashboard.server import refuse_v7_dashboard

    return refuse_v7_dashboard


def test_refuse_v7_dashboard_on_pure_v7_repo(tmp_path: Path):
    (tmp_path / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    (tmp_path / "设定").mkdir()

    reason = _import_refuse()(tmp_path)

    assert reason is not None
    assert "不支持纯 v7" in reason
    assert "doctor" in reason or "project-status" in reason


def test_refuse_v7_dashboard_allows_v6_repo(tmp_path: Path):
    (tmp_path / ".webnovel").mkdir()
    (tmp_path / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    assert _import_refuse()(tmp_path) is None


def test_dashboard_skill_states_v7_unsupported():
    text = (_plugin_root() / "skills" / "webnovel-dashboard" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "不支持纯 v7" in text
    assert "story-runtime/health" in text


def test_main_exits_before_start_on_v7(monkeypatch, tmp_path, capsys):
    (tmp_path / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    (tmp_path / "设定").mkdir()
    plugin_root = _plugin_root()
    if str(plugin_root) not in sys.path:
        monkeypatch.syspath_prepend(str(plugin_root))
    monkeypatch.setattr(
        sys,
        "argv",
        ["server", "--project-root", str(tmp_path), "--no-browser"],
    )
    from dashboard import server

    with pytest.raises(SystemExit) as exc:
        server.main()
    assert exc.value.code == 1
    assert "不支持纯 v7" in capsys.readouterr().err
