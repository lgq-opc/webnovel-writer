#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7_write — v7 story-repo 写路径最小闭环（S19/E3 垂直切片）。

流程：决策卡 → 上下文包 →（LLM 草稿，工作区/）→ 机检 → 作者验收 → settle（原子 commit）。
命名跟随 spec 0.4：定稿/正文/NNNN-标题.md（front matter 中文键）、
定稿/记忆/章摘要/NNNN.md（v7_cache 唯一认的摘要路径）、定稿/设定/名册/<正名>.md。
上下文包吸收 S1-S4 成果：20,000 字符总预算、section 配额、紧凑输出、缓存查询。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from data_modules.context_budget import apply_quota, estimate_tokens

# R12/F-15：占位符正则补 XXX / ??? / {…} / 未完待续
PLAN_PLACEHOLDER_RE = re.compile(r"\[[^\]]*待[^\]]*\]|TODO|FIXME|\(待补\)|（待补充）|XXX|\?\?\?|\{[^{}\n]{0,40}\}|未完待续")
QUOTED_NAME_RE = re.compile(r"「([一-鿿]{2,4})」")
MIN_WORDS, MAX_WORDS = 800, 6000
TOTAL_BUDGET_DEFAULT = 20000

V7_SECTION_QUOTAS: dict[str, int] = {
    "decision_card": 2000,
    "recent_summaries": 1200,
    "entities": 3000,
    "roster": 1500,
    "prev_chapter_tail": 1200,
    "book_meta": 500,
    # v8-gap-review 阶段一 P1-1（spec §4.2）：治理信号 section
    "stale_notes": 800,
    "pending_promises": 1000,
    "author_model": 800,
    "style_anchor": 500,
    "style_contract": 600,
    "reader_signal": 500,
    "materials": 1500,
    "outline_excerpt": 800,
    "protagonist": 600,
    "pov_discipline": 400,
}
# 总预算超限时：PROTECTED 只截不丢；其余按 DROP 顺序整段丢弃（spec §4.2 逐字）
V7_PROTECTED_SECTIONS = ("decision_card", "prev_chapter_tail", "stale_notes", "pending_promises")
V7_DROP_ORDER = (
    "materials", "reader_signal", "style_contract", "outline_excerpt", "protagonist",
    "pov_discipline", "style_anchor", "author_model", "roster", "recent_summaries", "entities",
)
V7_SECTION_TITLES: dict[str, str] = {
    "decision_card": "决策卡",
    "outline_excerpt": "本章章纲节选",
    "pending_promises": "本章应推进（承诺账本）",
    "stale_notes": "作者修改未消费（stale）",
    "recent_summaries": "前情摘要（近三章，v7_cache）",
    "prev_chapter_tail": "上一章结尾",
    "entities": "本章实体（名册查询）",
    "protagonist": "主角卡",
    "pov_discipline": "视角纪律",
    "roster": "名册清单",
    "materials": "素材装配",
    "style_contract": "文风宪法",
    "style_anchor": "文风锚点（高分样本）",
    "author_model": "作者模型",
    "reader_signal": "读者信号（追读力）",
    "book_meta": "书级元信息",
}
V7_RENDER_ORDER = tuple(V7_SECTION_TITLES)  # 渲染顺序 = 标题表声明顺序
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent


# ---------- 决策卡 ----------


def book_word_stats(repo: Path) -> dict[str, int]:
    """书史字数分布（从定稿正文直算，机检下限与决策卡目标字数的依据）。"""
    counts: list[int] = []
    for p in Path(repo).glob("定稿/正文/*.md"):
        text = p.read_text(encoding="utf-8")
        body = text.split("---", 2)[-1] if text.startswith("---") else text
        counts.append(len(re.sub(r"\s", "", body)))
    if not counts:
        return {"mean": 0, "median": 0, "min": 0, "max": 0, "chapters": 0}
    counts.sort()
    n = len(counts)
    return {"mean": int(sum(counts) / n), "median": counts[n // 2], "min": counts[0], "max": counts[-1], "chapters": n}


def write_decision_card(repo: Path, decision: dict[str, Any]) -> Path:
    chapter = int(decision["chapter"])
    lines = [f"# 决策卡 · 第{chapter:04d}章", ""]
    for key in ("title", "pov", "time_anchor"):
        if decision.get(key):
            lines.append(f"- {key}: {decision[key]}")
    if decision.get("target_words"):
        lines.append(f"- 目标字数: {decision['target_words']}（下限 {int(decision['target_words'] * 0.75)}）")
    lines.append(f"- 目标: {decision.get('goal', '')}")
    lines.append("- 必须覆盖节点:")
    lines += [f"  - {n}" for n in decision.get("nodes") or []]
    lines.append("- 本章禁区:")
    lines += [f"  - {n}" for n in decision.get("forbidden") or []]
    if decision.get("promises"):
        # 增量审阅 P2-9：承诺渲染进决策卡作者界面（承诺系统完整读写仍属 v7.1）
        lines.append("- 推进承诺:")
        lines += [f"  - {p}" for p in decision["promises"]]
    lines.append("- 承诺结转豁免: " + ("是（" + decision["waiver"] + "）" if decision.get("waiver") else "否"))
    lines.append("- 合同断言:")
    lines += [f"  - {c}" for c in decision.get("contract") or []]
    lines.append("- 关键实体: " + "、".join(decision.get("entities") or []))
    path = Path(repo) / "工作区" / f"决策卡-{chapter:04d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------- 上下文包 ----------


def _find_setting_path(settings_dir: Path, keyword: str) -> Optional[Path]:
    exact = settings_dir / f"{keyword}.md"
    if exact.exists():
        return exact
    matches = sorted(settings_dir.glob(f"*{keyword}*.md"))
    return matches[0] if matches else None


def load_context_budget(repo: Path) -> dict[str, Any]:
    """book.yaml `context_budget:` 节解析（S22/S23 按书覆盖）。

    识别迁移器/作者写入的防呆方言两级形态：
        context_budget:
          total: 20000
          sections:
            prev_chapter_tail: 1340
    无该节返回 {"total": None, "sections": {}}（缺省 = 静态默认，零行为变化）。
    """
    out: dict[str, Any] = {"total": None, "sections": {}}
    book_yaml = Path(repo) / "book.yaml"
    if not book_yaml.exists():
        return out
    cb_indent = -1
    sections_indent = -1
    for raw in book_yaml.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if sections_indent >= 0:
            if indent > sections_indent and ":" in stripped:
                key, _, val = stripped.partition(":")
                try:
                    out["sections"][key.strip()] = int(val.strip())
                except ValueError:
                    pass
                continue
            sections_indent = -1  # 缩进回落 = sections 块结束
        if cb_indent < 0:
            if indent == 0 and stripped == "context_budget:":
                cb_indent = 0
            continue
        if indent <= cb_indent:
            cb_indent = -1  # 顶层键 = context_budget 块结束
            continue
        if stripped == "sections:":
            sections_indent = indent
        elif stripped.startswith("total:"):
            try:
                out["total"] = int(stripped.split(":", 1)[1].strip())
            except ValueError:
                pass
    return out


def _book_yaml_scalar(repo: Path, key: str) -> str:
    """book.yaml 顶层标量（`主角:` / `卷规模:` 等）；缺失返回空串。"""
    book_yaml = Path(repo) / "book.yaml"
    if not book_yaml.exists():
        return ""
    for raw in book_yaml.read_text(encoding="utf-8").splitlines():
        if raw.startswith(f"{key}:"):
            return raw.split(":", 1)[1].strip().strip('"').strip("'")
    return ""


# ---------- 治理信号 section 读函数（阶段一 P1-1；每个只做一件事，异常由 build_context_pack 统一记账） ----------


def _sec_stale_notes(repo: Path) -> list[dict[str, Any]]:
    from data_modules.author_journal import unconsumed_stale

    return unconsumed_stale(repo)


def _sec_pending_promises(repo: Path, chapter: int) -> dict[str, Any]:
    from data_modules.promise_ledger import pending_for_chapter

    if not (Path(repo) / "大纲" / "条目").is_dir():
        return {}
    out = pending_for_chapter(repo, chapter=chapter)
    items, from_card = out.get("items") or [], out.get("from_card") or []
    return {"items": items, "from_card": from_card} if (items or from_card) else {}


def _sec_author_model(repo: Path) -> dict[str, str]:
    from data_modules.author_model import load_author_model_section

    return {k: v for k, v in load_author_model_section(repo).items() if v}


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
    keys = ("recent_reading_power", "hook_type_usage", "review_trend", "differentiation_reminder")
    return sig if any(sig.get(k) for k in keys) else {}


def _sec_materials(repo: Path) -> dict[str, Any]:
    from data_modules.material_store import assemble_materials

    if not (Path(repo) / "素材").is_dir():
        return {}
    k = int(_book_yaml_scalar(repo, "素材装配条数") or 3)
    out = assemble_materials(repo, k=k)
    live = {
        table: [{"id": r.get("id"), "名称": r.get("名称"), "核心摘要": r.get("核心摘要")} for r in rows]
        for table, rows in (out.get("live") or {}).items()
    }
    return {"live": live, "frozen_version": out.get("frozen_version")} if live else {}


def _sec_outline_excerpt(repo: Path, decision: dict[str, Any], chapter: int) -> str:
    """当卷详细大纲中本章小节；先 `第NN卷-详细大纲.md` 再 `第NN卷.md`（P2-1 统一路径前的兼容读）。"""
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
    """N11：决策卡 pov ≠ book.yaml `主角` 时注入单章视角纪律（references/shared/pov-management.md §一）。

    book.yaml 未声明 `主角` 时无法判定越界，省略（不注入噪音）。
    """
    pov = str(decision.get("pov") or "").strip()
    protagonist = _book_yaml_scalar(repo, "主角")
    if not pov or not protagonist or pov == protagonist:
        return {}
    ref = _PLUGIN_ROOT / "references" / "shared" / "pov-management.md"
    rules = ref.read_text(encoding="utf-8") if ref.is_file() else ""
    m = re.search(r"^## 一、[^\n]*\n(.*?)(?=^## |\Z)", rules, re.M | re.S)
    return {"本章视角": pov, "主角": protagonist, "规则": (m.group(1) if m else rules).strip()}


def build_context_pack(repo: Path, decision: dict[str, Any], *, db_path: Optional[Path] = None, total_budget: Optional[int] = None):
    repo = Path(repo)
    from v7_cache import find_entity, get_summary

    chapter = int(decision["chapter"])
    book_budget = load_context_budget(repo)
    quotas_effective = {**V7_SECTION_QUOTAS, **book_budget["sections"]}
    sections: dict[str, Any] = {}

    card_path = repo / "工作区" / f"决策卡-{chapter:04d}.md"
    sections["decision_card"] = card_path.read_text(encoding="utf-8") if card_path.exists() else json.dumps(decision, ensure_ascii=False)

    summaries = {}
    for prev in range(max(1, chapter - 3), chapter):
        text = get_summary(repo, prev)
        if text:
            summaries[f"ch{prev:04d}"] = text[:500]
    sections["recent_summaries"] = summaries or "（暂无章摘要）"

    entities = {}
    for name in decision.get("entities") or []:
        hit = find_entity(repo, name)
        entities[name] = hit or {"name": name, "aliases": "", "first_chapter": "", "note": "名册未登记"}
    sections["entities"] = entities

    roster_files = sorted((repo / "定稿" / "设定" / "名册").glob("*.md"))
    sections["roster"] = [p.stem for p in roster_files]

    prev_chapter = chapter - 1
    prev_files = list((repo / "定稿" / "正文").glob(f"{prev_chapter:04d}-*.md"))
    if prev_files:
        text = prev_files[0].read_text(encoding="utf-8")
        sections["prev_chapter_tail"] = "……" + text[-int(quotas_effective["prev_chapter_tail"]):]

    book_meta = {}
    book_yaml = repo / "book.yaml"
    if book_yaml.exists():
        book_meta = {"raw": book_yaml.read_text(encoding="utf-8")[:500]}
    sections["book_meta"] = book_meta

    # S19 诊断修复：字数契约——书史基准 + 本章目标进入上下文包
    stats = book_word_stats(repo)
    target = int(decision.get("target_words") or stats["mean"] or 2000)
    sections["length_contract"] = {
        "书史章数": stats["chapters"],
        "书史均值": stats["mean"],
        "书史中位": stats["median"],
        "本章目标字数": target,
        "下限": int(target * 0.75),
    }

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

    stats_before = sum(estimate_tokens(v) for v in sections.values())
    sizes_before = {name: estimate_tokens(v) for name, v in sections.items()}
    for name, quota in quotas_effective.items():
        if name in sections:
            sections[name] = apply_quota(sections[name], quota)
    truncated = [n for n, v in sections.items() if n in sizes_before and estimate_tokens(v) < sizes_before[n]]

    effective_total = int(total_budget) if total_budget is not None else (book_budget["total"] or TOTAL_BUDGET_DEFAULT)
    # 超总预算：按 DROP 顺序整段丢弃非 PROTECTED section（P1-1「饱和测试三段保全」）
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
        "used": used,
        "total_budget": effective_total,
        "sections_before": stats_before,
        "sections": dict(quotas_effective),
        "truncated_sections": truncated,
        "dropped_sections": dropped,
        "section_errors": section_errors,
        "budget_used_ratio": round(used / effective_total, 3) if effective_total else 1.0,
    }
    return md, stats


def _render_pack_markdown(chapter: int, sections: dict[str, Any]) -> str:
    out = [f"# 上下文包 · 第{chapter:04d}章", ""]
    for name in V7_RENDER_ORDER:
        value = sections.get(name)
        if not value:
            continue
        out.append(f"## {V7_SECTION_TITLES[name]}")
        if isinstance(value, str):
            out.append(value)
        else:
            out.append("```json")
            out.append(json.dumps(value, ensure_ascii=False, indent=1))
            out.append("```")
        out.append("")
    return "\n".join(out)


# ---------- 机检 ----------


def body_clean_of(text: str) -> str:
    """正文净稿口径（R12/F-15）：剥 front matter 与首行标题——机检 check 与 settle 统一。"""
    body = text.split("---", 2)[-1].lstrip() if text.startswith("---") else text
    return re.sub(r"^#\s*.*?\n", "", body, count=1).lstrip()


def run_checks(repo: Path, decision: dict[str, Any], draft_text: str) -> dict[str, Any]:
    repo = Path(repo)
    body = body_clean_of(draft_text)
    word_count = len(re.sub(r"\s", "", body))
    placeholders = sorted(set(PLAN_PLACEHOLDER_RE.findall(body)))

    title = str(decision.get("title") or "")
    # 标题核对用原稿（含首行标题）；净稿口径只用于字数/占位/承诺检查
    first_line = next((ln.strip().lstrip("# ").strip() for ln in draft_text.splitlines() if ln.strip()), "")
    title_ok = (not title) or (title in first_line) or (title in draft_text[:200])

    promises = decision.get("promises") or []
    promise_ok = bool(promises) or bool(decision.get("waiver"))

    roster_names = {p.stem for p in (repo / "定稿" / "设定" / "名册").glob("*.md")}
    known = set(decision.get("entities") or []) | roster_names | set((decision.get("title") or "").split())
    new_name_candidates = sorted({n for n in QUOTED_NAME_RE.findall(body) if n not in known})

    book_stats = book_word_stats(repo)
    target = int(decision.get("target_words") or 0)
    # R12/F-15：无目标字数时回退 = 书史均值×0.75（与提示词一致），无书史再退默认下限
    if target:
        min_words = max(1, int(target * 0.75))
        min_words_source = "target"
    elif book_stats["chapters"] and book_stats["mean"] > 0:
        min_words = max(1, int(book_stats["mean"] * 0.75))
        min_words_source = "book_mean"
    else:
        min_words = MIN_WORDS
        min_words_source = "default"

    # 承诺推进存在性匹配（R12/F-15）：语义判断交 reviewer，此处查关键词前缀渐进命中（6/4/2 字）
    promise_progress = []
    for promise in promises:
        keyword = re.split(r"[:：]", str(promise), maxsplit=1)[-1].strip()
        keyword = re.sub(r"^[A-Za-z]-\d+\s*", "", keyword)  # 剥承诺 ID 前缀（P-031 等）
        found = any(keyword[:n] in body for n in (6, 4, 2) if len(keyword[:n]) >= 2)
        promise_progress.append({"promise": str(promise), "keyword": keyword, "found": found})

    issues: list[dict[str, str]] = []
    # 上限闸（R12/F-15）：超书史 max 或 6000 硬顶 → high issue「疑似灌水」（不阻断，进审查）
    over_book_max = bool(book_stats["chapters"]) and word_count > int(book_stats["max"])
    over_hard = word_count > MAX_WORDS
    if over_hard or over_book_max:
        issues.append(
            {
                "severity": "high",
                "category": "pacing",
                "description": "疑似灌水：字数超上限",
                "evidence": f"word_count={word_count}, book_max={book_stats['max']}, hard_cap={MAX_WORDS}",
            }
        )
    for item in promise_progress:
        if not item["found"]:
            issues.append(
                {
                    "severity": "high",
                    "category": "logic",
                    "description": "承诺未见推进：承诺关键词在正文无存在性命中（语义复核交 reviewer）",
                    "evidence": str(item["promise"]),
                }
            )

    ok = word_count >= min_words and not placeholders and title_ok and promise_ok
    return {
        "ok": ok,
        "word_count": word_count,
        "min_words": min_words,
        "min_words_source": min_words_source,
        "target_words": target,
        "placeholders": placeholders,
        "title_ok": title_ok,
        "promise_ok": promise_ok,
        "promise_progress": promise_progress,
        "new_name_candidates": new_name_candidates,
        "issues": issues,
        "checks": {
            "min_words": MIN_WORDS,
            "max_words": MAX_WORDS,
            "book_max": book_stats["max"],
            "placeholder_scan": "v7-write",
            "promise_waiver_reason": decision.get("waiver") or "",
        },
    }


# ---------- settle ----------


def _git(repo: Path, *args: str) -> None:
    try:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or f"exit {exc.returncode}"
        raise RuntimeError(f"git {' '.join(args)}: {detail}") from exc


def _commit_with_identity_fallback(repo: Path, message: str) -> None:
    """无任何 git 身份配置时兜底提交身份，避免 settle 因身份缺失整体回滚（增量审阅 P2-3）。"""
    probe = subprocess.run(
        ["git", "-C", str(repo), "config", "user.email"],
        capture_output=True, text=True,
    )
    identity: list[str] = []
    if not probe.stdout.strip():
        identity = ["-c", "user.name=webnovel-settle", "-c", "user.email=webnovel-settle@local"]
    _git(repo, *identity, "commit", "-m", message)


def _v6_root_from_git_config(repo: Path) -> str:
    """增量审阅 P2-4：读迁移器落在 v7 仓 git config 的 dualformat.v6root 映射（无则空串）。"""
    probe = subprocess.run(
        ["git", "-C", str(repo), "config", "dualformat.v6root"],
        capture_output=True, text=True,
    )
    return probe.stdout.strip() if probe.returncode == 0 else ""


def settle(
    repo: Path,
    decision: dict[str, Any],
    *,
    draft_path: Path,
    summary: str,
    commit: bool = True,
) -> dict[str, Any]:
    repo = Path(repo)
    chapter = int(decision["chapter"])
    title = str(decision.get("title") or f"第{chapter}章")

    draft_text = Path(draft_path).read_text(encoding="utf-8")
    report = run_checks(repo, decision, draft_text)
    if not report["ok"]:
        raise RuntimeError(f"机检未通过，拒绝 settle：{json.dumps(report, ensure_ascii=False)}")

    # S18/E4：唯一写入路径——v6 侧已落定该章时禁止 v7 settle
    from data_modules.dual_format_guard import check_unique_write_path, has_v7_settled_chapter

    v6_root = decision.get("v6_project_root") or _v6_root_from_git_config(repo)
    if v6_root:
        blocker = check_unique_write_path(Path(v6_root), chapter, target_format="v7", story_repo_root=repo)
        if blocker:
            raise RuntimeError("唯一写入路径：" + blocker["message"])
    # 章号前缀判重（增量审阅 P2-1）：同章改标题不得绕过防双写
    if has_v7_settled_chapter(repo, chapter):
        raise RuntimeError(f"唯一写入路径：该章已 settle（定稿/正文 存在 {chapter:04d}- 前缀文件），禁止双写")
    chapter_file = repo / "定稿" / "正文" / f"{chapter:04d}-{title}.md"

    body_clean = body_clean_of(draft_text)  # R12/F-15：与机检同一净稿口径
    word_count = len(re.sub(r"\s", "", body_clean))
    front = [
        "---",
        f"章号: {chapter}",
        f"标题: {title}",
        f"卷: {decision.get('volume') or 1}",
    ]
    if decision.get("pov"):
        front.append(f"视角: {decision['pov']}")
    if decision.get("time_anchor"):
        front.append(f"书内时间: {decision['time_anchor']}")
    front.append(f"字数: {word_count}")
    if decision.get("waiver"):
        front.append(f"承诺豁免: {decision['waiver']}")
    if decision.get("promises"):
        front.append("推进承诺:")
        front += [f"  - {p}" for p in decision["promises"]]
    front.append("合同:")
    front += [f"  - {c}" for c in decision.get("contract") or []]
    front.append("---")
    chapter_file.write_text("\n".join(front) + "\n\n" + body_clean + "\n", encoding="utf-8")

    # S19 原子性：任一步失败 → 清除本次新建的定稿文件（工作区草稿原样保留）
    created: list[Path] = [chapter_file]
    try:
        summary_dir = repo / "定稿" / "记忆" / "章摘要"
        summary_dir.mkdir(parents=True, exist_ok=True)
        summary_text = (summary or "").strip()[:200]
        summary_file = summary_dir / f"{chapter:04d}.md"
        summary_file.write_text(summary_text + "\n", encoding="utf-8")
        created.append(summary_file)

        new_entities = decision.get("new_entities") or []
        for entity in new_entities:
            name = entity.get("name") or ""
            if not name:
                continue
            entity_file = repo / "定稿" / "设定" / "名册" / f"{name}.md"
            if entity_file.is_file():
                continue
            entity_file.parent.mkdir(parents=True, exist_ok=True)
            entity_file.write_text(
                "---\n"
                f"正名: {name}\n"
                f"别名: {json.dumps(entity.get('aliases') or [], ensure_ascii=False)}\n"
                f"类型: {entity.get('type') or '角色'}\n"
                f"首现章: {chapter}\n---\n",
                encoding="utf-8",
            )
            created.append(entity_file)

        result = {"chapter": chapter, "committed": False, "chapter_file": str(chapter_file), "checks": report}
        if commit:
            _git(repo, "add", "定稿")
            _commit_with_identity_fallback(repo, f"settle: 第{chapter:04d}章 {title}")
            result["committed"] = True
    except Exception as exc:
        # 逐文件保护（增量审阅 P2-2）：单个 unlink 失败（Windows 文件锁）不得阻断 git reset
        for p in created:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        if commit:
            # 只清本次 add 的 定稿 路径，不波及作者自行 staged 的无关改动；
            # 无 HEAD 的新仓回退到全量 reset，仍失败则不遮蔽原始错误
            for reset_args in (("reset", "--quiet", "HEAD", "--", "定稿"), ("reset", "--quiet")):
                try:
                    _git(repo, *reset_args)
                    break
                except Exception:
                    continue
        raise RuntimeError(f"settle 回滚：定稿未变更（{exc}）") from exc
    # 派生缓存刷新是 best-effort：失败不回滚已完成的 settle 事务（下一章 pack 依赖它可见新章）
    try:
        from v7_cache import rebuild_cache

        rebuild_cache(repo)
        result["cache_rebuilt"] = True
    except Exception:
        result["cache_rebuilt"] = False
    return result


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
            decision["entities"] = [e.strip() for e in re.split(r"[、,，]", s.split(":", 1)[1]) if e.strip()]
    return decision


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="v7 写路径：决策卡/上下文包/机检/settle")
    sub = parser.add_subparsers(dest="action", required=True)
    p_decision = sub.add_parser("decision", help="生成决策卡（参数经 --json 文件传入）")
    p_decision.add_argument("--repo", required=True)
    p_decision.add_argument("--json", required=True, help="决策内容 JSON 文件")
    p_pack = sub.add_parser("pack", help="生成上下文包（需已有决策卡）")
    p_pack.add_argument("--repo", required=True)
    p_pack.add_argument("--chapter", type=int, required=True)
    p_pack.add_argument("--json", help="决策内容 JSON 文件（可选；无则从决策卡回退解析 title/pov/关键实体）")
    p_check = sub.add_parser("check", help="机检草稿")
    p_check.add_argument("--repo", required=True)
    p_check.add_argument("--chapter", type=int, required=True)
    p_check.add_argument("--draft", required=True)
    p_check.add_argument("--json", required=True, help="决策内容 JSON 文件")
    args = parser.parse_args(argv)

    if args.action == "decision":
        decision = json.loads(Path(args.json).read_text(encoding="utf-8"))
        print(write_decision_card(Path(args.repo), decision))
        return 0
    if args.action == "pack":
        decision = json.loads(Path(args.json).read_text(encoding="utf-8")) if args.json else decision_from_card(Path(args.repo), args.chapter)
        decision["chapter"] = args.chapter
        md, stats = build_context_pack(Path(args.repo), decision)
        out = Path(args.repo) / "工作区" / f"上下文包-{args.chapter:04d}.md"
        out.write_text(md, encoding="utf-8")
        print(f"OK v7-write pack chapter={args.chapter} used={stats['used']:,} file={out}")
        return 0
    if args.action == "check":
        decision = json.loads(Path(args.json).read_text(encoding="utf-8"))
        report = run_checks(Path(args.repo), decision, Path(args.draft).read_text(encoding="utf-8"))
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0 if report["ok"] else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
