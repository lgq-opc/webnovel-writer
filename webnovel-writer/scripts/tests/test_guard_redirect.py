"""Tests for guard_runtime_write redirect regex fix (P0-5)."""
import json
import pytest
import subprocess
import sys
import os

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'hooks'))
from guard_runtime_write import _looks_like_direct_projection_write

GUARD_SCRIPT = Path(__file__).resolve().parents[2] / 'hooks' / 'guard_runtime_write.py'


def _run_guard_hook(command: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GUARD_SCRIPT)],
        input=json.dumps({'tool_name': 'Bash', 'tool_input': {'command': command}}),
        capture_output=True,
        text=True,
        encoding='utf-8',
    )


class TestRedirectDetection:
    def test_bash_simple_redirect_to_commits(self):
        """echo foo > .story-system/commits/ should be blocked."""
        cmd = 'echo test > .story-system/commits/chapter_001.commit.json'
        assert _looks_like_direct_projection_write(cmd) is True

    def test_powershell_set_content_to_index_db(self):
        cmd = "Set-Content .webnovel/index.db 'data'"
        assert _looks_like_direct_projection_write(cmd) is True

    def test_runtime_safe_command_allowed(self):
        cmd = 'python webnovel.py --project-root /tmp v7-write settle --chapter 1 --summary ok'
        assert _looks_like_direct_projection_write(cmd) is False

    def test_unrelated_command_allowed(self):
        cmd = 'echo hello > output.txt'
        assert _looks_like_direct_projection_write(cmd) is False

    def test_double_redirect_append(self):
        cmd = 'echo more >> .webnovel/memory_scratchpad.json'
        assert _looks_like_direct_projection_write(cmd) is True

    def test_chapter_commit_direct_call_blocked(self):
        cmd = 'python chapter_commit.py --chapter 1'
        assert _looks_like_direct_projection_write(cmd) is True


class TestBypassCommandCoverage:
    """增量审阅 P3-17：cp/mv/tee/sed -i/dd/git checkout 等绕过命令同样拦截。"""

    def test_cp_overwrite_index_db(self):
        assert _looks_like_direct_projection_write("cp backup.db .webnovel/index.db") is True

    def test_mv_overwrite_index_db(self):
        assert _looks_like_direct_projection_write("mv x.db .webnovel/index.db") is True

    def test_tee_append_projection_log(self):
        assert _looks_like_direct_projection_write("echo x | tee .webnovel/projection_log.jsonl") is True

    def test_sed_inplace_scratchpad(self):
        assert _looks_like_direct_projection_write("sed -i 's/a/b/' .webnovel/memory_scratchpad.json") is True

    def test_dd_of_commits(self):
        assert _looks_like_direct_projection_write("dd if=x of=.story-system/commits/chapter_001.commit.json") is True

    def test_git_checkout_commits(self):
        assert _looks_like_direct_projection_write("git checkout HEAD -- .story-system/commits/") is True

    def test_read_only_grep_on_protected_still_allowed(self):
        assert _looks_like_direct_projection_write("grep foo .webnovel/index.db") is False


class TestRuntimeWhitelistAlignment:
    """CC 评审 A-1：运行白名单与 deny 文案同源——在役 v7 写链不得被自家闸拦下，
    已撤的 v6 命令名也不再是通行券。"""

    # deny 文案点名的命令；同一行还带受保护后缀（.webnovel/index.db）与 python token
    SANCTIONED_SETTLE = (
        'python -X utf8 webnovel.py --project-root . v7-write settle --chapter 7 '
        '--draft "工作区/草稿-0007.md" --json "工作区/决策-7.json" --summary "落定第七章" '
        "&& ls -l .webnovel/index.db"
    )

    def test_sanctioned_settle_with_protected_suffix_not_blocked(self):
        assert _looks_like_direct_projection_write(self.SANCTIONED_SETTLE) is False

    def test_retired_v6_command_name_no_longer_a_pass(self):
        # 改前实测 rc=0：撤出的命令名曾把 `&& rm -f .webnovel/index.db` 一并放行。
        cmd = "python webnovel.py --project-root . chapter-commit && rm -f .webnovel/index.db"
        assert _looks_like_direct_projection_write(cmd) is True

    def test_direct_python_write_still_blocked(self):
        assert _looks_like_direct_projection_write("python fix_index.py .webnovel/index.db") is True

    def test_shell_overwrite_still_blocked(self):
        assert _looks_like_direct_projection_write("rm -f .webnovel/index.db") is True

    def test_python_without_webnovel_entry_still_blocked(self):
        assert _looks_like_direct_projection_write(
            "python -X utf8 other_tool.py .webnovel/memory_scratchpad.json"
        ) is True

    # CC 复评 R-1：sanctioned 段只给「自己那段」当通行券，不得连带放行同行的破坏性段。
    def test_compound_and_with_destructive_suffix_is_blocked(self):
        cmd = "python webnovel.py --project-root . v7-write settle && rm -f .webnovel/index.db"
        assert _looks_like_direct_projection_write(cmd) is True

    def test_compound_semicolon_with_destructive_suffix_is_blocked(self):
        cmd = "python webnovel.py --project-root . v7-write settle ; rm -f .webnovel/index.db"
        assert _looks_like_direct_projection_write(cmd) is True

    def test_compound_pipe_with_destructive_suffix_is_blocked(self):
        cmd = "python webnovel.py --project-root . v7-write settle | tee .webnovel/index.db"
        assert _looks_like_direct_projection_write(cmd) is True

    def test_compound_or_with_destructive_suffix_is_blocked(self):
        cmd = "python webnovel.py --project-root . v7-write settle || rm -f .webnovel/index.db"
        assert _looks_like_direct_projection_write(cmd) is True

    def test_compound_spoofed_sanctioned_prefix_still_blocked(self):
        # 子串伪造（复评表 G）落在独立段里：伪造段放行，破坏段照拦。
        cmd = 'echo "webnovel.py v7-write settle" && rm -f .webnovel/index.db'
        assert _looks_like_direct_projection_write(cmd) is True

    def test_compound_readonly_suffix_still_allowed(self):
        # 只读后缀不是破坏性形状：段切分不得误伤（既有 SANCTIONED_SETTLE 语义）。
        cmd = "python webnovel.py --project-root . v7-write settle --chapter 1 && ls -l .webnovel/index.db"
        assert _looks_like_direct_projection_write(cmd) is False


class TestRuntimeCompoundCommandEndToEnd:
    """CC 复评 R-1 端到端：拉起真实 hook 子进程，确认 rc 与判定一致。

    落在本文件（任务书 §1 清单内）而非 test_hooks.py（§1 未列，§6「不碰其它文件」）。
    """

    def test_sanctioned_settle_with_destructive_suffix_blocked(self):
        proc = _run_guard_hook(
            "python -X utf8 webnovel.py --project-root . v7-write settle --chapter 7 "
            "--summary ok && rm -f .webnovel/index.db"
        )
        assert proc.returncode == 2
        assert "permissionDecision" in proc.stdout

    def test_sanctioned_settle_with_readonly_suffix_allowed(self):
        proc = _run_guard_hook(
            "python -X utf8 webnovel.py --project-root . v7-write settle --chapter 7 "
            "--summary ok && ls -l .webnovel/index.db"
        )
        assert proc.returncode == 0





