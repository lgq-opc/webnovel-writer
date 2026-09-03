# v7 写前链路补全 实施计划

> **执行者注意：** 按任务逐个实施，用 subagent-driven-development（推荐）或逐批人工执行。
> 步骤用 checkbox（`- [x]`）语法跟踪，完成即勾选。
> **执行记录（2026-09-04，Cursor）**：7 任务全部完成，commit `d645d70`（T1-3）/ `d404a29`（T4+T5a）/ `73b70a7`（T5b）/ `841831b`（T6）/ `06a9ed1`（prompt 完整性注册表，计划未预见）/ 本文件所在的收尾 docs commit（T7）。与计划的偏差：① 饱和测试预算 4000 不足以触发丢弃，改 2500；② `pov_discipline` 在 book.yaml 无 `主角` 时省略、且只注入 §一（计划原写全文，会恒截断并破坏 legacy `test_no_override_zero_change`）；③ `CLEAN_BODY` 夹具重写为 `prose_check` 实测 `flagged=[]` 的多段文本（计划初稿 6 句 ×12 被 lexicon / said_tag / variance 三项命中）；④ write SKILL 的 v7 段不得出现 `chapter-commit` / `write-gate` 字面（会打乱 v6 契约 eval 的 `find` 顺序）；⑤ `create_entry` 关键字为 `due_chapter`/`note`（计划预留了核对步骤）。

**目标：** 让 v7 书仓的写章链在写前拿到 v8 治理信号（10 个新 section）、在 settle 前过审查/文笔/素材引用三门禁，并让 `/webnovel:write` 能按 `book.yaml` 分流到这条链。
**架构：** 只改 `v7_write.py`（section 声明表 + `_run_gates`）、`webnovel.py`（一个转发子命令）、write SKILL（一个 v7 分支小节）与评测夹具；所有新 section 直接调用 v8 各域模块已有的读函数，v6 `context_manager` / write-gate 零改动。
**技术栈：** Python ≥3.10（`str | None` 语法已在仓内使用）、pytest + pytest-cov（`pytest.ini` 已配 `--cov-fail-under=80`）、git CLI。
**Spec：** `docs/cursor/阶段一-写前链路补全/2026-09-04-v7-write-chain-spec.md`（执行者先读 spec 再读本计划；Human 2026-09-04 批准，默认值按 spec）

## 全局约束

- 不修改 `data_modules/context_manager.py`、`write_gates/*`、任何 `test_context_manager*` / v6 测试（spec §7）。
- 每个新 section 读取包 `try/except` 并记 `stats["section_errors"][name]`，打包永不因单个域缺失失败（spec §4.2）。
- PROTECTED = `decision_card` / `prev_chapter_tail` / `stale_notes` / `pending_promises`（只截不丢）；DROP 顺序 = `materials → reader_signal → style_contract → outline_excerpt → protagonist → pov_discipline → style_anchor → author_model → roster → recent_summaries → entities`（spec §4.2 逐字）。
- 默认配额：stale_notes 800 / pending_promises 1000 / author_model 800 / style_anchor 500 / style_contract 600 / reader_signal 500 / materials 1500 / outline_excerpt 800 / protagonist 600 / pov_discipline 400（spec §4.2）。
- 门①：`<repo>/.webnovel/tmp/review_results.json` 缺失 → 拒绝；`blocking_count > 0` → 拒绝；顶层或 `review_result.` 嵌套两种 schema 都认（spec §8 风险 1；fantasy01 实样为顶层）。门②：`check_prose(...)["flagged"]` 非空 → 拒绝。门③：`material_refs` 任一 `resolve_ref` 失败 → 拒绝，**不可绕过**。
- 绕过只有 `--force-review-bypass "<理由>"`；放行后 front matter 加 `审查绕过: <理由>`，journal 追加事件（`actor=author, action=settle, domain=正文, change_kind=content`——四值都在 `author_journal.VALID_*` 白名单内，`validate_journal` 无需改）。
- 退出码：0 成功 / 2 门禁或机检拒绝 / 1 其他错误。
- 测试用 tmp 书仓，fantasy01 只做最终冒烟；中文路径全部 `-X utf8`。
- 提交：Conventional Commits，UTF-8 文件 + `git commit -F`；每任务至少一个 commit。

## 执行总览

| 序号 | 任务名 | 依赖 | 验证方式 |
|---|---|---|---|
| 1 | pack 新增 10 个 section（声明表 + 读函数 + 渲染 + section_errors） | — | `pytest data_modules/tests/test_v7_write_pack_sections.py`（spec 验收 #1 的三段断言） + 既有 `test_v7_write.py` 全绿 |
| 2 | 总预算超限的 PROTECTED / DROP 顺序 + `dropped_sections` | 依赖 Task 1 | 同文件 `TestSaturation`（spec 验收 #2） |
| 3 | `pack --json` 修 entities 恒空 + 决策卡回退解析 | 依赖 Task 1；可与 Task 4 并行 | `TestPackCli`（spec 验收 #7） |
| 4 | settle 三门禁 + `--force-review-bypass` 留痕 + `GateRejected` | — （可与 Task 1-3 并行） | `pytest data_modules/tests/test_v7_write_gates.py`（spec 验收 #3 #4 #5 #6）；legacy `TestSettle` 经夹具仍绿 |
| 5 | `v7_write.py settle` CLI（退出码）+ `webnovel.py v7-write` 转发 | 依赖 Task 3、Task 4 | `TestSettleCli` + `tests/test_webnovel_cli_v7_write.py` |
| 6 | SKILL v7 分支 + 行为评测用例 + `docs/guides/v7-write-path.md` 同步 | 依赖 Task 5 | `python run_behavior_evals.py --suite fast` 全 PASS；`validate_reference_wiring.py` drift=0 |
| 7 | fantasy01 冒烟 + 全量回归 + gap-review 阶段一勾选 + 交接 | 依赖 Task 1-6 | fantasy01 副本 `pack --chapter 42` 含三节标题；`pytest` ≥1455 passed 且 cov ≥80（spec 验收 #8） |

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `webnovel-writer/scripts/v7_write.py` | 修改 | 新 section 读函数 `_sec_*`、`V7_PACK_SECTIONS` 声明表、`V7_PROTECTED_SECTIONS` / `V7_DROP_ORDER`、`_run_gates`、`GateRejected`、`settle(..., force_review_bypass=)`、CLI `settle` / `pack --json` |
| `webnovel-writer/scripts/data_modules/webnovel.py` | 修改 | `v7-write` 转发子命令（REMAINDER 透传） |
| `webnovel-writer/scripts/data_modules/tests/test_v7_write_pack_sections.py` | 新增 | Task 1-3 测试 |
| `webnovel-writer/scripts/data_modules/tests/test_v7_write_gates.py` | 新增 | Task 4-5 测试 |
| `webnovel-writer/scripts/data_modules/tests/test_v7_write.py` | 修改（仅加夹具） | legacy `TestSettle` 加 `_gates_green` autouse 夹具（写 0-blocking 审查文件 + monkeypatch `check_prose` 全绿），测试本体不改 |
| `webnovel-writer/scripts/tests/test_webnovel_cli_v7_write.py` | 新增 | 转发子命令测试 |
| `webnovel-writer/skills/webnovel-write/SKILL.md` | 修改 | 「准备：预检」后加「书仓形态判定」+ 新小节「v7 书仓分支」 |
| `webnovel-writer/evals/fixtures/behavior/fast.json` | 修改 | 新 `skill_contract` 用例 `skill_write_v7_branch` |
| `docs/guides/v7-write-path.md` | 修改 | §3 补 settle CLI、门禁与 bypass 说明 |
| `docs/zcode/v8-gap-review-3rounds/README.md` | 修改 | 阶段一 P1-1 / P1-2 勾选 + 证据 |

---

## Task 1：pack 新增 10 个 section

**文件**：`v7_write.py`；新测试 `data_modules/tests/test_v7_write_pack_sections.py`

- [x] **写失败测试**（新文件，完整内容）：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7_write 上下文包新 section（v8-gap-review 阶段一 P1-1）。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

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
    (repo / "定稿" / "设定" / "名册" / "苏小白.md").write_text("---\n正名: 苏小白\n别名: [苏哥]\n类型: 角色\n首现章: 1\n---\n主角卡正文：吃灾修行。\n", encoding="utf-8")
    _git(repo, "init"); _git(repo, "config", "user.email", "t@l"); _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A"); _git(repo, "commit", "-m", "init")
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
    create_entry(repo, kind="伏笔", name="灭门真凶", planted_chapter=30, latest_chapter=45, description="真凶身份")


def _seed_author_model(repo: Path) -> None:
    (repo / "作者" / "author_model.md").write_text("# author_model\n\n- 偏好：短句收尾\n", encoding="utf-8")


class TestNewSections:
    def test_three_governance_sections_present(self, tmp_path):
        """spec 验收 #1：「上下文包含 stale_notes、账本应推进项、author_model 三段」。"""
        repo = _v7_repo(tmp_path)
        _seed_stale(repo); _seed_ledger(repo); _seed_author_model(repo)

        md, stats = build_context_pack(repo, _decision())

        assert "## 作者修改未消费（stale）" in md and "作者改了卷纲" in md
        assert "## 本章应推进（承诺账本）" in md and "灭门真凶" in md
        assert "## 作者模型" in md and "短句收尾" in md
        assert stats["section_errors"] == {}

    def test_missing_domains_are_omitted_not_errors(self, tmp_path):
        repo = _v7_repo(tmp_path)

        md, stats = build_context_pack(repo, _decision())

        for title in ("作者修改未消费", "本章应推进", "作者模型", "文风锚点", "文风宪法", "读者信号", "素材装配", "本章章纲节选"):
            assert title not in md
        assert stats["section_errors"] == {}

    def test_style_contract_and_outline_excerpt(self, tmp_path):
        repo = _v7_repo(tmp_path)
        (repo / "文风" / "宪法.md").write_text("# 文风宪法\n\n一律用短句。\n", encoding="utf-8")
        (repo / "大纲" / "卷纲" / "第02卷-详细大纲.md").write_text(
            "# 第02卷\n\n## 第41章 旧章\n旧内容\n\n## 第42章 风暴前夜\n兽潮南逃，苏小白布防。\n\n## 第43章 次章\n别的\n", encoding="utf-8")

        md, _ = build_context_pack(repo, _decision())

        assert "## 文风宪法" in md and "一律用短句" in md
        assert "## 本章章纲节选" in md and "兽潮南逃" in md and "别的" not in md

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
        for name, quota in {"stale_notes": 800, "pending_promises": 1000, "author_model": 800, "style_anchor": 500,
                            "style_contract": 600, "reader_signal": 500, "materials": 1500, "outline_excerpt": 800,
                            "protagonist": 600, "pov_discipline": 400}.items():
            assert v7w.V7_SECTION_QUOTAS[name] == quota
```

- [x] **跑它确认失败**：`python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_v7_write_pack_sections.py -q -p no:cacheprovider --no-cov` → 预期 `AttributeError`/`KeyError`（`_sec_author_model` / `section_errors` 不存在）。
- [x] **注意 `create_entry` 签名**：先 `python -X utf8 -c "import inspect,sys; sys.path.insert(0,'webnovel-writer/scripts'); from data_modules import promise_ledger as p; print(inspect.signature(p.create_entry))"`，按实际关键字名修正测试里 `_seed_ledger`（计划写的是 `planted_chapter/latest_chapter/description`，若名不同以实际为准；`pending_for_chapter` 判「即将到期」的窗口看 `foreshadow_scan` 的 due_soon 阈值，必要时把 `latest_chapter` 调到窗口内）。
- [x] **写最小实现**（`v7_write.py`）：

```python
# --- 顶部常量区：扩 V7_SECTION_QUOTAS ---
V7_SECTION_QUOTAS: dict[str, int] = {
    "decision_card": 2000, "recent_summaries": 1200, "entities": 3000, "roster": 1500,
    "prev_chapter_tail": 1200, "book_meta": 500,
    # v8-gap-review 阶段一 P1-1（spec §4.2）
    "stale_notes": 800, "pending_promises": 1000, "author_model": 800, "style_anchor": 500,
    "style_contract": 600, "reader_signal": 500, "materials": 1500, "outline_excerpt": 800,
    "protagonist": 600, "pov_discipline": 400,
}
V7_PROTECTED_SECTIONS = ("decision_card", "prev_chapter_tail", "stale_notes", "pending_promises")
V7_DROP_ORDER = ("materials", "reader_signal", "style_contract", "outline_excerpt", "protagonist",
                 "pov_discipline", "style_anchor", "author_model", "roster", "recent_summaries", "entities")
V7_SECTION_TITLES: dict[str, str] = {
    "decision_card": "决策卡", "recent_summaries": "前情摘要（近三章，v7_cache）", "entities": "本章实体（名册查询）",
    "roster": "名册清单", "prev_chapter_tail": "上一章结尾", "book_meta": "书级元信息",
    "stale_notes": "作者修改未消费（stale）", "pending_promises": "本章应推进（承诺账本）", "author_model": "作者模型",
    "style_anchor": "文风锚点（高分样本）", "style_contract": "文风宪法", "reader_signal": "读者信号（追读力）",
    "materials": "素材装配", "outline_excerpt": "本章章纲节选", "protagonist": "主角卡", "pov_discipline": "视角纪律",
}
V7_RENDER_ORDER = ("decision_card", "outline_excerpt", "pending_promises", "stale_notes", "recent_summaries",
                   "prev_chapter_tail", "entities", "protagonist", "pov_discipline", "roster", "materials",
                   "style_contract", "style_anchor", "author_model", "reader_signal", "book_meta")
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def _book_yaml_scalar(repo: Path, key: str) -> str:
    book_yaml = Path(repo) / "book.yaml"
    if not book_yaml.exists():
        return ""
    for raw in book_yaml.read_text(encoding="utf-8").splitlines():
        if raw.startswith(f"{key}:"):
            return raw.split(":", 1)[1].strip().strip('"').strip("'")
    return ""


# ---------- 新 section 读函数（每个只做一件事；异常由 build_context_pack 统一捕获） ----------

def _sec_stale_notes(repo: Path) -> list[dict[str, Any]]:
    from data_modules.author_journal import unconsumed_stale
    return unconsumed_stale(repo)


def _sec_pending_promises(repo: Path, chapter: int) -> dict[str, Any]:
    from data_modules.promise_ledger import pending_for_chapter
    if not (Path(repo) / "大纲" / "条目").is_dir():
        return {}
    out = pending_for_chapter(repo, chapter=chapter)
    return {"items": out.get("items") or [], "from_card": out.get("from_card") or []} if (out.get("items") or out.get("from_card")) else {}


def _sec_author_model(repo: Path) -> dict[str, str]:
    from data_modules.author_model import load_author_model_section
    sec = load_author_model_section(repo)
    return {k: v for k, v in sec.items() if v}


def _sec_style_anchor(repo: Path) -> dict[str, Any]:
    from data_modules.style_domain import build_style_anchor_section
    return build_style_anchor_section(repo)


def _sec_style_contract(repo: Path) -> str:
    from data_modules.style_domain import constitution_path
    p = constitution_path(repo)
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _sec_reader_signal(repo: Path) -> dict[str, Any]:
    from data_modules.reader_signal_builder import build_reader_signal
    sig = build_reader_signal(repo)
    return sig if any(sig.get(k) for k in ("recent_reading_power", "hook_type_usage", "review_trend", "differentiation_reminder")) else {}


def _sec_materials(repo: Path) -> dict[str, Any]:
    from data_modules.material_store import assemble_materials
    if not (Path(repo) / "素材").is_dir():
        return {}
    k = int(_book_yaml_scalar(repo, "素材装配条数") or 3)
    out = assemble_materials(repo, k=k)
    live = {t: [{"id": r.get("id"), "名称": r.get("名称"), "核心摘要": r.get("核心摘要")} for r in rows] for t, rows in (out.get("live") or {}).items()}
    return {"live": live, "frozen_version": out.get("frozen_version")} if live else {}


def _sec_outline_excerpt(repo: Path, decision: dict[str, Any], chapter: int) -> str:
    vol = int(decision.get("volume") or 0)
    if not vol:
        size = int(_book_yaml_scalar(repo, "卷规模") or 0)
        vol = (chapter - 1) // size + 1 if size else 1
    base = Path(repo) / "大纲" / "卷纲"
    for name in (f"第{vol:02d}卷-详细大纲.md", f"第{vol:02d}卷.md"):
        p = base / name
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        m = re.search(rf"^(#+)\s*第\s*0*{chapter}\s*章[^\n]*\n", text, re.M)
        if not m:
            continue
        level = len(m.group(1))
        rest = text[m.end():]
        nxt = re.search(rf"^#{{1,{level}}}\s", rest, re.M)
        return (m.group(0) + (rest[: nxt.start()] if nxt else rest)).strip()
    return ""


def _sec_protagonist(repo: Path) -> dict[str, Any]:
    name = _book_yaml_scalar(repo, "主角")
    if not name:
        return {}
    card = Path(repo) / "定稿" / "设定" / "名册" / f"{name}.md"
    return {"正名": name, "名册卡": card.read_text(encoding="utf-8")} if card.is_file() else {"正名": name}


def _sec_pov_discipline(repo: Path, decision: dict[str, Any]) -> dict[str, Any]:
    pov = str(decision.get("pov") or "").strip()
    protagonist = _book_yaml_scalar(repo, "主角")
    if not pov or (protagonist and pov == protagonist):
        return {}
    ref = _PLUGIN_ROOT / "references" / "shared" / "pov-management.md"
    rules = ref.read_text(encoding="utf-8") if ref.is_file() else ""
    return {"本章视角": pov, "主角": protagonist, "规则": rules}
```

在 `build_context_pack` 中，`sections["length_contract"] = {...}` 之后、配额应用之前插入：

```python
    # v8-gap-review 阶段一 P1-1：治理信号 section（读函数失败只记账不阻断）
    section_errors: dict[str, str] = {}
    loaders = {
        "stale_notes": lambda: _sec_stale_notes(repo),
        "pending_promises": lambda: _sec_pending_promises(repo, chapter),
        "author_model": lambda: _sec_author_model(repo),
        "style_anchor": lambda: _sec_style_anchor(repo),
        "style_contract": lambda: _sec_style_contract(repo),
        "reader_signal": lambda: _sec_reader_signal(repo),
        "materials": lambda: _sec_materials(repo),
        "outline_excerpt": lambda: _sec_outline_excerpt(repo, decision, chapter),
        "protagonist": lambda: _sec_protagonist(repo),
        "pov_discipline": lambda: _sec_pov_discipline(repo, decision),
    }
    for name, load in loaders.items():
        try:
            value = load()
        except Exception as exc:  # noqa: BLE001 - 单域失败不阻断打包
            section_errors[name] = f"{type(exc).__name__}: {exc}"
            continue
        if value:
            sections[name] = value
```

`stats` 加 `"section_errors": section_errors`。`_render_pack_markdown` 改为遍历 `V7_RENDER_ORDER` 并用 `V7_SECTION_TITLES`（删除函数内 `titles` 字典与硬编码元组）。

- [x] **跑测试**：同上命令 → 7 passed；再跑 `python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_v7_write.py -q --no-cov -p no:cacheprovider` → 既有全绿（`test_no_override_zero_change` 断言 `stats["sections"] == V7_SECTION_QUOTAS` 仍成立，因两边同源）。
- [x] **提交**：`feat(v7-write): 上下文包新增 10 个治理 section（stale/账本/作者模型/文风/读者信号/素材/章纲节选/主角/视角，P1-1）`

## Task 2：饱和时 PROTECTED / DROP 顺序

- [x] **写失败测试**（追加到 `test_v7_write_pack_sections.py`）：

```python
class TestSaturation:
    def test_protected_sections_survive_budget_squeeze(self, tmp_path):
        """spec 验收 #2：「饱和测试三段保全」。"""
        repo = _v7_repo(tmp_path)
        _seed_stale(repo); _seed_ledger(repo); _seed_author_model(repo)
        (repo / "文风" / "宪法.md").write_text("宪" * 600, encoding="utf-8")
        for i in range(30):
            (repo / "定稿" / "设定" / "名册" / f"配角{i:02d}.md").write_text("---\n正名: x\n---\n", encoding="utf-8")

        md, stats = build_context_pack(repo, _decision(), total_budget=4000)

        assert stats["dropped_sections"], "预算 4000 必须触发整段丢弃"
        for title in ("## 决策卡", "## 作者修改未消费（stale）", "## 本章应推进（承诺账本）"):
            assert title in md, title
        assert not (set(stats["dropped_sections"]) & set(v7w.V7_PROTECTED_SECTIONS))
        assert stats["used"] <= 4000

    def test_drop_order_is_spec_order(self, tmp_path):
        repo = _v7_repo(tmp_path)
        _seed_author_model(repo)
        (repo / "文风" / "宪法.md").write_text("宪" * 600, encoding="utf-8")

        _, stats = build_context_pack(repo, _decision(), total_budget=2500)

        dropped = stats["dropped_sections"]
        order = list(v7w.V7_DROP_ORDER)
        assert dropped == [s for s in order if s in dropped], "丢弃序列必须是 V7_DROP_ORDER 的子序列"
        assert stats["dropped_sections"] == [] if stats["sections_before"] == {} else True
```

- [x] **跑它确认失败**：`KeyError: 'dropped_sections'`。
- [x] **写最小实现**：把 `build_context_pack` 末尾的渲染/截断替换为：

```python
    effective_total = int(total_budget) if total_budget is not None else (book_budget["total"] or TOTAL_BUDGET_DEFAULT)
    dropped: list[str] = []
    md = _render_pack_markdown(chapter, sections)
    for name in V7_DROP_ORDER:
        if estimate_tokens(md) <= effective_total:
            break
        if name in sections and name not in V7_PROTECTED_SECTIONS:
            sections.pop(name)
            dropped.append(name)
            md = _render_pack_markdown(chapter, sections)
    used = estimate_tokens(md)
    if used > effective_total:
        md = md[: effective_total - 8] + "…（预算截断）"
        used = estimate_tokens(md)
    stats = {
        "used": used, "total_budget": effective_total, "sections_before": stats_before,
        "sections": dict(quotas_effective), "truncated_sections": truncated, "dropped_sections": dropped,
        "section_errors": section_errors,
        "budget_used_ratio": round(used / effective_total, 3) if effective_total else 1.0,
    }
    return md, stats
```

- [x] **跑测试** → 绿；`test_v7_write.py` 仍绿（`test_no_override_zero_change` 只断言 `truncated_sections == []`，不涉及 dropped）。
- [x] **提交**：`feat(v7-write): 总预算超限按 DROP 顺序整段丢弃，四个 PROTECTED section 只截不丢（P1-1）`

## Task 3：`pack --json` 修 entities 恒空

- [x] **写失败测试**（追加）：

```python
class TestPackCli:
    def _run(self, repo: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-X", "utf8", str(Path(_scripts_dir) / "v7_write.py"), "pack", "--repo", str(repo), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def test_pack_json_populates_entities(self, tmp_path):
        """spec 验收 #7：「pack --json 后 entities 非空」。"""
        repo = _v7_repo(tmp_path)
        dj = tmp_path / "d.json"; dj.write_text(json.dumps(_decision(), ensure_ascii=False), encoding="utf-8")

        proc = self._run(repo, "--chapter", "42", "--json", str(dj))

        assert proc.returncode == 0, proc.stderr
        md = (repo / "工作区" / "上下文包-0042.md").read_text(encoding="utf-8")
        assert "## 本章实体（名册查询）" in md and "苏小白" in md.split("## 本章实体（名册查询）", 1)[1]

    def test_pack_without_json_falls_back_to_card(self, tmp_path):
        repo = _v7_repo(tmp_path)
        v7w.write_decision_card(repo, _decision(entities=["苏小白", "林知夏"]))

        proc = self._run(repo, "--chapter", "42")

        assert proc.returncode == 0, proc.stderr
        md = (repo / "工作区" / "上下文包-0042.md").read_text(encoding="utf-8")
        assert "林知夏" in md.split("## 本章实体（名册查询）", 1)[1]
```

- [x] **跑它确认失败**：第一个因 `--json` 未知参数退出 2；第二个实体节缺失。
- [x] **写最小实现**：

```python
def decision_from_card(repo: Path, chapter: int) -> dict[str, Any]:
    """无决策 JSON 时从决策卡文本回退解析（title / pov / 关键实体），供 pack CLI 用。"""
    card = Path(repo) / "工作区" / f"决策卡-{chapter:04d}.md"
    decision: dict[str, Any] = {"chapter": chapter, "title": "", "entities": []}
    if not card.exists():
        return decision
    for line in card.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("- title:"):
            decision["title"] = s.split(":", 1)[1].strip()
        elif s.startswith("- pov:"):
            decision["pov"] = s.split(":", 1)[1].strip()
        elif s.startswith("- 关键实体:"):
            decision["entities"] = [e for e in re.split(r"[、,，]", s.split(":", 1)[1]) if e.strip()]
    return decision
```

`main()`：`p_pack.add_argument("--json", help="决策内容 JSON 文件（可选；无则从决策卡回退解析）")`；pack 分支改为

```python
        decision = json.loads(Path(args.json).read_text(encoding="utf-8")) if args.json else decision_from_card(Path(args.repo), args.chapter)
        decision["chapter"] = args.chapter
```

- [x] **跑测试** → 绿。
- [x] **提交**：`fix(v7-write): pack 子命令支持 --json 并从决策卡回退解析实体，修 entities 恒空`

## Task 4：settle 三门禁 + bypass 留痕

**文件**：`v7_write.py`；新测试 `test_v7_write_gates.py`；`test_v7_write.py` 只加夹具。

- [x] **先给 legacy 测试加夹具**（`test_v7_write.py` 的 `class TestSettle:` 体首行前插入；其余不动）：

```python
    @pytest.fixture(autouse=True)
    def _gates_green(self, tmp_path, monkeypatch):
        """阶段一 P1-2 之后 settle 有三道门禁；本类只测 settle 事务语义，门禁在 test_v7_write_gates.py 单测。"""
        import v7_write as v7w
        review_dir = tmp_path / "repo" / ".webnovel" / "tmp"
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "review_results.json").write_text(json.dumps({"chapter": 37, "blocking_count": 0, "issues": []}), encoding="utf-8")
        monkeypatch.setattr(v7w, "_prose_flagged", lambda _body: [])
```

（`_v7_repo` 在 `tmp_path/"repo"` 建仓，夹具先建 `.webnovel/tmp` 不影响 `mkdir(parents=True)` 的建仓——注意 `_v7_repo` 用 `mkdir(parents=True)` 于子目录，`repo` 已存在无碍；若 `git add -A` 把 `.webnovel` 提交进去也无碍。）

- [x] **写失败测试**（新文件 `test_v7_write_gates.py`）：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""settle 三门禁（v8-gap-review 阶段一 P1-2）：审查 / 文笔 / 素材引用 + --force-review-bypass 留痕。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_scripts_dir = str(Path(__file__).resolve().parent.parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import v7_write as v7w  # noqa: E402
from v7_write import GateRejected, settle  # noqa: E402

CLEAN_BODY = "# 风暴前夜\n\n" + "\n\n".join(
    [
        "苏小白站在围墙上。风从北边来，带着咸腥味。",
        "「今晚谁守夜？」老周问。没人答话，火堆噼啪响了一声。",
        "林知夏把地图铺开。她用炭条圈出三个缺口，说第二个最危险。",
        "远处有兽群在跑。它们往南，像是在躲什么。",
        "苏小白想起第四十章的风暴。那次城南先亮，然后一切都黑了。",
        "老六蹲下去摸了摸地面。土是热的。",
    ] * 12
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    for rel in ("定稿/正文", "定稿/记忆/章摘要", "定稿/设定/名册", "工作区", "作者", "大纲/章纲", "素材/活", ".webnovel/tmp"):
        (repo / rel).mkdir(parents=True)
    (repo / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".cache/\n工作区/\n.webnovel/\n", encoding="utf-8")
    (repo / "定稿" / "正文" / "0041-旧章.md").write_text("---\n章号: 41\n---\n" + "夜" * 1500, encoding="utf-8")
    _git(repo, "init"); _git(repo, "config", "user.email", "t@l"); _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A"); _git(repo, "commit", "-m", "init")
    (repo / "工作区" / "草稿-0042.md").write_text(CLEAN_BODY, encoding="utf-8")
    return repo


def _review(repo: Path, blocking: int, chapter: int = 42, nested: bool = False) -> None:
    payload = {"chapter": chapter, "blocking_count": blocking, "issues_count": blocking, "issues": []}
    if nested:
        payload = {"chapter": chapter, "review_result": {"blocking_count": blocking, "issues_count": blocking}}
    (repo / ".webnovel" / "tmp" / "review_results.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _decision(**over) -> dict:
    d = {"chapter": 42, "title": "风暴前夜", "entities": ["苏小白"], "promises": [], "waiver": "测试", "contract": []}
    d.update(over)
    return d


def _settle(repo: Path, d: dict, **kw):
    return settle(repo, d, draft_path=repo / "工作区" / "草稿-0042.md", summary="s", commit=kw.pop("commit", False), **kw)


def _journal_events(repo: Path) -> list[dict]:
    p = repo / "作者" / "journal.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.is_file() else []


class TestReviewGate:
    def test_blocking_review_rejects_without_side_effects(self, tmp_path):
        """spec 验收 #3：「构造 blocking 审查 → settle 拒绝」。"""
        repo = _repo(tmp_path); _review(repo, blocking=1)
        head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout

        with pytest.raises(GateRejected, match="blocking"):
            _settle(repo, _decision(), commit=True)

        assert not list((repo / "定稿" / "正文").glob("0042-*"))
        assert subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout == head

    def test_missing_review_file_rejects(self, tmp_path):
        """spec 验收 #5：无审查文件 → 拒绝。"""
        repo = _repo(tmp_path)
        with pytest.raises(GateRejected, match="review_results.json"):
            _settle(repo, _decision())

    def test_review_for_other_chapter_counts_as_missing(self, tmp_path):
        repo = _repo(tmp_path); _review(repo, blocking=0, chapter=41)
        with pytest.raises(GateRejected, match="章号不符|chapter"):
            _settle(repo, _decision())

    def test_nested_schema_accepted(self, tmp_path):
        repo = _repo(tmp_path); _review(repo, blocking=0, nested=True)
        result = _settle(repo, _decision())
        assert result["gates"]["review"]["blocking_count"] == 0

    def test_clean_review_passes_and_reports_gates(self, tmp_path):
        repo = _repo(tmp_path); _review(repo, blocking=0)
        result = _settle(repo, _decision())
        assert result["gates"]["review"]["ok"] and result["gates"]["prose"]["ok"] and result["gates"]["materials"]["ok"]
        assert result["gates"]["bypassed"] is False


class TestBypass:
    def test_bypass_lets_blocking_through_with_traces(self, tmp_path):
        """spec 验收 #3 后半：bypass 放行且 front matter 含「审查绕过」、journal 含事件。"""
        repo = _repo(tmp_path); _review(repo, blocking=2)

        result = _settle(repo, _decision(), commit=True, force_review_bypass="作者要求先发再修")

        text = (repo / "定稿" / "正文" / "0042-风暴前夜.md").read_text(encoding="utf-8")
        assert "审查绕过: 作者要求先发再修" in text
        ev = [e for e in _journal_events(repo) if "审查绕过" in e.get("summary", "")]
        assert ev and ev[0]["actor"] == "author" and ev[0]["action"] == "settle" and ev[0]["domain"] == "正文"
        assert "blocking=2" in ev[0]["summary"]
        assert result["gates"]["bypassed"] is True and result["gates"]["bypass_reason"] == "作者要求先发再修"
        from data_modules.author_journal import validate_journal
        assert validate_journal(repo) == []

    def test_bypass_requires_non_empty_reason(self, tmp_path):
        repo = _repo(tmp_path); _review(repo, blocking=1)
        with pytest.raises(ValueError, match="理由"):
            _settle(repo, _decision(), force_review_bypass="   ")

    def test_no_bypass_trace_when_gates_were_green(self, tmp_path):
        repo = _repo(tmp_path); _review(repo, blocking=0)
        _settle(repo, _decision(), force_review_bypass="多余的理由")
        text = (repo / "定稿" / "正文" / "0042-风暴前夜.md").read_text(encoding="utf-8")
        assert "审查绕过" not in text, "门禁本来就绿，不写绕过痕迹"


class TestProseGate:
    def test_flagged_prose_rejects(self, tmp_path):
        """spec 验收 #6：构造 said tag 超阈值净稿 → 拒绝。"""
        repo = _repo(tmp_path); _review(repo, blocking=0)
        (repo / "工作区" / "草稿-0042.md").write_text("# 风暴前夜\n\n" + "「走。」他说道。「不走。」她说道。\n" * 120, encoding="utf-8")

        with pytest.raises(GateRejected, match="prose|文笔"):
            _settle(repo, _decision())

    def test_flagged_prose_bypassed_with_reason(self, tmp_path):
        repo = _repo(tmp_path); _review(repo, blocking=0)
        (repo / "工作区" / "草稿-0042.md").write_text("# 风暴前夜\n\n" + "「走。」他说道。「不走。」她说道。\n" * 120, encoding="utf-8")

        result = _settle(repo, _decision(), force_review_bypass="风格化重复，作者认可")

        assert result["gates"]["prose"]["ok"] is False and result["gates"]["bypassed"] is True


class TestMaterialGate:
    def test_unresolvable_ref_rejects_even_with_bypass(self, tmp_path):
        """spec 验收 #4：「引用不存在 ID → 报错」且 bypass 不放行。"""
        repo = _repo(tmp_path); _review(repo, blocking=0)

        with pytest.raises(GateRejected, match="X-999"):
            _settle(repo, _decision(material_refs=["X-999"]), force_review_bypass="想绕")

    def test_refs_from_chapter_card_are_checked_too(self, tmp_path):
        repo = _repo(tmp_path); _review(repo, blocking=0)
        (repo / "大纲" / "章纲" / "0042.md").write_text('---\n章号: 42\n素材引用: ["桥段:Q-404"]\n---\n', encoding="utf-8")

        with pytest.raises(GateRejected, match="Q-404"):
            _settle(repo, _decision())

    def test_resolvable_ref_passes(self, tmp_path):
        repo = _repo(tmp_path); _review(repo, blocking=0)
        from data_modules.material_store import append_entries
        append_entries(repo, "桥段", [{"id": "Q-001", "名称": "夜袭", "分类": "冲突", "核心摘要": "夜里偷袭", "状态": "active"}])

        result = _settle(repo, _decision(material_refs=["桥段:Q-001"]))

        assert result["gates"]["materials"]["ok"] and result["gates"]["materials"]["resolved"] == ["桥段:Q-001"]
```

- [x] **跑它确认失败**：`ImportError: cannot import name 'GateRejected'`。
- [x] **写最小实现**（`v7_write.py`，settle 段前）：

```python
class GateRejected(RuntimeError):
    """settle 门禁拒绝（退出码 2）。`.report` 为结构化明细。"""

    def __init__(self, message: str, report: dict[str, Any]):
        super().__init__(message)
        self.report = report


def _prose_flagged(body: str) -> list[str]:
    from data_modules.prose_check import check_prose
    return list(check_prose(body).get("flagged") or [])


def _read_review(repo: Path, chapter: int) -> dict[str, Any]:
    path = Path(repo) / ".webnovel" / "tmp" / "review_results.json"
    if not path.is_file():
        return {"ok": False, "reason": f"未审查：缺 {path.relative_to(repo)}", "blocking_count": None}
    payload = json.loads(path.read_text(encoding="utf-8"))
    inner = payload.get("review_result") if isinstance(payload.get("review_result"), dict) else payload
    got_chapter = payload.get("chapter", inner.get("chapter"))
    if got_chapter is not None and int(got_chapter) != int(chapter):
        return {"ok": False, "reason": f"审查文件章号不符（chapter={got_chapter}，本章 {chapter}），视同未审查", "blocking_count": None}
    blocking = int(inner.get("blocking_count") or 0)
    return {"ok": blocking == 0, "blocking_count": blocking, "reason": "" if blocking == 0 else f"审查 blocking={blocking}"}


def _material_refs(repo: Path, decision: dict[str, Any], chapter: int) -> list[str]:
    refs = [str(r) for r in (decision.get("material_refs") or [])]
    card = Path(repo) / "大纲" / "章纲" / f"{chapter:04d}.md"
    if card.is_file():
        from data_modules.chapter_outline_batch import parse_chapter_card
        fields, _ = parse_chapter_card(card.read_text(encoding="utf-8"))
        extra = fields.get("素材引用") or []
        refs += [extra] if isinstance(extra, str) else [str(r) for r in extra]
    return list(dict.fromkeys(refs))


def _run_gates(repo: Path, decision: dict[str, Any], body: str, *, bypass_reason: str) -> dict[str, Any]:
    """三门禁：审查 / 文笔（可 bypass）/ 素材引用（不可 bypass）。拒绝抛 GateRejected。"""
    chapter = int(decision["chapter"])
    review = _read_review(repo, chapter)
    flagged = _prose_flagged(body)
    prose = {"ok": not flagged, "flagged": flagged}
    from data_modules.material_usage import resolve_ref
    resolved, unresolved = [], []
    for ref in _material_refs(repo, decision, chapter):
        (resolved if resolve_ref(repo, ref).get("ok") else unresolved).append(ref)
    materials = {"ok": not unresolved, "resolved": resolved, "unresolved": unresolved}
    gates = {"review": review, "prose": prose, "materials": materials, "bypassed": False, "bypass_reason": ""}
    if unresolved:
        raise GateRejected(f"素材引用无法解析（不可绕过）：{'、'.join(unresolved)}", gates)
    soft_fail = [n for n, g in (("review", review), ("prose", prose)) if not g["ok"]]
    if soft_fail:
        if not bypass_reason:
            detail = "；".join(filter(None, [review.get("reason"), f"文笔 flagged={flagged}" if flagged else ""]))
            raise GateRejected(f"门禁拒绝（{'/'.join(soft_fail)}）：{detail}。作者明确要求时可 --force-review-bypass \"<理由>\"", gates)
        gates["bypassed"] = True
        gates["bypass_reason"] = bypass_reason
    return gates
```

`settle` 签名加 `force_review_bypass: str | None = None`；在 `report = run_checks(...)` 失败检查之后插入：

```python
    bypass_reason = (force_review_bypass or "").strip()
    if force_review_bypass is not None and not bypass_reason:
        raise ValueError("--force-review-bypass 需要非空理由")
    body_clean = body_clean_of(draft_text)
    gates = _run_gates(repo, decision, body_clean, bypass_reason=bypass_reason)
```

（把后面原有的 `body_clean = body_clean_of(draft_text)` 删除，避免重复。）front matter 在 `字数:` 行后加：

```python
    if gates["bypassed"]:
        front.append(f"审查绕过: {gates['bypass_reason']}")
```

`result` 加 `"gates": gates`；commit 成功后（`result["committed"] = True` 之后，仍在 try 内）追加 journal：

```python
        if gates["bypassed"]:
            from data_modules.author_journal import append_events
            append_events(repo, [{
                "actor": "author", "action": "settle", "domain": "正文",
                "path": f"定稿/正文/{chapter_file.name}", "change_kind": "content",
                "diff_stat": {"ins": word_count, "del": 0},
                "summary": f"settle 审查绕过：{gates['bypass_reason']}（blocking={gates['review'].get('blocking_count')}, prose_flagged={gates['prose']['flagged']}）",
                "impact": [],
            }])
```

注意 journal 写入要在 `commit` 分支外也执行（`commit=False` 的测试也断言事件）——放在 `result = {...}` 之后、`if commit:` 之前。

- [x] **跑测试**：`python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_v7_write_gates.py webnovel-writer/scripts/data_modules/tests/test_v7_write.py -q --no-cov -p no:cacheprovider` → 全绿。若 `test_flagged_prose_rejects` 未触发 flagged，改用 `check_said_tags` 阈值上方的更密集 said tag 文本（先 `python -X utf8 webnovel-writer/scripts/data_modules/prose_check.py --file <临时文件> --format json` 看实测）。
- [x] **提交**：`feat(v7-write): settle 三门禁（审查/文笔/素材引用）+ --force-review-bypass 留痕（P1-2）`

## Task 5：settle CLI + `webnovel.py v7-write` 转发

- [x] **写失败测试**（追加到 `test_v7_write_gates.py`）：

```python
class TestSettleCli:
    def _run(self, repo: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-X", "utf8", str(Path(_scripts_dir) / "v7_write.py"), "settle", "--repo", str(repo), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def test_exit_2_on_gate_reject_with_json_detail(self, tmp_path):
        repo = _repo(tmp_path); _review(repo, blocking=1)
        dj = tmp_path / "d.json"; dj.write_text(json.dumps(_decision(), ensure_ascii=False), encoding="utf-8")

        proc = self._run(repo, "--chapter", "42", "--draft", str(repo / "工作区" / "草稿-0042.md"), "--json", str(dj), "--summary", "s", "--no-commit")

        assert proc.returncode == 2
        assert "blocking" in proc.stderr and '"review"' in proc.stderr

    def test_exit_0_with_bypass(self, tmp_path):
        repo = _repo(tmp_path); _review(repo, blocking=1)
        dj = tmp_path / "d.json"; dj.write_text(json.dumps(_decision(), ensure_ascii=False), encoding="utf-8")

        proc = self._run(repo, "--chapter", "42", "--draft", str(repo / "工作区" / "草稿-0042.md"), "--json", str(dj), "--summary", "s", "--no-commit", "--force-review-bypass", "作者要求")

        assert proc.returncode == 0, proc.stderr
        assert "OK v7-write settle chapter=42" in proc.stdout and "bypassed=True" in proc.stdout
```

新文件 `webnovel-writer/scripts/tests/test_webnovel_cli_v7_write.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""webnovel.py v7-write 转发（阶段一 P1-2）：纯 v7 书仓直接按给定目录转发到 v7_write.main。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent


def test_v7_write_forwarding_pack(tmp_path):
    repo = tmp_path / "book"
    for rel in ("定稿/正文", "定稿/记忆/章摘要", "定稿/设定/名册", "工作区"):
        (repo / rel).mkdir(parents=True)
    (repo / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")

    proc = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "webnovel.py"), "--project-root", str(repo), "v7-write", "pack", "--chapter", "3"],
                          capture_output=True, text=True, encoding="utf-8")

    assert proc.returncode == 0, proc.stderr
    assert "OK v7-write pack chapter=3" in proc.stdout
    assert (repo / "工作区" / "上下文包-0003.md").is_file()
```

- [x] **跑它确认失败**：`v7_write.py settle` → argparse `invalid choice: 'settle'`；`webnovel.py v7-write` → `invalid choice`。
- [x] **写最小实现**：`v7_write.main()` 加

```python
    p_settle = sub.add_parser("settle", help="门禁 + 原子落定（正文/章摘要/新实体 + git commit）")
    p_settle.add_argument("--repo", required=True)
    p_settle.add_argument("--chapter", type=int, required=True)
    p_settle.add_argument("--draft", required=True)
    p_settle.add_argument("--json", required=True, help="决策内容 JSON 文件")
    g = p_settle.add_mutually_exclusive_group(required=True)
    g.add_argument("--summary", help="章摘要文本（≤200 字）")
    g.add_argument("--summary-file", help="章摘要文件")
    p_settle.add_argument("--no-commit", action="store_true")
    p_settle.add_argument("--force-review-bypass", metavar="理由", help="显式绕过审查/文笔门禁；理由写入 front matter 与 journal")
```

分支：

```python
    if args.action == "settle":
        decision = json.loads(Path(args.json).read_text(encoding="utf-8"))
        decision["chapter"] = args.chapter
        summary = args.summary if args.summary is not None else Path(args.summary_file).read_text(encoding="utf-8")
        try:
            result = settle(Path(args.repo), decision, draft_path=Path(args.draft), summary=summary,
                            commit=not args.no_commit, force_review_bypass=args.force_review_bypass)
        except GateRejected as exc:
            print(f"REJECTED v7-write settle chapter={args.chapter}: {exc}", file=sys.stderr)
            print(json.dumps(exc.report, ensure_ascii=False, indent=1), file=sys.stderr)
            return 2
        except RuntimeError as exc:
            print(f"REJECTED v7-write settle chapter={args.chapter}: {exc}", file=sys.stderr)
            return 2 if "机检" in str(exc) else 1
        print(f"OK v7-write settle chapter={args.chapter} committed={result['committed']} bypassed={result['gates']['bypassed']} file={result['chapter_file']}")
        return 0
```

`webnovel.py`：在 `p_materials` 之后加

```python
    p_v7_write = sub.add_parser("v7-write", help="v7 书仓写链（decision / pack / check / settle，阶段一 P1-1/P1-2）")
    p_v7_write.add_argument("action", choices=["decision", "pack", "check", "settle"])
    p_v7_write.add_argument("v7_args", nargs=argparse.REMAINDER, help="透传给 v7_write.py 的参数（--chapter/--json/--draft/…）")
    p_v7_write.set_defaults(func=cmd_v7_write)
```

```python
def cmd_v7_write(args: argparse.Namespace) -> int:
    """v7 书仓写链转发（阶段一）：--repo 取自 --project-root（宽松解析，纯 v7 书仓直接用给定目录）。"""
    import v7_write

    root = _resolve_root_lenient(args.project_root)
    rest = list(getattr(args, "v7_args", []) or [])
    if rest[:1] == ["--"]:
        rest = rest[1:]
    return v7_write.main([args.action, "--repo", str(root), *rest])
```

`v7_write.main` 签名改为 `def main(argv: list[str] | None = None) -> int:` 且 `args = parser.parse_args(argv)`。

- [x] **跑测试** → 绿；再跑 `python -X utf8 -m pytest webnovel-writer/scripts/tests -q --no-cov -p no:cacheprovider`（确认 CLI 相关既有测试如 `test_webnovel_cli*` 不受影响）。
- [x] **提交**：`feat(v7-write): settle CLI（退出码 0/2/1）+ webnovel.py v7-write 转发子命令`

## Task 6：SKILL v7 分支 + 行为评测 + guides

- [x] **写失败评测用例**（`evals/fixtures/behavior/fast.json` 的 `cases` 追加）：

```json
{
  "id": "skill_write_v7_branch",
  "type": "skill_contract",
  "skill": "webnovel-write",
  "description": "/webnovel-write detects book.yaml and routes to the v7 chain with gated settle and traced bypass.",
  "required": [
    "book.yaml",
    "v7-write pack --chapter {chapter_num}",
    "v7-write check --chapter {chapter_num}",
    "v7-write settle --chapter {chapter_num}",
    "--force-review-bypass",
    "理由必须来自作者原话"
  ],
  "ordered": [
    ["v7-write pack --chapter {chapter_num}", "v7-write check --chapter {chapter_num}"],
    ["v7-write check --chapter {chapter_num}", ".webnovel/tmp/review_results.json"],
    ["prose-check", "v7-write settle --chapter {chapter_num}"]
  ]
}
```

- [x] **跑它确认失败**：`python -X utf8 webnovel-writer/scripts/run_behavior_evals.py --suite fast` → `skill_write_v7_branch FAIL`。（若脚本参数名不同，先 `--help`。）
- [x] **改 SKILL**（`skills/webnovel-write/SKILL.md`）：在「### 准备：预检」代码块之后、「### 准备：刷新合同树」之前插入：

```markdown
### 准备：书仓形态判定

`${PROJECT_ROOT}/book.yaml` 存在 → 本书是 v7 story-repo，**跳过下文 v6 步骤（刷新合同树 / write-gate / chapter-commit），改走「v7 书仓分支」**；不存在 → 继续 v6 流程。判定只看 `book.yaml`，不看 `.webnovel/` 是否存在（v7 书仓也可能有 `.webnovel/tmp/` 审查产物目录）。

### v7 书仓分支（book.yaml 存在时）

上下文包 → 草稿 → 机检 → 审查 → 文笔检测 → settle。所有命令经 `webnovel.py v7-write` 转发，`--project-root` 即书仓根。

1. **决策卡与上下文包**（替代 Step 1 的写作任务书；context-agent 仍可用于起草决策 JSON，但决策 JSON 的字段以 `docs/guides/v7-write-path.md` §3 为准）：
   ```bash
   python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" v7-write decision --json "${PROJECT_ROOT}/工作区/决策-{chapter_num}.json"
   python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" v7-write pack --chapter {chapter_num} --json "${PROJECT_ROOT}/工作区/决策-{chapter_num}.json"
   ```
   上下文包落 `工作区/上下文包-{NNNN}.md`，含决策卡 / 章纲节选 / 承诺账本应推进 / 作者修改未消费（stale）/ 前情 / 上章结尾 / 实体 / 主角卡 / 视角纪律 / 素材装配 / 文风宪法与锚点 / 作者模型 / 读者信号。起草只以此包为依据。
2. **起草**：同 Step 2（多稿择优 `drafts` 照用），草稿写 `工作区/草稿-{NNNN}.md`。
3. **机检**：
   ```bash
   python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" v7-write check --chapter {chapter_num} --draft "${PROJECT_ROOT}/工作区/草稿-{NNNN}.md" --json "${PROJECT_ROOT}/工作区/决策-{chapter_num}.json"
   ```
   退出码 2 = 字数/占位符/标题/承诺未过，回到起草。
4. **审查**：同 Step 3，reviewer 直写 `${PROJECT_ROOT}/.webnovel/tmp/review_results.json`（顶层 `blocking_count`）。**settle 门禁会读这个文件**：缺失或章号不符视同未审查。
5. **文笔检测**：`python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" prose-check --file "${PROJECT_ROOT}/工作区/草稿-{NNNN}.md" --format json`；flagged 非空先润色（Step 4 规则照用）。
6. **settle**（替代 Step 5/6；原子 commit，含正文 / 章摘要 / 新实体）：
   ```bash
   python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" v7-write settle --chapter {chapter_num} --draft "${PROJECT_ROOT}/工作区/草稿-{NNNN}.md" --json "${PROJECT_ROOT}/工作区/决策-{chapter_num}.json" --summary "{≤200 字章摘要}"
   ```
   退出码 2 = 门禁拒绝（stderr 有 JSON 明细：`review` / `prose` / `materials`）。处理顺序：**改稿重审 → 再 settle**。素材引用不存在（`materials.unresolved`）只能改决策 JSON / 章纲卡，不可绕过。仅当作者明确要求发布时，加 `--force-review-bypass "<理由>"`——理由必须来自作者原话，不得由主流程代拟；绕过会写进正文 front matter（`审查绕过:`）与 `作者/journal.jsonl`，最终报告必须如实列出。
```

- [x] **跑评测** → 全 PASS；`python -X utf8 webnovel-writer/scripts/validate_reference_wiring.py` → drift=0（SKILL 未新增 reference 引用；若报 drift，按其输出补 `reference-loading-map.md`）。
- [x] **guides**：`docs/guides/v7-write-path.md` §3 把 `python -c "from v7_write import settle; ..."` 行替换为 settle CLI 示例；「要点」加两条：「三门禁：审查（缺文件/章号不符/blocking>0 拒）/ 文笔（flagged 拒）/ 素材引用（不可绕过）」「`--force-review-bypass "<理由>"` 留痕于 front matter `审查绕过:` 与 journal」；「已知边界」删掉「承诺流转未实现」句（T28 已实现，pack 现读账本）。决策 JSON 字段表加 `material_refs`（可选，`表:ID` 或裸 ID 列表）与 `volume`（可选，缺省按 `卷规模` 推算）。
- [x] **提交**：`docs(write): /webnovel:write 按 book.yaml 分流 v7 链 + settle 门禁/bypass 契约进评测 + v7 指南同步`

## Task 7：fantasy01 冒烟 + 回归 + 勾选

- [x] **fantasy01 冒烟（只读副本）**：
  ```powershell
  $src="c:\lgq\ai-workspace\projects\loom-books\fantasy01"; $dst="$env:TEMP\fantasy01-smoke"
  if (Test-Path $dst) { python -X utf8 -c "import shutil; shutil.rmtree(r'\\?\$dst')" }
  python -X utf8 -c "import shutil; shutil.copytree(r'$src', r'$dst', ignore=shutil.ignore_patterns('.git'))"
  python -X utf8 webnovel-writer/scripts/webnovel.py --project-root $dst v7-write pack --chapter 42
  Select-String -Path "$dst\工作区\上下文包-0042.md" -Pattern "^## " | ForEach-Object { $_.Line }
  ```
  期望：出现 `## 作者模型`（fantasy01 有 `作者/author_model.md`）与 `## 文风宪法`/`## 素材装配`（有 `文风/`、`素材/`）；`## 作者修改未消费（stale）` 与 `## 本章应推进（承诺账本）` 取决于真仓当下是否有 stale / 到期条目——**如实记录出现了哪些**，并用 `webnovel.py --project-root $dst author-sync --format json` / `promise-ledger scan` 查证「没出现」的原因是数据为空而非读函数失败（`stats["section_errors"]` 应为空：临时用 `python -X utf8 -c "...build_context_pack...; print(stats['section_errors'], stats['dropped_sections'])"`）。
- [x] **全量回归**：`python -X utf8 -m pytest -q -p no:cacheprovider` → 记录 `N passed` 与覆盖率行（spec 验收 #8：≥1455 passed，cov ≥80）；`python -X utf8 webnovel-writer/scripts/validate_plugin_package.py`；`sync_plugin_version.py --check`。
- [x] **勾选**：`docs/zcode/v8-gap-review-3rounds/README.md` 阶段一表 P1-1 / P1-2 行加 `✅ 2026-09-0x <commit>`，验收列引用本计划测试名；同表下方补一句「实现时发现 v7_write 未被任何 skill 调用，已在同批接线（见 spec §1）」。
- [x] **交接**：`docs/cursor/项目复审/2026-09-04-会话交接.md` 步骤 6 状态改「阶段一完成」，列出 commit 与 fantasy01 冒烟实际输出摘要。
- [x] **提交**：`docs: v8-gap-review 阶段一 P1-1/P1-2 勾选 + fantasy01 冒烟记录 + 交接`；工作区同步子模块指针。
