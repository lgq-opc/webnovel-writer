#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""webnovel.py v7-write 转发（阶段一 P1-2 / spec §4.1）：纯 v7 书仓直接按给定目录转发到 v7_write.main。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent


def _book(tmp_path: Path) -> Path:
    repo = tmp_path / "book"
    for rel in ("定稿/正文", "定稿/记忆/章摘要", "定稿/设定/名册", "工作区"):
        (repo / rel).mkdir(parents=True)
    (repo / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    return repo


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "webnovel.py"), "--project-root", str(repo), "v7-write", *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def test_v7_write_forwarding_pack(tmp_path):
    repo = _book(tmp_path)

    proc = _run(repo, "pack", "--chapter", "3")

    assert proc.returncode == 0, proc.stderr
    assert "OK v7-write pack chapter=3" in proc.stdout
    assert (repo / "工作区" / "上下文包-0003.md").is_file()


def test_v7_write_forwarding_settle_gate_exit_code(tmp_path):
    """转发不得吞掉 v7_write 的退出码 2（门禁拒绝）。"""
    import json

    repo = _book(tmp_path)
    (repo / "定稿" / "正文" / "0002-旧.md").write_text("---\n章号: 2\n---\n" + "夜" * 1200, encoding="utf-8")
    draft = repo / "工作区" / "草稿-0003.md"
    draft.write_text("# 三\n\n" + "夜" * 1200, encoding="utf-8")
    dj = tmp_path / "d.json"
    dj.write_text(json.dumps({"chapter": 3, "title": "三", "waiver": "t"}, ensure_ascii=False), encoding="utf-8")

    proc = _run(repo, "settle", "--chapter", "3", "--draft", str(draft), "--json", str(dj), "--summary", "s", "--no-commit")

    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert "review_results.json" in proc.stderr
