#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any


DISABLE_ENV = "WEBNOVEL_DISABLE_RUNTIME_GUARD_HOOK"
# state.json is intentionally NOT protected: audits routinely require bulk
# fixes that update_state.py flags cannot express, and state.json has its own
# backup + rebuild path (issue #113).
PROTECTED_SUFFIXES = (
    ".story-system/commits/",
    ".webnovel/index.db",
    ".webnovel/vectors.db",
    ".webnovel/memory_scratchpad.json",
    ".webnovel/projection_log.jsonl",
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_input() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalized_path(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    raw = raw.replace("\\", "/")
    try:
        if ":" in raw[:3]:
            raw = PureWindowsPath(str(value)).as_posix()
        else:
            raw = PurePosixPath(raw).as_posix()
    except Exception:
        pass
    return raw.lower()


def _deny(message: str) -> int:
    payload = {
        "hookSpecificOutput": {"permissionDecision": "deny"},
        "systemMessage": message,
    }
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    return 2


def _tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("tool_input") or payload.get("toolInput") or payload.get("input") or {}
    return value if isinstance(value, dict) else {}


def _tool_name(payload: dict[str, Any]) -> str:
    return str(payload.get("tool_name") or payload.get("toolName") or payload.get("tool") or "").strip()


def _file_path_from_tool_input(tool_input: dict[str, Any]) -> str:
    for key in ("file_path", "path", "filename"):
        value = tool_input.get(key)
        if value:
            return str(value)
    return ""


def _is_protected_path(path: str) -> bool:
    normalized = _normalized_path(path)
    if not normalized:
        return False
    return any(suffix in normalized for suffix in PROTECTED_SUFFIXES)


# v7 写链是唯一在役的运行时写通道；v6 的 `chapter-commit` / `projections retry|replay`
# 已随 v6 写链退役从 CLI 撤出（走它们 rc=2 invalid choice，见
# data_modules/project_status.py:57）。deny 文案与白名单同源取自下面两个常量：只改一侧
# 就会重现「文案推荐、闸门拦截」的脱钩（CC 评审 A-1）。
RUNTIME_ENTRY_MARKER = "webnovel.py"
RUNTIME_SAFE_MARKERS = ("v7-write",)
RUNTIME_WRITE_HINT = f"{RUNTIME_ENTRY_MARKER} v7-write settle"


def _command_is_runtime_safe(command: str) -> bool:
    lowered = command.lower()
    if RUNTIME_ENTRY_MARKER not in lowered:
        return False
    return any(marker in lowered for marker in RUNTIME_SAFE_MARKERS)


# 复合命令（`&&` / `||` / `;` / `|`）按段切分后逐段判定（CC 复评 R-1）：白名单只豁免
# sanctioned 段自身，不能让 `… v7-write settle && rm -f .webnovel/index.db` 的破坏性
# 后缀段搭车放行（改前命中白名单即整条 `return False`，拦截集因此在白名单换代后收缩）。
_COMMAND_SEPARATOR_RE = re.compile(r"&&|\|\||[;|]")
_PROTECTED_WRITE_RE = re.compile(
    r"(?:^|\s)("
    r">>|>|out-file|set-content|add-content|copy-item|move-item|remove-item|"
    r"del|rm|rmdir|python|python3|cp|mv|tee|dd|sed\s+-\S*i|git\s+checkout"
    r")(?=\s|$)"
)


def _segment_looks_like_direct_projection_write(segment: str) -> bool:
    if _command_is_runtime_safe(segment):
        return False
    # 增量审阅 P3-17：补齐 cp/mv/rm/tee/sed -i/dd/git checkout 等绕过写入通道
    if any(suffix in segment for suffix in PROTECTED_SUFFIXES) and _PROTECTED_WRITE_RE.search(segment):
        return True
    if "chapter_commit.py" in segment and "webnovel.py" not in segment:
        return True
    return False


def _looks_like_direct_projection_write(command: str) -> bool:
    lowered = command.lower().replace("\\", "/")
    segments = _COMMAND_SEPARATOR_RE.split(lowered)
    return any(_segment_looks_like_direct_projection_write(segment) for segment in segments)


def main() -> int:
    if _truthy(os.environ.get(DISABLE_ENV)):
        return 0

    payload = _load_input()
    tool_input = _tool_input(payload)
    tool = _tool_name(payload)

    command = str(tool_input.get("command") or "")
    if tool.lower() == "bash" or command:
        if _looks_like_direct_projection_write(command):
            return _deny(
                "webnovel-writer blocked a direct write or bypass command for Story System/read-model files. "
                f"Use the webnovel runtime commands instead (v7 书仓写链：{RUNTIME_WRITE_HINT}) so "
                "commit/projection invariants stay consistent."
            )
        return 0

    path = _file_path_from_tool_input(tool_input)
    if _is_protected_path(path):
        return _deny(
            "webnovel-writer blocked a direct edit to Story System/read-model files. Use runtime commands so commit/projection invariants stay consistent."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


