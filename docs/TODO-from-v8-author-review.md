# TODO：源自 2026-09-10 v8-author 复审报告

> 详细证据见 [docs/reviews/2026-09-10-v8-author-review.md](reviews/2026-09-10-v8-author-review.md)（含 2026-09-09 复审补充章节）。
> 状态标记沿用 AGENTS.md 约定：`[x]` 已完成且有代码/测试证据，`[~]` 部分完成，`[ ]` 未完成，`[blocked]` 被阻塞。

## 2026-09-09 复审更新

分支自上次审阅以来只新增 1 个提交（`53894b8`，仅新增本报告与本 TODO 文件本身），未发现任何一条待办已被处理；下方所有条目状态原样保留。本轮独立重跑测试/校验脚本，逐项复核见报告「复审说明」一节，结论均与首次一致，未发现推翻或降级项。新增 1 条 P2 待办（见下方 P2 末尾「依赖版本锁定」）。

## P0（阻断级）

- 无。

## P1

- [x] **补一条跑测试套件的 CI workflow**：新增/扩展 `.github/workflows/`，在 push/PR 触及 `webnovel-writer/scripts/**`、`webnovel-writer/mcp/**`、`webnovel-writer/dashboard/**` 时自动跑 `pytest`（含覆盖率门槛），而不是只校验发版元数据。建议同时跑 `validate_reference_wiring.py` 等四个校验脚本。证据：`.github/workflows/plugin-release.yml`、`plugin-version.yml` 当前均不含 `pytest`。**（2026-09-10 已完成：新增 `.github/workflows/plugin-tests.yml`，ubuntu+py3.13 仅装 `requirements.lock`，跑全量 pytest + 四校验脚本；真实 Linux 结果待 workflow 首次触发确认）**
- [x] **修复 `test_runtime_compat.py` 两个平台耦合用例**：`test_fix_sys_argv_opt_in_repairs_powershell_mojibake`、`test_fix_sys_argv_opt_in_accepts_true_variants` 需 `monkeypatch.setattr(sys, "platform", "win32")`（或等价方式），使其不依赖运行机器的真实系统平台。修复后应在 Linux/Mac 上也能通过，为上一条 CI 打基础。证据：`runtime_compat.py:51` `if sys.platform != "win32": return`。**（2026-09-10 已完成：两条用例已打桩；模拟 linux 平台红→绿验证，Windows 主环境全量 1588 passed / 83.03%）**
- [x] **重写或标注 `docs/architecture/overview.md`**：要么整体更新为 v8.1.0 现状（8 skill / 14 MCP 工具 / 13 命令 / v7 book-repo / doctor 治理八组 / 六项不变量），要么在文件顶部加醒目提示"本文档描述 v6 架构，现状请看 X/Y/Z"并链接到 `docs/guides/v7-write-path.md`、`docs/zcode/webnovel-copilot-300/04-architecture.md` 等现行文档。**（2026-09-10 已完成：选择整体重写，七层模型/真源编译产物/双写链路/组件面 8×4×13×14/治理与六不变量/工程面，事实源为 04-architecture、v7-write-path、06-data-design §12、server.py/agents/commands 实测清单）**

## P2

- [x] **同步 `AGENTS.md`「当前状态」段落**：版本号 v8.0.0→v8.1.0；"57 提交领先 master"→实测 122 提交（2026-09-09 复审时因多了 `53894b8` 一条文档提交，实测为 123，此数字会随后续提交继续增长，同步时应以当时 `git log --oneline origin/master..origin/v8-author \| wc -l` 实测值为准，不要照抄本 TODO 里的具体数字）；"尚未打 tag/推送"→已推送（tag `v8.1.0`，commit `21a0980`/`26a3d8d`）。建议以后把"发版流程 checklist"里加一项"同步 AGENTS.md 状态段"，避免再次遗漏。**（2026-09-10 已完成：v8.1.0/125 提交实测/已推送/远程 lgq-opc 均已同步，并加发版 checklist 提示语与 CI 行）**
- [x] **`dual_format_guard` 缺配置时输出 warning**：v6 侧（`STORY_REPO_ROOT` 环境变量为空）或 v7 侧（`git config dualformat.v6root` 缺失且 decision 无 `v6_project_root`）导致守卫静默跳过时，至少打印一条 warning 或写入 journal，避免用户误以为"唯一写入路径守卫"总是生效。证据：`v7_write.py` 内 `_v6_root_from_git_config`、`config.py:231` `DataModulesConfig.story_repo_root`。**（2026-09-10 已完成：新增 `unchecked_other_side_warning()`；prewrite/precommit 写入 gate report warnings（code=dual_format_guard_config_missing，不阻断），settle 无 v6 根时 stderr 打印；测试 6 条新增全绿）**
- [x] **给 `security_utils.py` 补测试至更高覆盖率**（当前 53%），尤其 `git_graceful_operation` 异常分支（322-343 行）与 `restore_from_backup`（540-554 行）；评估是否需要给安全关键模块单独设更高的覆盖率门槛（而非依赖整体 80% 均摊）。**（2026-09-10 已完成：新增 `scripts/tests/test_security_utils.py` 18 条测试（sanitize 边界 / git 优雅降级含超时与 OSError / atomic 失败路径与备份容错 / read / restore / 内置自检），53%→95%（Windows 实测，剩 11 行为 filelock 回退与 POSIX 专属分支）；评估结论=需要独立闸：plugin-tests.yml 新增 `coverage report --include="*security_utils.py" --fail-under=90` 步骤）**
- [x] **视情况扩充 `skills/webnovel-write`、`skills/webnovel-review` 的 evals 集**（当前分别只有 3 条、1 条），或至少明确记录"生成质量目前主要靠 fantasy01 真仓人工冒烟验证，非自动化"这一验证方式的边界，写进对应 SKILL.md 或 README 的"已知限制"章节，避免后来者误以为已有充分自动化覆盖。**（2026-09-10 已完成：选择"记录边界"选项——README「开发与测试」新增「已知限制（自动化验证边界）」节；扩充 evals 留待积累真实样本后另行立项）**
- [ ] **跟踪交接文档登记的数据缺口**：fantasy01 真仓 `定稿/设定/名册/苏小白.md` 缺失导致"主角卡"字段不全（见 `docs/cursor/项目复审/2026-09-04-会话交接.md`），标注"不阻塞"但应补一条正式 TODO 项防止遗忘。（2026-09-09 复审：该测试书仓不在本仓库/本次审阅环境中，未能独立复核，状态维持不变）
- [x] **给依赖声明补锁文件**：根 `requirements.txt`、`webnovel-writer/scripts/requirements.txt`、`webnovel-writer/dashboard/requirements.txt` 全部为无上界的 `>=` 声明，仓库内无任何 `*.lock`/`pip-compile` 产物。建议生成一份 `pip freeze` 锁文件作为 CI 与发版验证的"已知良好"基线，`requirements.txt` 本身可保留宽松范围供人工升级。与上面「补 CI」一条一起处理，二者叠加才能防止"依赖漂移导致测试结果不可复现"。证据：2026-09-09 复审新发现（P2-5），见报告「本轮新发现」一节；实测本次虚拟环境已装到比首次审阅更新的 `starlette`/`fastapi` 补丁版本（pytest 警告数从 2 条变为 27 条）。**（2026-09-10 已完成：新增根 `requirements.lock`（py3.13.5 干净 venv freeze，41 包）；仅装锁的干净 venv pip check 通过，全量 pytest 1588 passed / 81.35%，四校验脚本全绿）**

## P3

- [x] **MCP server 参数加前导 `-` 字符白名单校验**（`project_root`/`table` 等字符串/数组参数），降低理论上的参数注入面，非阻断项。**（2026-09-10 已完成：`call_tool` 入口统一 `_reject_leading_dash()`——字符串值与数组元素含前导 `-` 一律按 invalid arguments 拒绝，覆盖全部 14 工具；测试 4 条新增全绿）**
- [x] **同步 `AGENTS.md` 里的远程仓库地址**：文档写 `git@github.com:alittleseven/webnovel-writer.git`，实际 `origin` 为 `https://github.com/lgq-opc/webnovel-writer.git`。**（2026-09-10 已完成：AGENTS.md 已写 `git@github.com:lgq-opc/webnovel-writer.git`，与本地 origin 一致）**
- [x] **（可选）补充 ADR 归档约定**：如果团队认可"重大架构决策分散记录在各 `docs/zcode/<任务>/` spec 里、不额外抽 ADR"的现状，建议在 AGENTS.md 里显式写一句说明这个分工，减少"docs/decisions/ 只有 1 篇是不是漏了"的误判成本。**（2026-09-10 已完成：AGENTS.md「注意事项」新增 ADR 约定一条）**

## 已验证无需处理（供归档参考）

- 六项交接假设（ResourceWarning / 六条不变量 / 主角卡注入 / Inv-5 warn / README 徽章现状 / target_chapter 一致性）已于 2026-09-09 全部验证通过，无需重复处理。
- README 徽章/Star History 指向上游 fork 是维护者主动确认保留的现状，非缺陷。
