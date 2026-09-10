from __future__ import annotations

import os
import shutil
import sqlite3
import stat
import tempfile
import time
import uuid
import warnings
from pathlib import Path

import pytest

# 超 MAX_PATH 的路径需要扩展前缀；本模块与 long_paths.py 同目录，pytest 会把该目录
# 放进 sys.path（prepend 导入模式），故可直接导入。
from long_paths import WIN_EXTENDED_PREFIX


_ORIGINAL_SQLITE_CONNECT = sqlite3.connect
_ORIGINAL_TEMPORARY_DIRECTORY = tempfile.TemporaryDirectory


def _delete_path_str(path) -> str:
    """删除专用的路径字符串：Windows 上**无条件**加扩展前缀。

    不用 :func:`long_paths.win_long_abs`：它按**根路径长度**决定加不加前缀，而删除
    要面对的是整棵树——根只有 140 字符、树里第 6 层却可能超 MAX_PATH，前缀就漏了。
    实测 `test_long_paths` 造的 `正文\\dddd…\\dddd…` 正是这种形态：根不加前缀 →
    `os.walk` 在深处静默走不下去 → 深层只读文件清不掉 → `rmtree` 报
    WinError 145「目录不是空的」。

    `\\?\` 会关闭 Win32 路径规范化（不解析 `.`/`..`、不认正斜杠），故先 `abspath`
    规范化再拼接。
    """
    s = os.path.abspath(str(path))
    if os.name == "nt" and not s.startswith(WIN_EXTENDED_PREFIX):
        s = WIN_EXTENDED_PREFIX + s
    return s


def _chdir_out_of(path: Path) -> None:
    """若当前工作目录落在待删目录内，先退出到仓库根。

    **Windows 不允许删除仍是某进程 cwd 的目录**（`WinError 32`）。而测试常用
    ``monkeypatch.chdir(tmp_path / "workspace")`` 把**测试进程自己**的 cwd 切进去
    （见 `test_webnovel_unified_cli` 的 where/preflight/backup 三个用例）。
    monkeypatch 确实会还原 cwd，但**夹具 teardown 的先后顺序不保证**——tmp_path 的
    清理可能先于 monkeypatch 的还原跑，于是删除必然失败。

    这里主动兜底：删之前先离开。monkeypatch 之后仍会把自己的还原照做（它记的是
    测试开始时的 cwd），故不会互相打架。
    """
    # 两侧都 resolve()：Windows 上 os.getcwd() 可能返回 8.3 短名（如 TE4FAC~1），
    # 与夹具给出的长路径字符串比不出包含关系，会漏判。
    try:
        cwd = Path(os.getcwd()).resolve()
        target = Path(path).resolve()
    except OSError:  # cwd 已被删除等异常情形，无需再处理
        return
    if cwd == target or target in cwd.parents:
        try:
            os.chdir(_repo_root())
        except OSError:
            pass


def _clear_readonly(root: str) -> None:
    """递归清掉只读位。Windows 上 rmtree 删不掉带只读属性的文件。

    `root` 必须是已加长路径前缀的字符串（见 :func:`_delete_path_str`）：不加前缀时
    深层目录会超过 MAX_PATH，`os.walk` 在那种路径上静默走不下去，深层文件清不到。
    """
    for current, dirs, files in os.walk(root):
        for name in (*files, *dirs):
            try:
                os.chmod(os.path.join(current, name), stat.S_IWRITE)
            except OSError:
                pass


def rmtree_safely(path) -> None:
    """删除测试临时目录。

    **为什么不用 `shutil.rmtree(ignore_errors=True)`（F7 的根因）**：测试会建 git 仓，
    而 Windows 上 git 对象文件带只读属性 → rmtree 删不掉 → `ignore_errors=True`
    把异常静默吞掉 → 每个建仓用例漏一个目录。实测清理前累积 8179 个条目 / 202 MB，
    且该目录被 conftest 当作 TMP/TEMP，条目越多 IO 越慢。

    这里：先清只读位，再删；失败则重试（文件可能被子进程短暂占用）；
    重试仍失败则 **warnings.warn 告警但不抛出**——理由是实测校准出来的：

    - 硬抛会把瞬时锁变成测试 ERROR。`test_webnovel_unified_cli` 等用例以子进程跑
      CLI 并把被测目录当 cwd，Windows 上子进程刚退出时该目录仍被短暂占用，报
      `WinError 32 另一个程序正在使用此文件`——这正是旧实现用 `ignore_errors=True`
      容忍的那类，属环境性噪声，不该炸 CI。
    - 但**也不能静默**：旧实现的问题不在容忍瞬时锁，而在把**只读文件**这种永久性
      失败也一并吞了，才让泄漏长期隐身（一次全量漏 3000+ 个目录没人发现）。

    故：瞬时锁重试消化掉；重试仍失败的多半是真问题，用 warning 留在 pytest 摘要里
    可见，而不是无声无息。

    **长路径**：全程走 :func:`_delete_path_str` 无条件加扩展前缀。测试里有专门造
    超深目录的用例（`正文\\dddd...`），未加前缀时 `os.walk` 下不去、只读文件清不掉、
    `rmtree` 报 WinError 145「目录不是空的」——旧实现靠 `ignore_errors` 把它一起吞了，
    于是那些深目录同样长期泄漏。
    """
    _chdir_out_of(Path(path))
    long_root = _delete_path_str(path)
    if not os.path.exists(long_root):
        return
    last: OSError | None = None
    for attempt in range(5):
        if attempt:  # 首轮已尝试离开；后续轮次再兜一次（cwd 可能被别处改回）
            _chdir_out_of(Path(path))
        _clear_readonly(long_root)
        try:
            shutil.rmtree(long_root)
            return
        except OSError as exc:  # 文件/目录可能被尚未回收的子进程短暂占用
            last = exc
            time.sleep(0.1 * (attempt + 1))
    if os.path.exists(long_root):
        warnings.warn(
            f"测试临时目录未能删除，残留于 {long_root}：{last}",
            stacklevel=1,
        )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _tmp_root() -> Path:
    root = _repo_root() / ".tmp" / "pytest"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_mkdtemp(suffix: str | None = None, prefix: str | None = None, dir: str | os.PathLike[str] | None = None) -> str:
    """Avoid WindowsApps Python creating inaccessible 0o700 temp dirs."""
    suffix = "" if suffix is None else suffix
    prefix = "tmp" if prefix is None else prefix
    root = Path(dir) if dir is not None else _tmp_root()
    root.mkdir(parents=True, exist_ok=True)

    for _ in range(100):
        path = root / f"{prefix}{uuid.uuid4().hex}{suffix}"
        try:
            path.mkdir()
        except FileExistsError:
            continue
        return str(path.resolve())

    raise FileExistsError(f"Unable to create unique temporary directory under {root}")


def _install_safe_tempfile() -> None:
    root = _tmp_root()
    for name in ("TMP", "TEMP", "TMPDIR"):
        os.environ[name] = str(root)
    os.environ["WEBNOVEL_TEST_RELAX_ATOMIC_REPLACE"] = "1"
    tempfile.tempdir = str(root)
    tempfile.mkdtemp = _safe_mkdtemp
    tempfile.TemporaryDirectory = _SafeTemporaryDirectory


class _SafeTemporaryDirectory(_ORIGINAL_TEMPORARY_DIRECTORY):
    def __init__(self, suffix=None, prefix=None, dir=None, ignore_cleanup_errors=True, *, delete=True):
        super().__init__(
            suffix=suffix,
            prefix=prefix,
            dir=dir,
            ignore_cleanup_errors=ignore_cleanup_errors,
            delete=delete,
        )


class _ClosingConnection(sqlite3.Connection):
    """`with conn:` 结束时**真正关闭**连接。

    这是 F8 的根因之一：`with sqlite3.connect(...) as conn:` 是极常见的写法，但它
    **只提交/回滚事务，不关闭连接**——`sqlite3.Connection` 的 `__exit__` 不调 close()。
    连接一直开着 → 库文件被占 → 夹具 teardown 删不掉临时目录（`WinError 32`）。

    实测全量有 13 个用例因这个写法泄漏（库文件名：`test.db` / `vectors.db` / `index.db`，
    见 `test_db.py` 的 4 条 `test_connect_*`、`test_doctor_*`、`test_sqlite_null_*` 等）。
    项目自带的 `data_modules/db.py:connect()` 内部也走 `sqlite3.connect`，故一并覆盖。

    本改动**只在测试进程内生效**（patch 装在 conftest），不改变生产运行语义。
    """

    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def _safe_sqlite_connect(*args, **kwargs):
    kwargs.setdefault("factory", _ClosingConnection)
    conn = _ORIGINAL_SQLITE_CONNECT(*args, **kwargs)
    try:
        conn.execute("PRAGMA journal_mode=MEMORY")
    except sqlite3.DatabaseError:
        pass
    return conn


def _install_safe_sqlite() -> None:
    sqlite3.connect = _safe_sqlite_connect


def pytest_configure(config: pytest.Config) -> None:
    _install_safe_tempfile()
    _install_safe_sqlite()


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in request.node.name)
    path = _tmp_root() / f"{safe_name}_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if os.environ.get("WEBNOVEL_KEEP_TEST_TMP") != "1":
            rmtree_safely(path)


_install_safe_tempfile()
_install_safe_sqlite()
