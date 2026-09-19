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
    # U-14（2026-09-13）：字数契约原来只算不渲染（幽灵 section）。小字典，配额给足即可。
    "length_contract": 300,
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
    "length_contract",  # U-14：小且是写作契约，放最后丢——但必须可丢（非 PROTECTED）
)
V7_SECTION_TITLES: dict[str, str] = {
    "decision_card": "决策卡",
    # U-14（t-20260913-ff22）：渲染只遍历本表（见 V7_RENDER_ORDER），故「进上下文包」
    # 必须在这里登记——S19 方案 :42 要求「上下文包新增 length_contract 节」，
    # 此前只写了数据没登记标题，于是它计入 sections_before 统计却从未出现在包里。
    "length_contract": "字数契约（书史基准）",
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


def resolve_target_words(repo: Path, decision: dict[str, Any]) -> tuple[int, str]:
    """本章目标字数的**唯一事实源**：决策卡显式值 > 书史均值 > 2000 兜底。

    返回 `(字数, 来源)`，来源 ∈ `{"explicit", "book_mean", "default"}`。

    决策卡与上下文包都必须走这里。S19 曾把这条规则只写进了上下文包一侧，
    决策卡上作者看不到推导值——「两处各写一遍」正是它会漂的原因（t-20260913-38c4）。
    """
    explicit = int(decision.get("target_words") or 0)
    if explicit:
        return explicit, "explicit"
    mean = int(book_word_stats(repo)["mean"] or 0)
    if mean:
        return mean, "book_mean"
    return 2000, "default"


def write_decision_card(repo: Path, decision: dict[str, Any]) -> Path:
    chapter = int(decision["chapter"])
    lines = [f"# 决策卡 · 第{chapter:04d}章", ""]
    for key in ("title", "pov", "time_anchor"):
        if decision.get(key):
            lines.append(f"- {key}: {decision[key]}")
    # S19 第二半（t-20260913-38c4）：没显式给也要显示**推导值**——决策卡是作者界面单位，
    # 推导出来的字数契约同样要让他看见，并标明来源，免得他以为是自己的设定。
    target, target_source = resolve_target_words(Path(repo), decision)
    target_note = {"book_mean": "（推导自书史均值）", "default": "（默认值：书史不足）"}.get(target_source, "")
    lines.append(f"- 目标字数: {target}（下限 {int(target * 0.75)}）{target_note}")
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
    """当卷详细大纲中本章小节（规范路径优先，旧 nested / v6 平铺只读兼容）。"""
    from data_modules.outline_paths import extract_chapter_section, resolve_detailed_outline

    vol = int(decision.get("volume") or 0)
    if not vol:
        size = int(_book_yaml_scalar(repo, "卷规模") or 0)
        vol = (chapter - 1) // size + 1 if size else 1
    path = resolve_detailed_outline(repo, vol)
    if path is None:
        return ""
    return extract_chapter_section(path.read_text(encoding="utf-8"), chapter) or ""


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
    target, _target_source = resolve_target_words(repo, decision)  # 与决策卡同源，勿另写规则
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

    # 钩子硬闸（reader_signals 接通 spec §3.2，Human 2026-09-13 裁定）：沿用 promises/waiver
    # 的同一 idiom——把「静默跳过」变成「显式决定」。此前 v7 追读力恒 skipped 且无人察觉。
    hook_type = str(decision.get("hook_type") or "").strip()
    hook_ok = bool(hook_type) or bool(decision.get("hook_waiver"))

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
    if not hook_ok:
        issues.append(
            {
                "severity": "high",
                "category": "hook",
                "description": "钩子未声明：决策卡需给出 hook_type 或 hook_waiver（追读力投影据此落账）",
                "evidence": "hook_type 为空且无 hook_waiver",
            }
        )

    ok = word_count >= min_words and not placeholders and title_ok and promise_ok and hook_ok
    return {
        "ok": ok,
        "word_count": word_count,
        "min_words": min_words,
        "min_words_source": min_words_source,
        "target_words": target,
        "placeholders": placeholders,
        "title_ok": title_ok,
        "promise_ok": promise_ok,
        "hook_ok": hook_ok,
        "promise_progress": promise_progress,
        "new_name_candidates": new_name_candidates,
        "issues": issues,
        "checks": {
            "min_words": MIN_WORDS,
            "max_words": MAX_WORDS,
            "book_max": book_stats["max"],
            "placeholder_scan": "v7-write",
            "promise_waiver_reason": decision.get("waiver") or "",
            "hook_waiver_reason": decision.get("hook_waiver") or "",
        },
    }


# ---------- settle ----------


def _git(repo: Path, *args: str) -> None:
    try:
        # N-4：显式 encoding="utf-8"（git 输出为 UTF-8）。此处 **必须带 errors="replace"**：
        # 这两个流只用于下面那句错误消息——而 git 的**诊断消息**随 locale 走
        # （本地化中文版 git 会输出 GBK）。若用死板 UTF-8 解码，一旦某台机器装了本地化
        # git，解码异常会在 subprocess.run 内部抛出、**不被下面的 CalledProcessError 捕获**，
        # 把一个干净的业务报错变成未捕获崩溃。诊断文本宁可降级也不该炸。
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or f"exit {exc.returncode}"
        raise RuntimeError(f"git {' '.join(args)}: {detail}") from exc


def _commit_with_identity_fallback(repo: Path, message: str) -> None:
    """无任何 git 身份配置时兜底提交身份，避免 settle 因身份缺失整体回滚（增量审阅 P2-3）。"""
    probe = subprocess.run(
        ["git", "-C", str(repo), "config", "user.email"],
        # N-4：输出只用于判断"身份是否已配置"（看空不空），故英文/中文邮箱都只需可解码，
        # 无需死板——诊断性用途一律带 errors="replace"（同 _git）。
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    identity: list[str] = []
    if not probe.stdout.strip():
        identity = ["-c", "user.name=webnovel-settle", "-c", "user.email=webnovel-settle@local"]
    _git(repo, *identity, "commit", "-m", message)


def _v6_root_from_git_config(repo: Path) -> str:
    """增量审阅 P2-4：读迁移器落在 v7 仓 git config 的 dualformat.v6root 映射（无则空串）。

    N-4：必须显式 `encoding="utf-8"`。这个值是**路径**，且中文书仓路径很常见；
    省掉 encoding 时 `text=True` 会按 locale 解码（中文 Windows = cp936），
    把 UTF-8 的路径**静默改写**成乱码——守卫随后拿它去比对，两头都对不上，
    `dual_format_guard` 无声失效。实测已复现（见 tests/test_git_subprocess_encoding.py）。

    **此处刻意用严格 UTF-8（不设 `errors="replace"`）**，与同文件 `_git` 的处理相反：
    这是**取值**用途，值错了会被当路径用；宁可解码失败炸出来，也不要拿到一串看似
    正常的乱码路径。诊断性用途（`_git` / user.email / git --version）才用 replace。
    """
    probe = subprocess.run(
        ["git", "-C", str(repo), "config", "dualformat.v6root"],
        capture_output=True, text=True, encoding="utf-8",
    )
    return probe.stdout.strip() if probe.returncode == 0 else ""


class GateRejected(RuntimeError):
    """settle 门禁拒绝（CLI 退出码 2）。`.report` 为结构化明细（review / prose / materials）。"""

    def __init__(self, message: str, report: dict[str, Any]):
        super().__init__(message)
        self.report = report


def _prose_flagged(body: str) -> list[str]:
    from data_modules.prose_check import check_prose

    return list(check_prose(body).get("flagged") or [])


def _read_review(repo: Path, chapter: int) -> dict[str, Any]:
    """门①：读 reviewer 直写的 review_results.json；顶层或 review_result 嵌套两种 schema 都认。"""
    path = Path(repo) / ".webnovel" / "tmp" / "review_results.json"
    if not path.is_file():
        return {"ok": False, "blocking_count": None, "reason": "未审查：缺 .webnovel/tmp/review_results.json"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    inner = payload.get("review_result") if isinstance(payload.get("review_result"), dict) else payload
    got_chapter = payload.get("chapter", inner.get("chapter"))
    if got_chapter is not None and int(got_chapter) != int(chapter):
        return {"ok": False, "blocking_count": None, "reason": f"审查文件章号不符（chapter={got_chapter}，本章 {chapter}），视同未审查"}
    blocking = int(inner.get("blocking_count") or 0)
    return {"ok": blocking == 0, "blocking_count": blocking, "reason": "" if blocking == 0 else f"审查 blocking={blocking}"}


def _material_refs(repo: Path, decision: dict[str, Any], chapter: int) -> list[str]:
    """门③输入：决策 JSON `material_refs` ∪ 章纲卡 `素材引用`（与 material_usage.log_chapter_materials 同源）。"""
    refs = [str(r) for r in (decision.get("material_refs") or [])]
    card = Path(repo) / "大纲" / "章纲" / f"{chapter:04d}.md"
    if card.is_file():
        from data_modules.chapter_outline_batch import parse_chapter_card

        fields, _ = parse_chapter_card(card.read_text(encoding="utf-8"))
        extra = fields.get("素材引用") or []
        refs += [extra] if isinstance(extra, str) else [str(r) for r in extra]
    return list(dict.fromkeys(refs))


def _run_gates(repo: Path, decision: dict[str, Any], body: str, *, bypass_reason: str) -> dict[str, Any]:
    """三门禁（阶段一 P1-2）：审查 / 文笔可 bypass；素材引用不可 bypass。拒绝抛 GateRejected。"""
    chapter = int(decision["chapter"])
    review = _read_review(repo, chapter)
    flagged = _prose_flagged(body)
    prose = {"ok": not flagged, "flagged": flagged}
    from data_modules.material_usage import resolve_ref

    resolved: list[str] = []
    unresolved: list[str] = []
    for ref in _material_refs(repo, decision, chapter):
        (resolved if resolve_ref(repo, ref).get("ok") else unresolved).append(ref)
    materials = {"ok": not unresolved, "resolved": resolved, "unresolved": unresolved}
    gates: dict[str, Any] = {"review": review, "prose": prose, "materials": materials, "bypassed": False, "bypass_reason": ""}
    if unresolved:
        raise GateRejected(f"素材引用无法解析（不可绕过）：{'、'.join(unresolved)}", gates)
    soft_fail = [name for name, gate in (("review", review), ("prose", prose)) if not gate["ok"]]
    if soft_fail:
        if not bypass_reason:
            detail = "；".join(filter(None, [review.get("reason"), f"文笔 flagged={flagged}" if flagged else ""]))
            raise GateRejected(
                f"门禁拒绝（{'/'.join(soft_fail)}）：{detail}。作者明确要求时可 --force-review-bypass \"<理由>\"", gates
            )
        gates["bypassed"] = True
        gates["bypass_reason"] = bypass_reason
    return gates


_SETTLE_ADD_PATHS = (
    "定稿",
    "素材/使用轨迹.jsonl",
    "文风/指纹.yaml",
    "作者/journal.jsonl",
)


def _run_post_hooks(repo: Path, chapter: int, decision: dict[str, Any]) -> dict[str, Any]:
    """P3-1：素材轨迹 → 文风指纹/采样 → 追读力。各自失败不阻断 settle。

    追读力自 2026-09-13 起不再写盘：钩子已随正文 front matter 落 canonical，
    `.cache` 由 settle 末尾的 rebuild 重算（见 reading_power_projection.reading_status）。
    """
    post: dict[str, Any] = {}
    try:
        from data_modules.material_usage import log_chapter_materials

        report = log_chapter_materials(repo, chapter)
        if report.get("ok"):
            post["materials"] = {"status": "ok", "logged": len(report.get("logged") or [])}
        elif report.get("error") == "already_logged":
            post["materials"] = {"status": "already_logged"}
        else:
            post["materials"] = {"status": "skipped", "reason": str(report.get("error") or "")}
    except Exception as exc:
        post["materials"] = {"status": "error", "reason": str(exc)}
    try:
        from data_modules.style_domain import settle_style_domain

        review = repo / ".webnovel" / "tmp" / "review_results.json"
        extraction = repo / ".webnovel" / "tmp" / "extraction_result.json"
        style = settle_style_domain(
            repo,
            chapter=chapter,
            review_file=review if review.is_file() else None,
            extraction_file=extraction if extraction.is_file() else None,
        )
        post["style"] = {
            "status": "ok",
            "recorded": int(style.get("recorded") or 0),
            "fingerprint_chapters": style.get("fingerprint_chapters", 0),
        }
    except Exception as exc:
        post["style"] = {"status": "error", "reason": str(exc)}
    try:
        from data_modules.reading_power_projection import reading_status

        post["reading"] = reading_status(
            chapter,
            decision.get("hook_type", ""),
            decision.get("hook_strength", ""),
        )
    except Exception as exc:
        post["reading"] = {"status": "error", "reason": str(exc)}
    return post


def _git_ignored(repo: Path, rel: str) -> bool:
    probe = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "-q", "--", rel],
        capture_output=True,
    )
    return probe.returncode == 0


def _git_add_settle_paths(repo: Path) -> list[str]:
    added: list[str] = []
    for rel in _SETTLE_ADD_PATHS:
        path = repo / rel
        if rel != "定稿" and not path.exists():
            continue
        if _git_ignored(repo, rel):
            continue
        _git(repo, "add", "--", rel)
        added.append(rel)
    return added


def _format_post(post: dict[str, Any]) -> str:
    materials = post.get("materials") or {}
    style = post.get("style") or {}
    reading = post.get("reading") or {}
    mat = str(materials.get("status") or "skipped")
    if mat == "ok":
        mat = f"ok/{int(materials.get('logged') or 0)}"
    sty = str(style.get("status") or "skipped")
    if sty == "ok":
        sty = f"fp={style.get('fingerprint_chapters', 0)},samples={style.get('recorded', 0)}"
    read = str(reading.get("status") or "skipped")
    return f"materials:{mat} style:{sty} reading:{read}"


def settle(
    repo: Path,
    decision: dict[str, Any],
    *,
    draft_path: Path,
    summary: str,
    commit: bool = True,
    force_review_bypass: Optional[str] = None,
) -> dict[str, Any]:
    repo = Path(repo)
    chapter = int(decision["chapter"])
    title = str(decision.get("title") or f"第{chapter}章")

    draft_text = Path(draft_path).read_text(encoding="utf-8")
    report = run_checks(repo, decision, draft_text)
    if not report["ok"]:
        raise RuntimeError(f"机检未通过，拒绝 settle：{json.dumps(report, ensure_ascii=False)}")

    # 阶段一 P1-2：三门禁在唯一写入路径检查之前、任何落盘之前
    bypass_reason = (force_review_bypass or "").strip()
    if force_review_bypass is not None and not bypass_reason:
        raise ValueError("--force-review-bypass 需要非空理由")
    body_clean = body_clean_of(draft_text)  # R12/F-15：与机检同一净稿口径
    gates = _run_gates(repo, decision, body_clean, bypass_reason=bypass_reason)

    # S18/E4：唯一写入路径——v6 侧已落定该章时禁止 v7 settle
    from data_modules.dual_format_guard import (
        check_unique_write_path,
        has_v7_settled_chapter,
        unchecked_other_side_warning,
    )

    v6_root = decision.get("v6_project_root") or _v6_root_from_git_config(repo)
    if v6_root:
        blocker = check_unique_write_path(Path(v6_root), chapter, target_format="v7", story_repo_root=repo)
        if blocker:
            raise RuntimeError("唯一写入路径：" + blocker["message"])
    else:
        # P2-2：v6 根未配置时守卫无法校验 v6 侧，必须提示而非静默
        gap = unchecked_other_side_warning("v7", project_root=None)
        print(f"[dual-format-guard] warning: {gap}", file=sys.stderr)
    # 章号前缀判重（增量审阅 P2-1）：同章改标题不得绕过防双写
    if has_v7_settled_chapter(repo, chapter):
        raise RuntimeError(f"唯一写入路径：该章已 settle（定稿/正文 存在 {chapter:04d}- 前缀文件），禁止双写")
    # t-20260913-a126：`book-init --no-git` 建的仓没有 .git，settle 默认承诺「原子提交」履行不了。
    # 这里在任何落盘之前给出**可执行**诊断；否则作者看到的是 git 的原始报错
    # 「fatal: not a git repository (or any of the parent directories): .git」，
    # 与 `--no-git` 的因果关系完全看不出来（该报错还被包在「settle 回滚」里，更难定位）。
    if commit and not (repo / ".git").exists():
        raise RuntimeError(
            f"settle 需要 git 才能提交，但该书仓不是 git 仓库：{repo}（`book-init --no-git` 建的仓没有 .git）。"
            "二选一：① 在该仓执行 `git init` 后重跑；② 本次加 `--no-commit`（只落盘、不提交）。"
        )
    chapter_file = repo / "定稿" / "正文" / f"{chapter:04d}-{title}.md"

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
    # 钩子落 canonical（reader_signals 接通 spec §3.1）：.cache 的追读力表由此重算，
    # 故必须与 书内时间/推进承诺/合同 同处正文 front matter，而非可清理的 工作区/。
    hook_type = str(decision.get("hook_type") or "").strip()
    if hook_type:
        from v7_cache import normalize_hook_strength

        front.append(f"钩子类型: {hook_type}")
        front.append(f"钩子强度: {normalize_hook_strength(decision.get('hook_strength', ''))}")
    front.append(f"字数: {word_count}")
    if gates["bypassed"]:
        front.append(f"审查绕过: {gates['bypass_reason']}")
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

        result = {"chapter": chapter, "committed": False, "chapter_file": str(chapter_file), "checks": report, "gates": gates}
        if gates["bypassed"]:
            # 绕过留痕（spec §4.3）：journal 事件四值均在 author_journal.VALID_* 白名单内
            from data_modules.author_journal import append_events

            append_events(
                repo,
                [
                    {
                        "actor": "author",
                        "action": "settle",
                        "domain": "正文",
                        "path": f"定稿/正文/{chapter_file.name}",
                        "change_kind": "content",
                        "diff_stat": {"ins": word_count, "del": 0},
                        "summary": (
                            f"settle 审查绕过：{gates['bypass_reason']}"
                            f"（blocking={gates['review'].get('blocking_count')}, prose_flagged={gates['prose']['flagged']}）"
                        ),
                        "impact": [],
                    }
                ],
            )
        result["post"] = _run_post_hooks(repo, chapter, decision)
        if commit:
            _git_add_settle_paths(repo)
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


def decision_card_path(repo: Path, chapter: int) -> Path:
    """决策卡路径（决策卡与 pack 的 --chapter 一一对应）。"""
    return Path(repo) / "工作区" / f"决策卡-{chapter:04d}.md"


def decision_from_card(repo: Path, chapter: int) -> Optional[dict[str, Any]]:
    """无决策 JSON 时从决策卡文本回退解析（title / pov / 关键实体），供 pack CLI 用。

    决策卡不存在时返回 None —— 由调用方决定报错策略（pack 必须显式报错退出，不得静默产出降级包）。
    """
    card = decision_card_path(repo, chapter)
    if not card.exists():
        return None
    decision: dict[str, Any] = {"chapter": chapter, "title": "", "entities": []}
    for line in card.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("- title:"):
            decision["title"] = s.split(":", 1)[1].strip()
        elif s.startswith("- pov:"):
            decision["pov"] = s.split(":", 1)[1].strip()
        elif s.startswith("- 关键实体:"):
            decision["entities"] = [e.strip() for e in re.split(r"[、,，]", s.split(":", 1)[1]) if e.strip()]
    return decision


_RUN_LOG_EVENT_PREFIX = "v7-"


def _log_write_step(repo: Path, action: str, chapter: int | None, status: str = "completed") -> None:
    """F4：把本次 v7 写链动作落进 `run_last.log`。

    写链的崩溃粒度靠 `run_last.log`——崩溃后靠最后一条判断卡在哪。前提是**每个
    步骤完成后有落账**。此前这步完全依赖模型记得手调
    `run-log --event <step> --append`，而那条要求只写在 SKILL.md 里、没有任何机器闸；
    实测在快模型上必然漏（fantasy01-v2 的 ch40 日志只剩 `write-start` 一行，
    doctor 因此长期报 `run_log.step_coverage`）。

    改为**由执行该步骤的工具自己落账**：跑过 `v7-write <action>` 就必然留痕，
    不再依赖自觉。

    「同章追加、换章重开」：日志末条属于本章就 `append`，否则（或日志不存在）
    覆盖重开——这样即使模型漏调 `write-start`，也不会把多章日志混在一起。

    记账失败**绝不阻断写链本身**（日志是旁路，不是门禁）。
    """
    try:
        from data_modules.run_logger import log_path, write_run_log

        chapter_num = int(chapter or 0)
        path = log_path(repo)
        append = False
        if path.is_file():
            try:
                lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
                if lines:
                    previous = json.loads(lines[-1])
                    append = int((previous.get("payload") or {}).get("chapter") or 0) == chapter_num
            except (OSError, ValueError):
                append = False
        write_run_log(
            repo,
            event=f"{_RUN_LOG_EVENT_PREFIX}{action}",
            payload={"chapter": chapter_num, "step": f"{_RUN_LOG_EVENT_PREFIX}{action}", "status": status},
            append=append,
        )
    except Exception:
        pass


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
    p_settle = sub.add_parser("settle", help="门禁 + 原子落定 + 后置落账（轨迹/指纹/追读力）")
    p_settle.add_argument("--repo", required=True)
    p_settle.add_argument("--chapter", type=int, required=True)
    p_settle.add_argument("--draft", required=True)
    p_settle.add_argument("--json", required=True, help="决策内容 JSON 文件")
    summary_group = p_settle.add_mutually_exclusive_group(required=True)
    summary_group.add_argument("--summary", help="章摘要文本（≤200 字）")
    summary_group.add_argument("--summary-file", help="章摘要文件")
    p_settle.add_argument("--no-commit", action="store_true")
    p_settle.add_argument(
        "--force-review-bypass", metavar="理由",
        help="显式绕过审查/文笔门禁（素材引用门不可绕过）；理由写入 front matter「审查绕过:」与 作者/journal.jsonl",
    )
    args = parser.parse_args(argv)

    if args.action == "decision":
        decision = json.loads(Path(args.json).read_text(encoding="utf-8"))
        print(write_decision_card(Path(args.repo), decision))
        _log_write_step(Path(args.repo), "decision", decision.get("chapter"))
        return 0
    if args.action == "pack":
        decision = json.loads(Path(args.json).read_text(encoding="utf-8")) if args.json else decision_from_card(Path(args.repo), args.chapter)
        if decision is None:
            card = decision_card_path(Path(args.repo), args.chapter)
            print(
                f"ERROR v7-write pack chapter={args.chapter}: 未提供 --json，且决策卡不存在：{card}\n"
                f"上下文包依赖决策卡（标题 / POV / 关键实体 / 承诺与合同断言）。正确顺序："
                f"先 `v7-write decision --chapter {args.chapter} --json <决策.json>` 生成决策卡，再 `v7-write pack --chapter {args.chapter}`。",
                file=sys.stderr,
            )
            return 1
        decision["chapter"] = args.chapter
        md, stats = build_context_pack(Path(args.repo), decision)
        out = Path(args.repo) / "工作区" / f"上下文包-{args.chapter:04d}.md"
        out.write_text(md, encoding="utf-8")
        print(f"OK v7-write pack chapter={args.chapter} used={stats['used']:,} file={out}")
        _log_write_step(Path(args.repo), "pack", args.chapter)
        return 0
    if args.action == "check":
        decision = json.loads(Path(args.json).read_text(encoding="utf-8"))
        report = run_checks(Path(args.repo), decision, Path(args.draft).read_text(encoding="utf-8"))
        print(json.dumps(report, ensure_ascii=False, indent=1))
        _log_write_step(Path(args.repo), "check", args.chapter, "completed" if report["ok"] else "failed")
        return 0 if report["ok"] else 2
    if args.action == "settle":
        decision = json.loads(Path(args.json).read_text(encoding="utf-8"))
        decision["chapter"] = args.chapter
        summary = args.summary if args.summary is not None else Path(args.summary_file).read_text(encoding="utf-8")
        try:
            result = settle(
                Path(args.repo), decision, draft_path=Path(args.draft), summary=summary,
                commit=not args.no_commit, force_review_bypass=args.force_review_bypass,
            )
        except GateRejected as exc:
            print(f"REJECTED v7-write settle chapter={args.chapter}: {exc}", file=sys.stderr)
            print(json.dumps(exc.report, ensure_ascii=False, indent=1), file=sys.stderr)
            _log_write_step(Path(args.repo), "settle", args.chapter, "rejected")
            return 2
        except (RuntimeError, ValueError) as exc:
            print(f"REJECTED v7-write settle chapter={args.chapter}: {exc}", file=sys.stderr)
            _log_write_step(Path(args.repo), "settle", args.chapter, "failed")
            return 2 if "机检" in str(exc) else 1
        print(
            f"OK v7-write settle chapter={args.chapter} committed={result['committed']} "
            f"bypassed={result['gates']['bypassed']} file={result['chapter_file']} "
            f"post={_format_post(result.get('post') or {})}"
        )
        _log_write_step(Path(args.repo), "settle", args.chapter)
        return 0
    return 0


if __name__ == "__main__":
    from runtime_compat import enable_windows_utf8_stdio
    enable_windows_utf8_stdio(skip_in_pytest=True)
    raise SystemExit(main())
