# 坑点经验累积（experience-log）

> 用途：解决一个棘手问题的**当下**顺手记录，让下次同类问题自动被想起。
> 格式见 `docs/templates/experience-entry-template.md`；新条目加在最上面。

---

### 2026-09-11 `os.chmod(x, stat.S_IWRITE)` 在 POSIX 上是「整值替换模式位」，不是「清除只读位」——把目录 chmod 成 0o200 会让整棵树再也删不掉

- **问题**：CI 的 ubuntu job 上 `scripts/tests/test_conftest_tmp_cleanup.py` **4 条红**（`assert not target.exists()` 失败），同一提交的 `tests-windows` job 全绿。失败签名是 `UserWarning: 测试临时目录未能删除，残留于 …：[Errno 13] Permission denied: 'repo'`，而不是任何显式报错。

- **触发条件**：Windows + Linux 双平台仓库里，用 `os.chmod(path, stat.S_IWRITE)` 清只读位，**且把目录也一并 chmod**（本仓 `scripts/conftest.py::_clear_readonly` 原先写成 `for name in (*files, *dirs)`）。
  - Windows：`os.chmod` 只切「只读属性」一位，不解释 r/x → 目录照常可遍历，**看不出任何异常**。
  - POSIX：`stat.S_IWRITE` 是 `0o200`，`os.chmod` 是**整值替换**（不是位或）→ 目录变成 `--w-------`，同时丢掉 `r` 和 `x`。
  - 后果链：`os.walk` 在 yield 出父目录后、循环体把子目录 chmod 成 0o200 → walk 恢复时对其 `scandir` 抛 `PermissionError` → **`os.walk` 默认 `onerror=None` 会静默跳过**，深层文件根本没被处理；紧接着 `shutil.rmtree` 在同一处失败。全程只有一条 warning，表现为「目录莫名残留」。

- **解决**：给 `_clear_readonly` 加平台门禁——Windows 保留原行为（已验证，不动），POSIX 直接 `return`。理由是 POSIX 上删除文件只取决于**父目录**的写权限，与文件自身模式无关，这一步本就不需要。修法原则：**不为了修一个平台而去改另一个平台已验证的行为**。

- **校验**：本机 WSL Ubuntu-22.04 上用**真实 `scripts/conftest.py`**（只给 pytest 打最小 stub 以便导入，不重写实现、不重写断言）跑测试体，红绿对照——
  - 还原为修复前：`2 passed, 4 failed`，失败四条与 CI **逐条一致**，并复现同一 `PermissionError: [Errno 13] Permission denied: 'repo'`；
  - 应用修复后：`6 passed, 0 failed`；Windows 侧同文件亦 `6 passed`（行为未变）。
  - **下次提前发现**：本仓库已有成对 job（ubuntu `tests` + `tests-windows`），平台专属缺陷不会再对 CI 隐身——**但前提是改动真的被推上去**。本次这条回归从修复（2026-09-10）到暴露（2026-09-11 首次推送）隔了一天，期间本地全量 1500+ 用例一直是绿的。

- **顺带发现（值得单独记住）**：这条回归同时是 **30× 的性能拖累**，远不止 4 条断言红——同一步骤耗时 **1385.32s → 46.80s**、warnings **893 → 4**。机理：失败路径上每个 `tmp_path` teardown 都要走满 5 次退避重试（合计 1.5s）且目录持续残留，而 `.tmp/pytest` 又被 conftest 当作 TMP/TEMP，条目越多 IO 越慢，约 1500 个用例把这点开销放大成 23 分钟。**结论：CI 耗时与告警数的异常漂移本身就是回归信号，不是背景噪声。**本轮若只盯红/绿，会漏掉这个退化。
  - CI 终审：run `34531448903` @ `ed9da38` → `tests` 与 `tests-windows` 双绿。

- **元教训**：**本地全绿（Windows）与 CI 全绿（Linux）是两件事**。凡涉及 `os.chmod` / 路径语义 / 大小写敏感 / locale / 行尾 / 符号链接的改动，「本地全量通过」不构成跨平台结论；本仓对此的机械闸就是 `plugin-tests.yml` 的双平台 job，**改动应在同一会话内推送以便验红绿**，而不是攒在本地。
