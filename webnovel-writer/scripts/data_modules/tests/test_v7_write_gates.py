#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""settle 三门禁（v8-gap-review 阶段一 P1-2）：审查 / 文笔 / 素材引用 + --force-review-bypass 留痕。

spec：docs/cursor/阶段一-写前链路补全/2026-09-04-v7-write-chain-spec.md §4.3 §4.4
验收 #3「构造 blocking 审查 → settle 拒绝」；#4「引用不存在 ID → 报错」；#5 无审查文件 → 拒绝；#6 prose 门。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_scripts_dir = str(Path(__file__).resolve().parent.parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from v7_write import GateRejected, settle  # noqa: E402

# 经 prose_check 实测 flagged=[] 的净稿（段落长短错落、对白多为裸引号、无枚举/总结模板词）
CLEAN_BODY = "# 风暴前夜\n\n" + "\n\n".join(
    [
        "苏小白站在围墙上。风从北边来，带着咸腥味，吹得火把的光一歪一歪，把墙根下那些人的影子拉得很长，又忽然缩短。他数了数，能站起来的还有二十七个，能拿刀的不到二十。",
        "「今晚谁守夜？」",
        "没人答话。火堆噼啪响了一声。",
        "林知夏把地图铺开，用炭条圈出三个缺口。她的手指停在中间那个上面，敲了两下。",
        "「这里。」",
        "老周凑过来，指着东边那段矮墙，问为什么不是那里。",
        "「东边墙矮，可东边是水。兽群怕水。」她把炭条放下，抬头看了一眼天，「它们从北边来。」",
        "远处有兽群在跑，尘土像一道灰色的墙，压着地平线往南推。不是在追什么，是在躲。",
        "四十章前的那场风暴又回到苏小白眼前。那一次，城南先亮，亮得像白天，一眨眼全黑了，黑得连自己的手都看不见。黑里走了两天，靴子里灌满了沙。",
        "「北边。」他说。",
        "老六蹲下去摸了摸地面。土是热的。手心贴上去，再抬起来，掌纹里全是灰。",
        "「多久？」",
        "老六没抬头，把灰在裤腿上蹭掉。",
        "「天亮前。」",
        "林知夏把地图卷起来，塞进怀里，没有再看那三个缺口，径直走到火堆边，把一块干柴丢进去，火苗腾起来，照亮她半边脸，半边留在暗里。",
        "「那就别睡了。」",
    ]
    * 4
)
SAID_TAG_BODY = "# 风暴前夜\n\n" + "「走。」他说道。「不走。」她说道。\n" * 120


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    for rel in ("定稿/正文", "定稿/记忆/章摘要", "定稿/设定/名册", "工作区", "作者", "大纲/章纲", "素材/活", ".webnovel/tmp"):
        (repo / rel).mkdir(parents=True)
    (repo / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".cache/\n工作区/\n.webnovel/\n", encoding="utf-8")
    (repo / "定稿" / "正文" / "0041-旧章.md").write_text("---\n章号: 41\n---\n" + "夜" * 1500, encoding="utf-8")
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@l")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    (repo / "工作区" / "草稿-0042.md").write_text(CLEAN_BODY, encoding="utf-8")
    return repo


def _review(repo: Path, blocking: int, chapter: int = 42, nested: bool = False) -> None:
    payload: dict = {"chapter": chapter, "blocking_count": blocking, "issues_count": blocking, "issues": []}
    if nested:
        payload = {"chapter": chapter, "review_result": {"blocking_count": blocking, "issues_count": blocking}}
    (repo / ".webnovel" / "tmp" / "review_results.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _decision(**over) -> dict:
    d = {"chapter": 42, "title": "风暴前夜", "entities": ["苏小白"], "promises": [], "waiver": "测试", "contract": []}
    d.update(over)
    return d


def _settle(repo: Path, d: dict, **kw):
    commit = kw.pop("commit", False)
    return settle(repo, d, draft_path=repo / "工作区" / "草稿-0042.md", summary="s", commit=commit, **kw)


def _head(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout


def _journal_events(repo: Path) -> list[dict]:
    p = repo / "作者" / "journal.jsonl"
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


class TestReviewGate:
    def test_blocking_review_rejects_without_side_effects(self, tmp_path):
        """spec 验收 #3：「构造 blocking 审查 → settle 拒绝」。"""
        repo = _repo(tmp_path)
        _review(repo, blocking=1)
        head = _head(repo)

        with pytest.raises(GateRejected, match="blocking"):
            _settle(repo, _decision(), commit=True)

        assert not list((repo / "定稿" / "正文").glob("0042-*"))
        assert _head(repo) == head

    def test_missing_review_file_rejects(self, tmp_path):
        """spec 验收 #5：无审查文件 → 拒绝。"""
        repo = _repo(tmp_path)

        with pytest.raises(GateRejected, match="review_results.json"):
            _settle(repo, _decision())

    def test_review_for_other_chapter_counts_as_missing(self, tmp_path):
        repo = _repo(tmp_path)
        _review(repo, blocking=0, chapter=41)

        with pytest.raises(GateRejected, match="章号不符"):
            _settle(repo, _decision())

    def test_nested_schema_accepted(self, tmp_path):
        repo = _repo(tmp_path)
        _review(repo, blocking=0, nested=True)

        result = _settle(repo, _decision())

        assert result["gates"]["review"]["blocking_count"] == 0

    def test_clean_review_passes_and_reports_gates(self, tmp_path):
        repo = _repo(tmp_path)
        _review(repo, blocking=0)

        result = _settle(repo, _decision())

        gates = result["gates"]
        assert gates["review"]["ok"] and gates["prose"]["ok"] and gates["materials"]["ok"]
        assert gates["bypassed"] is False


class TestBypass:
    def test_bypass_lets_blocking_through_with_traces(self, tmp_path):
        """spec 验收 #3 后半：bypass 放行且 front matter 含「审查绕过」、journal 含事件。"""
        repo = _repo(tmp_path)
        _review(repo, blocking=2)

        result = _settle(repo, _decision(), commit=True, force_review_bypass="作者要求先发再修")

        text = (repo / "定稿" / "正文" / "0042-风暴前夜.md").read_text(encoding="utf-8")
        assert "审查绕过: 作者要求先发再修" in text
        events = [e for e in _journal_events(repo) if "审查绕过" in e.get("summary", "")]
        assert events, "journal 必须留痕"
        assert events[0]["actor"] == "author" and events[0]["action"] == "settle" and events[0]["domain"] == "正文"
        assert "blocking=2" in events[0]["summary"]
        assert result["gates"]["bypassed"] is True and result["gates"]["bypass_reason"] == "作者要求先发再修"
        from data_modules.author_journal import validate_journal

        assert validate_journal(repo) == []

    def test_bypass_requires_non_empty_reason(self, tmp_path):
        repo = _repo(tmp_path)
        _review(repo, blocking=1)

        with pytest.raises(ValueError, match="理由"):
            _settle(repo, _decision(), force_review_bypass="   ")

    def test_no_bypass_trace_when_gates_were_green(self, tmp_path):
        repo = _repo(tmp_path)
        _review(repo, blocking=0)

        result = _settle(repo, _decision(), force_review_bypass="多余的理由")

        text = (repo / "定稿" / "正文" / "0042-风暴前夜.md").read_text(encoding="utf-8")
        assert "审查绕过" not in text, "门禁本来就绿，不写绕过痕迹"
        assert result["gates"]["bypassed"] is False
        assert not [e for e in _journal_events(repo) if "审查绕过" in e.get("summary", "")]


class TestProseGate:
    def test_flagged_prose_rejects(self, tmp_path):
        """spec 验收 #6：构造 said tag 超阈值净稿 → 拒绝。"""
        repo = _repo(tmp_path)
        _review(repo, blocking=0)
        (repo / "工作区" / "草稿-0042.md").write_text(SAID_TAG_BODY, encoding="utf-8")

        with pytest.raises(GateRejected, match="文笔"):
            _settle(repo, _decision())

    def test_flagged_prose_bypassed_with_reason(self, tmp_path):
        repo = _repo(tmp_path)
        _review(repo, blocking=0)
        (repo / "工作区" / "草稿-0042.md").write_text(SAID_TAG_BODY, encoding="utf-8")

        result = _settle(repo, _decision(), force_review_bypass="风格化重复，作者认可")

        assert result["gates"]["prose"]["ok"] is False and result["gates"]["bypassed"] is True


class TestMaterialGate:
    def test_unresolvable_ref_rejects_even_with_bypass(self, tmp_path):
        """spec 验收 #4：「引用不存在 ID → 报错」且 bypass 不放行。"""
        repo = _repo(tmp_path)
        _review(repo, blocking=0)

        with pytest.raises(GateRejected, match="X-999"):
            _settle(repo, _decision(material_refs=["X-999"]), force_review_bypass="想绕")

    def test_refs_from_chapter_card_are_checked_too(self, tmp_path):
        repo = _repo(tmp_path)
        _review(repo, blocking=0)
        (repo / "大纲" / "章纲" / "0042.md").write_text('---\n章号: 42\n素材引用: ["桥段:Q-404"]\n---\n', encoding="utf-8")

        with pytest.raises(GateRejected, match="Q-404"):
            _settle(repo, _decision())

    def test_resolvable_ref_passes(self, tmp_path):
        repo = _repo(tmp_path)
        _review(repo, blocking=0)
        from data_modules.material_store import append_entries

        append_entries(repo, "桥段", [{"id": "Q-001", "名称": "夜袭", "分类": "冲突", "核心摘要": "夜里偷袭", "状态": "active"}])

        result = _settle(repo, _decision(material_refs=["桥段:Q-001"]))

        assert result["gates"]["materials"]["ok"] and result["gates"]["materials"]["resolved"] == ["桥段:Q-001"]


class TestSettleCli:
    def _run(self, repo: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(Path(_scripts_dir) / "v7_write.py"), "settle", "--repo", str(repo), *args],
            capture_output=True, text=True, encoding="utf-8",
        )

    def _common(self, tmp_path: Path, repo: Path) -> list[str]:
        dj = tmp_path / "d.json"
        dj.write_text(json.dumps(_decision(), ensure_ascii=False), encoding="utf-8")
        return ["--chapter", "42", "--draft", str(repo / "工作区" / "草稿-0042.md"), "--json", str(dj), "--summary", "s", "--no-commit"]

    def test_exit_2_on_gate_reject_with_json_detail(self, tmp_path):
        repo = _repo(tmp_path)
        _review(repo, blocking=1)

        proc = self._run(repo, *self._common(tmp_path, repo))

        assert proc.returncode == 2
        assert "blocking" in proc.stderr and '"review"' in proc.stderr

    def test_exit_0_with_bypass(self, tmp_path):
        repo = _repo(tmp_path)
        _review(repo, blocking=1)

        proc = self._run(repo, *self._common(tmp_path, repo), "--force-review-bypass", "作者要求")

        assert proc.returncode == 0, proc.stderr
        assert "OK v7-write settle chapter=42" in proc.stdout and "bypassed=True" in proc.stdout
