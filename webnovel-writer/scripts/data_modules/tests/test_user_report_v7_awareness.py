"""F5 回归：用户报告不得对纯 v7 书仓套 v6 合同标准。

与 F1（doctor）同类：`build_init_report` / `build_plan_report` 此前无条件按 v6 骨架与
`.story-system` 四份合同判缺，于是在写了 40 章的纯 v7 书上给出

    overall_status = needs_user
    must_handle × 4  code=mainline_ready=false
    面向作者的话：「这本书的写作档案还没就绪」
    next_action：「先运行 /webnovel-init 创建项目档案」

——**让作者去重新初始化一本已经写了 40 章的书**。这比噪音严重得多：它是一条看起来
可执行的错误指引。
"""

from __future__ import annotations

import json

import pytest

from data_modules.user_report import build_init_report, build_plan_report


def _v7_book(root, *, chapter: int = 1, with_master: bool = True, with_volume_outline: bool = True):
    """最小 v7 书仓：book.yaml + 六域骨架（+ 可选总纲 / 卷纲本章小节）。"""
    from data_modules.domain_contract import REQUIRED_DIRS, REQUIRED_FILES

    (root / "book.yaml").write_text('spec_version: "7.0"\n书名: 测试书\n', encoding="utf-8")
    for rel in REQUIRED_DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)
    for rel in REQUIRED_FILES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    if with_master:
        (root / "大纲" / "总纲.md").write_text("# 总纲\n", encoding="utf-8")
    if with_volume_outline:
        (root / "大纲" / "卷纲").mkdir(parents=True, exist_ok=True)
        (root / "大纲" / "卷纲" / "第01卷-详细大纲.md").write_text(
            f"## 第{chapter}章：起始\n\n- 目标：开篇\n", encoding="utf-8"
        )
    return root


def _v6_book(root):
    """最小 v6 书仓：state.json + v6 骨架，无 book.yaml。"""
    from data_modules.project_phase import INIT_REQUIRED_DIRS, INIT_REQUIRED_FILES

    for rel in INIT_REQUIRED_DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)
    for rel in INIT_REQUIRED_FILES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}" if path.suffix == ".json" else "", encoding="utf-8")
    return root


def _must_handle(report):
    return (report.get("issues") or {}).get("must_handle") or []


def _paths(report):
    return {item.get("path") for item in _must_handle(report)}


# --- build_init_report ---

def test_init_report_accepts_v7_skeleton(tmp_path):
    """v7 书仓的六域骨架齐备时，不该因缺 v6 骨架而报"档案没就绪"。"""
    _v7_book(tmp_path)

    report = build_init_report(tmp_path)

    assert report["overall_status"] != "needs_user", f"仍报未就绪：{_paths(report)}"
    assert ".story-system/MASTER_SETTING.json" not in _paths(report)
    assert not any(
        str(item.get("next_action", "")).find("/webnovel-init") >= 0
        for item in _must_handle(report)
    ), "对已就绪的 v7 书仓给出了「先运行 /webnovel-init」这种错误指引"


def test_init_report_flags_missing_v7_domain(tmp_path):
    """v7 书仓真的缺六域目录时，仍要如实报出来（别把闸门一起拆了）。"""
    import shutil

    from data_modules.domain_contract import REQUIRED_DIRS

    _v7_book(tmp_path)
    shutil.rmtree(tmp_path / REQUIRED_DIRS[0])

    report = build_init_report(tmp_path)

    assert report["overall_status"] == "needs_user"
    assert any(REQUIRED_DIRS[0] in str(p or "") for p in _paths(report))


def test_init_report_v6_repo_behaviour_unchanged(tmp_path):
    """v6 书仓仍按 v6 骨架判定——原行为不得被削弱。"""
    _v6_book(tmp_path)

    report = build_init_report(tmp_path)

    assert report["overall_status"] != "needs_user", f"v6 仓正常却报未就绪：{_paths(report)}"


# --- build_plan_report ---

def test_plan_report_does_not_demand_v6_contracts_on_v7_book(tmp_path):
    """v7 书仓不该被要求提供 .story-system 四份 v6 合同。"""
    _v7_book(tmp_path, chapter=5)

    report = build_plan_report(tmp_path, chapter=5)

    offending = {p for p in _paths(report) if ".story-system" in str(p)}
    assert not offending, f"仍按 v6 合同判缺：{offending}"


def test_plan_report_flags_missing_chapter_outline_on_v7_book(tmp_path):
    """v7 书仓缺本章章纲时，要用 v7 语境的措辞报出来（而不是 v6 合同那套）。"""
    _v7_book(tmp_path, chapter=5, with_volume_outline=False)

    report = build_plan_report(tmp_path, chapter=5)

    codes = {item.get("code") for item in _must_handle(report)}
    assert codes == {"v7 outline missing"}, f"实际: {codes}"
    assert report["overall_status"] == "needs_user"  # 总纲在，故不是 failed


def test_plan_report_accepts_v7_book_with_outline(tmp_path):
    """v7 书仓总纲 + 本章章纲齐备 → 不该报任何 must_handle。"""
    _v7_book(tmp_path, chapter=5)

    report = build_plan_report(tmp_path, chapter=5)

    assert not _must_handle(report), f"误报：{_paths(report)}"


def test_plan_report_v6_repo_still_demands_contracts(tmp_path):
    """守住反向：v6 书仓缺合同时必须照旧报出来。"""
    _v6_book(tmp_path)
    (tmp_path / "大纲" / "总纲.md").write_text("# 总纲\n", encoding="utf-8")

    report = build_plan_report(tmp_path, chapter=5)

    assert any(".story-system" in str(p) for p in _paths(report)), (
        "v6 书仓缺合同却不再报——把闸门拆了"
    )
