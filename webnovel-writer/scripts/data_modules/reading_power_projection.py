"""追读力投影 writer（webnovel-copilot-300 · M5/T25，R4/F-05）。

**v7 路径**（2026-09-13 起）：钩子由决策卡声明 → settle 写入正文 front matter →
`.cache/index.db` 的 chapter_reading_power 表由 `v7_cache.rebuild_cache` 重算。
本模块在 v7 侧只剩 `reading_status`（回报落账状态，不写盘）。

**v6 路径**（冻结）：`ReadingPowerProjectionWriter` 仍服务 v6 投影链——accepted 提交
自动落表，数据源为 data-agent extraction_result 的钩子字段（顶层 `hook_type`/
`hook_strength`，或摘要 front matter 中的同名键）；无钩子字段时 skipped（不阻断提交）。
该 writer 的生产引用者的去留属 Phase 3（见 docs/plans/2026-09-10-v6线退役方案.md）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_HOOK_TYPE_RE = re.compile(r"^hook_type:\s*[\"']?([^\n\"']+)", re.MULTILINE)
_HOOK_STRENGTH_RE = re.compile(r"^hook_strength:\s*[\"']?([^\n\"']+)", re.MULTILINE)


def extract_hook_fields(extraction_result: dict[str, Any]) -> tuple[str, str]:
    """从 extraction_result 取钩子字段：顶层键优先，其次摘要 front matter。"""
    if not isinstance(extraction_result, dict):
        return "", ""
    hook_type = str(extraction_result.get("hook_type") or "").strip()
    hook_strength = str(extraction_result.get("hook_strength") or "").strip()
    if hook_type and hook_strength:
        return hook_type, hook_strength
    summary = str(extraction_result.get("summary_text") or "")
    if summary.startswith("---"):
        if not hook_type:
            match = _HOOK_TYPE_RE.search(summary)
            if match:
                hook_type = match.group(1).strip()
        if not hook_strength:
            match = _HOOK_STRENGTH_RE.search(summary)
            if match:
                hook_strength = match.group(1).strip()
    return hook_type, hook_strength


def reading_status(chapter: int, hook_type: str = "", hook_strength: str = "") -> dict[str, Any]:
    """v7 settle 后置：回报本章追读力落账状态（写盘职责已退役，见 spec §3.4）。

    钩子由决策卡声明、settle 写入正文 front matter（canonical），`.cache` 的
    chapter_reading_power 表由 `v7_cache.rebuild_cache` 从那里重算——故此处**只回报不写盘**。

    此前它从摘要 front matter 提取钩子再写 v6 `.webnovel/index.db`：真实流程传的是
    纯文本摘要（`skills/webnovel-write/SKILL.md:177`），故恒 skipped；且属 D-2 乙要消灭的
    v6 域副作用。两条问题一并随本次改动消失。
    """
    hook = str(hook_type or "").strip()
    if not hook:
        return {"status": "skipped", "reason": "not_required"}
    return {
        "status": "ok",
        "hook_type": hook,
        "hook_strength": hook_strength or "medium",
        "chapter": int(chapter),
    }


class ReadingPowerProjectionWriter:
    name = "reading_power"

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def apply(self, commit_payload: dict) -> dict:
        status = str((commit_payload.get("meta") or {}).get("status") or "")
        if status != "accepted":
            return {"applied": False, "writer": self.name, "reason": "commit_rejected"}
        extraction = commit_payload.get("extraction_result") or {}
        hook_type, hook_strength = extract_hook_fields(extraction if isinstance(extraction, dict) else {})
        if not hook_type:
            return {"applied": False, "writer": self.name, "reason": "not_required"}
        try:
            from .config import DataModulesConfig
            from .index_manager import ChapterReadingPowerMeta, IndexManager

            meta = ChapterReadingPowerMeta(
                chapter=int((commit_payload.get("meta") or {}).get("chapter") or 0),
                hook_type=hook_type,
                hook_strength=hook_strength or "medium",
            )
            IndexManager(DataModulesConfig.from_project_root(self.project_root)).save_chapter_reading_power(meta)
        except Exception as exc:  # noqa: BLE001 - 投影失败走 failed 状态，不中断链
            return {"applied": False, "writer": self.name, "reason": f"error:{exc}"}
        return {"applied": True, "writer": self.name, "chapter": meta.chapter, "hook_type": hook_type}
