#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt 完整性静态校验。

验证 agents/*.md 和 skills/*/SKILL.md 的结构、引用、CLI 命令等，
不需要 LLM 调用，可加入 CI。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 基础路径
# ---------------------------------------------------------------------------

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
AGENTS_DIR = PLUGIN_ROOT / "agents"
SKILLS_DIR = PLUGIN_ROOT / "skills"
REFERENCES_DIR = PLUGIN_ROOT / "references"
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"

AGENT_FILES = sorted(AGENTS_DIR.glob("*.md"))
SKILL_FILES = sorted(SKILLS_DIR.glob("*/SKILL.md"))
ALL_PROMPT_FILES = AGENT_FILES + SKILL_FILES
AUTHOR_REPORT_SKILLS = (
    "webnovel-init",
    "webnovel-plan",
    "webnovel-write",
    "webnovel-review",
)
SUBAGENT_RUN_FIELDS = (
    '"status": "completed | partial | failed | skipped"',
    '"problems": []',
    '"auto_handled": []',
    '"needs_user_action": false',
    '"duration_ms": 0',
    '"outputs": []',
)
SUBAGENT_PROMPT_FILES = (
    "context-agent.md",
    "reviewer.md",
    "data-agent.md",
    "deconstruction-agent.md",
)

def _registered_cli_subcommands() -> set[str]:
    """**活**注册表：从 `data_modules/webnovel.py` 源码的顶层 `add_parser` 调用实提取。

    2026-09-13 修正：此处原为**手工维护的字面量集合**（注释却写「从 add_parser 提取」）。
    v6 退役 Phase 2 删掉 `chapter-commit` / `memory-contract` / `project-memory` /
    `projections` / `story-events` / `write-gate` 六个子命令后它没同步，后果是双重的：
    ① 这 6 个**死命令被白名单放过**——引导文件因此长期教模型调不存在的命令
    （2026-09-13 实测 `memory-contract` 退出码 2），而守卫全绿；
    ② 另有 21 个活命令漏收，正常的引用反而可能被误判。
    改为实提取后，源码增删子命令会自动反映到守卫上，这类漂移不再能隐身。
    """
    source = (SCRIPTS_DIR / "data_modules" / "webnovel.py").read_text(encoding="utf-8")
    match = re.search(r"^\s*(\w+)\s*=\s*parser\.add_subparsers\(", source, re.MULTILINE)
    assert match, "未找到顶层 add_subparsers —— 提取逻辑失效，守卫会退化为空集（比红灯更危险）"
    return set(re.findall(rf"{match.group(1)}\.add_parser\(\s*\"([^\"]+)\"", source))


REGISTERED_CLI_SUBCOMMANDS = _registered_cli_subcommands()


def test_registered_cli_subcommands_extracted_from_source():
    """守住提取本身：集合必须非空、含代表性活命令、且**不含**已知已删命令。

    没有这条，提取逻辑一旦静默失效（返回空集或全集）守卫就形同虚设——
    这正是上一个版本长期绿着却放任死引用的原因。
    """
    assert len(REGISTERED_CLI_SUBCOMMANDS) > 40, "提取结果过小，疑似正则失效"
    for live in ("v7-write", "knowledge", "foreshadow-scan", "book-init"):
        assert live in REGISTERED_CLI_SUBCOMMANDS, f"活命令 {live} 未被提取到"
    for removed in ("memory-contract", "chapter-commit", "projections", "story-events", "write-gate"):
        assert removed not in REGISTERED_CLI_SUBCOMMANDS, f"已删命令 {removed} 不得在注册表内"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_frontmatter(text: str) -> dict:
    """提取 YAML frontmatter 为 dict。"""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def _extract_referenced_paths(text: str, base_dir: Path) -> list[tuple[str, Path]]:
    """从 markdown 中提取被引用的文件路径（references/, skills/, agents/ 等）。

    返回 (raw_ref, resolved_path) 列表。
    """
    refs = []
    # 匹配 `references/xxx.md`、`../../references/xxx.md`、`skills/xxx` 等相对路径
    for m in re.finditer(r'[`"]((?:\.\./)*(?:references|skills|agents)/[^\s`"]+\.md)[`"]', text):
        raw = m.group(1)
        resolved = (base_dir / raw).resolve()
        refs.append((raw, resolved))
    # 匹配 references 段落中列出的路径（不带引号）
    for m in re.finditer(r'^- `((?:\.\./)*(?:references|skills|agents)/[^\s`]+\.md)`', text, re.MULTILINE):
        raw = m.group(1)
        resolved = (base_dir / raw).resolve()
        refs.append((raw, resolved))
    return refs


def _extract_cli_subcommands(text: str) -> list[str]:
    """从 prompt 中提取 webnovel.py 调用的子命令。"""
    cmds = set()
    for m in re.finditer(r'webnovel\.py["\s]+--project-root\s+[^\s]+\s+([a-z][\w-]*)', text):
        cmd = m.group(1)
        cmds.add(cmd)
    return sorted(cmds)


# ---------------------------------------------------------------------------
# 1. Frontmatter 完整性
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=lambda f: f.name)
def test_agent_frontmatter_complete(agent_file: Path):
    """每个 agent 必须有 name, description, tools。"""
    fm = _extract_frontmatter(_read_text(agent_file))
    assert "name" in fm, f"{agent_file.name}: 缺少 name"
    assert "description" in fm, f"{agent_file.name}: 缺少 description"
    assert "tools" in fm, f"{agent_file.name}: 缺少 tools"


@pytest.mark.parametrize("skill_file", SKILL_FILES, ids=lambda f: f.parent.name)
def test_skill_frontmatter_complete(skill_file: Path):
    """每个 skill 必须有 name, description。"""
    fm = _extract_frontmatter(_read_text(skill_file))
    assert "name" in fm, f"{skill_file.parent.name}: 缺少 name"
    assert "description" in fm, f"{skill_file.parent.name}: 缺少 description"


# ---------------------------------------------------------------------------
# 2. Agent 模板结构（≥4 段）
# ---------------------------------------------------------------------------

EXPECTED_AGENT_SECTIONS = [
    "1.",
    "2.",
    "3.",
    "4.",
]


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=lambda f: f.name)
def test_agent_template_structure(agent_file: Path):
    """每个 agent 至少包含 4 个编号段（§12.2 松绑：不强制 8 段，避免为过测试留空段）。"""
    text = _read_text(agent_file)
    missing = []
    for section in EXPECTED_AGENT_SECTIONS:
        # 匹配 "## 1. 身份与目标" 或 "## 2. 可用工具与脚本"（允许后缀）
        pattern = rf"^## {re.escape(section)}"
        if not re.search(pattern, text, re.MULTILINE):
            missing.append(section)
    assert not missing, f"{agent_file.name}: 缺少段落 {missing}"


# ---------------------------------------------------------------------------
# 3. 引用完整性
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prompt_file", ALL_PROMPT_FILES, ids=lambda f: f.name)
def test_all_references_exist(prompt_file: Path):
    """prompt 中引用的所有文件路径都必须真实存在。"""
    text = _read_text(prompt_file)
    base_dir = prompt_file.parent
    refs = _extract_referenced_paths(text, base_dir)
    missing = []
    for raw, resolved in refs:
        if not resolved.exists():
            missing.append(raw)
    assert not missing, f"{prompt_file.name}: 引用了不存在的文件 {missing}"


def test_setting_cards_are_optional_and_status_aware():
    """设定增强卡必须按需读取，并明确不能覆盖主链事实。"""
    context_text = _read_text(AGENTS_DIR / "context-agent.md")
    reviewer_text = _read_text(AGENTS_DIR / "reviewer.md")
    plan_text = _read_text(SKILLS_DIR / "webnovel-plan" / "SKILL.md")

    for text in (context_text, reviewer_text, plan_text):
        assert "设定集/增强设定/索引.md" in text
        assert "按需" in text

    for text in (context_text, plan_text):
        assert "规划设定" in text
        assert "待确认" in text

    assert "已确认事实" in reviewer_text
    assert "不能自行升级为正文事实" in reviewer_text


# ---------------------------------------------------------------------------
# 4. CLI 命令有效性
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prompt_file", ALL_PROMPT_FILES, ids=lambda f: f.name)
def test_cli_commands_valid(prompt_file: Path):
    """prompt 中的 webnovel.py 子命令都必须在 CLI 注册表中。"""
    text = _read_text(prompt_file)
    cmds = _extract_cli_subcommands(text)
    # 排除已知例外（如 webnovel-review 的 workflow 命令待重构）
    skill_name = prompt_file.parent.name
    exceptions = _KNOWN_CLI_EXCEPTIONS.get(skill_name, set())
    invalid = [c for c in cmds if c not in REGISTERED_CLI_SUBCOMMANDS and c not in exceptions]
    assert not invalid, f"{prompt_file.name}: 使用了未注册的 CLI 子命令 {invalid}"


# ---------------------------------------------------------------------------
# 5. Review Schema 一致性
# ---------------------------------------------------------------------------

def test_review_schema_consistency():
    """reviewer.md 输出格式中的字段必须与 review_schema.py 定义匹配。"""
    reviewer_text = _read_text(AGENTS_DIR / "reviewer.md")

    # 从 reviewer.md 的 JSON 示例中提取 issue 字段
    issue_fields_in_prompt = set()
    json_block = re.search(r'"issues":\s*\[\s*\{([^}]+)\}', reviewer_text, re.DOTALL)
    if json_block:
        for m in re.finditer(r'"(\w+)":', json_block.group(1)):
            issue_fields_in_prompt.add(m.group(1))

    # 从 review_schema.py 提取 ReviewIssue 字段
    schema_path = SCRIPTS_DIR / "data_modules" / "review_schema.py"
    schema_text = _read_text(schema_path)
    schema_fields = set()
    in_review_issue = False
    for line in schema_text.splitlines():
        if "class ReviewIssue" in line:
            in_review_issue = True
            continue
        if in_review_issue:
            if line.strip().startswith("class ") or line.strip().startswith("def "):
                break
            m = re.match(r"\s+(\w+):\s+", line)
            if m:
                schema_fields.add(m.group(1))

    # reviewer prompt 中的字段应该是 schema 字段的子集
    assert issue_fields_in_prompt, "无法从 reviewer.md 提取 issue 字段"
    assert schema_fields, "无法从 review_schema.py 提取字段"
    extra = issue_fields_in_prompt - schema_fields
    assert not extra, f"reviewer.md 中有字段不在 review_schema.py 中: {extra}"
    assert "blocking_count" in reviewer_text
    assert "issues_count" in reviewer_text


# ---------------------------------------------------------------------------
# 6. 无残留引用（已删文件）
# ---------------------------------------------------------------------------

KNOWN_DELETED_FILES = [
    "step-1.5-contract.md",
    "step-3-review-gate.md",
    "step-5-debt-switch.md",
    "workflow-details.md",
    "checker-output-schema.md",
    "workflow_manager.py",
    "webnovel-resume",
    "golden_three_checker.py",
    "snapshot_manager.py",
]

_KNOWN_CLI_EXCEPTIONS = {}


@pytest.mark.parametrize("prompt_file", ALL_PROMPT_FILES, ids=lambda f: f.name)
def test_no_stale_references(prompt_file: Path):
    """不得引用已知已删除的文件。"""
    text = _read_text(prompt_file)
    found = [name for name in KNOWN_DELETED_FILES if name in text]
    assert not found, f"{prompt_file.name}: 残留引用已删除文件 {found}"


def test_webnovel_review_skill_uses_unified_reviewer_pipeline():
    """webnovel-review 必须与 webnovel-write 使用同一套 reviewer + review-pipeline 链路。"""
    skill_text = _read_text(SKILLS_DIR / "webnovel-review" / "SKILL.md")

    assert "`reviewer`" in skill_text
    assert "Use the Agent tool to run `webnovel-writer:reviewer`" in skill_text
    assert "subagent_type:" not in skill_text
    assert "review-pipeline" in skill_text
    assert ".webnovel/tmp/review_results.json" in skill_text
    assert ".webnovel/tmp/review_metrics.json" in skill_text

    for legacy_agent in (
        "consistency-checker",
        "continuity-checker",
        "ooc-checker",
        "reader-pull-checker",
        "high-point-checker",
        "pacing-checker",
    ):
        assert legacy_agent not in skill_text

    assert " workflow " not in skill_text


def test_active_skills_use_agent_tool_name_not_legacy_task():
    """Claude Code 2.1.63+ 将 Task 工具改名为 Agent；active skills 不应再声明 Task。"""
    for skill_file in SKILL_FILES:
        text = _read_text(skill_file)
        fm = _extract_frontmatter(text)
        allowed_tools = fm.get("allowed-tools", "")
        assert "Task" not in allowed_tools, f"{skill_file.parent.name}: allowed-tools 仍声明 Task"
        assert "Task 调用" not in text, f"{skill_file.parent.name}: 仍使用软性的 Task 调用描述"
        assert "必须通过 `Task`" not in text, f"{skill_file.parent.name}: 仍要求旧 Task 工具名"


def test_webnovel_write_skill_uses_explicit_agent_invocation_templates():
    """关键 subagent 必须经 Agent 工具按注册名 webnovel-writer:X 显式调用；不再用伪函数 subagent_type 块（plan §4.4.2/§8.4）。"""
    text = _read_text(SKILLS_DIR / "webnovel-write" / "SKILL.md")
    fm = _extract_frontmatter(text)

    assert "Agent" in fm.get("allowed-tools", "")
    # v6 退役 Phase 1（2026-09-10）：写链只保留 reviewer（强制，审查步）与可选的
    # context-agent（起草决策 JSON）。data-agent 属 v6 写链——v7 由 settle 自行落账，
    # 故不再要求、且不应出现，否则会误导模型去调一个本链不存在的步骤。
    for subagent in ("reviewer", "context-agent"):
        assert f"webnovel-writer:{subagent}" in text, f"缺少 {subagent} 的注册名显式调用"
    assert "webnovel-writer:data-agent" not in text, "v6 的 data-agent 不该出现在 v7 写链"
    assert "subagent_type:" not in text, "不应再使用伪函数 subagent_type 调用块"
    assert "不得用主流程口头代替 subagent 输出" in text


@pytest.mark.parametrize("skill_name", AUTHOR_REPORT_SKILLS)
def test_main_skills_define_author_friendly_final_report_contract(skill_name: str):
    """四个主 Skill 必须提供作者友好的总状态 + 三段式最终报告契约。"""
    text = _read_text(SKILLS_DIR / skill_name / "SKILL.md")

    assert "作者友好最终报告契约" in text
    assert "总状态：已完成 / 部分完成 / 需要你处理 / 未完成" in text
    for section in (
        "一、产生的文件与完成情况",
        "二、过程中遇到的问题与异常耗时",
        "三、下一步建议",
    ):
        assert section in text, f"{skill_name}: 缺少最终报告段落 {section}"
    for issue_type in ("已自动处理", "建议确认", "必须处理"):
        assert issue_type in text, f"{skill_name}: 缺少异常分类 {issue_type}"
    assert "任务化语言" in text
    assert "可复制命令" in text
    assert "/webnovel-doctor" in text
    assert "不写 token 统计" in text


def test_write_skill_final_report_covers_v7_artifacts():
    """写章最终报告必须覆盖 v7 写链的实际产物。

    v6 退役 Phase 1（2026-09-10）：原断言针对 v6 制品——`审查报告路径`、
    `fulfillment/disambiguation/extraction_result.json`、`.story-system/commits/*.commit.json`、
    `state / index / summary / memory / vector`、`备份状态`、`projection retry`。
    这些属于 v6 写链（已冻结、写路径不再走），故按 v7 制品改写而非删除整条守卫：
    仍然要求报告把**本链真实产出**逐项列全。
    """
    text = _read_text(SKILLS_DIR / "webnovel-write" / "SKILL.md")
    for required in (
        "正文文件路径",
        "决策卡与决策 JSON",
        "上下文包",
        "草稿",
        ".webnovel/tmp/review_results.json",
        "后置落账结果",
        "是否可以继续写下一章",
    ):
        assert required in text
    assert "最终状态不得写“已完成”" in text
    assert "--fast" in text and "--minimal" in text
    # v6 专有制品不应再出现在写章契约里（退役后仍写着会误导模型去调不存在的步骤）
    for retired in (
        ".story-system/commits/chapter_{NNN}.commit.json",
        "fulfillment_result.json",
        "备份状态",
    ):
        assert retired not in text, f"v6 制品 {retired} 仍留在写章契约里（Phase 1 已退役）"


def test_review_skill_final_report_covers_metrics_and_blocking_decision():
    """审查最终报告必须覆盖报告、metrics、blocking 数与用户裁决状态。"""
    text = _read_text(SKILLS_DIR / "webnovel-review" / "SKILL.md")
    for required in (
        "审查报告文件",
        ".webnovel/tmp/review_results.json",
        ".webnovel/tmp/review_metrics.json",
        "review_metrics",
        "阻断问题数量",
        "用户裁决状态",
        "如果无阻断，明确可以继续写作",
    ):
        assert required in text
    assert "有 blocking 问题且用户未选择处理策略" in text
    assert "最终状态为“需要你处理”" in text


def test_main_skills_record_subagent_run_summaries_for_agent_calls():
    """主 Skill 调用 Agent 后必须记录 SubagentRun 汇总，供最终报告使用。"""
    expected = {
        "webnovel-init": ("deconstruction-agent",),
        # v6 退役 Phase 1：写链只剩 reviewer（强制 Agent 调用）。context-agent 在 v7
        # 是可选步骤、data-agent 属 v6 写链，两者都不进 SubagentRun 强制集。
        "webnovel-write": ("reviewer",),
        "webnovel-review": ("reviewer",),
    }

    for skill_name, agents in expected.items():
        text = _read_text(SKILLS_DIR / skill_name / "SKILL.md")
        assert "SubagentRun" in text, f"{skill_name}: 缺少 SubagentRun 汇总契约"
        for field in SUBAGENT_RUN_FIELDS:
            assert field in text, f"{skill_name}: 缺少 SubagentRun 字段 {field}"
        for agent_name in agents:
            assert f'"name": "{agent_name}"' in text, (
                f"{skill_name}: 缺少 {agent_name} 的 SubagentRun name"
            )
    plan_text = _read_text(SKILLS_DIR / "webnovel-plan" / "SKILL.md")
    assert "SubagentRun" not in plan_text, "webnovel-plan 当前不调用 Agent，不应虚构 SubagentRun"


@pytest.mark.parametrize("agent_file_name", SUBAGENT_PROMPT_FILES)
def test_agents_expose_subagent_run_summary_signals_without_changing_outputs(agent_file_name: str):
    """Agent prompt 必须暴露可汇总信号，但不得把 SubagentRun 写入原始产物。"""
    text = _read_text(AGENTS_DIR / agent_file_name)

    assert "SubagentRun 可汇总信号" in text
    for field in ("`status`", "`problems`", "`auto_handled`", "`needs_user_action`", "`duration_ms`", "`outputs`"):
        assert field in text, f"{agent_file_name}: 缺少可汇总字段 {field}"
    assert "主流程" in text and "记录" in text

    if agent_file_name == "reviewer.md":
        assert "不要把 `SubagentRun` 写进 reviewer JSON" in text
    elif agent_file_name == "data-agent.md":
        assert "不要把 `SubagentRun` 写进三份 artifact" in text
    elif agent_file_name == "deconstruction-agent.md":
        assert "不要把 `SubagentRun` 写进 `init_reference_research` 顶层" in text
    elif agent_file_name == "context-agent.md":
        assert "不要把 `SubagentRun` JSON 写入任务书" in text


@pytest.mark.parametrize("skill_name", AUTHOR_REPORT_SKILLS)
def test_main_skills_define_author_friendly_progress_and_recovery_contract(skill_name: str):
    """四个主 Skill 必须有过程提示、少打扰确认、卡住恢复和日志边界。"""
    text = _read_text(SKILLS_DIR / skill_name / "SKILL.md")

    for required in (
        "作者友好过程提示与恢复契约",
        "过程提示",
        "少打扰确认策略",
        "有限选项",
        "卡住时必须说明",
        "卡点",
        "已完成内容",
        "恢复建议",
        ".webnovel/logs/run_last.log",
        "run-log",
        "user-report",
    ):
        assert required in text, f"{skill_name}: 缺少过程/恢复契约 {required}"
    assert "不直接输出原始 JSON" in text or "不输出原始 JSON" in text


def test_write_skill_progress_nodes_are_author_friendly_and_limited():
    """写章流程必须压缩到不超过 6 个作者可理解阶段。

    v6 退役 Phase 1（2026-09-10）：原断言查的是 v6 的「写章过程节点（最多 6 个）」
    与其六个 run-log 节点名——那套随 v6 写链一起退役。改为守护 v7 写链的六步
    （决策/包 → 起草 → 机检 → 审查 → 润色文笔 → settle），要求仍然一样：
    **步数 ≤6、面向作者、不出现内部机器词**。
    """
    text = _read_text(SKILLS_DIR / "webnovel-write" / "SKILL.md")
    marker = "## 执行流程"
    assert marker in text
    section = text[text.find(marker): text.find("## 作者友好过程提示与恢复契约")]
    steps = re.findall(r"^### (\d+)\. (.+)$", section, flags=re.MULTILINE)
    numbers = [int(n) for n, _ in steps]
    assert numbers == list(range(1, len(steps) + 1)), f"步骤编号不连续: {numbers}"
    assert 1 <= len(steps) <= 6, f"步骤数应 ≤6，实际 {len(steps)}"
    for forbidden in ("write-gate", "chapter-commit", "projection_status", "schema"):
        assert forbidden not in "\n".join(title for _, title in steps)
    for friendly in ("决策卡与上下文包", "起草", "机检", "审查", "润色与文笔检测", "settle"):
        assert any(friendly in title for _, title in steps), f"缺少作者友好步骤 {friendly}"


def test_write_skill_resume_contract_uses_runtime_ledger_and_confirmation_boundaries():
    """写章重复执行必须在覆盖风险处停下确认。

    v6 退役 Phase 1（2026-09-10）：原断言的 `run-ledger write-resume`、`可信断点`、
    `本章已 accepted` 等属 v6 台账（v7 写链不使用 run-ledger）。**但这条红线要守的
    东西没变——重复执行不得覆盖作者手改、遇到覆盖风险必须给有限选项**，故改为断言
    v7 的等价契约：崩溃断点看 `run_last.log`（CLI 自动落账），覆盖风险走确认边界。
    """
    text = _read_text(SKILLS_DIR / "webnovel-write" / "SKILL.md")
    for required in (
        "run_last.log",
        "文件覆盖风险",
        "不得覆盖作者手改",
        "有限选项",
    ):
        assert required in text, f"缺少 v7 断点/确认契约 {required}"


# v6 退役 Phase 1（2026-09-10）：原 `test_story_system_runtime_contract_commands_exist`
# 守护的是 v6 写链的运行时合同刷新（story-system --emit-runtime-contracts）。该步骤
# 随 v6 写链一起退役——**红线本身是有意移除的，不是丢失**：v7 书仓按设计不使用
# `.story-system`，写章前也不再刷新合同。故事系统相关 CLI 的守护仍由
# webnovel-plan / webnovel-query 等仍在 v6 面的技能承担。


def test_webnovel_write_skill_uses_settle_as_final_step():
    """v6 退役 Phase 1：落定主线由 v6 `chapter-commit`（Step 5）改为 v7 `v7-write settle`。

    红线要守的没变——**落定必须走唯一的 CLI 主线，不得让主流程直接写状态**。
    """
    text = (SKILLS_DIR / "webnovel-write" / "SKILL.md").read_text(encoding="utf-8")
    assert "v7-write settle" in text
    assert "chapter-commit" not in text, "v6 的 chapter-commit 不该再出现在 v7 写链"
    assert "state process-chapter" not in text


def test_webnovel_write_skill_commits_via_cli_not_bare_git_add():
    """v6 退役 Phase 1：v6 的 `webnovel.py backup` 子命令随写链退役；v7 由
    `v7-write settle` 做原子提交。**红线不变：不得裸 `git add .` / 主流程自己提交。**
    """
    text = (SKILLS_DIR / "webnovel-write" / "SKILL.md").read_text(encoding="utf-8")
    assert "webnovel.py" in text
    assert "v7-write settle" in text
    assert "git add ." not in text
    assert "git commit" not in text, "提交必须由 settle 完成，不得让主流程自己 commit"


def test_webnovel_query_skill_uses_v7_truth_sources():
    """v7 查询技能必须指向六域真源，而不是 v6 的合同树与已删的 memory-contract。

    2026-09-13 改写：原断言要求 `memory-contract load-context` 与 `.story-system/` **存在**，
    等于把 v6 模型锁进技能。而 `memory-contract` 已被 v6 退役 Phase 2 删除（实测退出码 2），
    于是技能长期在教模型调一个不存在的命令，且守卫全绿（注册表是硬编码快照，见上方说明）。
    新断言反向守住两件事：v7 真源必须在，已删命令不得再出现。
    """
    text = (SKILLS_DIR / "webnovel-query" / "SKILL.md").read_text(encoding="utf-8")
    # v7 真源与最窄工具
    assert "book.yaml" in text, "v7 书仓标志必须写明"
    assert "定稿/" in text
    assert ".cache/index.db" in text
    assert "setting-read" in text
    assert "foreshadow-scan" in text or "promise-ledger" in text
    # 不得再教模型调已删命令
    assert "memory-contract" not in text
    assert "project-memory" not in text
    # v7 的能力边界必须写明（不产逐章状态与关系，勿臆造）
    assert "不产" in text


def test_context_agent_uses_v7_pack_and_six_domains():
    """context-agent 的主入口是 v7 的 `v7-write pack`，真源是六域——不是 v6 合同树。

    2026-09-13 改写：原断言要求 `story_contracts`/`.story-system/`、`CHAPTER_COMMIT`/
    `chapter-commit`、`load-context` 三者齐备，全是 v6 写链概念；其中 `chapter-commit`
    与 `memory-contract`（load-context 的载体）均已删除。该 agent 在 v7 写链中会被调用，
    指引错了会直接影响写章行为。
    """
    text = (AGENTS_DIR / "context-agent.md").read_text(encoding="utf-8")
    assert "v7-write pack" in text, "主入口必须是 v7 的上下文包装配"
    assert "上下文包" in text
    assert "book.yaml" in text
    assert "定稿/" in text
    assert "memory-contract" not in text
    assert "chapter-commit" not in text


def test_context_agent_loads_fixed_guides_and_outputs_writer_brief():
    text = (AGENTS_DIR / "context-agent.md").read_text(encoding="utf-8")
    # core-constraints 和 anti-ai-guide 已内化为"写作铁律"段落
    assert "写作铁律" in text or "Anti-AI" in text
    assert "写作任务书" in text
    assert "Step 2 直写提示词" not in text
    assert "Context Contract" not in text


def test_agents_do_not_name_nonexistent_writing_dna_files():
    for filename in ("context-agent.md", "reviewer.md"):
        text = (AGENTS_DIR / filename).read_text(encoding="utf-8")
        assert "P20_WRITING_DNA" not in text
        assert "WRITING_DNA.md" not in text
        assert ".claude/rules/P20_" not in text


def test_data_agent_is_described_as_extraction_only_not_direct_write_mainline():
    text = (AGENTS_DIR / "data-agent.md").read_text(encoding="utf-8")
    assert "chapter-commit" in text
    assert "extraction_result.json" in text
    assert "planned_nodes" in text
    assert "missed_nodes" in text
    assert "pending" in text
    assert "event_id" in text
    assert "event_type" in text
    assert "subject" in text
    assert "直接写入 index.db 和 state.json" not in text
    for forbidden in (
        "RAG 向量索引",
        "observability",
        "场景索引已写入",
        "索引失败",
    ):
        assert forbidden not in text, f"data-agent.md 不应保留 projection 写入语义: {forbidden}"
    # data-agent 不得携带可运行的 chapter-commit 命令（commit 是主流程的事实提交入口，data-agent 只产 artifact）
    assert not re.search(r"webnovel\.py[^\n]+chapter-commit", text), (
        "data-agent.md 不应出现可运行的 webnovel.py ... chapter-commit 命令"
    )


# (已按 plan §12.2 退役) test_webnovel_write_data_agent_prompt_requires_extraction_schema：
# 该测试逐字要求主 Skill 写出 data artifact 的 schema 字段名，与判据一冲突。schema 字段保障已迁到
# data-agent.md 生产方（test_data_agent_is_described_as_extraction_only_not_direct_write_mainline）
# + precommit 负向用例（Task 7）。主 Skill 不再内联长 schema。


def test_dashboard_and_plan_skills_surface_story_runtime_mainline():
    dashboard_text = (SKILLS_DIR / "webnovel-dashboard" / "SKILL.md").read_text(encoding="utf-8")
    plan_text = (SKILLS_DIR / "webnovel-plan" / "SKILL.md").read_text(encoding="utf-8")
    assert "story-runtime/health" in dashboard_text
    assert ".story-system/" in plan_text


def test_webnovel_write_skill_routes_drafting_through_context_pack():
    """v6 退役 Phase 1：起草依据由 v6 的「写作任务书」改为 v7 的「上下文包」。

    红线要守的没变——**起草只能以链路上游产出的那份依据为准，不得自行拼凑**。
    """
    text = (SKILLS_DIR / "webnovel-write" / "SKILL.md").read_text(encoding="utf-8")
    assert "上下文包" in text
    assert "起草只以" in text and "为依据" in text
    assert "context-agent" in text
    assert "Step 0.5" not in text
    assert 'cat "${SKILL_ROOT}/../../references/shared/core-constraints.md"' not in text
    assert 'cat "${SKILL_ROOT}/references/anti-ai-guide.md"' not in text


def test_context_agent_and_write_skill_form_isolated_write_chain():
    context_text = (AGENTS_DIR / "context-agent.md").read_text(encoding="utf-8")
    skill_text = (SKILLS_DIR / "webnovel-write" / "SKILL.md").read_text(encoding="utf-8")

    assert "写作任务书" in context_text
    # v6 退役 Phase 1：写侧的依据产物由「写作任务书」改为「上下文包」；
    # context-agent 仍被引用（可选起草决策 JSON），故仍要求出现。
    assert "上下文包" in skill_text
    assert "context-agent" in skill_text
    assert "Context Contract" not in context_text
    assert "Step 2 直写提示词" not in context_text


def test_no_direct_state_writes_in_write_skill():
    """webnovel-write SKILL.md 中不应有 set-chapter-status 调用。"""
    text = (SKILLS_DIR / "webnovel-write" / "SKILL.md").read_text(encoding="utf-8")
    assert "state set-chapter-status" not in text, (
        "webnovel-write 中不应直接调用 state set-chapter-status，"
        "chapter_status 由 state_projection_writer 在 commit 时自动推进"
    )


def test_no_direct_state_writes_in_agents():
    """agents 目录中不应有直接写 state/index 的指令。"""
    for agent_file in AGENT_FILES:
        text = _read_text(agent_file)
        assert "state set-chapter-status" not in text, (
            f"{agent_file.name}: 不应直接调用 state set-chapter-status"
        )


def test_deconstruction_agent_preserves_init_handoff_and_boundaries():
    """reference deconstruction must remain extraction-only and init-scoped."""
    text = _read_text(AGENTS_DIR / "deconstruction-agent.md")

    assert "init_reference_research" in text
    assert ".webnovel/tmp/reference_analyses/<safe-title>/" not in text
    assert "不写任何文件" in text
    assert "不得写 `_progress.md`" in text
    assert "resume_state" in text
    assert "tools: Read, Grep, Bash" in text
    assert "快速模式" in text
    assert "深度模式" in text
    assert "黄金三章" in text
    assert "情节点" in text
    assert "质量门控" in text
    assert "不得凭记忆" in text
    assert "条件框架" in text
    assert "情绪链条" in text
    assert "核心梗边界" in text

    for field in (
        "reader_promise",
        "opening_hook_patterns",
        "cool_point_loops",
        "protagonist_patterns",
        "antagonist_pressure_patterns",
        "pacing_notes",
        "borrowable_structures",
        "do_not_copy",
        "differentiation_requirements",
        "init_candidates",
        "quality",
        "resume_state",
        "orphan_plot_fallback",
        "canon_contamination_warnings",
    ):
        assert f'"{field}"' in text

    for forbidden_path in (
        ".story-system/",
        "设定集/",
        "大纲/",
        "正文/",
        ".webnovel/",
    ):
        assert forbidden_path in text

    assert "不写 `idea_bank.json`" in text
    assert "用户确认后" in text
    assert "MIT License attribution" not in text


def test_webnovel_init_deconstruction_wiring_keeps_confirmation_gate():
    """init may consume only confirmed, transformed reference patterns."""
    text = _read_text(SKILLS_DIR / "webnovel-init" / "SKILL.md")

    assert "Use the Agent tool to run `webnovel-writer:deconstruction-agent`" in text
    assert "subagent_type:" not in text
    assert "Step 1.5：灵感来源询问" in text
    assert "进入故事核采集前" in text
    assert "不要默认拆书" in text
    assert "你这本书的灵感来源想从哪里开始" in text
    assert "init_reference_research" in text
    assert "init_reference_research JSON 对象" in text
    assert ".webnovel/tmp/reference_analyses/<safe-title>/" not in text
    assert "project_root=${PROJECT_ROOT" not in text
    assert "不写任何文件" in text
    assert "不得由 init 主流程口头替代拆解结果" in text
    assert "`quality`" in text
    assert "`quality.passed=false`" in text
    assert "`confidence < 0.85`" in text

    for handoff_field in (
        "reader_promise",
        "opening_hook_patterns",
        "cool_point_loops",
        "protagonist_patterns",
        "antagonist_pressure_patterns",
        "pacing_notes",
        "borrowable_structures",
        "differentiation_requirements",
        "init_candidates",
    ):
        assert handoff_field in text

    for forbidden_path in (
        "idea_bank.json",
        ".story-system",
        "设定集",
        "大纲",
        "正文",
        ".webnovel/state.json",
    ):
        assert forbidden_path in text

    assert "用户确认前" in text
    assert "Step 2-6 只能使用用户确认过、并已变形为本书差异化表达的模式" in text
    assert "汇总 Step 1.5 已确认的灵感来源" in text


# ---------------------------------------------------------------------------
# 7. A 类跨层红线：行为/契约级断言（Phase 0 守护）
#    这些断言守护「已实现」的业务红线，全部应为绿。优先断言结构不变量
#    （命令存在/顺序、节点 schema、变量化的真实参数），不做脆弱的文案匹配。
# ---------------------------------------------------------------------------

# A 类红线 2：placeholder-scan 必须出现在 plan 与 write 两层的关键节点。
def test_placeholder_scan_runs_in_both_plan_and_write_skills():
    """红线 2：plan 与 write 都必须显式做占位符扫描。

    S9 后 write 侧经 `preflight --all` 合并扫描（占位符存在退出码 1），
    plan 侧仍为独立 `placeholder-scan` 调用。
    """
    plan_text = _read_text(SKILLS_DIR / "webnovel-plan" / "SKILL.md")
    write_text = _read_text(SKILLS_DIR / "webnovel-write" / "SKILL.md")
    plan_cmds = _extract_cli_subcommands(plan_text)
    assert "placeholder-scan" in plan_cmds, "webnovel-plan: 关键节点缺少 placeholder-scan CLI 调用"
    write_cmds = _extract_cli_subcommands(write_text)
    write_covers = (
        "placeholder-scan" in write_cmds
        or ("preflight" in write_cmds and "preflight --all" in write_text)
    )
    assert write_covers, "webnovel-write: 关键节点缺少占位符扫描（preflight --all 或 placeholder-scan）"


# A 类红线 3：story-system 章级刷新必须传入真实 CHAPTER_GOAL 变量，
# 不得把 {章纲目标} / 第N章章纲目标 这类占位文本当作 positional query。
# v6 退役 Phase 1（2026-09-10）：参数表移除 webnovel-write——story-system 章级
# 合同刷新属 v6 写链（v7 书仓按设计不使用 .story-system）。webnovel-plan 仍在
# v6 面且仍在刷新合同，红线继续守护。
@pytest.mark.parametrize("skill_name", ["webnovel-plan"])
def test_story_system_chapter_refresh_uses_real_goal_not_placeholder_query(skill_name: str):
    """红线 3：story-system 的 query 实参是 ${CHAPTER_GOAL} 变量，且禁占位文本写在命令里。"""
    text = _read_text(SKILLS_DIR / skill_name / "SKILL.md")
    # 命令必须用变量化的真实目标作为 query 实参
    assert 'story-system "${CHAPTER_GOAL}"' in text, (
        f"{skill_name}: story-system 未使用真实 ${{CHAPTER_GOAL}} 作为 query 实参"
    )
    # 占位 query 绝不能作为 story-system 的 positional 实参出现
    for placeholder in ("{章纲目标}", "第N章章纲目标"):
        assert f'story-system "{placeholder}"' not in text, (
            f"{skill_name}: story-system 不得把占位文本 {placeholder} 当作 query"
        )
    # 必须显式声明「禁止占位 query」这一约束（断言事实存在，不锁具体措辞）
    assert "{章纲目标}" in text and "第N章章纲目标" in text, (
        f"{skill_name}: 缺少对占位 query 的明确禁止说明"
    )


# A 类红线 4：story-system 章级刷新必须 --persist 且 --emit-runtime-contracts。
# v6 退役 Phase 1（2026-09-10）：参数表移除 webnovel-write——story-system 章级
# 合同刷新属 v6 写链（v7 书仓按设计不使用 .story-system）。webnovel-plan 仍在
# v6 面且仍在刷新合同，红线继续守护。
@pytest.mark.parametrize("skill_name", ["webnovel-plan"])
def test_story_system_chapter_refresh_persists_runtime_contracts(skill_name: str):
    """红线 4：章级 story-system 刷新必须同时 --persist 与 --emit-runtime-contracts。"""
    text = _read_text(SKILLS_DIR / skill_name / "SKILL.md")
    cmd_start = text.find('story-system "${CHAPTER_GOAL}"')
    assert cmd_start >= 0, f"{skill_name}: 缺少章级 story-system 调用"
    # 取该调用所在的命令行（到下一空行/段落结束），断言两个关键开关都在
    cmd_tail = text[cmd_start:cmd_start + 400]
    assert "--persist" in cmd_tail, f"{skill_name}: 章级 story-system 缺少 --persist"
    assert "--emit-runtime-contracts" in cmd_tail, (
        f"{skill_name}: 章级 story-system 缺少 --emit-runtime-contracts"
    )
    assert "--chapter" in cmd_tail, f"{skill_name}: 章级 story-system 缺少 --chapter"


# A 类红线 5：write-gate 三道闸门必须齐全且顺序为 prewrite→precommit→postcommit。
def test_write_skill_gates_ordered_check_then_settle():
    """v6 退役 Phase 1：v6 的 write-gate 三闸门（prewrite→precommit→postcommit）
    随写链退役。v7 的等价物是**两道顺序固定的闸门**：先 `v7-write check`（机检草稿），
    后 `v7-write settle`（落定门禁）。**红线不变：闸门必须在落定之前、且顺序不可乱。**
    """
    text = _read_text(SKILLS_DIR / "webnovel-write" / "SKILL.md")
    check = text.find("v7-write check")
    settle = text.find("v7-write settle")
    assert check >= 0, "缺少 v7-write check 机检闸门"
    assert settle >= 0, "缺少 v7-write settle 落定闸门"
    assert check < settle, "闸门顺序必须为 机检(check) → 落定(settle)"


# A 类红线 7：reviewer 原始 JSON 必须经 review-pipeline --save-metrics 落库（write 与 review 两层）。
@pytest.mark.parametrize("skill_name", ["webnovel-review"])
def test_review_pipeline_persists_metrics_in_review_chain(skill_name: str):
    """红线 7：reviewer JSON 经 review-pipeline --save-metrics 落库。

    v6 退役 Phase 1（2026-09-10）：从参数里移除 `webnovel-write`——review-pipeline
    属 v6 写链（写审查报告到 `审查报告/` 并落 index.db metrics），v7 的 settle 直接读
    `.webnovel/tmp/review_results.json`，不经过它。**红线未撤销**：`webnovel-review`
    这条路径仍在 v6 面且仍在跑，继续守护。
    """
    text = _read_text(SKILLS_DIR / skill_name / "SKILL.md")
    cmds = _extract_cli_subcommands(text)
    assert "review-pipeline" in cmds, f"{skill_name}: 缺少 review-pipeline CLI 调用"
    assert "--save-metrics" in text, f"{skill_name}: review-pipeline 未带 --save-metrics 落库"


# A 类红线 10：postcommit 必须验证 projection 五项；失败只 projections retry。
def test_write_skill_settle_reports_post_hooks():
    """v6 退役 Phase 1：v6 的五投影（state/index/summary/memory/vector）+ projections retry
    随写链退役。v7 settle 的等价后置落账是**素材轨迹 / 文风指纹 / 追读力**三项。

    **红线要守的没变：后置落账的结果必须如实进最终报告，不允许静默。**
    """
    text = _read_text(SKILLS_DIR / "webnovel-write" / "SKILL.md")
    assert "后置落账" in text, "缺少 v7 settle 后置落账说明"
    for hook in ("素材轨迹", "文风指纹", "追读力"):
        assert hook in text, f"缺少 v7 后置落账项 {hook}"
    assert "不得在最终报告中静默" in text
    assert "projections retry" not in text, "v6 的 projections retry 不该再出现在 v7 写链"


# A 类红线 12：plan 必须覆盖节拍表/时间线/结构化章纲节点/结构化总纲写回/状态更新。
def test_plan_skill_covers_outline_writeback_and_state_sync_contract():
    """红线 12：plan 的节拍表/时间线/章纲节点/总纲写回 JSON/master-outline-sync/update-state。"""
    text = _read_text(SKILLS_DIR / "webnovel-plan" / "SKILL.md")
    # 节拍表 / 时间线 输出物
    assert "大纲/第{volume_id}卷-节拍表.md" in text
    assert "大纲/第{volume_id}卷-时间线.md" in text
    # 结构化章纲节点
    for node in ("CBN", "CPNs", "CEN", "必须覆盖节点", "本章禁区"):
        assert node in text, f"plan 缺少结构化章纲节点标记 {node}"
    # 结构化总纲写回文件（不可从自由文本推断伏笔）
    assert "大纲/第{volume_id}卷-总纲写回.json" in text
    # 设定写回 + 状态同步命令
    cmds = _extract_cli_subcommands(text)
    assert "master-outline-sync" in cmds, "plan 缺少 master-outline-sync 写回命令"
    assert "update-state" in cmds, "plan 缺少 update-state 状态更新命令"


def test_plan_skill_writes_canonical_detailed_outline_path():
    """阶段二 P2-1：plan 详细大纲写规范路径，标题格式固定 ## 第N章：标题。"""
    text = _read_text(SKILLS_DIR / "webnovel-plan" / "SKILL.md")
    assert "大纲/卷纲/第{volume_id}卷-详细大纲.md" in text
    assert "## 第N章：标题" in text
    assert "大纲/第{volume_id}卷-详细大纲.md" not in text



# ---------------------------------------------------------------------------
# 8. B 类跨层新契约（plan §5.2-B / §4.5 写入所有权矩阵）
#    tools↔落盘一致性现状已满足 → 作通过型守护；
#    提交前只读 git diff 变更面校验现状缺失 → xfail，Task 5（Phase 1）落地后移除标记转正。
# ---------------------------------------------------------------------------

def _agent_tools(agent_name: str) -> list[str]:
    """解析某 agent frontmatter 的 tools 列表。"""
    fm = _extract_frontmatter(_read_text(AGENTS_DIR / f"{agent_name}.md"))
    return [t.strip() for t in fm.get("tools", "").split(",") if t.strip()]


# B 类红线（写入所有权 ↔ tools 一致，单一写入者）：
# data-agent 是三份 tmp artifact 的唯一写入者 → 必须持 Write；
# reviewer 持受限 Write（唯一允许写 review_results.json，B6 直写契约）→ 必须持 Write；
# context-agent/deconstruction-agent 只返回结果、由主流程落盘 → 不得持 Write。
def test_agent_write_ownership_matches_tools_frontmatter():
    """红线（写入所有权）：data-agent 与 reviewer 持受限 Write，其余两个 agent 不持 Write。"""
    assert "Write" in _agent_tools("data-agent"), (
        "data-agent 必须持有 Write（它是三份 tmp artifact 的唯一写入者）"
    )
    assert "Write" in _agent_tools("reviewer"), (
        "reviewer 必须持有受限 Write（唯一允许写 review_results.json，B6 直写契约）"
    )
    for agent_name in ("context-agent", "deconstruction-agent"):
        assert "Write" not in _agent_tools(agent_name), (
            f"{agent_name} 不得持有 Write（它只返回结果，由主流程落盘）"
        )


# v6 退役 Phase 1（2026-09-10）：原 `test_write_skill_has_readonly_git_diff_change_surface_check`
# 要求**主流程**在 chapter-commit 前跑只读 `git diff --name-status` / `git diff --check`。
# 该步骤属 v6 写链且已随写链退役——v7 的变更面由 `v7-write settle` 自己保证：
# 它用 `_git_add_settle_paths` 只 stage 本链产物后原子提交，主流程不再经手 git。
# 因此这条「让模型记得手动校验」的要求被**有意移除**，替换为下面这条针对 v7 的硬守护。


def test_write_skill_leaves_staging_and_commit_to_settle():
    """红线（变更面）：v7 写链的 stage/commit 由 settle 独占，主流程不得经手 git。"""
    text = _read_text(SKILLS_DIR / "webnovel-write" / "SKILL.md")
    assert "settle" in text
    assert "git add" not in text, "主流程不得自己 stage，变更面由 settle 保证"
    assert "git commit" not in text, "主流程不得自己 commit，落定由 settle 完成"


# B 类红线（写入所有权·prompt 层）：write/review 必须在文本层声明所有权，
# 与 frontmatter（test_agent_write_ownership_matches_tools_frontmatter）+ behavior eval（artifact_ownership）三处互守。
def test_write_review_skills_state_artifact_ownership():
    """reviewer 返回 JSON、主流程落盘 review_results.json、data-agent 唯一写入者。"""
    write_text = _read_text(SKILLS_DIR / "webnovel-write" / "SKILL.md")
    review_text = _read_text(SKILLS_DIR / "webnovel-review" / "SKILL.md")
    for name, text in (("webnovel-write", write_text), ("webnovel-review", review_text)):
        assert "主流程" in text and ".webnovel/tmp/review_results.json" in text, (
            f"{name}: 缺 reviewer→主流程落盘 review_results.json 的所有权说明"
        )
    # v6 退役 Phase 1：原先此处要求写章契约声明 `data-agent 唯一写入者` 与
    # `不直接写 state/index/summaries/memory/vectors/projection`——两者都是 v6 写链的
    # 所有权模型（data-agent 产三份 tmp artifact、主流程驱动五投影）。v7 写链里
    # 这些角色由 `v7-write settle` 承担，故不再要求；但**主流程不得自己落盘**这一
    # 所有权红线仍由上面那条 `主流程 ... .webnovel/tmp/review_results.json` 守住，
    # 且 frontmatter 与 behavior eval 两侧仍在守护 agent 的 Write 所有权。
    assert "主流程只检查文件存在与 schema" in write_text


# §9.3/§12.3：reviewer 删除 ReAct/思维链 元叙述后的正向守护（审查只给输出合同，不教它怎么想）。
def test_reviewer_has_no_react_meta_narrative():
    """reviewer.md 不得保留 ReAct/思维链 元叙述。"""
    text = _read_text(AGENTS_DIR / "reviewer.md")
    assert "ReAct" not in text, "reviewer 不应出现 ReAct 字样"
    assert "思维链" not in text, "reviewer 不应保留思维链元叙述"
