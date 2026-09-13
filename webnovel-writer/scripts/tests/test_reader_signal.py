#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T25（M5）反馈闭合测试（reading_power 投影 + reader_signal）。

对应方案：03 R4（F-05/F-06）、08 T25。
验收契约：accepted 提交投影后 chapter_reading_power 自动有记录（生产端闭合）；
连续两章同型钩子后第三章 reader_signal 含差异化提醒（消费端闭合）；
index get-reader-signals 含 review_trend。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_scripts_dir = str(Path(__file__).resolve().parent.parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)


def _commit_payload(chapter: int, *, hook_type: str = "危机钩", hook_strength: str = "strong") -> dict:
    return {
        "meta": {"chapter": chapter, "status": "accepted"},
        "extraction_result": {
            "summary_text": f"---\nchapter: {chapter:04d}\nhook_type: \"{hook_type}\"\nhook_strength: \"{hook_strength}\"\n---\n## 剧情摘要\n摘要",
            "accepted_events": [],
        },
    }


@pytest.fixture()
def root(tmp_path: Path):
    from data_modules.config import DataModulesConfig

    cfg = DataModulesConfig.from_project_root(tmp_path)
    cfg.ensure_dirs()
    cfg.state_file.write_text("{}", encoding="utf-8")
    return tmp_path


class TestProduction:
    def test_writer_extracts_hook_from_summary_front_matter(self, root: Path):
        from data_modules.reading_power_projection import ReadingPowerProjectionWriter, extract_hook_fields

        assert extract_hook_fields({"hook_type": "悬念钩", "hook_strength": "weak"}) == ("悬念钩", "weak")
        writer = ReadingPowerProjectionWriter(root)
        result = writer.apply(_commit_payload(37))

        assert result["applied"] is True
        assert result["hook_type"] == "危机钩"

    def test_writer_skips_without_hook_fields(self, root: Path):
        from data_modules.reading_power_projection import ReadingPowerProjectionWriter

        payload = _commit_payload(38)
        payload["extraction_result"] = {"summary_text": "无 front matter 摘要", "accepted_events": []}
        result = ReadingPowerProjectionWriter(root).apply(payload)

        assert result["applied"] is False
        assert result["reason"] == "not_required"




class TestConsumption:
    def test_differentiation_reminder_after_two_same_hooks(self):
        from data_modules.reader_signal_builder import derive_differentiation_reminder

        recent = [
            {"chapter": 39, "hook_type": "危机钩"},
            {"chapter": 38, "hook_type": "危机钩"},
        ]
        reminder = derive_differentiation_reminder(recent)

        assert "危机钩" in reminder and "差异化" in reminder

    def test_no_reminder_for_varied_hooks(self):
        from data_modules.reader_signal_builder import derive_differentiation_reminder

        recent = [
            {"chapter": 39, "hook_type": "危机钩"},
            {"chapter": 38, "hook_type": "悬念钩"},
        ]
        assert derive_differentiation_reminder(recent) == ""


    def test_reader_signal_degrades_without_index_db(self, tmp_path: Path):
        from data_modules.reader_signal_builder import build_reader_signal

        signal = build_reader_signal(tmp_path)

        assert signal == {
            "recent_reading_power": [],
            "hook_type_usage": {},
            "review_trend": [],
            "differentiation_reminder": "",
        }


def _v7_book(tmp_path: Path, hooks: dict[int, str] | None = None) -> Path:
    """v7 书仓：book.yaml + 定稿/正文（钩子写在 front matter，settle 的产物形态）。"""
    repo = tmp_path / "v7book"
    (repo / "定稿" / "正文").mkdir(parents=True)
    (repo / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    for num, hook in (hooks or {}).items():
        (repo / "定稿" / "正文" / f"{num:04d}-章{num}.md").write_text(
            f"---\n章号: {num}\n标题: 章{num}\n钩子类型: {hook}\n钩子强度: 强\n---\n正文\n",
            encoding="utf-8",
        )
    return repo


class TestV7Consumption:
    """reader_signals 接通 Task 5（spec §3.5）：v7 书仓读 `.cache`；v6 书仓路径不变。"""

    def test_v7_repo_reads_reading_power_from_cache(self, tmp_path: Path):
        from data_modules.reader_signal_builder import build_reader_signal

        signal = build_reader_signal(_v7_book(tmp_path, {1: "危机钩"}))

        assert signal["recent_reading_power"] == [
            {"chapter": 1, "hook_type": "危机钩", "hook_strength": "strong"}
        ]
        assert signal["hook_type_usage"] == {"危机钩": 1}
        assert signal["review_trend"] == []  # v7 无生产者，spec 列为非目标

    def test_v7_reminder_from_cached_hooks(self, tmp_path: Path):
        from data_modules.reader_signal_builder import build_reader_signal

        signal = build_reader_signal(_v7_book(tmp_path, {1: "危机钩", 2: "危机钩"}))

        assert "危机钩" in signal["differentiation_reminder"]

    def test_v7_repo_without_hooks_degrades_gracefully(self, tmp_path: Path):
        from data_modules.reader_signal_builder import build_reader_signal

        signal = build_reader_signal(_v7_book(tmp_path, {}))

        assert signal["recent_reading_power"] == []
        assert signal["differentiation_reminder"] == ""

    def test_v6_repo_still_reads_webnovel_index_db(self, tmp_path: Path):
        """反向守住：有 state.json 的 v6 书仓不得改走 .cache，仍读 .webnovel/index.db。"""
        import json

        from data_modules.config import DataModulesConfig
        from data_modules.index_manager import ChapterReadingPowerMeta, IndexManager
        from data_modules.reader_signal_builder import build_reader_signal

        repo = tmp_path / "v6book"
        (repo / ".webnovel").mkdir(parents=True)
        (repo / ".webnovel" / "state.json").write_text(
            json.dumps({"project_info": {"title": "旧书"}}, ensure_ascii=False), encoding="utf-8"
        )
        IndexManager(DataModulesConfig.from_project_root(repo)).save_chapter_reading_power(
            ChapterReadingPowerMeta(chapter=7, hook_type="信息钩", hook_strength="weak")
        )

        signal = build_reader_signal(repo)

        assert signal["recent_reading_power"][0]["hook_type"] == "信息钩"

    def test_cli_index_get_reader_signals_reads_cache_for_v7(self, tmp_path: Path):
        """CLI 派发：纯 v7 仓的 `index get-reader-signals` 走 .cache，不再返回空。"""
        import json
        import subprocess

        repo = _v7_book(tmp_path, {1: "危机钩"})
        scripts = Path(__file__).resolve().parent.parent

        proc = subprocess.run(
            [
                sys.executable, "-X", "utf8", str(scripts / "webnovel.py"),
                "--project-root", str(repo),
                "index", "get-reader-signals", "--limit", "5", "--last-n", "20",
            ],
            capture_output=True, text=True, encoding="utf-8",
        )

        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        payload = json.loads(proc.stdout)
        assert payload["data"]["recent_reading_power"][0]["hook_type"] == "危机钩"
