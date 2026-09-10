# v8-author 复审落实核验报告（2026-09-10）

> 审阅人：Sisyphus（OpenCode，只读审阅，未改动业务代码）
> 基准：`docs/reviews/2026-09-10-v8-author-review.md` + `docs/TODO-from-v8-author-review.md`（12 项 P1–P3）
> 范围：`53894b8`（上次复审基线）→ `7585257`（HEAD），共 9 个提交、18 个文件、+716/−116
> 方法：直接读 diff/代码 + 按 `requirements.lock` 建**干净 venv** 实跑 + `53894b8` worktree 基线对照 + GitHub Actions 实跑记录核对
> 标注约定：**事实** = 本次亲自跑命令/读代码得到；**推断** = 基于事实的判断，未穷举验证。

---

## 0. 结论先行

- **本次修复的 11 项可验证 `[x]` 全部属实**，逐条在代码/测试/CI 里找到对应实现，未发现「文档写完成、代码缺失」。第 12 项（fantasy01 数据缺口）状态维持 `[ ]`，属外部测试书仓、本次环境不可复核。
- **未发现本次 9 个提交引入的回归**。用 `53894b8` worktree 对照，出现的失败全部在基线同样失败。
- **发现 2 条此前两轮审阅未暴露的问题**（均为**既有**问题，非本次回归；根因是前两轮审阅在 Linux 上跑、而问题只在中文 Windows 暴露）：
  - **N-1（P1，证据可复现性）**：`AGENTS.md` 与 `run_tests.ps1` 记录的测试命令在中文 Windows 上**不是全绿**——`python -X utf8 -m pytest` 有 **23 条失败**，`run_tests.ps1 -Mode full` 有 **2 条失败**；只有按项目自身既有约定设 `PYTHONUTF8=1` 才全绿。即「Windows 主环境全量 1588 passed」这一证据行，用文档命令无法复现。
  - **N-2（P3，CI 维护）**：新 CI 跑在 `ubuntu-latest`（locale 天然 UTF-8），因此**结构性地无法发现 N-1**；另有一条 GitHub Actions Node.js 20 弃用告警。

---

## 1. 修复前基线（`53894b8`）与本次闭环路径

| 提交 | 内容 | CI 结果（实测） |
|---|---|---|
| `7505...` 之前 | — | — |
| `0f3fa36` | test(security): 覆盖率 53%→95%，CI 设 90% 独立闸 | Plugin Tests **failure**（run `34420779902`） |
| `aa78fa7` | chore(ci): 补测试门禁——平台解耦、锁文件、pytest workflow | — |
| `f49e8d1` | feat(guard): dual_format_guard 缺配置产出 warning | — |
| `f3075bf` | feat(mcp): 工具实参拒绝前导 `-` | — |
| `8943cc8` | docs: 同步 v8.1.0 现状 | — |
| `8997e9c` | fix(test): 修 CI 抓出的两条平台耦合用例 | Plugin Tests **failure**（run `34423162284`） |
| `7f97b2f` | fix(test): 自检路径断言按 os.name 分流，修 Linux 覆盖率跌破 90 闸 | Plugin Tests **success**（run `34423430111`，1m3s） |
| `7585257` | docs(plans): v6 线退役方案（本报告后新增，docs-only，不触发 CI） | 未触发（path 过滤，符合预期） |

**事实**：`gh run list` 显示 `Plugin Tests` 最新一次（对应 `7f97b2f`）**success**。即上次报告 P1-1 里遗留的「真实 Linux 结果待 workflow 首次触发确认」**已由实跑关闭**。中间两次 failure→修复→转绿，说明该 workflow 真实生效、并已实际抓出并修掉两条平台耦合问题。

---

## 2. 12 项待办逐条核验

| 编号 | 上次结论 | 本次独立核验（事实） | 判定 |
|---|---|---|---|
| **P1-1** 补 CI 跑测试套件 | 未做 | `.github/workflows/plugin-tests.yml` 存在：`push master/v8-author` 与 `PR` 在触及 `requirements*.txt/lock`、`pytest.ini`、`webnovel-writer/{scripts,mcp,dashboard}/**`、本 workflow 时触发；ubuntu+py3.13，仅装 `requirements.lock`，跑全量 pytest + 四校验脚本 + security 覆盖率独立闸。GitHub 实跑 `34423430111` success。 | **[x] 属实** |
| **P1-2** 修 `test_runtime_compat` 两条平台耦合用例 | 未做 | `test_runtime_compat.py:69,81` 已加 `monkeypatch.setattr(sys, "platform", "win32")`，用例不再读真实平台。四组新增/相关测试在 lock venv 全绿。 | **[x] 属实** |
| **P1-3** 重写/标注 `overview.md` | 未做 | 已整体重写为 v8.1.0：七层模型 / 真源与编译产物 / v6·v7 双写链 / 组件面 8×4×13×14 / 治理与六不变量 / 工程面；文件头注明来源与替代旧版。实测 13 命令、14 MCP 工具清单与 `server.py` 一致。 | **[x] 属实** |
| **P2-1** 同步 `AGENTS.md` 状态段 | 未做 | 版本 v8.1.0、tag 已推送、远程 `lgq-opc`、加 CI 行、换待办入口均已同步；并加「引用前请重新 `git log` 实测」的防漂提示。 | **[x] 属实（见 N-3）** |
| **P2-2** `dual_format_guard` 缺配置 warning | 未做 | 新增 `unchecked_other_side_warning()`；`prewrite.py`/`precommit.py` 写入 gate report warning（`code=dual_format_guard_config_missing`，不阻断）；`v7_write.settle()` 无 v6 根时 stderr 打印。新增 6 条测试全绿。 | **[x] 属实** |
| **P2-3** `security_utils` 补测试 + 独立覆盖率闸 | 53% | lock venv 实测 `security_utils.py` = **95%**；`coverage report --include="*security_utils.py" --fail-under=90` → **EXIT 0**；CI workflow 含该步骤。 | **[x] 属实** |
| **P2-4** 记录 evals 覆盖边界 | 未做 | `README.md`「开发与测试」新增「已知限制（自动化验证边界）」节（3 条），覆盖 fast suite 契约层性质、write/review evals 仅 3/1 条、生成质量靠人工冒烟。 | **[x] 属实（选了「记录边界」）** |
| **P2-5** 依赖锁文件 | 未做 | 新增 `requirements.lock`（41 包，py3.13.5 干净 venv freeze）；`pip check` 通过；CI 仅按该锁安装。已核 lock 为根 `requirements.txt`（含 `-r` 引入 scripts + dashboard 两个子需求）的完整 freeze。 | **[x] 属实** |
| **P3-1** MCP 参数前导 `-` 白名单 | 未做 | `server.py` 新增 `_reject_leading_dash()`，在 `call_tool` 入口对字符串值与数组元素统一拒绝前导 `-`，覆盖全部 14 工具；新增 4 条测试全绿。 | **[x] 属实** |
| **P3-2** `AGENTS.md` 远程地址 | 不一致 | `AGENTS.md` 已写 `git@github.com:lgq-opc/webnovel-writer.git`，与 `git remote -v` 实测一致。 | **[x] 属实** |
| **P3-3** 补 ADR 归档约定 | 未做 | `AGENTS.md`「注意事项」新增 ADR 约定一条。 | **[x] 属实** |
| 跟踪 fantasy01 `苏小白.md` 数据缺口 | 未变 | 外部测试书仓不在本仓库/本环境，**不可复核**，状态维持 `[ ]`。 | **[ ] 维持** |

**四校验脚本（事实，lock venv 与全局环境各跑一遍均全绿）**：
```
sync_plugin_version.py --check        → Versions are in sync: 8.1.0
validate_plugin_package.py            → OK，errors: 0 warnings: 0
validate_reference_wiring.py          → OK，assets=63 consumers=53 drift=0
validate_release_notes.py             → OK，version 8.1.0 / previous_tag: v8.0.0
```

---

## 3. 新发现（既有问题，非本次回归）

### 【N-1 / P1】文档记录的测试命令在中文 Windows 上不是全绿；只有 `PYTHONUTF8=1` 才全绿

**事实（按 `requirements.lock` 干净 venv，Python 3.13.5，中文 Windows 本机实测）**：

| 调用方式 | 结果 |
|---|---|
| `python -X utf8 -m pytest`（**AGENTS.md 原样命令**） | **1618 collected / 23 failed / 0 error**，TOTAL 覆盖率 83.44% |
| `python -m pytest`（**`run_tests.ps1` 用的形式**） | 2 failed（`test_v7_write.py::TestSettle` 两条） |
| `PYTHONUTF8=1` + `python -X utf8 -m pytest` | **1618 / 0 failed / 0 error（全绿）** |
| `run_tests.ps1 -Mode smoke`（实测） | exit 0 |
| `run_tests.ps1 -Mode full`（实测） | **exit 1**，2 failed（同上 `test_v7_write`） |

`-X utf8` 下的 23 条失败为：`test_reference_search.py` 21 条 + `test_validate_csv.py` 2 条。

**根因（同一族：子进程文本解码的编码假设与实际字节编码不匹配）**：

- 测试用 `subprocess.run([...], text=True)` 读取子进程 stdout，未显式指定 `encoding`。
- **`-X utf8` 模式**：父进程按 UTF-8 解码，但被 `subprocess` 拉起的 **Python 子进程不继承 `-X utf8`**（本机 `PYTHONUTF8` 为空），子进程按系统 locale（cp936/GBK）输出 → 父进程 UTF-8 解码报 `UnicodeDecodeError: 'utf-8' codec ...`。
- **非 UTF-8 模式**：父进程按 GBK 解码，而 **git 的输出是 UTF-8**（提交含中文）→ `UnicodeDecodeError: 'gbk' codec ...`，`stdout` 变 `None` → `test_v7_write` 断言崩。
- 因此在本机**没有任何一种记录在案的调用方式能让全套变绿**，除非设 `PYTHONUTF8=1`。

**这是既有问题，非本次回归（事实，`53894b8` worktree 对照）**：
```
BASE(53894b8) reference_search w/ -X utf8  → 21 failed
BASE(53894b8) validate_csv     w/ -X utf8  →  2 failed   （= 23，与 HEAD 同集合）
BASE(53894b8) v7_write         w/o -X utf8 →  2 failed   （与 HEAD 同集合）
```

**与项目自身约定的冲突（事实）**：项目自己的设计文档明确规定 Windows 下要设 `PYTHONUTF8=1`，且「禁止依赖系统 locale」——
- `docs/architecture/story-repo-spec-2026-06-10.md:81`：脚本与子进程入口统一注入 `PYTHONUTF8=1`；禁止依赖系统 locale。
- `docs/superpowers/plans/2026-06-10-audit-fix-plan.md:15,400`：Python 3.10+ / pytest（Windows 下设 `PYTHONUTF8=1`）…全绿。
- `docs/operations/*`（2026-06-03/04）：示例一律 `$env:PYTHONUTF8='1'; python -m pytest`。
- `docs/zcode/zcode-native-adaptation/04-enhancement-design.md:51-52`：MCP 服务注入 `"PYTHONIOENCODING":"utf-8"`、`"PYTHONUTF8":"1"`。

但**当前 `AGENTS.md`「常用命令」只写 `python -X utf8 -m pytest`，`run_tests.ps1` 连 `-X utf8` 都未带、也未设 `PYTHONUTF8`**。两处都与项目既有实践脱节 → 新接手的协作者/会话按文档跑，会在中文 Windows 上看到 23 或 2 条「假失败」，浪费时间排查，也会污染「测试全绿」这一证据。

**两条可选修复路径（择一或并用）**：
1. **文档侧（最小改动）**：`AGENTS.md` 与 `run_tests.ps1` 统一为 `$env:PYTHONUTF8='1'; python -X utf8 -m pytest`（或脚本内 `$env:PYTHONUTF8="1"`），与项目既有约定对齐。
2. **测试侧（更彻底）**：给所有 `subprocess.run(..., text=True)` 显式指定 `encoding="utf-8"`，并让子进程入口统一走 UTF-8（`python -X utf8` / 注入 `PYTHONUTF8`），使结果不再依赖调用方的编码模式。

### 【N-2 / P3】新 CI 结构性地看不到 N-1；另有 Actions Node20 弃用告警

**事实**：`plugin-tests.yml` 固定 `runs-on: ubuntu-latest`。在 Linux 上 locale 天然 UTF-8，父子进程一致，N-1 不出现 → CI 绿。**推断**：这意味着「CI 绿」不能作为「在维护者本机（中文 Windows）按文档能跑绿」的证据；两条互相独立的信息，README/AGENTS 建议明确区分。

**事实**：`gh run view 34423430111` 附带告警——`actions/checkout@v4`、`actions/setup-python@v5` 目标 Node.js 20 已被强制跑在 Node.js 24 上。不影响当前结果，属 CI 维护项，后续升到 v5/v6 即可。

### 【N-3 / 观察】`AGENTS.md` 领先提交数为滚动快照

**事实**：`AGENTS.md` 写「125 提交领先 master（2026-09-10 实测…引用前请重新实测）」；本次实测 `git rev-list --count origin/master..HEAD` = **132**。因文件已自带「此数会增长、引用前重新实测」的提示，**不作为缺陷**，仅提示：这类滚动数字仍会漂，可考虑直接写命令而不写数字。

---

## 4. 方法与局限

- 本次在**按 `requirements.lock` 新建的干净 venv**（Python 3.13.5，41 包，`pip check` 通过）中实跑，比上次审阅「复用遗留 venv」更强；另用 `53894b8` worktree 做基线对照以区分「回归 vs 既有」。
- N-1 的根因结论基于：两种父进程模式（`-X utf8` / 非 UTF-8 / `PYTHONUTF8=1`）的实测对照 + 报错栈 + 本机 `PYTHONUTF8` 为空 + 子进程继承规则。**未**在 Linux 上二次复现 23 条失败（预期不出现，因 Linux locale 为 UTF-8），故 N-1 定性为「中文 Windows locale 特有」。
- 未启动 MCP stdio server、未启动 dashboard 做端到端手工调用；相关修复（P3-1）以代码 + 单测覆盖为准。
- 本次审阅期间曾因清理命令 glob 误删被跟踪的 `.coveragerc`，已 `git checkout -- .coveragerc` 立即还原，`git status` 干净；未留下任何对仓库的改动。
- MCP 参数加固、dual_format warning 的行为验证以静态读码 + 单测为主，未构造真实双格式书仓跑 settle。
