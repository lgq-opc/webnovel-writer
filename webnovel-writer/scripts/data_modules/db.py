"""Unified SQLite connection factory.

All data_modules code MUST use this instead of bare sqlite3.connect()
to ensure consistent concurrency settings (WAL + busy_timeout + FK).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

BUSY_TIMEOUT_MS = 5000


class _AutoClosingConnection(sqlite3.Connection):
    """`with connect(...) as conn:` 退出时**关闭连接**。

    这是 F8 在生产侧的同类修复。`sqlite3.Connection.__exit__` 只提交/回滚事务、
    **不关闭连接**——于是 `with connect(...) as conn:` 用完不关，库文件一直被占。
    短命 CLI 进程靠退出兜底看不出来，但同进程内有后续操作时，Windows 上会挡住
    删除/改名（实测 `WinError 32`），也是测试临时目录清不掉的根因之一。

    只在 `with` 用法上生效；`conn = connect(...)` 那种写法完全不受影响，
    仍由调用方自行 `close()`。
    """

    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def connect(db_path: PathLike) -> sqlite3.Connection:
    """Open a SQLite connection with WAL, busy_timeout, and foreign_keys ON.

    `with connect(...)` 退出时自动关闭（见 :class:`_AutoClosingConnection`）。
    """
    conn = sqlite3.connect(str(db_path), factory=_AutoClosingConnection)
    conn.execute(f"PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
