"""F8 回归：`with sqlite3.connect(...) as conn:` 必须真正关闭连接。

`sqlite3.Connection.__exit__` **只提交/回滚事务，不关闭连接**——这是极常见的误写。
连接不关 → 库文件被占 → 夹具 teardown 删不掉临时目录（`WinError 32`）。
conftest 把 `sqlite3.connect` 换成返回 `_ClosingConnection`，使 `with` 语义符合直觉。

实测（2026-09-10 全量）有 13 个用例因此泄漏临时目录。
"""

from __future__ import annotations

import sqlite3

import pytest


def test_with_block_closes_connection(tmp_path):
    """with 块结束后连接必须已关闭。"""
    db = tmp_path / "closed.db"

    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE t(a INTEGER)")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")


def test_db_file_removable_after_with_block(tmp_path):
    """块结束后库文件必须可删——这正是临时目录泄漏的直接原因。"""
    db = tmp_path / "removable.db"

    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE t(a INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")

    db.unlink()  # 未关闭的连接会让这一步抛 PermissionError
    assert not db.exists()


def test_exception_in_block_still_closes_connection(tmp_path):
    """块内抛异常时同样要关闭（__exit__ 的 finally 分支）。"""
    db = tmp_path / "boom.db"

    with pytest.raises(ValueError):
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE t(a INTEGER)")
            raise ValueError("boom")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")


def test_db_module_helper_also_closes(tmp_path):
    """项目自带的 db.connect() 内部走 sqlite3.connect，同样应被覆盖。"""
    import sys
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parents[1]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from data_modules.db import connect

    db = tmp_path / "helper.db"
    with connect(db) as conn:
        conn.execute("CREATE TABLE t(a INTEGER)")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")


def test_plain_connection_is_not_closed_by_gc_contract(tmp_path):
    """守住前提：不经 with 的连接不受影响，仍可正常使用。

    避免把补丁写成"一律立即关闭"而破坏正常用法。
    """
    db = tmp_path / "plain.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE t(a INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone() == (1,)
    finally:
        conn.close()
