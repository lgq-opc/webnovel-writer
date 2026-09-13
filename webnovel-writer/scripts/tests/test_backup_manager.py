from __future__ import annotations

import subprocess
from pathlib import Path

import backup_manager
from backup_manager import GitBackupManager


def test_backup_manager_gitignore_excludes_env(tmp_path, monkeypatch):
    def fake_run(args, cwd=None, check=False, capture_output=False, text=False, encoding=None, timeout=None):
        if args == ["git", "init"]:
            (tmp_path / ".git").mkdir(exist_ok=True)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(backup_manager, "is_git_available", lambda: True)
    monkeypatch.setattr(backup_manager.subprocess, "run", fake_run)

    GitBackupManager(str(tmp_path))

    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore
    assert ".env.*" in gitignore
    assert "!.env.example" in gitignore


def _run_git(project_root, *args):
    return subprocess.run(
        ["git", *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _configure_git_identity(project_root):
    assert _run_git(project_root, "config", "user.name", "Test Author").returncode == 0
    assert _run_git(project_root, "config", "user.email", "author@example.com").returncode == 0


def test_backup_aborts_when_git_commit_fails_without_identity(tmp_path, monkeypatch, capsys):
    isolated_home = tmp_path / "home"
    isolated_home.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()

    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    assert _run_git(project_root, "init", "-b", "main").returncode == 0
    assert _run_git(project_root, "config", "--local", "user.useConfigOnly", "true").returncode == 0
    _run_git(project_root, "config", "--local", "--unset", "user.name")
    _run_git(project_root, "config", "--local", "--unset", "user.email")

    manuscript_dir = project_root / "正文"
    manuscript_dir.mkdir()
    (manuscript_dir / "第0001章-test.md").write_text("正文", encoding="utf-8")

    manager = GitBackupManager(str(project_root))

    assert manager.backup(1, "身份缺失") is False

    output = capsys.readouterr().out
    assert "备份失败" in output
    assert _run_git(project_root, "rev-parse", "--verify", "ch0001").returncode != 0


def test_rollback_restores_files_on_current_branch_with_new_commit(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    assert _run_git(project_root, "init", "-b", "main").returncode == 0
    _configure_git_identity(project_root)

    manuscript_dir = project_root / "正文"
    manuscript_dir.mkdir()
    chapter_file = manuscript_dir / "第0001章-test.md"

    chapter_file.write_text("第一版", encoding="utf-8")
    assert _run_git(project_root, "add", ".").returncode == 0
    assert _run_git(project_root, "commit", "-m", "Chapter 1").returncode == 0
    assert _run_git(project_root, "tag", "ch0001").returncode == 0

    chapter_file.write_text("第二版", encoding="utf-8")
    assert _run_git(project_root, "add", ".").returncode == 0
    assert _run_git(project_root, "commit", "-m", "Chapter 2").returncode == 0
    assert _run_git(project_root, "tag", "ch0002").returncode == 0
    before_count = int(_run_git(project_root, "rev-list", "--count", "HEAD").stdout.strip())

    manager = GitBackupManager(str(project_root))

    assert manager.rollback(1) is True

    assert _run_git(project_root, "symbolic-ref", "--short", "HEAD").stdout.strip() == "main"
    assert chapter_file.read_text(encoding="utf-8") == "第一版"
    after_count = int(_run_git(project_root, "rev-list", "--count", "HEAD").stdout.strip())
    assert after_count == before_count + 1
    assert "rollback: 恢复到 ch0001 备份点" in _run_git(project_root, "log", "-1", "--format=%s").stdout


def test_local_backup_copies_manuscript_when_git_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_manager, "is_git_available", lambda: False)

    # Windows MAX_PATH 限制：pytest 的 tmp_path 路径极长（含 test 名 hash），
    # 叠加 .story-system 深层子目录会超 260 字符导致 copytree 静默跳文件。
    # 改用系统短临时目录规避，验证备份逻辑本身正确。
    import tempfile as _tempfile
    import shutil as _shutil

    short_root = Path(_tempfile.mkdtemp(prefix="wtest_"))
    try:
        _run_local_backup_assertions(short_root, monkeypatch)
    finally:
        _shutil.rmtree(short_root, ignore_errors=True)


def _run_local_backup_assertions(tmp_path, monkeypatch):
    webnovel_dir = tmp_path / ".webnovel"
    manuscript_dir = tmp_path / "正文"
    outline_dir = tmp_path / "大纲"
    settings_dir = tmp_path / "设定集"
    story_system_dir = tmp_path / ".story-system"
    webnovel_dir.mkdir()
    manuscript_dir.mkdir()
    outline_dir.mkdir()
    settings_dir.mkdir()
    story_system_dir.mkdir()
    (webnovel_dir / "state.json").write_text('{"current_chapter": 1}', encoding="utf-8")
    (webnovel_dir / "index.db").write_text("sqlite-bytes", encoding="utf-8")
    (webnovel_dir / "vectors.db").write_text("sqlite-bytes", encoding="utf-8")
    (webnovel_dir / "memory_scratchpad.json").write_text("{}", encoding="utf-8")
    (story_system_dir / "MASTER_SETTING.json").write_text("{}", encoding="utf-8")
    (manuscript_dir / "第0001章-x.md").write_text("正文内容", encoding="utf-8")
    (outline_dir / "第0001章.md").write_text("大纲内容", encoding="utf-8")
    (settings_dir / "人物.md").write_text("设定内容", encoding="utf-8")

    manager = GitBackupManager(str(tmp_path))

    assert manager.backup(1) is True

    snapshots = sorted((webnovel_dir / "backups").glob("snapshot_ch0001_*"))
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert (snapshot / "正文" / "第0001章-x.md").read_text(encoding="utf-8") == "正文内容"
    assert (snapshot / "大纲" / "第0001章.md").read_text(encoding="utf-8") == "大纲内容"
    assert (snapshot / "设定集" / "人物.md").read_text(encoding="utf-8") == "设定内容"
    assert (snapshot / ".webnovel" / "state.json").read_text(encoding="utf-8") == '{"current_chapter": 1}'
    # P1-5 修复：补全 .story-system 合同树与投影数据库的备份
    assert (snapshot / ".story-system" / "MASTER_SETTING.json").exists()
    assert (snapshot / ".webnovel" / "index.db").exists()
    assert (snapshot / ".webnovel" / "vectors.db").exists()
    assert (snapshot / ".webnovel" / "memory_scratchpad.json").exists()
    # 临时目录应已被原子 rename 清除，不留残留
    assert not any((webnovel_dir / "backups").glob(".tmp_*"))

    for chapter in range(2, 13):
        assert manager.backup(chapter) is True

    snapshots = sorted((webnovel_dir / "backups").glob("snapshot_ch*"))
    assert len(snapshots) == 10
    assert snapshot not in snapshots


def test_local_backup_covers_v7_six_domains(tmp_path, monkeypatch):
    """t-20260913-f847：本地备份清单必须覆盖 v7 六域。

    原实现只列 v6 的 `正文/大纲/设定集` + `.story-system` + `.webnovel` 四个文件，
    纯 v7 仓跑本地备份的结果是**只剩 `大纲/`**——`定稿/`（正文 + 章摘要 + 名册）、
    `设定/`、`文风/`、`素材/`、`作者/` 全部漏掉。**备份静默漏内容比不备份更危险**：
    作者以为有备份，恢复时才发现正文没了。
    """
    monkeypatch.setattr(backup_manager, "is_git_available", lambda: False)

    # 与 v6 用例同因：pytest tmp_path 过长会触发 MAX_PATH，改用系统短临时目录。
    import shutil as _shutil
    import tempfile as _tempfile

    short_root = Path(_tempfile.mkdtemp(prefix="wtest7_"))
    try:
        _run_v7_local_backup_assertions(short_root)
    finally:
        _shutil.rmtree(short_root, ignore_errors=True)


def _run_v7_local_backup_assertions(tmp_path):
    from data_modules.domain_contract import init_domain_skeleton

    init_domain_skeleton(tmp_path)
    (tmp_path / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    for rel, body in (
        ("定稿/正文/0001-开篇.md", "正文内容"),
        ("定稿/记忆/章摘要/0001.md", "摘要内容"),
        ("定稿/设定/名册/苏小白.md", "名册内容"),
        ("设定/世界观.md", "世界观内容"),
        ("文风/宪法.md", "宪法内容"),
        ("素材/活/桥段.csv", "桥段内容"),
        ("作者/author_model.md", "作者模型内容"),
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    manager = GitBackupManager(str(tmp_path))
    assert manager.backup(1) is True

    snapshot = next((tmp_path / ".webnovel" / "backups").glob("snapshot_ch0001_*"))
    assert (snapshot / "定稿" / "正文" / "0001-开篇.md").read_text(encoding="utf-8") == "正文内容"
    assert (snapshot / "定稿" / "记忆" / "章摘要" / "0001.md").exists()
    assert (snapshot / "定稿" / "设定" / "名册" / "苏小白.md").exists()
    assert (snapshot / "设定" / "世界观.md").read_text(encoding="utf-8") == "世界观内容"
    assert (snapshot / "文风" / "宪法.md").exists()
    assert (snapshot / "素材" / "活" / "桥段.csv").exists()
    assert (snapshot / "作者" / "author_model.md").exists()


def test_rollback_removes_files_created_after_target_tag(tmp_path):
    """增量审阅 P3-19：回滚须删除 tag 之后新增的文件，与『恢复到备份点 100% 一致』承诺相符。"""
    project_root = tmp_path / "project"
    project_root.mkdir()
    assert _run_git(project_root, "init", "-b", "main").returncode == 0
    _configure_git_identity(project_root)

    manuscript_dir = project_root / "正文"
    manuscript_dir.mkdir()
    chapter_file = manuscript_dir / "第0001章-test.md"
    chapter_file.write_text("第一版", encoding="utf-8")
    assert _run_git(project_root, "add", ".").returncode == 0
    assert _run_git(project_root, "commit", "-m", "Chapter 1").returncode == 0
    assert _run_git(project_root, "tag", "ch0001").returncode == 0

    new_chapter = manuscript_dir / "第0002章-new.md"
    new_chapter.write_text("第二章", encoding="utf-8")
    assert _run_git(project_root, "add", ".").returncode == 0
    assert _run_git(project_root, "commit", "-m", "Chapter 2").returncode == 0
    assert _run_git(project_root, "tag", "ch0002").returncode == 0

    manager = GitBackupManager(str(project_root))

    assert manager.rollback(1) is True

    assert chapter_file.read_text(encoding="utf-8") == "第一版"
    assert not new_chapter.exists(), "tag 之后新增的章节文件在回滚后残留"
