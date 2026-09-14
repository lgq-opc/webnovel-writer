# Phase 2 三增量的独立核验（Claude Code 单｜试点③）

> 派单方：Hermes 编排台 ｜ 执行：Claude Code（模型 `deepseek-v4-flash`）｜ 日期：2026-09-14
> 执行位置：**git worktree** `C:\lgq\ai-workspace\projects\zcode-plugins\webnovel-writer.pilot-verify`
> 分支 `pilot/verify-phase2`（从 `v8-author` HEAD 检出）｜ 未 push、未合入 ｜ **生产代码 0 改动**
> 核验对象：v6 线退役方案 Phase 2 的**增量 1 / 2 / 3**（提交 `511531e` / `438e45e` / `1b5bf95`）
> 依据：`docs/plans/2026-09-10-v6线退役方案.md` §1.5 / §1.6

---

## 0｜总体判断（先给结论）

**三处删除没有削弱任何 KEEP 侧的能力**。v7 写链、v6 守卫（`dual_format_guard`）、doctor 的 v6 可诊断面、
`contract_migrations` 与 6 条 invariants、全部 131 个生产模块的导入完整性——逐条实测**均未退化**。
`dual_format_guard` 与 `write_gates` 的解耦做到了「签名 + 输出逐字一致」（机器证明，非肉眼）。

**但删除未收口**：存在一批**指向已删命令的活引用**，其中 **3 处运行时可达且直接面向用户**
（`project-status` 的 next_action、guard hook 的 deny 文案、`state_manager` 的错误建议）。
它们不削弱能力，但会让用户/代理被引导去执行已经不存在的命令。

**一条派生结论**：本 worktree 路径下全量 pytest **不是全绿**（1 failed / 1546 passed）。
该失败**与三个增量无关**——已证明是 Windows MAX_PATH（260）环境限制，且失败用例在整个 Phase 2 期间**逐字未变**。
换言之：增量实施者自述的「全量绿」在原仓路径下可能为真，但**在试点 worktree 路径下不可复现**。

**无 P0**。上述死引用按性质属 P1（对外承诺面 + 用户可见文案），不阻塞合并，但建议在收口时一并修。

---

## 1｜断言清单（逐条结论）

图例：**成立** = 有命令与输出支持；**反例** = 有命令与输出**证伪**；**存疑** = 本次未取得足够证据，进 §5 待确认。

### A 组｜删除面收口（残留引用）

| # | 断言 | 结论 | 证据 |
|---|---|---|---|
| A1 | 被删 16 个模块名在生产代码中无 import／子模块导入／字符串派发引用 | **成立** | 技法 1 AST 扫描 16/16 CLEAN（`scan_residue.py`）；技法 2a 动态派发扫出的 19 个调用点无一指向被删模块 |
| A2 | 已删模块名显式 import 全部 `ModuleNotFoundError` | **成立** | 22/22（`import_all_assert.py`） |
| A3 | 全部 **131** 个生产模块可导入（无悬空导入） | **成立** | 131/131 成功。比 AST 静态扫描更强的证明——import 会当场求值模块级代码 |
| A4 | 被摘 6 条 CLI 命令在真入口上确实不存在 | **成立** | 全部 `rc=2 invalid choice`；对照 5 条在役命令全部仍被接受（`cli_removed_probe.py`） |
| A5 | 被摘 CLI 命令在 skills/commands/agents **无引用** | **反例** | 见 D5、D1、D2。命中：`agents/data-agent.md` 6 处、`hooks/guard_runtime_write.py` 6 处、`README.md` 5 行、`docs/guides/commands.md` 10 行、`docs/operations/operations.md` 5 行 |
| A6 | `data_modules/__init__.py` 无悬空导出名 | **成立** | `__all__` 与 `_LAZY_EXPORTS` 逐名一致；仅残留一行空注释 `# Memory Contract`（无内容，无害） |

### B 组｜KEEP 侧行为未削弱

| # | 断言 | 结论 | 证据 |
|---|---|---|---|
| B1 | `dual_format_guard._issue` 与已删的 `write_gates.issue` 签名与输出逐字一致 | **成立** | 7 个参数（名/顺序/默认值）全等 + 4 组输入键序与值全等（`check_issue_equiv.py`，§3.1） |
| B2 | 守卫拦截语义未削弱（v6↔v7 双向、不误伤、落定口径未漂） | **成立** | 夹具断言 C1–C7 全过（§3.2） |
| B3 | doctor 的 v6 合同树可诊断面未退化 | **成立** | `file.contract.{master,volume,chapter,review}` 四条仍在；坏合同 JSON 仍被抓为 error（D1–D4） |
| B4 | `contract_migrations` 与 6 条 invariants（含 `inv-5-contracts`）保留 | **成立** | E1、E2——与 §1.6「暂缓不删」的裁决一致 |
| B5 | v7 写链未受影响 | **成立** | 131/131 生产模块可导入，含 `v7_write` / `v7_cache` / `dual_format_guard` 与 §4 硬约束清单全部模块 |

### C 组｜既有测试覆盖

| # | 断言 | 结论 | 证据 |
|---|---|---|---|
| C1 | 全量 pytest 全绿 | **反例** | `1 failed, 1546 passed, 1 warning in 173.15s`，EXIT=1（§2） |
| C2 | 该失败**与三个增量无关** | **成立** | ① 失败用例在整个 Phase 2 期间 sha256 逐字未变；② 独立合成实验把悬崖钉在总路径长 **260**（§3.3） |
| C3 | 四个校验脚本全绿 | **成立** | 4/4 `EXIT=0`（§2） |

### D 组｜残留引用的运行时可达性（本次新发现）

| # | 发现 | 结论 | 证据 |
|---|---|---|---|
| D1 | `project-status` 的 next_action 把用户指向已删命令 | **反例（运行时可达）** | `phase=ready_to_commit → 'run webnovel.py chapter-commit --chapter 4'`，而该命令真跑 `rc=2 invalid choice`（H1） |
| D2 | guard hook 的 deny 文案推荐 3 条已删命令 | **反例（运行时可达）** | hook 真跑吐出 deny，文案含 `write-gate` / `chapter-commit` / `projections retry/replay`，三条命令实测**全部不存在**（H2） |
| D3 | `ALLOWED_RUNTIME_MARKERS` 是死常量 | **成立（缺陷）** | 全文件仅 1 处出现 = 定义处，零读取点；真正生效的判断 `_command_is_runtime_safe` 另硬编码同一批字符串（H3） |
| D4 | `state_manager`（`update-state`）的错误建议指向 `projections retry` | **存疑（静态命中）** | `state_manager.py:1485`。仅 `SQLITE_SYNC_FAILED` 分支触发，本次未构造该故障 → 进 §5 待确认 |
| D5 | 现行文档仍把已删命令列为在役 | **反例** | `README.md:260-264` CLI 入口表仍列 `write-gate`/`projections`/`chapter-commit`/`story-events`；`docs/guides/commands.md`、`docs/operations/operations.md` 仍给完整调用示例 |
| D6 | dashboard 的 `/api/story-events` 读一个已无写入方的表 | **存疑** | `dashboard/app.py:784,821` 查 `story_events` 表；写入方 `event_log_store` 已在增量 3 删除。属**读侧**，按 §1.6 归 Phase 3 → §5 待确认 |

### 逐条结论汇总

- **成立 12 条**（A1/A2/A3/A4/A6、B1–B5、C2/C3、D3）
- **反例 5 条**（A5、C1、D1、D2、D5）
- **存疑 2 条**（D4、D6）

> 注意 A5 与 D1/D2/D5 是同一事实的不同切面：**「被删命令在技能/文档面已无引用」这条断言不成立**。
> 这正是任务书 §3.1 给出的示例断言，本次**证伪**。

---

## 2｜复跑记录（原样输出）

### 2.1 全量 pytest

环境：`python 3.13.5`（`C:\software\development\python\python-3135\python.exe`，pytest 8.3.3 + pytest-cov）。
命令（**不在 PATH 上的 hermes venv python——它没有 pytest**，故用绝对路径）：

```powershell
$env:PYTHONUTF8='1'; $env:TMP=(Resolve-Path .tmp).Path
& 'C:\software\development\python\python-3135\python.exe' -m pytest --basetemp .tmp\pt-baseline
```

末尾原样输出：

```
TOTAL                                                               22675   3933    83%
Required test coverage of 80% reached. Total coverage: 82.65%
=========================== short test summary info ===========================
FAILED webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py::test_webnovel_skill_flow_runs_story_contract_context_and_review_pipeline_with_stubbed_vector_model
1 failed, 1546 passed, 1 warning in 173.15s (0:02:53)
```

**EXIT=1**。覆盖率 **82.65%**（门槛 80% 达到，失败原因是测试而非覆盖率）。

失败原样（节选）：

```
>       (refs_dir / "reading-power-taxonomy.md").write_text("## xuanhuan\n- 冲突钩优先", encoding="utf-8")
E       FileNotFoundError: [Errno 2] No such file or directory:
        'C:\\...\\webnovel-writer.pilot-verify\\.tmp\\pytest\\test_webnovel_skill_flow_..._book\\.claude\\references\\reading-power-taxonomy.md'
```

> 注意失败形状：**同一目录内，前一行 `genre-profiles.md` 写入成功，紧接着的 `reading-power-taxonomy.md` 失败**。
> 目录存在且可写（否则第一条也会失败）——差异只有文件名长度。这排除了「代码没建目录」这类回归解释。

### 2.2 四个校验脚本

```
=== 1) sync_plugin_version --check ===   Versions are in sync: 8.1.0            EXIT=0
=== 2) validate_release_notes ===        OK release notes / version: 8.1.0       EXIT=0
=== 3) validate_plugin_package ===       OK plugin package / errors: 0 warnings: 0 EXIT=0
=== 4) validate_reference_wiring ===     OK reference wiring: assets=63 consumers=53 drift=0  EXIT=0
```

**4/4 `EXIT=0`**。`validate_reference_wiring` 的 `assets=63 consumers=53 drift=0` 与
`docs/reports/2026-09-13-会话交接-缺陷修复与口径收口.md:69` 记录的值一致。

### 2.3 残留扫描（技法 1：AST 导入，按 `module.split('.')` 任一段匹配）

§1.6 记录了依赖扫描的两个盲区（字符串派发 / 子模块导入），本次两者都按它给的判据实现：

```
技法 1：AST 导入扫描（按 module.split('.') 任一段匹配）
  chapter_commit                   [增量1] CLEAN      memory_projection_writer  [增量1] CLEAN
  chapter_commit_service           [增量1] CLEAN      project_memory            [增量1] CLEAN
  event_log_store                  [增量3] CLEAN      projections               [增量1] CLEAN
  event_projection_router          [增量1] CLEAN      state_projection_writer   [增量1] CLEAN
  index_projection_writer          [增量1] CLEAN      story_events              [增量3] CLEAN
  memory_cli                       [增量1] CLEAN      summary_projection_writer [增量1] CLEAN
  memory_contract                  [增量1] CLEAN      vector_projection_writer  [增量1] CLEAN
  memory_contract_adapter          [增量1] CLEAN      write_gates               [增量2] CLEAN
```

**16/16 CLEAN**。含 13 个 BOM 文件在内的全量 `.py` 均纳入扫描（见 §3.4 的方法学说明）。

---

## 3｜构造用例与结果

> 任务书 §3.3 要求「**自己写，不抄原文方法**」。以下五个脚本全部为本单现场新写，
> 未复制仓库既有测试的任何 helper。完整源码见 §6 附录。

### 3.1 断言 B1：`_issue` 解耦等价性（成立样本）

做法：用 `importlib` 把**删除前**的 `write_gates/__init__.py` 从 git 对象加载成模块，
与当前的 `dual_format_guard._issue` 同输入比对签名与返回字典。不靠肉眼。

```
old issue signature: [('code','POSITIONAL_OR_KEYWORD','<empty>'), ('message','KEYWORD_ONLY','<empty>'),
                      ('severity','KEYWORD_ONLY','blocker'), ('path','KEYWORD_ONLY',''),
                      ('impact','KEYWORD_ONLY',''), ('repair','KEYWORD_ONLY',''), ('details','KEYWORD_ONLY',None)]
new _issue signature: （逐项相同）
  [OK] 签名（参数名 / 顺序 / 默认值）逐项一致
  [OK] 默认值全用: 键序 ['code','severity','message','path','impact','repair','details'] 值 {...}
  [OK] 显式填满:   键序同上，值含 details={"k":[1,2],"nested":{"x":null}}
  [OK] details 传 None / [OK] severity 显式 blocker
RESULT: PASS — _issue 与 write_gates.issue 签名与输出逐字一致（4/4 用例）
```

### 3.2 断言 B2/B3/B4：自建 v6 形态仓夹具（14/14）

夹具现场从零手写：完整 v6 骨架（8 个 `INIT_REQUIRED_DIRS` + 7 个 `INIT_REQUIRED_FILES`）+
`.story-system` 合同链（MASTER_SETTING / volumes / chapters / reviews）+ `commits/chapter_003.commit.json`
（`meta.status="accepted"`），外加一个 v7 形态仓（`book.yaml` + `定稿/正文/0003-*.md`）与一个空仓作对照。

```
=== 断言组 C：dual_format_guard（v7 settle 的唯一写入路径守卫）===
  [OK] C1 v6 已落定章 → 拦 v7 写入: {"code":"dual_format_write_blocked","severity":"blocker",
        "message":"第 3 章已以 v6 格式落定，禁止以 v7 双写", ...}
  [OK] C2 v7 已定稿章 → 拦 v6 写入: 同上，settled_format="v7"
  [OK] C3 空仓双向均放行（不误伤）
  [OK] C4 commit 非 accepted → 放行（落定口径未漂）
  [OK] C5 缺根配置 → 给出 warning；配置齐全 → None
  [OK] C6 detect 如实报 v6=True/v7=False
  [OK] C7 max_settled_chapter 正确: max=3

=== 断言组 D：doctor 的 v6 可诊断面 ===
  [OK] D1  命中 ['file.contract.master','file.contract.volume','file.contract.chapter','file.contract.review']
  [OK] D1b 组内 id 齐全
  [OK] D2  report.phase=plan_in_progress  snapshot.target_chapter=4  latest_accepted=3
  [OK] D3  json.contracts.{volumes,chapters,reviews} 均在跑
  [OK] D4  坏合同 JSON 被 doctor 抓出: json.contracts.chapters → error
           actual="broken=[{'path': '.story-system\\chapters\\chapter_003.json'"

=== 断言组 E：contract_migrations 与 invariants ===
  [OK] E1 contract_migrations 仍存在且可导入
  [OK] E2 invariants 仍为 6 条且含 inv-5-contracts
       ['inv-1-journal','inv-2-material-trajectory','inv-3-power','inv-4-promises','inv-5-contracts','inv-6-stale-age']

合计 14 条断言：14 成立 / 0 不成立
```

> **夹具修正留痕（W3 证据纪律）**：第一版夹具漏建骨架目录，phase 停在 `init_scaffolded`，
> 导致 D1/D4 假失败（命中为空）。这是**夹具缺陷不是产品缺陷**——补全骨架后复跑全过。
> 报告保留此过程，以便读者区分「实测到的」与「一开始看错的」。

### 3.3 断言 C2：pytest 失败的根因（反例样本）

**(a) 失败用例未被执行者改动**——从 git 取五个版本，`ast` 抽出该函数源码段比对哈希：

```
  511531e^    sha256[:16]=38c526aa02d53efc  行数=216
  511531e     sha256[:16]=38c526aa02d53efc  行数=216
  438e45e     sha256[:16]=38c526aa02d53efc  行数=216
  1b5bf95     sha256[:16]=38c526aa02d53efc  行数=216
  HEAD        sha256[:16]=38c526aa02d53efc  行数=216
RESULT: PASS — 该用例在整个 Phase 2 期间逐字一致
```

另：`git diff --stat 511531e^ HEAD -- test_webnovel_unified_cli.py` = **224 deletions / 0 insertions**
（三个增量只删用例，不改既有用例）。

**(b) 独立合成实验把悬崖钉在 260**——与失败用例无关的最小实验，
在与失败用例同深度的目录下写一串「前缀相同、仅名字变长」的文件：

```
目录部分长度 = 215
   总长  结果              文件名
    258  OK               xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.md
    259  OK               xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.md
    260  FileNotFoundError xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.md
    261  FileNotFoundError ...（此后全失败）
```

**悬崖精确落在 260**（Windows MAX_PATH）。回到失败用例：`genre-profiles.md` 总长 **257**（成功）、
`reading-power-taxonomy.md` 总长 **265**（失败）——**正好跨过 260**。

**根因**：worktree 根 `…\webnovel-writer.pilot-verify` 比原仓 `…\webnovel-writer` 长 **13** 字符。
`265 − 13 = 252 < 260`，即该用例在**原仓路径下不会失败**。
（仓储的 `scripts/conftest.py` 确实处理 MAX_PATH，但**只用于删除**（`\\?\` 前缀），不覆盖测试的 `tmp_path` 创建。）

> **本项仅证明到「260 悬崖」这一层，未在原仓实跑验证**（避免污染主检出）→ 进 §5 待确认 U-1。

### 3.4 断言 D1/D2/D3：死引用的运行时可达性

```
=== H1：project-status 的 next_action 指向已删命令 ===
  phase=ready_to_commit → next_action = 'run webnovel.py chapter-commit --chapter 4'
  真跑 `webnovel.py chapter-commit` → rc=2
  webnovel.py: error: argument tool: invalid choice: 'chapter-commit'
  (choose from where, preflight, project-status, doctor, freeze, timeline, ..., story-system, review-pipeline, knowledge)

=== H2：guard_runtime_write hook 的 deny 文案指向已删命令 ===
  rc=2（2=deny）
  systemMessage = 'webnovel-writer blocked a direct write or bypass command for Story System/read-model
                   files. Use webnovel.py write-gate, chapter-commit, or projections retry/replay instead.'
    文案推荐的 `write-gate`       → rc=2 invalid choice（命令不存在）
    文案推荐的 `chapter-commit`   → rc=2 invalid choice（命令不存在）
    文案推荐的 `projections retry` → rc=2 invalid choice（命令不存在）

=== H3：ALLOWED_RUNTIME_MARKERS 常量是否还有消费者 ===
  出现行号：[24]（仅 1 处 = 定义处；无任何读取点 → 死常量）
```

H1 顺带给出了**当前 CLI 的真实子命令表**（50 条），可据此核对 README/命令文档的承诺面。

### 3.5 方法学说明：扫描器自己的两个坑（供后续核验复用）

1. **UTF-8 BOM**：本仓 **13 个 `.py` 带 BOM**。用 `encoding="utf-8"` 读入后 `ast.parse` 会因 `U+FEFF` 直接
   `SyntaxError`，**整个文件被静默跳过**（BOM 本身不是缺陷——CPython 词法器会跳过它，所以文件能正常 import；
   但**扫描器**必须自己用 `utf-8-sig`）。第一版扫描器就漏了这 13 个文件。
2. **管道会吃掉输出**：`python … | Select-Object -First N` 在 PowerShell 下提前关管道，
   会让脚本以 `BrokenPipeError` 退出（实测 `EXIT=255`）而**看似失败**。改为重定向到文件再读。
   （与 `lgq/本机执行环境规避` 记忆一致：管道断开可能吞掉 stdout。）

> 这两条已计入 §1.6 的「依赖扫描盲区」清单之外，建议补为第 3 条盲区。

---

## 4｜结论与建议

### 4.1 对任务书核心问题的回答

> **「这些删除有没有削弱任何 KEEP 侧行为（v6 守卫、v7 写链、既有测试覆盖）？」**

- **v6 守卫 `dual_format_guard`：未削弱。** 解耦等价（B1 机器证明）+ 双向拦截语义完好（B2）。
  且因被删命令已不存在，守卫的**放行路径**（`_command_is_runtime_safe`）变成不可达——效果是**更严**，不是更松。
- **v7 写链：未削弱。** 131/131 生产模块可导入；§4 硬约束清单模块全部在盘。
- **既有测试覆盖：未削弱。** 唯一失败经三条独立证据链证明与增量无关（C2）。
- **v6 用户的可诊断性：未削弱。** doctor 的 `file.contract.*` 与 `json.contracts.*` 两组检查都在且真能抓错（B3）。
- **§1.6 的两处「暂缓」裁决：与实盘一致。** `contract_migrations` 在、invariants 仍 6 条（B4）。

### 4.2 建议（按性质分级；本次**不改生产代码**，仅供编排台/实施者参考）

**P1 — 对外承诺面与用户可见文案（建议收口时一并修）**

1. `scripts/data_modules/project_status.py:57` — `PHASE_READY_TO_COMMIT` 的 next_action 指向已删的 `chapter-commit`。
   该文案同时经 `project-status` CLI 与 **SessionStart hook** 暴露给代理（本会话开局即收到同类字段）。
2. `hooks/guard_runtime_write.py:134` — deny 文案推荐的 3 条命令全部不存在；同文件 `ALLOWED_RUNTIME_MARKERS`（第 24 行）已是死常量。
3. `README.md:260-264` + `docs/guides/commands.md` + `docs/operations/operations.md` — 仍把已删命令列为在役并给完整示例。
4. `agents/data-agent.md`（6 处）— 仍以 `chapter-commit` 描述落账机制；v7 路径实际由 settle 承载。

**P2 — 仅错误路径可达，量级低**

5. `scripts/data_modules/state_manager.py:1485`、`artifact_validator.py:261,277,296,319,330`、
   `doctor.py:425,513,566`、`user_report.py:375,687` — `repair` / `suggestion` 文案指向已删命令（D4 及同类）。
6. `scripts/data_modules/timeline_check.py:13`、`output_guard.py:9`、`data_modules/webnovel.py:1002` — 仅注释/文档字符串。

**P2 — 读侧面（按 §1.6 归 Phase 3，不建议现在动）**

7. `dashboard/app.py:784,821,837` 的 `/api/story-events` 两个端点，其数据源写入方已在增量 3 删除（D6）。
8. `data_modules/__init__.py:96` 残留空注释 `# Memory Contract`。

### 4.3 对退役方案文档的回写建议（W12）

建议在 §1.6 的「依赖扫描的两个盲区」之后**补第 3 条**：*扫描器自身对 BOM 与输出管道的处理*（§3.5）。
另建议在 §1.6 增量 1/2/3 各条末尾补一行「**本次未同步的 KEEP 面引用**」，把上述 P1/P2 显式登记为
「已知未收口」而非留白——当前方案读起来像是删除已完全收口，与实测不符。

---

## 5｜待确认（本次未取得充分证据，**不猜测**）

| # | 待确认项 | 为何未确认 |
|---|---|---|
| U-1 | 全量 pytest 在**原仓路径**（`…\webnovel-writer`）下是否全绿 | 已证明悬崖在 260 且 worktree 前缀多 13 字符，但**未在原仓实跑**——派单明令「不要改动主检出目录」，故未执行 |
| U-2 | `state_manager.py:1485` 的 `SQLITE_SYNC_FAILED` 分支是否真能触发并吐出错命令 | 需构造 SQLite 同步失败，代价高；本次仅静态定位（D4） |
| U-3 | dashboard `/api/story-events` 删除后是否恒空、是否有真实消费者 | 属读侧，未运行 dashboard；D6 仅到「写入方已删」这一步 |
| U-4 | 与试点第 ① 单（ZCode 盲区复查）的残留引用结论交叉比对 | 本单未取到 ① 单报告；任务书 §5.2 的交叉比对需编排台侧执行 |
| U-5 | CI（GitHub Actions 双平台）实跑结果 | 本单只跑本地；派单 §6 禁止 push，触发不了 CI |
| U-6 | 任务书 §4 要求的 `--output-format json` 会话摘要（含 `total_cost_usd`） | **本次是交互式会话，不是 `claude -p` 无头调用**，未产生该 JSON → 无法提供成本字段。这是本单对任务书 §4 的**唯一未交付项**，如实标注 |
| U-7 | `_contract_json_checks` 之外，doctor 是否还有其它 v6 专属组在增量后失效 | 本次只覆盖了 §1.6 点名的两组（`file.contract.*` / `json.contracts.*`） |

---

## 6｜附录：可复跑脚本全文

> 验收配方（任务书 §5.1）建议抽 1 条「成立」与 1 条「反例」复跑。推荐组合：
> **成立样本 = §6.1**（`_issue` 等价性）、**反例样本 = §6.2**（死引用运行时可达性）。
> 两者均为**只读**，不写仓库、不需要夹具清理（§6.2 只读既有文件 + 跑 CLI）。

### 6.1 `check_issue_equiv.py`（成立样本｜B1）

前置：`git show 438e45e^:webnovel-writer/scripts/data_modules/write_gates/__init__.py > .tmp/old_write_gates_init.py`

```python
import importlib.util, inspect, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "webnovel-writer" / "scripts"))
spec = importlib.util.spec_from_file_location("_old_write_gates", ROOT/".tmp"/"old_write_gates_init.py")
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
from data_modules.dual_format_guard import _issue as new_issue

def sig_of(fn):
    return [(p.name, p.kind.name, p.default if p.default is not inspect.Parameter.empty else "<empty>")
            for p in inspect.signature(fn).parameters.values()]

fails = []
if sig_of(old.issue) != sig_of(new_issue):
    fails.append("签名不一致")
CASES = [
    ("默认值全用", ("dual_format_write_blocked",), {"message": "第 3 章已以 v6 格式落定"}),
    ("显式填满", ("artifact_missing",), {"message": "缺 artifact", "severity": "warning",
        "path": ".webnovel/tmp/a.json", "impact": "影响面", "repair": "修复法",
        "details": {"k": [1, 2], "nested": {"x": None}}}),
    ("details 传 None", ("x",), {"message": "", "details": None}),
    ("severity 显式 blocker", ("y",), {"message": "m", "severity": "blocker"}),
]
for name, args, kwargs in CASES:
    a, b = old.issue(*args, **kwargs), new_issue(*args, **kwargs)
    if list(a.keys()) != list(b.keys()) or a != b:
        fails.append(f"[{name}] 不一致：{a} vs {b}")
print("RESULT:", "FAIL " + str(fails) if fails else
      "PASS — _issue 与 write_gates.issue 签名与输出逐字一致（4/4 用例）")
raise SystemExit(1 if fails else 0)
```

### 6.2 `dead_ref_reachable.py`（反例样本｜D1/D2/D3）

```python
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "webnovel-writer" / "scripts"
CLI, HOOK = SCRIPTS / "webnovel.py", ROOT / "webnovel-writer" / "hooks" / "guard_runtime_write.py"
sys.path.insert(0, str(SCRIPTS))
env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

from data_modules.project_phase import PHASE_READY_TO_COMMIT, ProjectPhaseSnapshot
from data_modules.project_status import next_action_for_phase

snap = ProjectPhaseSnapshot(project_root=str(ROOT / ".tmp"), phase=PHASE_READY_TO_COMMIT,
                            target_chapter=4, latest_accepted_chapter=3)
action = next_action_for_phase(snap)
print(f"H1 phase={PHASE_READY_TO_COMMIT} → next_action = {action!r}")
p = subprocess.run([sys.executable, "-X", "utf8", str(CLI), "chapter-commit", "--chapter", "4"],
                   capture_output=True, env=env)
out = (p.stdout + p.stderr).decode("utf-8", "replace")
print(f"  真跑 chapter-commit → rc={p.returncode} :: "
      f"{next((l.strip() for l in out.splitlines() if 'invalid choice' in l), '')[:100]}")

payload = json.dumps({"tool_name": "Bash",
                      "tool_input": {"command": "python x.py > .webnovel/index.db"}})
p2 = subprocess.run([sys.executable, "-X", "utf8", str(HOOK)],
                    input=payload.encode("utf-8"), capture_output=True, env=env)
try:
    msg = json.loads(p2.stderr.decode("utf-8", "replace")).get("systemMessage", "")
except json.JSONDecodeError:
    msg = p2.stderr.decode("utf-8", "replace")
print(f"H2 rc={p2.returncode} systemMessage = {msg!r}")
for tok in ("write-gate", "chapter-commit", "projections retry", "projections replay"):
    if tok in msg:
        r = subprocess.run([sys.executable, "-X", "utf8", str(CLI), tok.split()[0], "--help"],
                           capture_output=True, env=env)
        o = (r.stdout + r.stderr).decode("utf-8", "replace")
        print(f"  文案推荐的 `{tok}` → rc={r.returncode} "
              f"{'invalid choice（不存在）' if 'invalid choice' in o else '仍存在'}")

src = HOOK.read_text(encoding="utf-8")
print("H3 ALLOWED_RUNTIME_MARKERS 出现行号：",
      [i for i, l in enumerate(src.splitlines(), 1) if "ALLOWED_RUNTIME_MARKERS" in l], "（仅定义处 → 死常量）")
```

### 6.3 其余脚本（本单现场新写，全文见执行会话）

| 脚本 | 对应断言 | 做法 |
|---|---|---|
| `scan_residue.py` | A1 / A5 | AST 导入（按段匹配）+ 动态派发实参 + 字符串字面量兜底 + CLI 命令文本引用（分「承诺面／历史面」） |
| `import_all_assert.py` | A2 / A3 / B5 | 真 import 全部 131 个生产模块 + 22 个已删模块名反证 |
| `cli_removed_probe.py` | A4 | 真入口跑 6 条已摘命令（期望 `invalid choice`）+ 5 条在役命令对照 |
| `v6_repo_assert.py` | B2 / B3 / B4 | 自建 v6/v7/空 三形态仓夹具，14 条断言 |
| `check_test_unchanged.py` | C2 | 五版本 `ast` 抽函数体比对 sha256 |
| `pathlen_cliff.py` | C2 | 合成路径长度悬崖实验 |

---

## 7｜会话摘要（任务书 §4 要求）

- **`--output-format json` 摘要 / `total_cost_usd`：未提供。**
  本单以**交互式会话**执行（非 `claude -p` 无头调用），未产生该 JSON。
  任务书 §7 的「成本起步价 ≈ $0.15 / 后续 ≈ $0.06–0.08」在本单无从核对 → 已登记为 §5 U-6。
- **`permission_denials`：无。** 本单未出现任何工具被拒；所有 Write/Edit/PowerShell 调用均执行成功，
  产物均已落盘（本报告本身即为在盘证据）。
- **生产代码改动：0。** `git status` 仅含本报告与 `.tmp/`（后者已 gitignore，且收尾清理）。

## 8｜交付自检（对照任务书 §4 / §6）

| 要求 | 状态 |
|---|---|
| §4 报告含断言清单 / 复跑记录 / 构造用例与结果 / 逐条结论 / 待确认 | ✅ 见 §1 §2 §3 §4 §5 |
| §4 `--output-format json` 会话摘要（含 `total_cost_usd`）附报告尾 | ❌ **未提供**——交互式会话无此 JSON，如实标注（§5 U-6） |
| §4 生产代码 0 改动 | ✅ 仅新增本报告文件 |
| §6 不 push、不合入 | ✅ 仅本地提交到 `pilot/verify-phase2` |
| §6 构造仓只在 `.tmp/`、用完清理 | ✅ 夹具与中间产物均在 `.tmp/`，收尾已清理 |
| §6 不确定的一律标「待确认」，不猜测 | ✅ §5 共 7 项 |
