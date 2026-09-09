# v8-author 分支独立复审报告（2026-09-10）

> 审阅人：Claude Sonnet 5（只读审阅，未改动业务代码）
> 范围：分支 `v8-author`（HEAD `26a3d8d`，v8.1.0 已发版并推送）
> 方法：直接读代码 + 实跑测试/校验脚本 + 两个只读调研子代理交叉验证 + git 历史核对
> 标注约定：**事实** = 本人或子代理亲自读代码/跑命令验证；**推断** = 基于事实的判断，未做穷举验证

---

## 0. 结论先行

这是一个自我审计纪律极强的项目：`docs/zcode/v8-gap-review-3rounds/README.md` 记录的 40 项缺口四阶段修复、`docs/cursor/项目复审/` 的交接与假设验证文档，都做到了"验收原文 → 具体测试/命令输出"逐条对齐，本次抽查未发现"文档写完成、代码却找不到"的情况。

但存在几个**该项目自己的审计方法论覆盖不到的盲区**：这些审计全部基于"跑通已有测试 + 真仓冒烟 1-2 章"，而非"环境是否稳定复现""是否有自动化门禁拦截退化"这类元层面问题。本次审阅的最主要发现集中在这一层：**没有 CI 跑测试套件**、**测试套件本身在非 Windows 环境下有 2 个必然失败的用例**、**核心架构总览文档从 v6 时代起就没更新过**。这三项加起来说明：项目的正确性证据目前完全依赖开发者本人在其 Windows 机器上手动执行 AGENTS.md 里的命令，一旦这个人不在场或换人，回归验证链条会立刻断裂。

未发现 P0（阻断级）问题。

---

## 1. 代码实现审阅

### 1.1 测试与质量门禁现状（事实）

在全新 Python 3.13 虚拟环境（无本地缓存、贴近"新协作者/CI"起点）中安装 `requirements.txt` + `dashboard/requirements.txt` 后：

```
python -m pytest   → 2 failed, 1581 passed, 5 skipped, 2 warnings in 24.06s
Total coverage: 81.22%（门槛 80%，pytest.ini --cov-fail-under=80）
sync_plugin_version.py --check         → Versions are in sync: 8.1.0
validate_plugin_package.py             → OK，errors:0 warnings:0
validate_reference_wiring.py           → OK，assets=63 consumers=53 drift=0
validate_release_notes.py              → OK，version 8.1.0
```

四个校验脚本全绿，证明 §2 讨论的"文档-代码对账"机制本身是可信、可重复的。

### 【P1-1】CI 未跑测试套件，代码正确性完全依赖人工本地执行

**事实**：`.github/workflows/` 下只有两个 workflow：
- `plugin-release.yml`：`on: push branches:[master]` + `workflow_dispatch`，内容是版本号解析、`sync_plugin_version.py --check`、`validate_release_notes.py`、`validate_plugin_package.py`、打 tag、建 GitHub Release —— **全部是发版元数据校验，不含 `pytest`**。
- `plugin-version.yml`：`on: push/pull_request` 但 `paths` 只限定在 `marketplace.json`/`plugin.json`/`sync_plugin_version.py`/`validate_release_notes.py`/`README.md`/`CHANGELOG.md`/`releases/**` —— 改动 `webnovel-writer/scripts/data_modules/*.py` 这类核心逻辑文件**根本不会触发这个 workflow**。

也就是说，仓库里 24,125 行源码、1580+ 条测试、80% 覆盖率门槛，全部只在贡献者本地手动执行（`AGENTS.md` 里写的 `python -X utf8 -m pytest`）。没有任何自动化机制阻止一次"忘了跑测试"的推送把回归带到 `v8-author` 分支上。

**推断**：这与该分支实际工作模式吻合——`git log` 显示开发全程在单一开发者本地 + Cursor/ZCode 会话中完成，`v8-author` 从未合并进 `master`（`git log --oneline origin/master..origin/v8-author` = 122 commits），发版走的是"本地打 tag 直推"（见 §1.3 交叉验证），而非触发 `plugin-release.yml` 的"push to master"路径——这意味着这个仓库里唯一一条写了 CI 定义的发版自动化流程，实际上从未被真正触发过。

### 【P1-2】测试套件在非 Windows 环境下有 2 个必然失败的用例

**事实**：失败用例是
`webnovel-writer/scripts/tests/test_runtime_compat.py::test_fix_sys_argv_opt_in_repairs_powershell_mojibake`
`webnovel-writer/scripts/tests/test_runtime_compat.py::test_fix_sys_argv_opt_in_accepts_true_variants`

根因在 `webnovel-writer/scripts/runtime_compat.py:51`：

```python
def _fix_sys_argv() -> None:
    if sys.platform != "win32":
        return
    ...
```

这两个测试设置了环境变量 `WEBNOVEL_FIX_ARGV_MOJIBAKE=1` 后断言 `sys.argv` 被修复，但函数第一行就因为 `sys.platform` 不是 `win32`（本次审阅环境 = Linux）直接返回，测试没有 `monkeypatch.setattr(sys, "platform", "win32")`，所以在任何非 Windows 环境（包括绝大多数 CI 供应商默认的 `ubuntu-latest`）上跑，这两条测试必然失败。

**推断**：项目文档里反复出现的"全量 XXXX passed"证据（`v8-gap-review-3rounds/README.md` 里能数出十几处）应该都是在 Windows 上跑出来的（`AGENTS.md` 明确要求 `-X utf8`、多处提到 PowerShell），这个平台相关缺陷此前从未暴露，正是因为没有 §1.1 提到的 CI——如果真的按 `plugin-release.yml` 里 `runs-on: ubuntu-latest` 的环境跑测试，这两条早就会红。这不是功能缺陷（`_fix_argv_mojibake` 本身逻辑测试独立跑是过的），而是**测试用例本身耦合了未声明的平台前提**，会让"贡献者在 Mac/Linux 上跑 `pytest` 却看到失败，误以为自己改坏了东西"。

### 【P1-3】核心架构总览文档严重过期，描述的是 v6 时代系统

**事实**：`docs/architecture/overview.md`（109 行）最后一次 git 修改在 `2026-06-04`（`git log -1 --format=%ad -- docs/architecture/overview.md`），全文 `grep -c "v7\|v8\|book.yaml\|MCP\|定稿"` 命中 **0 次**。内容仍是"7 个 Skill"、无 MCP、无 book-repo 概念的 v6 架构描述，而当前系统（v8.1.0）是 8 个 Skill + 14 个 MCP 只读工具 + 13 条命令 + v7 book-repo 双链路 + doctor 治理八组 + 六项数据不变量校验器。

**推断**：这份文件名叫 `overview.md`，位于 `docs/architecture/` 目录首位，是最容易被新协作者/新会话当作"系统是什么"入口来读的文档，但读到的会是一年多前的旧图。项目里其实有对应的新文档（`docs/guides/v7-write-path.md`、`docs/architecture/story-repo-spec-2026-06-10.md`、`docs/zcode/webnovel-copilot-300/04-architecture.md`），只是分散在 guides/zcode 目录下，`overview.md` 本身没有被替换或加一行"已过期，请看 XXX"的重定向。

### 【P2-1】AGENTS.md「当前状态」段落未随 v8.1.0 发版同步

**事实**：`AGENTS.md` 现存内容写"当前版本：v8.0.0……57 提交领先 master，尚未打 tag / 推送"。但：
- `webnovel-writer/.zcode-plugin/plugin.json` 实际版本是 `8.1.0`；`mcp/server.py` 的 `SERVER_VERSION` 同为 `8.1.0`。
- `git ls-remote --tags origin` 显示 `v8.1.0` 标签已存在于远端（对应 commit `21a0980`）。
- commit `26a3d8d`（"v8.1.0 推送收口"）记录 `push origin v8-author → 3d2ef5b..21a0980；push origin v8.1.0 → new tag`，`git status` 现为 `up to date with origin/v8-author`，工作区干净。
- 实测 `git log --oneline origin/master..origin/v8-author` = **122** 个提交，而非 AGENTS.md 里写的 57 个。
- `AGENTS.md` 最后一次改动是 `d726307`（"v8.0.0 文档面同步"），此后的 `21a0980`（release）、`26a3d8d`（推送收口）两次提交的改动文件列表里都**不包含 `AGENTS.md`**（已用 `git show --stat` 核实）。

**推断**：`AGENTS.md` 是本项目自己定义的"给协作者/AI 看的项目约定与当前状态"入口文件，但连续两次发版动作都漏掉了它的同步，导致任何依赖这份文件判断"现在是什么状态"的读者（包括下一次接手的 AI 会话）会得到过期结论（版本号、领先提交数、tag/推送状态三处均误）。这类"状态文件跟不上发版"的问题，恰恰是 `AGENTS.md` 自己在"OpenCode 工作区规则"一节里明令禁止的（"发现文档与代码不一致时，先……登记实际状态"）——即项目对自己提出的纪律，在最新一次发版里没有被完整执行。

### 【P2-2】v6/v7 双写守卫（dual_format_guard）配置来源不对称，缺失时静默降级

**事实**（子代理交叉核实）：v6 侧门禁（`write_gates/prewrite.py`、`precommit.py`）与 v7 侧 `v7_write.py` 的 `settle()` 都调用同一个 `dual_format_guard.check_unique_write_path`，但两侧取"另一格式是否已落定"的判断依据不对称：
- v6 侧从 `DataModulesConfig.story_repo_root` 取值，其来源是环境变量 `STORY_REPO_ROOT`（默认空）。
- v7 侧从 `decision.get("v6_project_root")` 或 `git config dualformat.v6root`（`v7_write.py` 内 `_v6_root_from_git_config`）反查，而这个 git config 键**只有 `migrate_v6_to_v7.py` 迁移器会自动写入**。

任一侧对应配置为空时，守卫直接跳过（代码里是 `if v6_root:` / `if story_repo_root:` 式的提前返回），**不打印 warning，不记录 journal**。

**推断**：CHANGELOG（v7.0.0 段）把这个机制描述为"唯一写入路径守卫"，容易让人以为它总是生效。实际上：只有书仓是经 `migrate_v6_to_v7.py` 迁移产生、或手工设置了对应环境变量/`git config` 时才会真正拦截"同一章号被 v6/v7 两边同时定稿"这种场景；人工新建或用其他方式复制出的双格式书仓，这层保护形同虚设且没有任何提示。这是一个"文档承诺 > 实际生效范围"的落差，建议至少在缺失配置时输出一条 warning。

### 【P2-3】安全相关模块测试覆盖率明显偏低，且门槛不区分模块风险等级

**事实**：`webnovel-writer/scripts/security_utils.py`（模块 docstring 自述"安全审计发现路径遍历和命令注入漏洞"，包含 `sanitize_filename`/`sanitize_commit_message`/`atomic_write_json`/`git_graceful_operation` 等安全关键函数）本次实测覆盖率仅 **53%**（637 行，约 104 行未覆盖，含 `git_graceful_operation` 部分异常分支 322-343 行、`restore_from_backup` 540-554 行）。其余偏低文件：`status_reporter.py` 34%、`update_state.py` 39%、`runtime_compat.py` 40%、`project_memory.py` 54%、`validate_release_notes.py` 51%。

`.coveragerc`/`pytest.ini` 的 `--cov-fail-under=80` 是**整体**门槛（当前 81.22%），单个高风险文件覆盖率低会被其他高覆盖率模块平均掩盖，不会单独触发失败。

**推断**：`security_utils.py` 因其"专门为修复安全漏洞而生"的定位，理应有更高的覆盖率要求（甚至到 100%），当前门槛设计发现不了这类模块的覆盖率滑坡。好消息（事实）：全仓 grep 未发现 `shell=True`、裸 `except:`、`eval(`/`exec(`/`os.system(`、硬编码密钥模式，说明代码本身的安全实践是干净的，缺口在"验证充分性"而非"已知漏洞"。

### 【P2-4】核心创作/审查技能的自动化行为评测覆盖很薄

**事实**：`run_behavior_evals.py --suite fast` 对应 `evals/fixtures/behavior/fast.json`，共 **23** 个 case，内容是"契约层"断言（skill frontmatter 是否存在、write-before-commit 顺序、artifact 归属、dashboard 只读等结构性检查），不涉及生成内容质量本身。而承担实际创作/审查职责的两个技能——`skills/webnovel-write/evals/evals.json` 只有 **3** 条 eval，`skills/webnovel-review/evals/evals.json` 只有 **1** 条 eval。

**推断**：项目现有的"验收证据"模式（`v8-gap-review-3rounds/README.md` 里反复出现）是"在 fantasy01 真仓的只读副本上跑 1-2 章冒烟，贴命令输出"，这种方式能验证代码路径是否跑通、门禁是否拦截构造出的坏用例，但样本量太小，无法系统性覆盖"AI 生成的正文/审查判断是否可靠"这类主观、长尾的问题域——而这恰恰是本项目的核心价值主张（"写到几百章依然不崩设定/伏笔/战力"）。这是纯单元测试和契约测试结构性覆盖不到的一类风险，建议视为长期项而非本轮可关闭项。

### 【P3-1】MCP server 部分参数缺少前导字符白名单校验

**事实**（子代理核实）：`mcp/server.py` 的 14 个工具（`where`/`project_status`/`doctor`/`setting_read`/`timeline_check`/`meter`/`rag_search`/`knowledge`/`context`/`materials_status`/`materials_assemble`/`power_check`/`foreshadow_scan`/`reader_signals`，与文档"14 个只读工具"数量一致）都以 list 形式（非 `shell=True`）拼进 `subprocess.run`，不存在 shell 注入；但 `project_root`、`table` 等字符串参数未做"不得以 `-` 开头"这类校验，理论上可构造参数值让下游 `argparse` 误解析成额外 flag。

**推断**：由于链路是本地 stdio、只读、且 `argparse` 对未知/重复 flag 会直接报错退出，实际可利用性很低，非阻断项，建议顺手加固但不需要作为本轮优先修复项。

### 【P3-2】远程仓库地址与 AGENTS.md 记载不一致

**事实**：`AGENTS.md` 写"远程：git@github.com:alittleseven/webnovel-writer.git"，但 `git remote -v` 实际显示 `origin` 为 `https://github.com/lgq-opc/webnovel-writer.git`。

**推断**：大概率是账号迁移/改名后遗留的文档漂移，不影响功能，但会误导协作者/AI 拼错误的 clone/issue 链接，顺手一并同步即可。

---

## 2. 需求/设计文档审阅

### 2.1 覆盖度评价（总体：好，好于同规模项目的平均水平）

**事实**：
- 每个大版本（v6.4.0 → v8.1.0）在 `docs/zcode/<任务名>/` 下都有完整的 spec → plan → 实施记录 三段式文档，例如 `docs/zcode/webnovel-copilot-300/` 包含 `01-requirements-and-principles.md` → `02-function-upgrade-map.md` → `03-critical-thinking.md` → `04-architecture.md` → `05-book-directory-structure.md` → `06-data-design.md` → `07-feature-flows.md` → `08-implementation-plan.md`，需求-架构-数据-流程-计划链条完整。
- `docs/zcode/v8-gap-review-3rounds/README.md` 的"F→T 反向对账"习惯（每个 spec 里的 F-项必须在 plan 里找到对应 T-项或显式"不覆盖"声明）在 AGENTS.md 里被写成硬规则并被后续文档执行，本次抽查（P2-1/P2-2/P3-3/P4-1）四项缺口修复均能在代码里找到对应实现和测试，未发现"文档写完成、代码缺失"的情况。
- `CHANGELOG.md` 质量突出：每个版本条目区分"给作者看的变化"和"维护者关心的技术细节"，且每条都带测试通过数/覆盖率/校验脚本结果，可追溯性强，是本次审阅能快速交叉验证的重要依据。
- 已弃用材料被规整归档在 `docs/archive/{architecture,superpowers}/`，未发现仍被引用的死文档。

### 2.2 具体缺口

1. **§1.1.3 提到的 `docs/architecture/overview.md` 过期**——归为文档缺口的核心一条，见上文 P1-3。
2. **决策记录（ADR）单薄**：`docs/decisions/` 目录只有 1 篇（`2026-09-02-多宿主适配立项决策.md`），而项目经历过 v6→v7→v8 多次架构级重大决策（book-repo 模型引入、MCP 只读化、settle 三门禁设计、doctor 治理组落地等），这些决策的"为什么这样选、否决了什么方案"目前分散在各 `docs/zcode/<任务>/` spec 的"理由"小节里，没有被抽出成独立可检索的 ADR。**推断**：不是缺失，而是分散，检索成本较高；如果团队认可"重大决策放 spec 里"的现状分工，可不作为待办，但值得在 AGENTS.md 里显式写明这一约定（目前 AGENTS.md 未提及 ADR 归档规则）。
3. **交接文档记录的一处"已知但未解决"的数据缺口**（子代理核实，事实）：`docs/cursor/项目复审/2026-09-04-会话交接.md` 记录真仓 `定稿/设定/名册/苏小白.md` 不存在，导致"主角卡"只有正名字段，标注"不阻塞"但未处理；这是针对具体测试书仓（fantasy01）的数据问题，不是代码缺陷，但既然文档已登记，建议纳入 TODO 跟踪避免遗忘。
4. **"六项交接假设验证"（`docs/cursor/项目复审/` 下 a00863c 对应文档，事实，子代理核实）**：六项假设（① ResourceWarning 不复现；② 06 §12 六条数据不变量当前已 6/6 实现；③ book.yaml 主角字段→主角卡/视角纪律注入生效；④ Inv-5 在无 `.story-system` 时正确 warn；⑤ README 徽章维持指向上游的现状确认；⑥ `target_chapter == max_settled_chapter` 相等）**全部验证通过/确认**，其中③验证过程中新登记了上述"苏小白.md 缺失"的数据缺口。未发现验证失败或部分通过的假设。

---

## 3. 亮点（供参考，不算待办）

- 全仓 grep 未发现 `shell=True`、裸 `except:`、`eval`/`exec`/`os.system`、硬编码密钥模式；`security_utils.py` 的函数命名和 docstring 直接指出对应 CWE 编号，安全意识清晰。
- `dashboard/` 有专门的安全测试文件 `test_dashboard_security.py`（CORS 白名单、只读连库、大文件拒绝、非回环地址默认拒绝需显式 flag），覆盖了一个本地可视化面板最容易踩的几类问题。
- 四个校验脚本（版本一致性/发布说明/插件包结构/引用布线）全部可独立运行且本次实测全绿，是文档-代码对账机制里少有的"自动化且已验证"的部分，值得作为其他项目缺口（如 §1 P1-1 的 CI 缺失）修复时的参照模式。

---

## 4. 审阅方法与局限性说明

- 本报告基于 2026-09-10 时点的 `v8-author` 分支（HEAD `26a3d8d`）快照；未审阅任何真实用户书仓数据（仅代码与文档）。
- pytest 是在 Linux + Python 3.13.5 + 全新 venv 中运行的，与项目主要开发环境（Windows + `-X utf8`）不同，这正是 P1-2 发现得以暴露的原因，同时也意味着本报告没有在 Windows 环境二次确认 1581 passed 的具体用例是否与项目历史记录的用例集合完全一致（只做了整体通过率层面的核实）。
- MCP/CLI/dashboard 的行为验证以静态读码 + 已有测试断言为主，未实际启动 MCP stdio server 或 dashboard 服务做端到端手工调用。
