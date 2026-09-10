"""仓库根 conftest：统一测试中「子进程文本编码」的契约。

## 为什么需要

N-1（2026-09-10 复现）：文档记录的测试命令在中文 Windows 上不是全绿——
`python -X utf8 -m pytest` = 23 failed，而 `PYTHONUTF8=1 python -X utf8 -m pytest` = 0 failed。

根因是**调用方与子进程的编码契约不一致**：
- 测试用 `sys.executable` 拉起脚本子进程时**不带** `-X utf8`，子进程在中文 Windows 上
  按 GBK 写 stdout；
- 调用方若处于 UTF-8 模式（`-X utf8` 或 `PYTHONUTF8=1`），`text=True` 会按 UTF-8 解码；
- GBK 字节按 UTF-8 解码 → `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xbd`。

反方向同样会崩：非 UTF-8 模式下父进程按 GBK 解码，而 git 等外部命令输出 UTF-8。

## 这里做什么

不改生产代码，只在**测试进程内**让子进程走确定性 UTF-8：

1. 给子进程环境注入 `PYTHONUTF8=1` 与 `PYTHONIOENCODING=utf-8`（含调用方自带的 env）；
2. text 模式下由调用方显式 `encoding="utf-8"`。

于是测试结果不再取决于调用者的 UTF-8 模式——`python -X utf8 -m pytest` 与
`PYTHONUTF8=1 python -X utf8 -m pytest` 等价，换机器/换 shell 都不会再漂。

**刻意不设 `errors=`**：解码仍会因真错而失败，只是不再因编码不确定而失败；
若设成 `errors="replace"` 会把真正的编码缺陷藏起来。

生产侧的同类隐患（`subprocess.run(text=True)` 未显式 `encoding`）不在此处修——
那是独立议题，见 docs/TODO-from-v8-author-review.md 的 N-4。
"""

from __future__ import annotations

import os
import subprocess

_ORIGINAL_RUN = subprocess.run
_INSTALLED = False

# 子进程强制 UTF-8 的标准输出/输入编码。
_CHILD_ENV = {
    "PYTHONUTF8": "1",
    "PYTHONIOENCODING": "utf-8",
}


def _with_utf8_env(env):
    """把 UTF-8 变量并进子进程环境；调用方自带 env 时也不能丢（否则子进程又回落到 GBK）。"""
    merged = dict(os.environ if env is None else env)
    for key, value in _CHILD_ENV.items():
        merged.setdefault(key, value)
    return merged


def _is_text_mode(kwargs) -> bool:
    return bool(
        kwargs.get("text")
        or kwargs.get("universal_newlines")
        or kwargs.get("encoding") is not None
        or kwargs.get("errors") is not None
    )


def install_utf8_subprocess() -> None:
    """幂等安装；重复调用不会叠加包装。"""
    global _INSTALLED
    if _INSTALLED:
        return

    def run(*args, **kwargs):
        if _is_text_mode(kwargs):
            kwargs.setdefault("encoding", "utf-8")
        kwargs["env"] = _with_utf8_env(kwargs.get("env"))
        return _ORIGINAL_RUN(*args, **kwargs)

    subprocess.run = run
    _INSTALLED = True


install_utf8_subprocess()
