"""F7 回归：测试临时目录必须被真正删掉。

原实现用 ``shutil.rmtree(path, ignore_errors=True)`` 清理 ``tmp_path`` 夹具目录。
测试会建 git 仓，而 Windows 上 git 对象文件带只读属性 → rmtree 删不掉 →
``ignore_errors=True`` 静默吞掉异常 → 每个建仓用例漏一个目录。

实测规模（2026-09-10 清理前）：``.tmp/pytest/`` 累积 8179 个条目 / 79,385 个文件
/ 202 MB；单跑 ``test_v7_write.py``（31 用例）净增 30 个。
"""

from __future__ import annotations

import importlib.util
import os
import stat
import uuid
from pathlib import Path

import pytest

_SCRIPTS_CONFTEST = Path(__file__).resolve().parents[1] / "conftest.py"


def _rmtree_safely():
    """取 scripts/conftest.py 里的 ``rmtree_safely``。

    不能写 ``import conftest``：pytest 以裸名注册 conftest，**仓根**那个
    conftest.py（N-1 统一子进程编码契约用的）先占位，裸名会解析到它而非本模块。
    本测试要测的是 scripts/ 下这个 conftest 的清理助手，故显式按文件路径加载。
    """
    spec = importlib.util.spec_from_file_location("_wn_scripts_conftest", _SCRIPTS_CONFTEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.rmtree_safely


def _make_readonly_tree(root: Path) -> Path:
    """造一棵含只读文件的目录树，模拟测试里 git 仓的 .git/objects。"""
    objects = root / "repo" / ".git" / "objects" / "13"
    objects.mkdir(parents=True)
    for name in ("266f0eacd8ba3bf2c7f4aa7dd3fe4842586b6b", "35e2df88b55d5d4c0b43e19e5485ab4738d467ba"):
        obj = objects / name
        obj.write_bytes(b"\x00")
        os.chmod(obj, stat.S_IREAD)
    return root


def test_rmtree_safely_removes_readonly_tree(tmp_path: Path):
    """含只读文件的树也必须被删干净——这是 git 仓测试会漏目录的直接原因。"""
    rmtree_safely = _rmtree_safely()

    target = _make_readonly_tree(tmp_path / f"leak-{uuid.uuid4().hex}")
    assert target.exists()

    rmtree_safely(target)

    assert not target.exists(), "含只读文件的目录仍未被删除（F7 回归）"


def test_rmtree_safely_tolerates_missing_path(tmp_path: Path):
    """目标不存在时不应抛异常（夹具 teardown 可能在失败路径上被调用）。"""
    _rmtree_safely()(tmp_path / "does-not-exist")


def test_rmtree_safely_leaves_no_partial_tree(tmp_path: Path):
    """深层的只读文件不能让父目录残留在磁盘上。"""
    rmtree_safely = _rmtree_safely()

    target = _make_readonly_tree(tmp_path / "deep" / "nested")
    root = tmp_path / "deep"
    assert root.exists()

    rmtree_safely(root)

    assert not root.exists()
    assert not target.exists()


@pytest.mark.parametrize("name", ["a", "b"])
def test_helper_is_idempotent(tmp_path: Path, name: str):
    rmtree_safely = _rmtree_safely()

    target = _make_readonly_tree(tmp_path / name)
    rmtree_safely(target)
    rmtree_safely(target)  # 第二次调用必须静默通过
    assert not target.exists()


def test_readonly_file_is_actually_readonly_in_fixture(tmp_path: Path):
    """守住测试夹具本身：造出来的确实带只读位，否则上面的用例是空测。"""
    target = _make_readonly_tree(tmp_path / "guard")
    obj = next((target / "repo" / ".git" / "objects" / "13").iterdir())
    assert not (obj.stat().st_mode & stat.S_IWRITE), "夹具未真正设置只读位，回归测试会失去意义"
