# TODO：源自 2026-09-10 v8-author 复审报告

> 详细证据见 [docs/reviews/2026-09-10-v8-author-review.md](reviews/2026-09-10-v8-author-review.md)（含 2026-09-09 复审补充章节）。
> 落实核验（11 项 `[x]` 是否属实 + 新发现 N 系列）见 [docs/reviews/2026-09-10-v8-author-fix-verification.md](reviews/2026-09-10-v8-author-fix-verification.md)。
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
- [superseded] **跟踪交接文档登记的数据缺口**：fantasy01 真仓 `定稿/设定/名册/苏小白.md` 缺失导致"主角卡"字段不全（见 `docs/cursor/项目复审/2026-09-04-会话交接.md`），标注"不阻塞"但应补一条正式 TODO 项防止遗忘。（2026-09-09 复审：该测试书仓不在本仓库/本次审阅环境中，未能独立复核，状态维持不变）**（2026-09-10 关闭，理由与实测证据：）**
  - 实测两仓：**缺名册的是 `fantasy01`（v1）**——`定稿/设定/名册` 不存在，其 `设定/` 下只有 `力量锚点.yaml`；而**活跃的 `fantasy01-v2` 已有 `定稿/设定/名册/苏小白.md`**。
  - v2 才是当前写链所在（ch40 由 `8d9ce0a settle: 第0040章 灾前夜` 落定，`book.yaml` 声明 `spec_version: "7.0"`），本条的原始影响面（主角卡字段不全）在活跃仓上不存在。
  - v1 是否继续维护，应由进行中的 v6 线退役方案（`docs/plans/2026-09-10-v6线退役方案.md`）统一裁决，而不是挂在这条数据缺口待办上。
- [x] **给依赖声明补锁文件**：根 `requirements.txt`、`webnovel-writer/scripts/requirements.txt`、`webnovel-writer/dashboard/requirements.txt` 全部为无上界的 `>=` 声明，仓库内无任何 `*.lock`/`pip-compile` 产物。建议生成一份 `pip freeze` 锁文件作为 CI 与发版验证的"已知良好"基线，`requirements.txt` 本身可保留宽松范围供人工升级。与上面「补 CI」一条一起处理，二者叠加才能防止"依赖漂移导致测试结果不可复现"。证据：2026-09-09 复审新发现（P2-5），见报告「本轮新发现」一节；实测本次虚拟环境已装到比首次审阅更新的 `starlette`/`fastapi` 补丁版本（pytest 警告数从 2 条变为 27 条）。**（2026-09-10 已完成：新增根 `requirements.lock`（py3.13.5 干净 venv freeze，41 包）；仅装锁的干净 venv pip check 通过，全量 pytest 1588 passed / 81.35%，四校验脚本全绿）**

## P3

- [x] **MCP server 参数加前导 `-` 字符白名单校验**（`project_root`/`table` 等字符串/数组参数），降低理论上的参数注入面，非阻断项。**（2026-09-10 已完成：`call_tool` 入口统一 `_reject_leading_dash()`——字符串值与数组元素含前导 `-` 一律按 invalid arguments 拒绝，覆盖全部 14 工具；测试 4 条新增全绿）**
- [x] **同步 `AGENTS.md` 里的远程仓库地址**：文档写 `git@github.com:alittleseven/webnovel-writer.git`，实际 `origin` 为 `https://github.com/lgq-opc/webnovel-writer.git`。**（2026-09-10 已完成：AGENTS.md 已写 `git@github.com:lgq-opc/webnovel-writer.git`，与本地 origin 一致）**
- [x] **（可选）补充 ADR 归档约定**：如果团队认可"重大架构决策分散记录在各 `docs/zcode/<任务>/` spec 里、不额外抽 ADR"的现状，建议在 AGENTS.md 里显式写一句说明这个分工，减少"docs/decisions/ 只有 1 篇是不是漏了"的误判成本。**（2026-09-10 已完成：AGENTS.md「注意事项」新增 ADR 约定一条）**

## 2026-09-10 落实核验新增（N 系列，源自 fix-verification 报告）

> 上述 P1–P3 的 11 项 `[x]` 已逐条独立核验属实，未发现本次修复引入的回归。以下为核验中发现、**此前两轮审阅未暴露的既有问题**（非本次回归；根因是问题只在中文 Windows locale 暴露，而前两轮在 Linux 跑）。

- [x] **N-1（P1，证据可复现性）文档记录的测试命令在中文 Windows 上不是全绿**：按 `requirements.lock` 干净 venv 实测——`python -X utf8 -m pytest`（AGENTS.md 原样命令）= **1618 collected / 23 failed**；`run_tests.ps1 -Mode full`（裸 `python -m pytest`）= **2 failed**；只有 `PYTHONUTF8=1` 才 0 failed。根因＝测试里 `subprocess.run(..., text=True)` 的编码假设与实际子进程输出不一致（`-X utf8` 模式子进程按 GBK 输出→父进程 UTF-8 解码崩；非 UTF-8 模式 git 输出 UTF-8→父进程 GBK 解码崩）。项目自身设计文档（`story-repo-spec` 等）本就要求 Windows 设 `PYTHONUTF8=1`，但 AGENTS.md/run_tests.ps1 未落实。修复路径：①文档侧统一加 `PYTHONUTF8=1`；②测试侧给 `subprocess.run` 显式 `encoding="utf-8"` 并让子进程入口走 UTF-8。**（2026-09-10 已完成，走"测试侧治本 + 文档统一"口径：）**
  - **①测试侧治本**：新增仓库根 `conftest.py`，在测试进程内统一子进程编码契约——text 模式调用方显式 `encoding="utf-8"`，并给子进程环境注入 `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8`（含调用方自带 env 的情形）。**刻意不设 `errors=`**：不让真编码缺陷被 replace 掩盖。此后再新增测试也不必逐处记得传 encoding。
  - **②文档与入口统一**：`AGENTS.md` 测试命令改为 `$env:PYTHONUTF8=1; python -X utf8 -m pytest`；`run_tests.ps1` 增 `$env:PYTHONUTF8`/`$env:PYTHONIOENCODING`，让不依赖 conftest 兜底的调用者也拿到确定编码。
  - **证据（同一命令、修前修后对照）**：`python -X utf8 -m pytest -p no:cov -q` 修前 = **23 failed**（21 `test_reference_search.py` + 2 `test_validate_csv.py`，报错均为 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xbd`）；加 conftest 后同一命令 = **0 failed**（`C_EXIT=0`），对照组 `PYTHONUTF8=1 python -X utf8 -m pytest` 修前即为 0 failed。
  - **不改生产代码**：生产侧同类隐患另立 N-4（见下）。
- [~] **N-2（P3，CI 维护）CI 结构性看不到 N-1**：`plugin-tests.yml` 固定 `ubuntu-latest`（locale UTF-8），N-1 不出现；另 `gh run view` 有 Actions `checkout@v4`/`setup-python@v5` 的 Node.js 20 弃用告警，建议后续升版。**（2026-09-10 已改，待一次真实 CI 运行确认：）**
  - `actions/checkout@v4`→`@v7`、`actions/setup-python@v5`→`@v7`（版本号经 GitHub API `releases/latest` 查证为 v7.0.1 / v7.0.0，非凭记忆；并已确认本 workflow 未使用 setup-python v7 移除的 `pip-install` 输入）。
  - 新增 `tests-windows` job：跑的就是 AGENTS.md 上写的原样命令、**刻意不设 `PYTHONUTF8`**，专门复现"用户照文档敲"的场景，使 N-1 这一类编码缺陷不再对 CI 隐身。
  - `on.push/pull_request.paths` 补 `conftest.py`（它现在是编码契约的一环，改它同样该触发 CI）。
  - **未证实项**：workflow YAML 已本地解析校验通过，但 **GitHub windows runner 的真实结果无法本地验证**——本机是中文 Windows（ANSI=GBK），runner 是 en-US（ANSI=cp1252），conftest 的设计是让测试不再依赖 locale，这一点需要一次真实 CI 运行才能确认。首次跑红时优先怀疑此项。
- [x] **N-3（观察）AGENTS.md 领先提交数为滚动快照**：文件写 125，实测 132（文件已自带「引用前重新实测」提示，非缺陷；可考虑只写命令不写数字）。**（2026-09-10 已完成：AGENTS.md「当前状态」改为不写死数字，只留 `git log --oneline origin/master..HEAD | wc -l` 命令；本次实测该值为 133。）**

## 2026-09-10 全项目巡查新增（F 系列 + N-4）

> 来源：本轮「待办清单清理 + 全项目审阅」的独立复现与巡查。证据均为本机实测命令输出。
> F 系列与前两轮审阅无关，是本轮新暴露的；N-4 是修 N-1 时顺带查出的同类隐患。

- [x] **F1（P1）doctor 在纯 v7 书上误报 v6 合同缺失，并把作者引向错误的路**：`fantasy01-v2` 已在 `book.yaml` 裁决弃用 v6 线、写到第 40 章，但 doctor 仍按 v6 的 `.story-system` 合同判 `mainline_ready=false`，并在 `recommended_actions` 里输出「补齐 Story System 合同和 accepted commit 后再写」——让作者去重建一个本仓已明确不要的东西。
  - **根因**：`story_runtime_sources.load_runtime_sources` 的 `fallback_sources` 完全由 v6 四份合同与 accepted commit 是否缺失决定；`story_runtime_health` 取 `mainline_ready = not fallback_sources`；`doctor` 直接消费它。
  - **一处勘察纠错**：任务描述里写「v7 仓没有 `.story-system`」，实际 `fantasy01-v2` **有** `.story-system/`（只剩 `commits/`+`events/` 迁移残留）。故判据取「**合同链锚点**是否存在」（`MASTER_SETTING.json` / `volumes` / `chapters` / `reviews`）而非目录存在性——只看目录会把这本书判回 v6，缺陷照旧。
  - **实现**：`domain_contract.py` 新增 `has_v6_contract_chain()` 与 `resolve_write_mode() -> "v6"|"v7"`（判据三条，任一命中即 v6：无 `book.yaml`、有 `.webnovel/state.json`、有 v6 合同链；**方向刻意偏向 v6**——误判 v6 只是多报告警，误判 v7 等于拆闸门）；`RuntimeSourceSnapshot`/health 报告透出 `write_mode`；`doctor` 按形态给 status/impact/repair；`invariant_check` 的 `Inv-5 合同重建` 对 v7 直接 skip。
  - **证据（真实书仓，修复前后）**：`--project-root .../fantasy01-v2 doctor` → `warnings: 3` → **`warnings: 1`**；`story_runtime.health` 的误导 repair 消失，`--format json` 中该条 `status: "ok"` 且 `"write_mode": "v7"`、`"mainline_ready": true`；剩下的 `run_log.step_coverage` 与本缺陷无关（见下 F4）。
  - **不削弱 v6 的证据**：构造 v6 形态仓跑真实 CLI，`mainline_ready=false` 与「补齐 Story System 合同」原样保留；`Inv-5` 仍 `status=fail`。新增测试 14 条（health 4 / doctor 4 / domain_contract 4 / invariant 2），其中 4 条专为"v6 闸门未被削弱"设卡。
  - **⚠️ 独立核验补齐的残留缺口（同日二轮修复）**：上述"v7 仓不再报 v6 合同缺失"**是形状相关的，不是全称**。独立核验构造出反例——纯 v7 仓（`book.yaml` + `定稿/正文` + 落定章，无 `state.json`）**只要 `.story-system` 残留任一 `volumes`/`chapters`/`reviews` 目录**，`has_v6_contract_chain` 即返回真 → 判回 `v6` → 原 F1 缺陷（`mainline_ready=false` + 「补齐 Story System 合同…」进 `recommended_actions` + Inv-5 `fail`）**原样复现**。根因是原判据只看目录**存在**，而空目录同样是迁移残留、并非合同链——**该错误期望还被写进了测试** `test_contract_chain_pins_v6`（建空 `volumes/` 后断言 `has_v6_contract_chain is True`）。
  - **二轮修法**：锚点目录改为**必须非空**（残留里只要有一份真合同文件仍判 v6，保守方向不变）；同步修正该测试并新增两条——空目录不构成链（判 v7）、空目录夹一份真合同仍判 v6。
  - **二轮证据**：复现核验员的构造用例 → `has_v6_contract_chain=False`、`resolve_write_mode=v7`；跑 doctor → `write_mode=v7`、Inv-5 由 `fail` 变 `skip`、误导 repair 出现次数 **0**。定向测试 93 项全绿。
  - **该缺口不是"拆闸门"方向**（是 v7 误判为 v6，多报告警），故 F1 的原始风险结论不变：独立核验**未发现任何 v6→v7 的可复现误判路径**，v6 闸门确实未被削弱。
- [x] **F2（P2）`v7-write` 子命令抛裸 traceback，且 `--help` 不工作**：`webnovel.py v7-write decision --help` 未捕获 `FileNotFoundError` 刷屏；根因是 `v7_args` 用 `nargs=REMAINDER`，`--help` 被当透传参数吃掉、到不了 argparse，于是继续解析项目根并崩。
  - **实现**：新增 `_resolve_root_or_report()`（复用 `cmd_where` 既有模式：捕获→stderr 诊断→返回 None），替换**全部 23 处**未捕获的 `_resolve_root_lenient` 调用点（22 个 `cmd_*` handler + 1 处 boundary；剩余 1 处 `_resolve_root_lenient` 在 `webnovel.py:563` 的 `try/except FileNotFoundError` 内，非未捕获、故意保留）。⚠️ **订正**：原提交 `bd892e4` 的 message 与实际不符，写的是「22 处」——独立核验实测为 23 处，无误漏，仅计数低报 1；以本条为准。
  - **证据**：修复前 `v7-write decision --help` → `Traceback ... FileNotFoundError`；修复后 → 打印 **v7_write 自己的** 帮助（含 `--repo`/`--json`，可确认非外层入口帮助）、`EXIT=0`。无项目根时 → 干净中文诊断 + `EXIT=1`、stderr 无 `Traceback`（`style-domain`/`learn` 同类命令一并生效）。
- [x] **F3（P2）`pack` 缺决策卡时静默产出降级上下文包**：`decision_from_card` 在决策卡不存在时静默返回空壳 `{"chapter": N, "title": "", "entities": []}`，`pack` 照常退出 0 并写出「## 决策卡」为空壳的上下文包——不报错、不警告，作者会拿着缺决策卡的包去写正文。
  - **实现**：`decision_from_card` 缺卡返回 `None`（抽出 `decision_card_path()`）；`pack` 分支遇 `None` 时 stderr 打印缺失文件全路径 + 正确顺序（先 decision 再 pack），`EXIT=1` 且**在写文件之前返回**。
  - **证据**：修复前 → `OK v7-write pack chapter=41 used=3,171` + 空壳决策卡段；修复后 → `ERROR ... 未提供 --json，且决策卡不存在：...\工作区\决策卡-0041.md` + `EXIT=1` + **未产出文件**（独立复核确认）。
  - **端到端反证（本轮"能开始写章"的实证）**：补齐决策 JSON 后重跑 `decision` → `pack`，上下文包的决策卡段**完整填充**（title/pov/time_anchor/目标字数/目标/节点），`used=3,606`。验证用产物已清理，书仓 `git status` 干净。
  - **一处既有测试随之修正**：`test_webnovel_cli_v7_write.py::test_v7_write_forwarding_pack` 原先在**没有决策卡**的仓上跑 `pack` 并断言退出 0——它固化的正是 F3 这个缺陷本身。已补最小决策卡夹具，使其继续只验证"转发"这件事。
- [ ] **N-4（P2，同类隐患，生产侧未修）生产代码中 `subprocess.run(text=True)` 未显式 `encoding`**：全仓 **12 处**（`v7_write.py` 3、`security_utils.py` 2、`backup_manager.py`/`init_project.py`/`author_sync.py`/`scale_drill.py`/`validate_release_notes.py`/`mcp/server.py`/`hooks/session_start.py` 各 1）。它们拉起的子进程有两类——`git`（输出 UTF-8）与**带 `-X utf8` 的 Python 子进程**（输出 UTF-8）——**两类都要求父进程处于 UTF-8 模式**；若父进程以裸 `python`（非 UTF-8 模式）启动，`text=True` 会按 GBK 解码 UTF-8 输出而崩。本轮按既定口径只治测试侧（N-1），生产侧未动。修复方向：给这些调用点显式 `encoding="utf-8"`，或在 CLI/钩子入口统一设置 UTF-8 模式。

### 独立核验结论（2026-09-10，evidence-verifier，只读）

对本轮 F1/F2/F3 与 N-1 的修复做了独立核验（不采信实施者自述，自建临时仓实跑）。结论：

- **F1 的原始风险不成立**：未发现任何 v6→v7 的可复现误判路径，v6 闸门未被削弱（构造 `state.json` 仓与 `state.json + commits` 仓实跑，`write_mode=v6`、原 repair 与 Inv-5 `fail` 原样保留）。
- **但发现一处残留缺口**（见 F1 条目内「独立核验补齐」），已二轮修复。
- **N-1 的决定性证据由核验方给出**：用 `--confcutdir` 关掉仓根 conftest 后，原 23 项失败**恰好复现**（21 `test_reference_search` + 2 `test_validate_csv`，均 `UnicodeDecodeError`）；不关则全绿。证明 conftest 是承重件且加载路径正确；并确认未用 `errors="replace"` 掩盖真缺陷。
- **测试质量**：7 个新增/改动用例逐条读过，**无空测试、无把修复前错误行为固化为期望值**（全部测试文件 0 删除行）。
- **两处数字修正**（不影响功能）：F2 称"替换 22 处"，实为 **23 处**（22 个 handler + 1 处 boundary）；另核验指出全量 `1645 passed / 83.38%` 未由核验方独立复跑，仅存实施方日志。
- **环境观察（已修）**：仓库根堆积 `.coverage.<host>.<pid>` 并行覆盖率文件（一次全量后 47 个），而 `.gitignore` 只忽略精确名 `.coverage` → 已补 `.coverage.*`。
- **核验未能覆盖**：因改动在核验中途被提交，无法回退到修复前代码执行"新测试必红"的反证，该判断为读父提交 diff 的推断；真实书仓 `fantasy01-v2` 的 `warnings 3→1` 按指令未由核验方触碰复核（由实施方实测）。

### F 系列遗留（本轮发现但未处理，需独立排期）

- [ ] **F4（P2）写章流程未按规范追加步骤日志**：`fantasy01-v2` 的 `.webnovel/logs/run_last.log` 只有 `write-start` 一行，doctor 因此报 `run_log.step_coverage` warning，其自述影响为「**写章崩溃后 run_last.log 无法定位最后卡点，排障困难**」。这是当前写链**唯一残留的 warning**，且直接关系"能否稳定写章"。修复方向：确认 SKILL 在每个关键步骤后调用 `run-log --event <step> --append`。
- [ ] **F5（P2）`user_report.py` 仍带同类 v6 专属假设**：`build_plan_report()`（约 884 行）按四份 v6 合同缺失判 `mainline_ready=false` 并记「missing {label} contract」；`build_init_report()` 按 v6 骨架（`设定集/正文/审查报告`）判缺。不在 doctor 链路上，本轮未动。可直接复用 F1 引入的 `resolve_write_mode`。
- [ ] **F6（P3）v7 仓的 `_resolve_chapter` 未覆盖纯 `定稿/正文` 形态**：`story_runtime_health._resolve_chapter` 仍只看 `.story-system` 与 `.webnovel/state.json`，不看 `定稿/正文`。`fantasy01-v2` 因有迁移残留 commits 解析出 40（正确）；一个只有 `定稿/正文` 而无两者痕迹的新 v7 仓会解析出 0，落到 `chapter_unspecified` 早返回分支（该分支现已带 `write_mode`，措辞正确，但会多一条 warning）。

## 已验证无需处理（供归档参考）

- 六项交接假设（ResourceWarning / 六条不变量 / 主角卡注入 / Inv-5 warn / README 徽章现状 / target_chapter 一致性）已于 2026-09-09 全部验证通过，无需重复处理。
- README 徽章/Star History 指向上游 fork 是维护者主动确认保留的现状，非缺陷。
