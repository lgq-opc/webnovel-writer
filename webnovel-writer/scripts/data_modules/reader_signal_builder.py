"""reader_signal 构建器（webnovel-copilot-300 · M5/T25，R4/F-06）。

消费端闭环：近期追读力 + 钩子类型分布 + 审查趋势汇总 → load-context 的
`reader_signal` section；`index get-reader-signals` 补 `review_trend` 字段。
`derive_differentiation_reminder`：连续两章同型钩子 → 第三章差异化提醒
（writing_guidance hook_diversification 的主路径等价实现）。

**数据源按书仓形态分叉（2026-09-13，reader_signals 接通 spec §3.5）**：

- v7 书仓 → `.cache/index.db`（由 `v7_cache.rebuild_cache` 从正文 front matter 重算）；
- v6 书仓 → `.webnovel/index.db`（冻结，原路不改）。

形态判据复用 `domain_contract.resolve_write_mode`（与 doctor / F1 / F5 同源），
不另立第二套——两边各写一套判据必然漂移。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

REMINDER_TEMPLATE = "连续 {count} 章同型钩子「{hook_type}」：本章钩子必须差异化（换钩型/换强度/换落点）"
_REVIEW_TREND_LIMIT = 5
_RECENT_LIMIT = 5
_HOOK_USAGE_WINDOW = 20


def _empty_signal() -> dict[str, Any]:
    """降级结构。每次新建：常量共享内层 list/dict 会被调用方改动污染。"""
    return {
        "recent_reading_power": [],
        "hook_type_usage": {},
        "review_trend": [],
        "differentiation_reminder": "",
    }


def _is_v7_repo(root: Path) -> bool:
    from .domain_contract import resolve_write_mode

    return resolve_write_mode(root) == "v7"


def derive_differentiation_reminder(recent_reading_power: list[dict[str, Any]], *, min_streak: int = 2) -> str:
    """最近章节（按章号降序）钩子类型连续同型 → 差异化提醒；否则空串。"""
    streak_type = ""
    streak_count = 0
    for row in recent_reading_power:
        hook_type = str(row.get("hook_type") or "").strip()
        if not hook_type:
            break
        if hook_type == streak_type:
            streak_count += 1
        elif streak_count < min_streak:
            streak_type = hook_type
            streak_count = 1
        else:
            break
    if streak_count >= min_streak and streak_type:
        return REMINDER_TEMPLATE.format(count=streak_count, hook_type=streak_type)
    return ""


def build_reader_signal(project_root: Path | str) -> dict[str, Any]:
    """汇总追读力信号（只读；无数据源时优雅降级为空结构）。"""
    root = Path(project_root)
    return _v7_signal(root) if _is_v7_repo(root) else _v6_signal(root)


def _v7_signal(root: Path) -> dict[str, Any]:
    """v7：读 `.cache/index.db`。命中即重建（派生物可丢弃），故无需前置存在性守卫。"""
    try:
        from v7_cache import get_hook_type_usage, get_recent_reading_power

        recent = get_recent_reading_power(root, _RECENT_LIMIT)
        return {
            "recent_reading_power": recent,
            "hook_type_usage": get_hook_type_usage(root, _HOOK_USAGE_WINDOW),
            # v7 无 review_metrics 生产者（spec 非目标），保持空
            "review_trend": [],
            "differentiation_reminder": derive_differentiation_reminder(recent),
        }
    except Exception:  # noqa: BLE001 - 信号缺失不阻断装配
        return _empty_signal()


def _v6_signal(root: Path) -> dict[str, Any]:
    """v6：原路读 `.webnovel/index.db`（冻结，不改行为）。"""
    if not (root / ".webnovel" / "index.db").is_file():
        return _empty_signal()
    try:
        from .config import DataModulesConfig
        from .index_manager import IndexManager

        manager = IndexManager(DataModulesConfig.from_project_root(root))
        recent = manager.get_recent_reading_power(_RECENT_LIMIT)
        return {
            "recent_reading_power": recent,
            "hook_type_usage": manager.get_hook_type_stats(_HOOK_USAGE_WINDOW),
            "review_trend": manager.get_recent_review_metrics(_REVIEW_TREND_LIMIT),
            "differentiation_reminder": derive_differentiation_reminder(recent),
        }
    except Exception:  # noqa: BLE001 - 信号缺失不阻断装配
        return _empty_signal()
