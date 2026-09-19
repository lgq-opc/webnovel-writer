#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""素材画廊 / regen 画廊路径穿越加固的回归测试（2026-09-20，复审 P1-3 / P2-5）。

背景：material_intake.discard/adopt 与 regen_gallery 的 --key 此前未净化，
`materials discard --batch "../../../victim.txt"` 可删除书仓外任意文件
（并行审阅动态实证）。本文件锁死穿越负例 + 合法流不回归。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_modules.material_intake import adopt_entries, discard_batch, propose_entries
from data_modules.regen_gallery import save_version


def _make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "book"
    (root / ".webnovel").mkdir(parents=True)
    (root / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    return root


def _make_victim(tmp_path: Path) -> Path:
    victim = tmp_path / "victim.txt"
    victim.write_text("VICTIM\n", encoding="utf-8")
    return victim


# ---------------------------------------------------------------------------
# material_intake：discard / adopt 不得越出画廊
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "batch",
    [
        "../../../victim.txt",
        "victim.txt",
        "sub/ai-v1.csv",
        "C:/Windows/victim.txt",
        "..\\victim.txt",
        "ai-v999999.csv",  # 形态合法但不存在 → batch_missing
    ],
)
def test_discard_rejects_traversal_batches(tmp_path, batch):
    root = _make_repo(tmp_path)
    victim = _make_victim(tmp_path)

    report = discard_batch(root, batch=batch)

    assert report == {"ok": False, "error": "batch_missing", "batch": batch}
    assert victim.is_file()


@pytest.mark.parametrize("batch", ["../../../victim.txt", "sub/ai-v1.csv"])
def test_adopt_rejects_traversal_batches(tmp_path, batch):
    root = _make_repo(tmp_path)
    victim = _make_victim(tmp_path)

    report = adopt_entries(root, batch=batch)

    assert report == {"ok": False, "error": "batch_missing", "batch": batch}
    assert victim.is_file()


def test_discard_legit_batch_still_works(tmp_path):
    root = _make_repo(tmp_path)
    source = tmp_path / "candidates.csv"
    source.write_text(
        "表,id\n人设,nr001\n", encoding="utf-8"
    )
    propose = propose_entries(root, channel="AI归纳", file=source)
    assert propose["ok"], propose
    batch_file = root / "素材" / "regen" / propose["batch"]
    assert batch_file.is_file()

    report = discard_batch(root, batch=propose["batch"])

    assert report["ok"] is True
    assert not batch_file.is_file()


def test_adopt_legit_missing_batch_reports_missing(tmp_path):
    root = _make_repo(tmp_path)
    report = adopt_entries(root, batch="ai-v42.csv")
    assert report == {"ok": False, "error": "batch_missing", "batch": "ai-v42.csv"}


# ---------------------------------------------------------------------------
# regen_gallery：章纲 key 不得越出书仓
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["../x", "..\\x", "a/b", "C:/tmp/pwn", "..", ".", "~x", ""])
def test_regen_save_rejects_traversal_keys(tmp_path, key):
    root = _make_repo(tmp_path)
    with pytest.raises(ValueError):
        save_version(root, domain="章纲", key=key, content="# pwn\n")


def test_regen_adopt_target_stays_inside_repo(tmp_path):
    """合法 key 的 save→adopt 全链可用，写回目标落在 大纲/章纲/ 内。"""
    root = _make_repo(tmp_path)
    saved = save_version(root, domain="章纲", key="0001", content="# v1\n")
    assert saved["ok"] is True

    from data_modules.regen_gallery import adopt_version, list_versions

    report = adopt_version(root, domain="章纲", key="0001", version=int(saved["version"]))
    assert report["ok"] is True
    assert (root / "大纲" / "章纲" / "0001.md").is_file()
    assert list_versions(root, domain="章纲", key="0001")


def test_regen_cli_reports_invalid_key_without_traceback(tmp_path):
    """CLI 层：非法 key 走干净错误出口，退出 1，不吐 traceback。"""
    import subprocess
    import sys

    root = _make_repo(tmp_path)
    scripts = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(scripts / "webnovel.py"),
         "--project-root", str(root),
         "regen", "adopt", "--domain", "章纲", "--key", "../pwn", "--version", "1"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 1, (proc.stdout, proc.stderr)
    assert "invalid regen key" in proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr
    # 完整 JSON 负载可解析（text 模式下是 ERROR 行，这里验 json 模式）
    proc_json = subprocess.run(
        [sys.executable, "-X", "utf8", str(scripts / "webnovel.py"),
         "--project-root", str(root),
         "regen", "adopt", "--domain", "章纲", "--key", "../pwn", "--version", "1", "--format", "json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    payload = json.loads(proc_json.stdout)
    assert payload["ok"] is False
