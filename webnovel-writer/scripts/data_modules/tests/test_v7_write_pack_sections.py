#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7_write 上下文包新 section（v8-gap-review 阶段一 P1-1）。

spec：docs/cursor/阶段一-写前链路补全/2026-09-04-v7-write-chain-spec.md §4.2
验收 #1「上下文包含 stale_notes、账本应推进项、author_model 三段」；#2「饱和测试三段保全」；#7「pack --json 后 entities 非空」。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import v7_write as v7w  # noqa: E402
from v7_write import build_context_pack  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _v7_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    for rel in ("定稿/正文", "定稿/记忆/章摘要", "定稿/设定/名册", "工作区", "作者", "大纲/卷纲", "大纲/章纲", "大纲/条目", "文风", "素材/活"):
        (repo / rel).mkdir(parents=True)
    (repo / "book.yaml").write_text("书名: 测试书\n主角: 苏小白\n卷规模: 40\n", encoding="utf-8")
    (repo / "定稿" / "正文" / "0041-旧章.md").write_text("---\n章号: 41\n标题: 旧章\n---\n" + "夜" * 1500, encoding="utf-8")
    (repo / "定稿" / "记忆" / "章摘要" / "0041.md").write_text("第41章摘要。", encoding="utf-8")
    (repo / "定稿" / "设定" / "名册" / "苏小白.md").write_text(
        "---\n正名: 苏小白\n别名: [苏哥]\n类型: 角色\n首现章: 1\n---\n主角卡正文：吃灾修行。\n", encoding="utf-8"
    )
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@l")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    return repo


def _decision(chapter: int = 42, **over) -> dict:
    d = {"chapter": chapter, "title": "风暴前夜", "pov": "苏小白", "entities": ["苏小白"], "promises": [], "waiver": "测试", "contract": []}
    d.update(over)
    return d


def _seed_stale(repo: Path) -> None:
    from data_modules.author_journal import mark_stale

    mark_stale(repo, target="大纲/卷纲/第01卷.md", reason="作者改了卷纲", impact=["0042"])


def _seed_ledger(repo: Path) -> None:
    from data_modules.promise_ledger import create_entry

    create_entry(repo, kind="伏笔", name="灭门真凶", planted_chapter=30, due_chapter=43, note="真凶身份")


def _seed_author_model(repo: Path) -> None:
    (repo / "作者" / "author_model.md").write_text("# author_model\n\n- 偏好：短句收尾\n", encoding="utf-8")


class TestNewSections:
    def test_three_governance_sections_present(self, tmp_path):
        """spec 验收 #1：「上下文包含 stale_notes、账本应推进项、author_model 三段」。"""
        repo = _v7_repo(tmp_path)
        _seed_stale(repo)
        _seed_ledger(repo)
        _seed_author_model(repo)

        md, stats = build_context_pack(repo, _decision())

        assert "## 作者修改未消费（stale）" in md and "作者改了卷纲" in md
        assert "## 本章应推进（承诺账本）" in md and "灭门真凶" in md
        assert "## 作者模型" in md and "短句收尾" in md
        assert stats["section_errors"] == {}

    def test_missing_domains_are_omitted_not_errors(self, tmp_path):
        repo = _v7_repo(tmp_path)

        md, stats = build_context_pack(repo, _decision())

        for title in ("作者修改未消费", "本章应推进", "作者模型", "文风锚点", "文风宪法", "读者信号", "素材装配", "本章章纲节选"):
            assert title not in md, title
        assert stats["section_errors"] == {}

    def test_style_contract_and_outline_excerpt(self, tmp_path):
        repo = _v7_repo(tmp_path)
        (repo / "文风" / "宪法.md").write_text("# 文风宪法\n\n一律用短句。\n", encoding="utf-8")
        (repo / "大纲" / "卷纲" / "第02卷-详细大纲.md").write_text(
            "# 第02卷\n\n## 第41章 旧章\n旧内容\n\n## 第42章 风暴前夜\n兽潮南逃，苏小白布防。\n\n## 第43章 次章\n别的\n",
            encoding="utf-8",
        )

        md, _ = build_context_pack(repo, _decision())

        assert "## 文风宪法" in md and "一律用短句" in md
        assert "## 本章章纲节选" in md and "兽潮南逃" in md and "别的" not in md

    def test_outline_excerpt_prefers_canonical_over_legacy_nested(self, tmp_path):
        repo = _v7_repo(tmp_path)
        (repo / "大纲" / "卷纲" / "第02卷.md").write_text("## 第42章：旧路径\n不应出现\n", encoding="utf-8")
        (repo / "大纲" / "卷纲" / "第02卷-详细大纲.md").write_text("## 第42章：风暴前夜\n规范路径正文\n", encoding="utf-8")

        md, _ = build_context_pack(repo, _decision())

        assert "规范路径正文" in md
        assert "不应出现" not in md

    def test_outline_excerpt_falls_back_to_legacy_nested(self, tmp_path):
        repo = _v7_repo(tmp_path)
        (repo / "大纲" / "卷纲" / "第02卷.md").write_text("## 第42章：风暴前夜\n仅旧 nested\n", encoding="utf-8")

        md, _ = build_context_pack(repo, _decision())

        assert "仅旧 nested" in md

    def test_protagonist_and_pov_discipline(self, tmp_path):
        repo = _v7_repo(tmp_path)

        md_same, _ = build_context_pack(repo, _decision(pov="苏小白"))
        md_other, _ = build_context_pack(repo, _decision(pov="林知夏"))

        assert "## 主角卡" in md_same and "吃灾修行" in md_same
        assert "## 视角纪律" not in md_same
        assert "## 视角纪律" in md_other and "林知夏" in md_other and "五感是唯一镜头" in md_other

    def test_materials_section_from_live_layer(self, tmp_path):
        repo = _v7_repo(tmp_path)
        from data_modules.material_store import append_entries

        append_entries(repo, "桥段", [{"id": "Q-001", "名称": "夜袭", "分类": "冲突", "核心摘要": "夜里偷袭", "状态": "active"}])

        md, _ = build_context_pack(repo, _decision())

        assert "## 素材装配" in md and "Q-001" in md

    def test_loader_exception_recorded_not_raised(self, tmp_path, monkeypatch):
        repo = _v7_repo(tmp_path)
        _seed_author_model(repo)

        def boom(_root):
            raise RuntimeError("坏了")

        monkeypatch.setattr(v7w, "_sec_author_model", boom)

        md, stats = build_context_pack(repo, _decision())

        assert "作者模型" not in md
        assert "author_model" in stats["section_errors"] and "坏了" in stats["section_errors"]["author_model"]

    def test_new_quotas_in_defaults(self):
        expected = {
            "stale_notes": 800, "pending_promises": 1000, "author_model": 800, "style_anchor": 500,
            "style_contract": 600, "reader_signal": 500, "materials": 1500, "outline_excerpt": 800,
            "protagonist": 600, "pov_discipline": 400,
        }
        for name, quota in expected.items():
            assert v7w.V7_SECTION_QUOTAS[name] == quota, name


class TestSaturation:
    def test_protected_sections_survive_budget_squeeze(self, tmp_path):
        """spec 验收 #2：「饱和测试三段保全」。"""
        repo = _v7_repo(tmp_path)
        _seed_stale(repo)
        _seed_ledger(repo)
        _seed_author_model(repo)
        (repo / "文风" / "宪法.md").write_text("宪" * 600, encoding="utf-8")
        for i in range(30):
            (repo / "定稿" / "设定" / "名册" / f"配角{i:02d}.md").write_text("---\n正名: x\n---\n", encoding="utf-8")

        md, stats = build_context_pack(repo, _decision(), total_budget=2500)

        assert stats["dropped_sections"], "预算 2500 必须触发整段丢弃"
        for title in ("## 决策卡", "## 作者修改未消费（stale）", "## 本章应推进（承诺账本）", "## 上一章结尾"):
            assert title in md, title
        assert not (set(stats["dropped_sections"]) & set(v7w.V7_PROTECTED_SECTIONS))
        assert stats["used"] <= 2500

    def test_drop_order_is_spec_subsequence(self, tmp_path):
        repo = _v7_repo(tmp_path)
        _seed_author_model(repo)
        (repo / "文风" / "宪法.md").write_text("宪" * 600, encoding="utf-8")

        _, stats = build_context_pack(repo, _decision(), total_budget=2500)

        dropped = stats["dropped_sections"]
        assert dropped, "预算 2500 必须触发丢弃"
        assert dropped == [s for s in v7w.V7_DROP_ORDER if s in dropped], "丢弃序列必须是 V7_DROP_ORDER 的子序列"


class TestPackCli:
    def _run(self, repo: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(Path(_scripts_dir) / "v7_write.py"), "pack", "--repo", str(repo), *args],
            capture_output=True, text=True, encoding="utf-8",
        )

    def test_pack_json_populates_entities(self, tmp_path):
        """spec 验收 #7：「pack --json 后 entities 非空」。"""
        repo = _v7_repo(tmp_path)
        dj = tmp_path / "d.json"
        dj.write_text(json.dumps(_decision(), ensure_ascii=False), encoding="utf-8")

        proc = self._run(repo, "--chapter", "42", "--json", str(dj))

        assert proc.returncode == 0, proc.stderr
        md = (repo / "工作区" / "上下文包-0042.md").read_text(encoding="utf-8")
        assert "## 本章实体（名册查询）" in md
        assert "苏小白" in md.split("## 本章实体（名册查询）", 1)[1]

    def test_pack_without_json_falls_back_to_card(self, tmp_path):
        repo = _v7_repo(tmp_path)
        v7w.write_decision_card(repo, _decision(entities=["苏小白", "林知夏"]))

        proc = self._run(repo, "--chapter", "42")

        assert proc.returncode == 0, proc.stderr
        md = (repo / "工作区" / "上下文包-0042.md").read_text(encoding="utf-8")
        assert "林知夏" in md.split("## 本章实体（名册查询）", 1)[1]
