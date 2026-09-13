#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""webnovel.py v7-write 转发（阶段一 P1-2 / spec §4.1）：纯 v7 书仓直接按给定目录转发到 v7_write.main。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent

# 会让 project_locator 命中「上一级/家目录」的书项目环境变量：裸工作区测试必须清掉。
_ROOT_ENV_VARS = (
    "WEBNOVEL_PROJECT_ROOT",
    "WEBNOVEL_BOOK_ROOT",
    "CLAUDE_PROJECT_DIR",
    "ZCODE_PROJECT_DIR",
    "WEBNOVEL_ZCODE_HOME",
    "ZCODE_HOME",
    "WEBNOVEL_CLAUDE_HOME",
    "CLAUDE_HOME",
)


def _book(tmp_path: Path) -> Path:
    repo = tmp_path / "book"
    for rel in ("定稿/正文", "定稿/记忆/章摘要", "定稿/设定/名册", "工作区"):
        (repo / rel).mkdir(parents=True)
    (repo / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    (repo / "工作区" / "决策卡-0003.md").write_text(
        "# 决策卡 · 第0003章\n\n- title: 三\n- pov: 苏小白\n- 关键实体: 苏小白\n", encoding="utf-8"
    )
    return repo


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "webnovel.py"), "--project-root", str(repo), "v7-write", *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def _bare_env(tmp_path: Path) -> dict:
    """清掉书项目解析相关的环境变量，并指向一个空的 zcode/claude home。"""
    env = {k: v for k, v in os.environ.items() if k not in _ROOT_ENV_VARS}
    env["WEBNOVEL_ZCODE_HOME"] = str(tmp_path / "empty-home")
    return env


def _run_in_empty_workspace(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "webnovel.py"), *args],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(workspace), env=_bare_env(tmp_path),
    )


def test_v7_write_forwarding_pack(tmp_path):
    repo = _book(tmp_path)

    proc = _run(repo, "pack", "--chapter", "3")

    assert proc.returncode == 0, proc.stderr
    assert "OK v7-write pack chapter=3" in proc.stdout
    assert (repo / "工作区" / "上下文包-0003.md").is_file()


@pytest.mark.parametrize("flag", ["--help", "-h"])
@pytest.mark.parametrize("action", ["decision", "pack"])
def test_v7_write_action_help_needs_no_project_root(tmp_path, action, flag):
    """`v7-write <action> --help` 必须被 v7_write 自己的 argparse 接住：无需项目根、退出 0。"""
    proc = _run_in_empty_workspace(tmp_path, "v7-write", action, flag)

    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    assert "usage:" in proc.stdout, proc.stdout
    # `--repo` 只有 v7_write 自己的 parser 定义（外层入口用的是 `--project-root`），
    # 据此确认打印的是 v7_write 的帮助而不是外层统一入口的帮助。
    assert "--repo" in proc.stdout, proc.stdout
    assert "Traceback" not in proc.stderr


def test_v7_write_reports_unresolvable_root_without_traceback(tmp_path):
    """项目根解析失败时必须走 cmd_where 的诊断路径：干净 stderr + 退出码 1。"""
    proc = _run_in_empty_workspace(tmp_path, "v7-write", "pack", "--chapter", "41")

    assert proc.returncode == 1, (proc.stdout, proc.stderr)
    assert "还没有激活的书项目" in proc.stderr, proc.stderr
    assert "Traceback" not in proc.stderr, proc.stderr


@pytest.mark.parametrize(
    "argv",
    [
        ("style-domain", "fingerprint"),
        ("learn", "show"),
        ("domains", "check"),
        ("freeze", "freeze", "--volume", "1"),
        ("power", "check"),
    ],
)
def test_lenient_root_commands_report_diagnostic_without_traceback(tmp_path, argv):
    """同样使用宽松解析的 v7/v8 转发命令：解析失败一律诊断 + 退出 1，不得抛裸 traceback。"""
    proc = _run_in_empty_workspace(tmp_path, *argv)

    assert proc.returncode == 1, (proc.stdout, proc.stderr)
    assert "还没有激活的书项目" in proc.stderr, proc.stderr
    assert "Traceback" not in proc.stderr, proc.stderr


def test_v7_write_forwarding_settle_gate_exit_code(tmp_path):
    """转发不得吞掉 v7_write 的退出码 2（门禁拒绝）。"""
    import json

    repo = _book(tmp_path)
    (repo / "定稿" / "正文" / "0002-旧.md").write_text("---\n章号: 2\n---\n" + "夜" * 1200, encoding="utf-8")
    draft = repo / "工作区" / "草稿-0003.md"
    draft.write_text("# 三\n\n" + "夜" * 1200, encoding="utf-8")
    dj = tmp_path / "d.json"
    # hook_waiver 一并给值：本用例测的是「转发不吞退出码 2」且断言指向 review 门禁，
    # 钩子硬闸不该抢先成为拒绝原因（钩子闸自身在 test_v7_write.py 单测）。
    dj.write_text(
        json.dumps({"chapter": 3, "title": "三", "waiver": "t", "hook_waiver": "t"}, ensure_ascii=False),
        encoding="utf-8",
    )

    proc = _run(repo, "settle", "--chapter", "3", "--draft", str(draft), "--json", str(dj), "--summary", "s", "--no-commit")

    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert "review_results.json" in proc.stderr
