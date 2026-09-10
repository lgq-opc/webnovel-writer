"""Tests for unified SQLite connection factory."""
import sqlite3

from data_modules.db import connect


def test_connect_sets_wal(tmp_path):
    db = tmp_path / "test.db"
    with connect(db) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_connect_sets_busy_timeout(tmp_path):
    db = tmp_path / "test.db"
    with connect(db) as conn:
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert timeout >= 5000


def test_connect_sets_foreign_keys_on(tmp_path):
    db = tmp_path / "test.db"
    with connect(db) as conn:
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_connect_accepts_str_path(tmp_path):
    db = str(tmp_path / "test.db")
    with connect(db) as conn:
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        row = conn.execute("SELECT id FROM t").fetchone()
    assert row[0] == 1


# --- F8 生产侧：with 退出即关闭（下列用例的 RED 证据在 pytest 外，见说明）---
#
# 说明：仓库根/scripts 的 conftest 会把 `sqlite3.connect` patch 成返回会关闭的连接，
# 所以**在 pytest 内**，即使 `db.connect` 不传 factory 这些用例也会通过——测试环境
# 掩盖了这个缺陷。真正的 RED/GREEN 对照要在 pytest 外跑（本次实测：
# 修复前 with 块后删库文件报 WinError 32；修复后连接已关闭、文件可删）。
# 下列用例的作用是**固化契约**：一旦 conftest 的 patch 被移除，它们会立刻抓住回归。


def test_connect_closes_on_with_exit(tmp_path):
    """`with connect(...)` 退出后连接必须已关闭。"""
    import pytest

    db = tmp_path / "closed.db"
    with connect(db) as conn:
        conn.execute("CREATE TABLE t (id INTEGER)")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")


def test_connect_releases_file_after_with_exit(tmp_path):
    """退出后库文件必须可删——句柄未释放的直接指标。"""
    db = tmp_path / "removable.db"
    with connect(db) as conn:
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")

    db.unlink()
    assert not db.exists()


def test_connect_without_with_is_unaffected(tmp_path):
    """不经 with 的写法不受影响，仍由调用方自行 close（守住补丁边界）。"""
    db = tmp_path / "plain.db"
    conn = connect(db)
    try:
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone() == (1,)
    finally:
        conn.close()
