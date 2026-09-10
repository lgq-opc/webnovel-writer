# -*- coding: utf-8 -*-
"""security_utils 安全关键函数测试（TODO-from-v8-author-review P2-3）。

覆盖目标：sanitize_* 边界、secure dir/file 平台分支、git 环境检测与优雅降级、
atomic 写入失败路径、read_json_safe / restore_from_backup、内置自检。
CI 对本模块单独设 90% 覆盖率闸（plugin-tests.yml security coverage floor）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import security_utils
from security_utils import (
    AtomicWriteError,
    atomic_write_json,
    create_secure_directory,
    create_secure_file,
    git_graceful_operation,
    is_git_available,
    is_git_repo,
    read_json_safe,
    restore_from_backup,
    sanitize_commit_message,
    sanitize_filename,
    validate_integer_input,
)


@pytest.fixture
def git_cache_reset(monkeypatch):
    """重置 git 可用性缓存，测试后由 monkeypatch 还原，防跨测试污染。"""
    monkeypatch.setattr(security_utils, "_git_available", None)


# ---------------------------------------------------------------------------
# sanitize_*：清理函数边界（截断 / 空串兜底）
# ---------------------------------------------------------------------------

def test_sanitize_filename_truncates_to_max_length():
    assert len(sanitize_filename("a" * 150, max_length=50)) == 50


def test_sanitize_filename_empty_falls_back():
    assert sanitize_filename("///") == "unnamed_entity"


def test_sanitize_commit_message_truncates_and_falls_back():
    assert len(sanitize_commit_message("字" * 300, max_length=20)) == 20
    assert sanitize_commit_message("   ") == "Untitled commit"


def test_validate_integer_input_error_message(capsys):
    with pytest.raises(ValueError):
        validate_integer_input("abc", "chapter_num")
    assert "chapter_num" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# secure dir/file：Windows / POSIX 分支
# ---------------------------------------------------------------------------

def test_create_secure_directory_and_file_roundtrip(tmp_path):
    # 走当前平台原生分支（Windows 与 Linux CI 合计覆盖 nt/posix 两个分支；
    # 不打桩 os.name——那会连带翻转 pathlib.Path 分派，测的是 mock 不是现实）
    d = create_secure_directory(str(tmp_path / "sub"))
    assert d.is_dir()
    f = tmp_path / "sub" / "state.json"
    create_secure_file(str(f), '{"ok": 1}')
    assert f.read_text(encoding="utf-8") == '{"ok": 1}'


# ---------------------------------------------------------------------------
# git 环境检测与优雅降级
# ---------------------------------------------------------------------------

def test_is_git_available_true_and_cached(git_cache_reset):
    # 开发机与 CI（ubuntu-latest）均有 git
    assert is_git_available() is True
    assert security_utils._git_available is True  # 结果已缓存
    assert is_git_available() is True


def test_is_git_available_handles_missing_binary(git_cache_reset, monkeypatch):
    def raise_fnf(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", raise_fnf)
    assert is_git_available() is False


def test_is_git_repo(tmp_path, git_cache_reset, monkeypatch):
    assert is_git_repo(tmp_path) is False  # 无 .git 目录
    (tmp_path / ".git").mkdir()
    assert is_git_repo(tmp_path) is True

    monkeypatch.setattr(security_utils, "_git_available", False)
    assert is_git_repo(tmp_path) is False  # git 不可用时一律 False


def test_git_graceful_operation_skips_when_unavailable(git_cache_reset, monkeypatch, capsys):
    monkeypatch.setattr(security_utils, "_git_available", False)

    ok, out, skipped = git_graceful_operation(["status"], cwd=".", fallback_msg="没有 git")

    assert (ok, out, skipped) == (False, "", True)
    assert "没有 git" in capsys.readouterr().err


def test_git_graceful_operation_success_and_failure(git_cache_reset, tmp_path):
    ok, out, skipped = git_graceful_operation(["--version"], cwd=tmp_path)
    assert ok is True and skipped is False
    assert "git version" in out

    # 非仓库目录里 rev-parse 一个不存在的 ref：git 正常执行但退出码非 0
    ok2, _, skipped2 = git_graceful_operation(
        ["rev-parse", "--verify", "definitely-no-such-ref"], cwd=tmp_path
    )
    assert ok2 is False and skipped2 is False


def test_git_graceful_operation_timeout_and_oserror(git_cache_reset, monkeypatch, capsys):
    monkeypatch.setattr(security_utils, "_git_available", True)

    def timeout_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=60)

    monkeypatch.setattr(subprocess, "run", timeout_run)
    ok, out, skipped = git_graceful_operation(["status"], cwd=".")
    assert (ok, out, skipped) == (False, "", False)
    assert "超时" in capsys.readouterr().err

    def oserror_run(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(subprocess, "run", oserror_run)
    ok2, out2, skipped2 = git_graceful_operation(["status"], cwd=".")
    assert (ok2, out2, skipped2) == (False, "", False)
    assert "Git 操作失败" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# atomic_write_json：失败路径与备份容错
# ---------------------------------------------------------------------------

def test_atomic_write_json_serialization_error(tmp_path):
    target = tmp_path / "state.json"

    with pytest.raises(AtomicWriteError, match="JSON 序列化失败"):
        atomic_write_json(target, {"bad": object()})

    assert not target.exists()
    assert not list(tmp_path.glob("*.tmp"))  # 序列化在建临时文件之前失败


def test_atomic_write_json_backup_failure_swallowed(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    target.write_text('{"old": 1}', encoding="utf-8")

    import shutil as _shutil

    def broken_copy(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(_shutil, "copy2", broken_copy)
    atomic_write_json(target, {"new": 2}, use_lock=False, backup=True)  # 备份失败不阻止写入

    assert read_json_safe(target) == {"new": 2}


def test_atomic_write_json_write_failure_wraps_and_cleans(tmp_path, monkeypatch):
    target = tmp_path / "state.json"

    def broken_fsync(fd):
        raise OSError("fsync failed")

    monkeypatch.setattr(os, "fsync", broken_fsync)

    with pytest.raises(AtomicWriteError, match="原子写入失败"):
        atomic_write_json(target, {"x": 1}, use_lock=False, backup=False)

    assert not target.exists()
    assert not list(tmp_path.glob("*.tmp"))  # finally 清理了临时文件


def test_atomic_write_json_temp_cleanup_failure_swallowed(tmp_path, monkeypatch):
    target = tmp_path / "state.json"

    def broken_fsync(fd):
        raise OSError("fsync failed")

    def broken_unlink(path):
        raise OSError("already gone")

    monkeypatch.setattr(os, "fsync", broken_fsync)
    monkeypatch.setattr(os, "unlink", broken_unlink)

    with pytest.raises(AtomicWriteError):  # 清理失败被吞掉，不影响原始异常上抛
        atomic_write_json(target, {"x": 1}, use_lock=False, backup=False)


# ---------------------------------------------------------------------------
# read_json_safe / restore_from_backup
# ---------------------------------------------------------------------------

def test_read_json_safe_variants(tmp_path, capsys):
    missing = tmp_path / "nope.json"
    assert read_json_safe(missing) == {}
    sentinel = {"default": True}
    assert read_json_safe(missing, sentinel) is sentinel

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert read_json_safe(bad, {"d": 1}) == {"d": 1}
    assert "读取 JSON 失败" in capsys.readouterr().err

    good = tmp_path / "good.json"
    good.write_text('{"ok": 1}', encoding="utf-8")
    assert read_json_safe(good) == {"ok": 1}


def test_restore_from_backup_missing_backup(tmp_path, capsys):
    assert restore_from_backup(tmp_path / "state.json") is False
    assert "备份文件不存在" in capsys.readouterr().err


def test_restore_from_backup_restores_content(tmp_path, capsys):
    target = tmp_path / "state.json"
    backup = target.with_suffix(".json.bak")
    backup.write_text('{"from": "backup"}', encoding="utf-8")

    assert restore_from_backup(target) is True
    assert json.loads(target.read_text(encoding="utf-8")) == {"from": "backup"}
    assert "已从备份恢复" in capsys.readouterr().out


def test_restore_from_backup_failure(tmp_path, monkeypatch, capsys):
    import shutil as _shutil

    target = tmp_path / "state.json"
    backup = target.with_suffix(".json.bak")
    backup.write_text("{}", encoding="utf-8")

    def broken_copy(*args, **kwargs):
        raise OSError("locked")

    monkeypatch.setattr(_shutil, "copy2", broken_copy)
    assert restore_from_backup(target) is False
    assert "恢复失败" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 内置自检
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform != "win32", reason="内置自检断言 Windows 反斜杠路径语义（posix 上 sanitize 结果不同属预期行为）")
def test_run_self_tests(capsys):
    security_utils._run_self_tests()
    assert "所有安全工具函数测试通过" in capsys.readouterr().out
