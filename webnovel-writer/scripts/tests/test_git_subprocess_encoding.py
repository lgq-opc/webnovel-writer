"""N-4 回归：读 git 输出的子进程必须显式 `encoding="utf-8"`。

**真实失败形态是「静默取值损坏」，不是崩溃**（实测 2026-09-10，本机中文 Windows）：

| 父进程模式 | `text=True`（无 encoding） | `text=True, encoding="utf-8"` |
|---|---|---|
| UTF-8 模式（`-X utf8` / `PYTHONUTF8=1`） | 值正确 | 值正确 |
| 非 UTF-8 模式（裸 `python`，locale=cp936） | **值被改写成乱码** | 值正确 |

git 存下的配置值是 UTF-8 字节（已核原始字节），而 `text=True` 在非 UTF-8 父进程里按
locale（cp936）解码 → `dualformat.v6root` 里的中文路径被悄悄改写成
``'...\\鎴戠殑涔︿粨\\...'``。这比崩溃更糟：**路径指向不存在的地方，
dual_format_guard 静默失效，没有任何报错**。

为什么必须起子进程测：pytest 按文档以 `-X utf8` 跑，父进程本身就是 UTF-8，**直接调用
永远看不出问题**。这里显式用 `PYTHONUTF8=0` 起一个非 UTF-8 子进程复现真实场景。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]


def _git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(["git", *args], cwd=str(cwd) if cwd else None, check=True, capture_output=True)


def _run_in_non_utf8_child(repo: Path, body: str) -> object:
    """在 PYTHONUTF8=0 的子进程里执行 body（可用 repo / json / sys），返回其打印的 JSON。"""
    script = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(SCRIPTS_DIR)!r})\n"
        "from pathlib import Path\n"
        f"repo = Path({str(repo)!r})\n"
        f"{body}\n"
    )
    env = {**os.environ, "PYTHONUTF8": "0", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, encoding="utf-8", env=env,
    )
    assert proc.returncode == 0, f"子进程失败: {proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_v6_root_from_git_config_keeps_chinese_path(tmp_path):
    """含中文的 dualformat.v6root 在非 UTF-8 父进程下必须原样读回。

    这是 N-4 里唯一「值被消费」的读法（守卫拿它当路径用），故也是危害最大的那处。
    """
    repo = tmp_path / "我的书仓"
    repo.mkdir()
    _git("init", cwd=repo)

    target = str(repo / "工作区" / "素材")
    _git("-C", str(repo), "config", "dualformat.v6root", target)

    result = _run_in_non_utf8_child(
        repo,
        "from v7_write import _v6_root_from_git_config\n"
        "print(json.dumps({'value': _v6_root_from_git_config(repo)}))",
    )

    assert result["value"] == target, (
        "含中文的 git config 值被 locale 解码改写——读取端缺 encoding=\"utf-8\"（N-4 回归）"
    )


def test_absent_config_still_returns_empty(tmp_path):
    """守住行为边界：没配 dualformat.v6root 时仍返回空串（别为了修编码改了语义）。"""
    repo = tmp_path / "无配置书仓"
    repo.mkdir()
    _git("init", cwd=repo)

    result = _run_in_non_utf8_child(
        repo,
        "from v7_write import _v6_root_from_git_config\n"
        "print(json.dumps({'value': _v6_root_from_git_config(repo)}))",
    )

    assert result["value"] == ""
