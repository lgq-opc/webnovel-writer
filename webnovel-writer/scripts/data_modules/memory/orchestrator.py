#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长期记忆编排器。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Set

from ..config import DataModulesConfig, get_config
from ..index_manager import IndexManager
from .schema import MemoryItem
from .store import ScratchpadManager
from .budget import allocate_limits

try:
    from chapter_outline_loader import load_chapter_outline
except ImportError:  # pragma: no cover
    from scripts.chapter_outline_loader import load_chapter_outline


class MemoryOrchestrator:
    PRIORITY = {
        "world_rule": 0,
        "character_state": 1,
        "relationship": 2,
        "story_fact": 3,
        "open_loop": 4,
        "reader_promise": 5,
        "timeline": 6,
    }

    # R13/F-13：subject 装 entity_id 的类别（来源 memory/bootstrap.py 的
    # subject=entity_id / from_entity）；其余类别（open_loop / reader_promise）
    # 的 subject 是自由文本。
    ENTITY_SUBJECT_CATEGORIES = frozenset(
        {"character_state", "story_fact", "world_rule", "timeline", "relationship"}
    )
    # 词元切分：拉丁/下划线词整体成一个词元，中文连续串按二元窗口切分
    TOKEN_RE = re.compile("[A-Za-z][A-Za-z0-9_]*|[\\u4e00-\\u9fff]+")
    # 单字符词元丢弃（避免「的/了」这类短词过度命中）
    TOKEN_MIN_CHARS = 2
    # 自由文本命中门槛：条目侧词元至少一半在章纲中出现（防超长串偶然命中）
    TOKEN_OVERLAP_THRESHOLD = 0.5

    def __init__(self, config: DataModulesConfig | None = None):
        self.config = config or get_config()
        self.index_manager = IndexManager(self.config)
        self.store = ScratchpadManager(self.config)

    def build_memory_pack(self, chapter: int, task_type: str = "write") -> Dict[str, Any]:
        outline = load_chapter_outline(self.config.project_root, chapter, max_chars=1500)

        working = self._build_working_memory(chapter=chapter, outline=outline)
        episodic = self._build_episodic_memory(chapter=chapter)
        active_items = self.store.query(status="active")
        conflicts = self.store.conflicts()
        filtered = self._filter_relevant(active_items, chapter=chapter, outline=outline)

        max_items = max(1, int(getattr(self.config, "memory_orchestrator_max_items", 30)))
        limits = allocate_limits(max_items=max_items, task_type=task_type)
        semantic_items = self._apply_budget(filtered, max_items=limits["semantic"])
        working_items = working[: limits["working"]]
        episodic_items = episodic[: limits["episodic"]]
        semantic_payload = [item.to_dict() for item in semantic_items]

        recent_changes = self.index_manager.get_recent_state_changes(
            limit=max(1, int(getattr(self.config, "memory_orchestrator_recent_changes_limit", 10)))
        )

        warnings = []
        if conflicts:
            warnings.append(
                {
                    "type": "memory_conflict",
                    "count": len(conflicts),
                    "sample": conflicts[:5],
                }
            )

        return {
            "working_memory": working_items,
            "episodic_memory": episodic_items,
            "semantic_memory": semantic_payload,
            # B4 去重：long_term_facts（=semantic_memory 复制）与 active_constraints
            # （semantic 子集复制）不再随包重复注入，语义事实以 semantic_memory 为唯一来源。
            "recent_changes": list(recent_changes),
            "warnings": warnings,
            "stats": {
                "total": len(active_items),
                "working_total": len(working),
                "episodic_total": len(episodic),
                "semantic_total": len(filtered),
                "injected": len(semantic_payload),
                "layered_total_injected": len(working_items) + len(episodic_items) + len(semantic_payload),
                "filtered": max(0, len(active_items) - len(filtered)),
                "conflicts": len(conflicts),
            },
        }

    def _filter_relevant(self, items: List[MemoryItem], chapter: int, outline: str) -> List[MemoryItem]:
        if not items:
            return []
        if not outline:
            return sorted(items, key=lambda x: (x.source_chapter, x.updated_at), reverse=True)

        outline_tokens = self._tokens(outline)
        alias_cache: Dict[str, List[str]] = {}
        keep: List[MemoryItem] = []
        source_window = max(1, int(getattr(self.config, "memory_orchestrator_source_window", 20)))
        for item in items:
            if self._matches_outline(item, outline, outline_tokens, alias_cache):
                keep.append(item)
                continue
            if item.source_chapter > 0 and chapter - item.source_chapter <= source_window:
                keep.append(item)

        return sorted(keep, key=lambda x: (self.PRIORITY.get(x.category, 99), -x.source_chapter))

    def _matches_outline(
        self,
        item: MemoryItem,
        outline: str,
        outline_tokens: Set[str],
        alias_cache: Dict[str, List[str]],
    ) -> bool:
        """R13/F-13：条目是否与本章相关。

        - 实体类（subject=entity_id）：展开实体全部别名，任一别名在章纲文本中出现即命中
          （代称/同义词不再漏检）；field/value 仍按词元重合比对。
        - 自由文本类：subject/field/value 与章纲按词元重合度比对，不再做整串子串包含。
        """
        if item.category in self.ENTITY_SUBJECT_CATEGORIES:
            if item.subject and item.subject in outline:
                return True
            for name in self._entity_names(item.subject, alias_cache):
                if name in outline:
                    return True
            return self._overlaps_outline((item.field, item.value), outline_tokens)
        return self._overlaps_outline((item.subject, item.field, item.value), outline_tokens)

    def _entity_names(self, entity_id: str, alias_cache: Dict[str, List[str]]) -> List[str]:
        """实体的候选名称（ID 本身 + 别名表全部别名）。

        同一次构建里同一个 entity_id 只查一次库——结果（含空结果）写入 alias_cache。
        """
        key = str(entity_id or "")
        if not key:
            return []
        if key not in alias_cache:
            names = [key]
            names.extend(self.index_manager.get_entity_aliases(key))
            alias_cache[key] = list(dict.fromkeys(name for name in names if name))
        return alias_cache[key]

    def _overlaps_outline(self, texts: Iterable[str], outline_tokens: Set[str]) -> bool:
        if not outline_tokens:
            return False
        for text in texts:
            tokens = self._tokens(text)
            if not tokens:
                continue
            matched = len(tokens & outline_tokens)
            if matched and matched / len(tokens) >= self.TOKEN_OVERLAP_THRESHOLD:
                return True
        return False

    def _tokens(self, text: str) -> Set[str]:
        """把文本切成语义词元：拉丁词（≥2 字符）整体、中文二元词元，单字丢弃。"""
        tokens: Set[str] = set()
        for raw in self.TOKEN_RE.findall(str(text or "")):
            if raw[0].isascii():
                if len(raw) >= self.TOKEN_MIN_CHARS:
                    tokens.add(raw.lower())
                continue
            if len(raw) < self.TOKEN_MIN_CHARS:
                continue
            if len(raw) == self.TOKEN_MIN_CHARS:
                tokens.add(raw)
            else:
                tokens.update(
                    raw[i : i + self.TOKEN_MIN_CHARS] for i in range(len(raw) - 1)
                )
        return tokens

    def _apply_budget(self, items: List[MemoryItem], max_items: int) -> List[MemoryItem]:
        if max_items <= 0:
            return []
        if len(items) <= max_items:
            return list(items)
        return list(items[:max_items])

    def _load_state(self) -> Dict[str, Any]:
        path = self.config.state_file
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            import sys
            print(f"⚠️ state.json 读取失败: {exc}", file=sys.stderr)
            return {}

    def _load_recent_summaries(self, chapter: int, window: int) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        summary_dir = self.config.webnovel_dir / "summaries"
        if not summary_dir.exists():
            return result
        for ch in range(max(1, chapter - window), chapter):
            path = summary_dir / f"ch{ch:04d}.md"
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            if text:
                result.append({"layer": "working", "source": "summary", "chapter": ch, "content": text[:800]})
        return result

    def _build_working_memory(self, chapter: int, outline: str) -> List[Dict[str, Any]]:
        state = self._load_state()
        result: List[Dict[str, Any]] = []
        if outline:
            result.append({"layer": "working", "source": "outline", "chapter": chapter, "content": outline})

        summary_window = max(1, int(getattr(self.config, "context_recent_summaries_window", 3)))
        result.extend(self._load_recent_summaries(chapter=chapter, window=summary_window))

        state_export = {
            "protagonist_state": state.get("protagonist_state", {}),
            "plot_threads": self._cap_list_values(state.get("plot_threads", {}) or {}),
            "disambiguation_pending": self._cap_pending(state.get("disambiguation_pending", []) or []),
        }
        result.append(
            {
                "layer": "working",
                "source": "state_export",
                "chapter": chapter,
                "content": state_export,
            }
        )
        return result

    def _cap_pending(self, pending: List[Any]) -> List[Any]:
        limit = max(0, int(getattr(self.config, "memory_state_export_pending_limit", 10)))
        if limit <= 0:
            return list(pending)
        return list(pending[:limit])

    def _cap_list_values(self, plot_threads: Dict[str, Any]) -> Dict[str, Any]:
        limit = max(0, int(getattr(self.config, "memory_state_export_pending_limit", 10)))
        capped: Dict[str, Any] = {}
        for key, value in plot_threads.items():
            if isinstance(value, list) and limit > 0:
                capped[key] = value[:limit]
            else:
                capped[key] = value
        return capped

    def _build_episodic_memory(self, chapter: int) -> List[Dict[str, Any]]:
        _ = chapter
        changes_limit = max(1, int(getattr(self.config, "memory_orchestrator_recent_changes_limit", 10)))
        rel_limit = max(1, min(20, changes_limit))

        recent_relationships = self.index_manager.get_recent_relationships(limit=rel_limit)
        recent_appearances = self.index_manager.get_recent_appearances(limit=rel_limit)

        result: List[Dict[str, Any]] = []
        for row in recent_relationships:
            result.append(
                {
                    "layer": "episodic",
                    "source": "relationship",
                    "chapter": int(row.get("chapter") or 0),
                    "entity_id": row.get("from_entity", ""),
                    "field": row.get("to_entity", ""),
                    "content": row,
                }
            )
        for row in recent_appearances:
            result.append(
                {
                    "layer": "episodic",
                    "source": "appearance",
                    "chapter": int(row.get("chapter") or 0),
                    "entity_id": row.get("entity_id", ""),
                    "field": "appearance",
                    "content": row,
                }
            )

        result.sort(key=lambda x: int(x.get("chapter") or 0), reverse=True)
        return result
