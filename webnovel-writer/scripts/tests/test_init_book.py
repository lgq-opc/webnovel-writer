"""v7-native 新书初始化（v6 退役 Phase 2 前置）。

背景（退役方案 §1.2「已知缺口」）：此前新书上 v7 的唯一入口是 `migrate_v6_to_v7`，
而它要求先存在一个 **v6 项目**——新书无处起步。`init_book` 补上这条缺口，且
**不产生任何 v6 遗留**。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from init_book import build_book_yaml, init_book  # noqa: E402


def _init(tmp_path, **kwargs):
    target = tmp_path / "新书"
    kwargs.setdefault("title", "测试新书")
    kwargs.setdefault("no_git", True)
    return target, init_book(target, **kwargs)


# --- book.yaml ---

def test_book_yaml_declares_spec_version_7(tmp_path):
    """book.yaml 是 v7 的唯一形态标志，spec_version 必须是 7.0。"""
    target, _ = _init(tmp_path)

    text = (target / "book.yaml").read_text(encoding="utf-8")
    assert 'spec_version: "7.0"' in text
    assert "书名: 测试新书" in text


def test_book_yaml_derives_per_chapter_words(tmp_path):
    """每章目标字数由 总字数/总章数 推导，卷规模取章数（上限 40）。"""
    target, _ = _init(tmp_path, target_words=2_000_000, target_chapters=600)

    text = (target / "book.yaml").read_text(encoding="utf-8")
    assert "每章目标字数: 3333" in text       # 2000000 // 600
    assert "卷规模: 40" in text               # 600 超过上限，取 40


def test_book_yaml_quotes_tricky_title():
    """标题含 `:`/引号时不能把 YAML 结构撑坏。"""
    text = build_book_yaml(title="标题: 带冒号", genre="都市")

    line = next(ln for ln in text.splitlines() if ln.startswith("书名:"))
    assert line.startswith('书名: "'), f"未加引号：{line}"


# --- 产出结构与 v6 隔离 ---

def test_init_creates_six_domain_skeleton(tmp_path):
    target, _ = _init(tmp_path)

    from data_modules.domain_contract import REQUIRED_DIRS, REQUIRED_FILES

    for rel in REQUIRED_DIRS:
        assert (target / rel).is_dir(), f"缺六域目录 {rel}"
    for rel in REQUIRED_FILES:
        assert (target / rel).is_file(), f"缺六域文件 {rel}"


def test_init_creates_finalized_dir(tmp_path):
    """`定稿/正文` 不在六域骨架里，但 v7 契约要求它存在（否则 doctor 一上来就 blocker）。"""
    target, _ = _init(tmp_path)

    assert (target / "定稿" / "正文").is_dir()


def test_init_produces_no_v6_leftovers(tmp_path):
    """新书不得带任何 v6 遗留——这正是相对「先建 v6 再迁移」的价值。"""
    target, _ = _init(tmp_path)

    assert not (target / ".story-system").exists(), "不该有 v6 的 .story-system"
    assert not (target / ".webnovel" / "state.json").exists(), "不该有 v6 的 state.json"


def test_init_seeds_materials(tmp_path):
    target, report = _init(tmp_path)

    assert report["seeded_materials"] > 0
    assert (target / "素材" / "活").is_dir()


# --- 与既有治理层打通 ---

def test_initialized_book_is_recognized_as_v7_by_doctor(tmp_path):
    """播种出来的书必须被 doctor 认成 v7 且**无 blocker**——这是「新书能起步」的判据。"""
    target, _ = _init(tmp_path)

    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS_DIR / "webnovel.py"),
         "--project-root", str(target), "doctor", "--format", "json"],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, proc.stderr

    import json
    payload = json.loads(proc.stdout)
    assert payload["phase"] == "v7_story_repo"

    blocking = [c for c in payload.get("checks", []) if c.get("severity") == "blocker"]
    assert blocking == [], f"新书不该有 blocker：{[c.get('id') for c in blocking]}"


def test_initialized_book_can_run_v7_chain(tmp_path):
    """在播种出的书上跑通 v7 写链前两步（decision → pack）。"""
    target, _ = _init(tmp_path)
    workspace = target / "工作区"
    workspace.mkdir(exist_ok=True)
    decision = workspace / "决策-1.json"
    decision.write_text('{"chapter": 1, "title": "开篇", "pov": "主角", "entities": ["主角"]}',
                        encoding="utf-8")

    for args in (["v7-write", "decision", "--json", str(decision)],
                 ["v7-write", "pack", "--chapter", "1", "--json", str(decision)]):
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", str(SCRIPTS_DIR / "webnovel.py"),
             "--project-root", str(target), *args],
            capture_output=True, encoding="utf-8", errors="replace",
        )
        assert proc.returncode == 0, f"{args[1]} 失败：{proc.stderr}"

    assert (workspace / "决策卡-0001.md").is_file()
    assert (workspace / "上下文包-0001.md").is_file()


# --- 安全边界 ---

def test_init_refuses_non_empty_target(tmp_path):
    """目标目录已有内容时拒绝——绝不在有内容的目录上播种。"""
    target = tmp_path / "已有书"
    target.mkdir()
    (target / "别动我.md").write_text("作者的东西", encoding="utf-8")

    with pytest.raises(FileExistsError, match="非空"):
        init_book(target, title="覆盖测试", no_git=True)

    assert (target / "别动我.md").read_text(encoding="utf-8") == "作者的东西"


def test_init_accepts_empty_existing_dir(tmp_path):
    """空目录是允许的（`mkdir -p` 后立刻初始化是常见用法）。"""
    target = tmp_path / "空目录"
    target.mkdir()

    init_book(target, title="空目录书", no_git=True)

    assert (target / "book.yaml").is_file()


def test_init_is_idempotent_by_refusal_not_overwrite(tmp_path):
    """重复初始化同一目录应被拒（而不是静默覆盖作者已开始的书）。"""
    target, _ = _init(tmp_path)

    with pytest.raises(FileExistsError):
        init_book(target, title="第二次", no_git=True)
