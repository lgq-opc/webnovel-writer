#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from data_modules.config import DataModulesConfig
from data_modules.index_manager import EntityMeta, IndexManager
from data_modules.memory.orchestrator import MemoryOrchestrator
from data_modules.memory.schema import MemoryItem
from data_modules.memory.store import ScratchpadManager


def _cfg(tmp_path):
    cfg = DataModulesConfig.from_project_root(tmp_path)
    cfg.ensure_dirs()
    return cfg


def _write_split_outline(cfg, chapter: int, text: str) -> None:
    outline_dir = cfg.project_root / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / f"第{chapter}章 章纲.md").write_text(text, encoding="utf-8")


def test_build_memory_pack_empty(tmp_path):
    orchestrator = MemoryOrchestrator(_cfg(tmp_path))
    pack = orchestrator.build_memory_pack(1)
    assert pack["stats"]["total"] == 0
    assert pack["semantic_memory"] == []
    assert "long_term_facts" not in pack
    assert "active_constraints" not in pack
    assert "working_memory" in pack
    assert "episodic_memory" in pack
    assert "semantic_memory" in pack


def test_build_memory_pack_filter_and_budget(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.memory_orchestrator_max_items = 1
    outline_dir = cfg.project_root / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第1卷 详细大纲.md").write_text("### 第10章：萧炎突破\n", encoding="utf-8")

    store = ScratchpadManager(cfg)
    store.upsert_item(
        MemoryItem(
            id="m1",
            layer="semantic",
            category="character_state",
            subject="萧炎",
            field="realm",
            value="斗师",
            source_chapter=9,
        )
    )
    store.upsert_item(
        MemoryItem(
            id="m2",
            layer="semantic",
            category="story_fact",
            subject="chapter_hook",
            field="9",
            value="神秘强者出现",
            source_chapter=9,
        )
    )

    orchestrator = MemoryOrchestrator(cfg)
    pack = orchestrator.build_memory_pack(10)
    assert pack["stats"]["total"] >= 2
    assert len(pack["semantic_memory"]) == 1
    assert pack["stats"]["semantic_total"] >= 1


def _seed_state(tmp_path, cfg, pending: int, thread_items: int) -> None:
    import json

    state = {
        "protagonist_state": {"name": "萧炎"},
        "plot_threads": {"foreshadowing": [{"id": i, "note": f"伏笔{i}"} for i in range(thread_items)]},
        "disambiguation_pending": [{"mention": f"实体{i}"} for i in range(pending)],
    }
    (cfg.project_root / ".webnovel" / "state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8"
    )


def _state_export(pack):
    working = pack["working_memory"]
    return next(item for item in working if item["source"] == "state_export")["content"]


def test_state_export_capped_to_limit(tmp_path):
    cfg = _cfg(tmp_path)
    _seed_state(tmp_path, cfg, pending=15, thread_items=15)

    pack = MemoryOrchestrator(cfg).build_memory_pack(1)

    export = _state_export(pack)
    assert len(export["disambiguation_pending"]) == 10
    assert len(export["plot_threads"]["foreshadowing"]) == 10


def test_state_export_limit_zero_keeps_all(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.memory_state_export_pending_limit = 0
    _seed_state(tmp_path, cfg, pending=15, thread_items=3)

    pack = MemoryOrchestrator(cfg).build_memory_pack(1)

    export = _state_export(pack)
    assert len(export["disambiguation_pending"]) == 15
    assert len(export["plot_threads"]["foreshadowing"]) == 3


def test_episodic_memory_has_no_state_change_duplicate(tmp_path):
    cfg = _cfg(tmp_path)

    pack = MemoryOrchestrator(cfg).build_memory_pack(1)

    assert all(item["source"] != "state_change" for item in pack["episodic_memory"])
    assert "recent_changes" in pack


def test_filter_relevant_keeps_item_matched_by_entity_alias(tmp_path):
    """R13/F-13：subject 是实体 ID、正名不在章纲、只有代称（别名）在章纲 → 必须保留。

    source_window 压到 1 排除「靠窗口兜底救回」，旧实现的整串子串比对
    （subject/field/value[:20] 都不在 outline）会漏检，故先失败。
    """
    cfg = _cfg(tmp_path)
    cfg.memory_orchestrator_source_window = 1
    _write_split_outline(
        cfg,
        50,
        "### 第50章：炎帝出手\n\n**目标**：炎帝当众展露实力，压服群雄。\n",
    )

    idx = IndexManager(cfg)
    idx.upsert_entity(
        EntityMeta(
            id="xiaoyan",
            type="角色",
            canonical_name="萧炎",
            current={"realm": "斗师"},
            first_appearance=1,
            last_appearance=5,
        )
    )
    assert idx.register_alias("炎帝", "xiaoyan", "角色") is True
    assert "炎帝" in idx.get_entity_aliases("xiaoyan")
    # 前提：章纲里既没有实体 ID，也没有正名，也没有 field/value 文本
    outline_text = (cfg.project_root / "大纲" / "第50章 章纲.md").read_text(encoding="utf-8")
    assert "xiaoyan" not in outline_text
    assert "萧炎" not in outline_text
    assert "realm" not in outline_text
    assert "斗师" not in outline_text

    ScratchpadManager(cfg).upsert_item(
        MemoryItem(
            id="m_alias",
            layer="semantic",
            category="character_state",
            subject="xiaoyan",
            field="realm",
            value="斗师",
            source_chapter=5,
        )
    )

    pack = MemoryOrchestrator(cfg).build_memory_pack(50)
    ids = [item["id"] for item in pack["semantic_memory"]]
    assert "m_alias" in ids


def test_entity_alias_lookup_memoized_once_per_build(tmp_path):
    """R13：同一次构建里同一个 entity_id 只查一次别名表（不在 per-item 循环里重复查库）。"""
    cfg = _cfg(tmp_path)
    cfg.memory_orchestrator_source_window = 1
    _write_split_outline(cfg, 50, "### 第50章：炎帝出手\n\n**目标**：压服群雄。\n")

    idx = IndexManager(cfg)
    idx.upsert_entity(
        EntityMeta(
            id="xiaoyan",
            type="角色",
            canonical_name="萧炎",
            current={},
            first_appearance=1,
            last_appearance=5,
        )
    )
    idx.register_alias("炎帝", "xiaoyan", "角色")

    store = ScratchpadManager(cfg)
    for field in ("realm", "location", "mood"):
        store.upsert_item(
            MemoryItem(
                id=f"m_{field}",
                layer="semantic",
                category="character_state",
                subject="xiaoyan",
                field=field,
                value="未知",
                source_chapter=5,
            )
        )

    calls = []
    original = IndexManager.get_entity_aliases

    def counting(self, entity_id):
        calls.append(entity_id)
        return original(self, entity_id)

    IndexManager.get_entity_aliases = counting
    try:
        MemoryOrchestrator(cfg).build_memory_pack(50)
    finally:
        IndexManager.get_entity_aliases = original

    assert calls.count("xiaoyan") == 1


def test_free_text_item_uses_keyword_token_overlap(tmp_path):
    """R13：自由文本类（open_loop）subject/field/value 与章纲按词元重合度比对。

    (a) 词元重合足够 → 保留（旧实现要求整串子串，会漏检）；
    (b) 只有一个词元偶然相同 → 不构成命中，不得靠它救回。
    """
    cfg = _cfg(tmp_path)
    cfg.memory_orchestrator_source_window = 1
    _write_split_outline(
        cfg,
        50,
        "### 第50章：风起\n\n**目标**：神秘人身份揭秘后，天空裂开。\n",
    )

    store = ScratchpadManager(cfg)
    store.upsert_item(
        MemoryItem(
            id="loop_hit",
            layer="semantic",
            category="open_loop",
            subject="神秘人身份揭秘伏笔钩",
            field="status",
            value="神秘人身份揭秘伏笔钩",
            source_chapter=5,
        )
    )
    store.upsert_item(
        MemoryItem(
            id="loop_miss",
            layer="semantic",
            category="open_loop",
            subject="天空之上的第九重封印为何松动",
            field="status",
            value="天空之上的第九重封印为何松动",
            source_chapter=5,
        )
    )

    pack = MemoryOrchestrator(cfg).build_memory_pack(50)
    ids = [item["id"] for item in pack["semantic_memory"]]
    assert "loop_hit" in ids
    assert "loop_miss" not in ids
