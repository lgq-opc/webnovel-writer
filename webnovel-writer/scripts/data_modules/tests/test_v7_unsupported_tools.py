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


_STILL_UNSUPPORTED = [
    ["rag", "search", "--query", "x"],
    ["context", "--chapter", "1"],
    # t-20260913-4a4d：status 由 status_reporter.py 实现，硬编码 state.json / 正文/。
    # 在 v7 仓上原本只打印「状态文件不存在」并退出 1（误导）；`project-status` 不受影响。
    ["status", "--focus", "urgency"],
]


@pytest.mark.parametrize("tail", _STILL_UNSUPPORTED)
def test_v6_domain_tools_report_unsupported_on_v7_repo(monkeypatch, tmp_path, capsys, tail):
    repo = _make_v7_repo(tmp_path / "book")

    code, out = _run(monkeypatch, ["--project-root", str(repo), *tail], capsys)

    payload = json.loads(out)
    assert payload["status"] == "unsupported"
    assert payload["reason"] and payload["hint"]
    assert code == 0, "明示不支持是预期行为，不应以非 0 退出"


@pytest.mark.parametrize("tail", _STILL_UNSUPPORTED)
def test_v6_repo_does_not_report_unsupported(monkeypatch, tmp_path, capsys, tail):
    """v6 仓不得被这条闸门拦下（别把闸门拆了/误伤）。"""
    repo = _make_v6_repo(tmp_path / "book")

    try:
        _, out = _run(monkeypatch, ["--project-root", str(repo), *tail], capsys)
    except Exception:
        return  # v6 路径本身可能因缺数据报错，那不是本测试关心的

    assert '"unsupported"' not in out and "'unsupported'" not in out


def test_project_status_not_in_unsupported_gate():
    """反回归（t-20260913-4a4d 查证结论）：`project-status` 走 `project_status.py`，
    实测在纯 v7 仓上码=0、正确输出 `phase: v7_story_repo`——**不受** `status_reporter.py`
    的 v6 硬编码影响。它与被闸的 `status` 只差一个词，最容易被顺手一起加进去，
    而一旦加了，`/webnovel:status`、doctor、session_start hook 三条链会一起断。
    """
    from data_modules import webnovel as webnovel_module

    assert "project-status" not in webnovel_module._V7_UNSUPPORTED


# ---------------------------------------------------------------------------
# knowledge：D-2 乙 收缩后改落点（不再整条不支持），但**能力边界必须如实声明**
# ---------------------------------------------------------------------------

def test_knowledge_on_v7_repo_returns_roster_scope(monkeypatch, tmp_path, capsys):
    repo = _make_v7_repo(tmp_path / "book")
    roster_dir = repo / "定稿" / "设定" / "名册"
    roster_dir.mkdir(parents=True)
    (roster_dir / "苏小白.md").write_text(
        "---\n正名: 苏小白\n别名: [\"小苏\"]\n类型: 角色\n首现章: 3\n---\n", encoding="utf-8"
    )

    code, out = _run(monkeypatch, [
        "--project-root", str(repo),
        "knowledge", "query-entity-state", "--entity", "苏小白", "--at-chapter", "10",
    ], capsys)

    assert code == 0, "knowledge 在 v7 仓不再是 unsupported"
    data = json.loads(out)["data"]
    assert data["found"] is True
    assert data["roster"]["name"] == "苏小白"
    assert data["roster"]["first_chapter"] == "3"
    assert "不产" in data["not_covered"], "必须如实声明未覆盖逐章状态与关系"
    assert data["where_to_look"], "必须给出取值范围指引"


def test_knowledge_on_v7_repo_reports_not_found(monkeypatch, tmp_path, capsys):
    """查不到时如实返回 found=false，不得伪造空状态对象。"""
    repo = _make_v7_repo(tmp_path / "book")

    code, out = _run(monkeypatch, [
        "--project-root", str(repo),
        "knowledge", "query-entity-state", "--entity", "查无此人", "--at-chapter", "1",
    ], capsys)

    assert code == 0
    data = json.loads(out)["data"]
    assert data["found"] is False
    assert data["roster"] is None


def test_knowledge_on_v7_repo_is_not_unsupported(monkeypatch, tmp_path, capsys):
    """回归守住：knowledge 已移出 _V7_UNSUPPORTED，不得再返回 unsupported。"""
    repo = _make_v7_repo(tmp_path / "book")

    _, out = _run(monkeypatch, [
        "--project-root", str(repo),
        "knowledge", "query-entity-state", "--entity", "主角", "--at-chapter", "1",
    ], capsys)

    assert '"unsupported"' not in out
