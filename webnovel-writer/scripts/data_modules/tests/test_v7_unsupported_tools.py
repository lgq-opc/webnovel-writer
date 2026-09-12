#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7 书仓下的工具面：v6 域工具须明示不支持（D-2 乙，2026-09-13）。

背景：rag / knowledge / context 三者的数据源在 v6 系统域（.webnovel/）。
v7 侧无替代（rag 无向量库、knowledge 无实体状态产物）或只有形态不同的等价物
（context → `v7-write pack`）。此前纯 v7 仓的表现是 Traceback（knowledge）
或 CONTEXT_BUILD_FAILED（context）——既不体面也不明确。

处置（D-2 乙 第一批）：返回 `{"status": "unsupported", "reason", "hint"}` 且退出码 0
——这是**预期的明确行为，不是故障**（冒烟脚本据此判 PASS 而非 BIZ，CI 基线才干净）。
"""

import json
import sys
from pathlib import Path

import pytest


def _make_v7_repo(root: Path) -> Path:
    """最小 v7 书仓：book.yaml + 六域之一。"""
    root.mkdir(parents=True, exist_ok=True)
    (root / "book.yaml").write_text("title: 测试书\n", encoding="utf-8")
    (root / "设定").mkdir(exist_ok=True)
    return root


def _make_v6_repo(root: Path) -> Path:
    """最小 v6 书仓：.webnovel/state.json。"""
    (root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")
    return root


def _run(monkeypatch, argv_tail, capsys):
    import data_modules.webnovel as webnovel_module

    monkeypatch.setattr(sys, "argv", ["webnovel", *argv_tail])
    with pytest.raises(SystemExit) as exc:
        webnovel_module.main()
    return exc.value.code, capsys.readouterr().out


_V6_DOMAIN_TOOLS = [
    ["rag", "search", "--query", "x"],
    ["knowledge", "query-entity-state", "--entity", "主角", "--at-chapter", "1"],
    ["context", "--chapter", "1"],
]


@pytest.mark.parametrize("tail", _V6_DOMAIN_TOOLS)
def test_v6_domain_tools_report_unsupported_on_v7_repo(monkeypatch, tmp_path, capsys, tail):
    repo = _make_v7_repo(tmp_path / "book")

    code, out = _run(monkeypatch, ["--project-root", str(repo), *tail], capsys)

    payload = json.loads(out)
    assert payload["status"] == "unsupported"
    assert payload["reason"] and payload["hint"]
    assert code == 0, "明示不支持是预期行为，不应以非 0 退出"


@pytest.mark.parametrize("tail", _V6_DOMAIN_TOOLS)
def test_v6_repo_does_not_report_unsupported(monkeypatch, tmp_path, capsys, tail):
    """v6 仓不得被这条闸门拦下（别把闸门拆了/误伤）。"""
    repo = _make_v6_repo(tmp_path / "book")

    try:
        _, out = _run(monkeypatch, ["--project-root", str(repo), *tail], capsys)
    except Exception:
        return  # v6 路径本身可能因缺数据报错，那不是本测试关心的

    assert '"unsupported"' not in out and "'unsupported'" not in out
