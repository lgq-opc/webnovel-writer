# 引用盲区复查报告（编排台试点① · ZCode 无头）

> 任务书：`C:\lgq\a-hermes-space\reports\20260914-试点任务书-ZCode-引用盲区复查.md`
> 派单方：Hermes 编排台 ｜ 执行：ZCode 无头会话 ｜ 日期：2026-09-14
> 工作区：`C:\lgq\ai-workspace\projects\zcode-plugins\webnovel-writer.pilot-refscan`（worktree）
> 分支：`pilot/zcode-refscan`（自 `v8-author` HEAD `428850e` 检出；开工核对 `git status` 干净）
> 口径：**只读复查 + 报告**；不修代码、不 push、不合入、不动 `docs/plans/`（任务书 §6）

## 0 范围与基线

- 扫描面：全仓 **297 个 `.py`**（排除 `.git/`、`__pycache__/`、`.tmp/`、`dist/`、`node_modules/` 等）。
  覆盖任务书 §1 点名的 `scripts/`、`mcp/`、`data_modules/`、`tests/`，并额外纳入 `hooks/`（4 个）、`dashboard/`（7 个）、仓库根（`conftest.py`、`sitecustomize.py`）以消除侧盲区。
- 被查名清单：抄自 `docs/plans/2026-09-10-v6线退役方案.md` §1.5/§1.6 的增量 1–3 删除记录（§1）。
- 结论先行：**19 个已删模块名在现行代码中 0 残留**——三路模块引用扫描（字符串派发 / 导入按段 / AST）全零；全文本提及的命中经逐条判读全部为非引用形态（数据值 / 表名 / 文件名 / 注释 / 负向测试断言），详见 §3.5、§5。

## 1 已删模块清单（抄自方案 §1.6 增量 1–3）

| 增量 | 已删模块名 | 出处 |
|---|---|---|
| 1（v6 提交链簇 + memory-contract 簇） | `chapter_commit_service`、`chapter_commit`、`projections`、`state_projection_writer`、`summary_projection_writer`、`vector_projection_writer`、`index_projection_writer`、`memory_projection_writer`、`event_projection_router`、`memory_contract_adapter`、`memory_contract`、`memory_cli`、`project_memory`（13 个） | §1.6 增量 1「删模块 13 个」 |
| 2（write_gates 簇） | `write_gates` 整包（含子模块 `__init__` / `prewrite` / `precommit` / `postcommit`） | §1.6 增量 2「删模块：`write_gates/` 整包」 |
| 3（story-events 簇） | `event_log_store`、`story_events` | §1.6 增量 3「删模块：`event_log_store.py` + `story_events.py`」 |

计 **16 个顶层名 + 4 个子模块名**（子模块名并入「按段匹配」口径；`__init__` 不作检索词）。
随删的还有 6 条 CLI 命令、3 个测试文件、2 个行为评测名——不属本单核心口径，作为附加项另查（§5.3）。

## 2 方法与灵敏度验证

### 2.1 五路技法

| 路 | 技法 | 实现 |
|---|---|---|
| A | 字符串式动态派发实参（**盲区一**的专门技法） | 正则 + AST 双路提取 `_run_data_module("X")` / `_run_script("X.py")` 的首个字符串实参，与清单比对 |
| A3 | 全字符串常量点分路径 | AST 遍历所有字符串常量，按 `.` 分段，任一段命中即报（覆盖 `importlib.import_module("data_modules.X")` 类形态） |
| B | 导入语句按段匹配（**盲区二**的专门技法） | 行首 `from/import` 的模块路径按 `.` 分段，任一段命中即报（含相对导入前导点） |
| C | 常规 AST import 扫描（对照） | `ast.Import/ImportFrom` 全量；同时跑「末段比对（历史口径）」与「任一段比对（修正口径）」 |
| D | 全文本词元提及 | 删除名作为独立词元（`(?<![A-Za-z0-9_])name(?![A-Za-z0-9_])`）出现在任意行即记录，注释 / 文档串 / 测试断言全部显形 |

A/B/C 三路是「模块引用」判定；A3/D 是超集证据，命中逐条判读（§3.5）。

### 2.2 灵敏度验证（阳性对照，先行）

**零命中的结论必须先证明扫描器不是「永远返回 0」。** 在临时目录建两文件样板，内容覆盖五路全部命中形态：

```python
# pkg/a.py
"""阳性对照样板 a。"""
from data_modules.write_gates.prewrite import check
import data_modules.chapter_commit_service
from .memory_cli import main


def f():
    return _run_data_module("chapter_commit_service", []) + _run_script("event_log_store.py", [])
```

```python
# pkg/b.py
"""阳性对照样板 b。"""
import importlib

mod = importlib.import_module("data_modules.event_projection_router")
X = "data_modules.write_gates"
# 历史注释：memory_cli / project_memory 已随增量 1 删除
```

同一套命令对样板运行的结果（输出原样见 §6）：

| 路 | 样板命中 | 说明 |
|---|---|---|
| A | `chapter_commit_service`、`event_log_store.py` | 两种函数、两种形态都命中（`.py` 后缀由 `(\.py)?` 兜住） |
| B | `chapter_commit_service:1`、`memory_cli:1`、`write_gates:1`、`prewrite:1` | **`from data_modules.write_gates.prewrite import` 被按段命中——盲区二在样板中复现** |
| C | 4 条语句中 3 条命中，含 `from data_modules.write_gates.prewrite` | 末段比对（包级清单）只命中 2 条——**历史盲区在对照中如实暴露**；含子模块清单的修正口径命中 3 条 |
| D | 19 名中 6 名命中（含注释行的 `memory_cli`/`project_memory`） | 注释 / 字符串形态显形 |

样板全路命中、仓库全路为零 ⇒ 零结果是「扫过了且没有」，不是「没扫到」。

## 3 结果

### 3.1 技法 A：字符串式动态派发——0 命中

派发实现确认：`data_modules/webnovel.py:115` `mod = importlib.import_module(f"data_modules.{module}")`——全仓仅此一处派发通道，其字符串实参已被全量提取。

命令与输出（原样，命令见 §6）：

```text
$ grep -rhoE '_run_(data_module|script)\("[^"]+"' --include='*.py' . | sed -E 's/.*\("([^"]+)"$/\1/' | sort -u
archive_manager.py
backup_manager.py
context_manager
entity_linker
extract_chapter_context.py
index_manager
init_book.py
init_project.py
memory.store
migrate_state_to_sqlite
nonexistent_script_xyz.py
placeholder_scanner
rag_adapter
review_pipeline.py
schemas
state_manager
status_reporter.py
story_system.py
style_sampler
update_master_outline.py
update_state.py

$ ...（同上管道）... | grep -E "^($NAMES)(\.py)?$" || echo "0 命中"
0 命中
```

- 21 个实参逐一核对：全部指向**现存**模块。其中 `memory.store` 按段为 `memory`/`store`（均非删除名）；`nonexistent_script_xyz.py` 与 `schemas` 来自负向测试用例（`data_modules/tests/test_coverage_boost.py:544/550`），非生产派发。
- 单引号形态另查：无输出（无变体）。
- AST 路与文本路结果一致：命中 0 处。

> 附注：`migrate_state_to_sqlite`（增量 1 曾因本盲区被漏判、后经 `migrate` 子命令确证可达而未删）**仍是现存模块**，与删除清单无关，此处仅为说明 A 路对它的覆盖是良性的。

### 3.2 技法 A3：全字符串常量点分路径——2 处（均非模块引用）

```text
HIT webnovel-writer/scripts/data_modules/context_manager.py:295 str='project_memory.json'
HIT webnovel-writer/scripts/data_modules/tests/test_context_manager.py:39 str='project_memory.json'
```

判读：两处都是**数据文件名** `.webnovel/project_memory.json`，不是模块引用。全仓 `project_memory.json` 仅此 2 处（`grep -rn "project_memory.json" --include="*.py" .` 输出 2 行），且**无任何写入者**——`context_manager.py:295` 是 `_load_json_optional(...)` 可选读取（文件不存在即跳过）。属 v6 读侧遗留的容错路径，不构成对已删 `project_memory.py` 的依赖。

### 3.3 技法 B：导入行按段匹配——0 命中

```text
$ for n in <19 名>; do c=$(grep -rE "^[[:space:]]*(from|import)[[:space:]]+[A-Za-z_.]*\b$n\b" --include='*.py' . | grep -v __pycache__ | wc -l); echo "$n: $c"; done
chapter_commit_service: 0
chapter_commit: 0
projections: 0
state_projection_writer: 0
summary_projection_writer: 0
vector_projection_writer: 0
index_projection_writer: 0
memory_projection_writer: 0
event_projection_router: 0
memory_contract_adapter: 0
memory_contract: 0
memory_cli: 0
project_memory: 0
write_gates: 0
prewrite: 0
precommit: 0
postcommit: 0
event_log_store: 0
story_events: 0
```

全仓 2697 条「import 行」逐一过段，无一命中。
文本路（2697 行）与 AST 路（2695 条）的 2 条差值已定位：`data_modules/__init__.py:10,12` 是**文档串里的示例行**（`from data_modules.index_manager import ...` 等，非语句），与删除名无关。

### 3.4 技法 C：AST import 对照——0 命中

```text
$ python -X utf8 - <<'PY' ...（脚本见 §6 命令 C）... PY
AST import 语句数=2695 解析跳过=0 命中=0
```

三种口径同时为零：末段比对（历史口径·包级清单）0、末段比对（含子模块清单）0、任一段比对 0。
解析跳过 0：13 个带 BOM 的文件按 `utf-8-sig` 读入（首轮曾跳过，已修正后重跑）。

### 3.5 技法 D：全文本词元提及——命中均为非引用形态

逐名计数（命令见 §6），命中判读如下：

| 名 | 计数 | 命中性质（逐条判读） |
|---|---|---|
| `chapter_commit` | 25 | ①状态结构的数据值 `"primary_write_source": "chapter_commit"` / `write_fact_role`（`story_runtime_sources.py:23`、`story_runtime_health.py:96`、`user_report.py:674/688/702`，及 tests 多处）；②守卫名单 `"chapter_commit.py"`（`hooks/guard_runtime_write.py:117`）；③测试仿真 / 注释（`scripts/tests/test_guard_redirect.py:34`、`test_hooks.py:102`）。**无 import、无派发。** |
| `projections` | 20 | 已撤命令词汇：hooks 4 处、`artifact_validator.py` 4 处、`doctor.py` 2 处、`state_manager.py:1485`、`impact_analyzer.py:155`、`material_usage.py:8`，tests 7 处。**无 import、无派发。** |
| `state_projection_writer` | 1 | `data_modules/tests/test_prompt_integrity.py:676`——**负向断言**文案（断言技能文本不得出现该说法）。 |
| `project_memory` | 2 | 数据文件名 `project_memory.json`（同 §3.2）。 |
| `write_gates` | 3 | `dual_format_guard.py:31-34` 注释，记录 Phase 1「`_issue` 内联自 `write_gates.issue`」的历史。 |
| `prewrite` | 6 | `timeline_check.py:13` 注释；`test_context_manager.py:378-380` 的**键名** `prewrite_validation`；`test_prompt_integrity.py:857/859` 注释。 |
| `precommit` | 6 | `run_ledger.py:303/306` 注释（术语用法）；tests 注释。 |
| `postcommit` | 5 | `artifact_validator.py:295/329` 的 impact 文案（v6 门禁词汇）；tests 注释。 |
| `story_events` | 5 | **SQL 表名**：`dashboard/app.py:792/804/824/837`（`FROM story_events`）、`tests/mock_demo.py:389`（建表）。读侧数据命名，非模块。 |
| 其余 10 名 | 0 | `chapter_commit_service`、`summary_projection_writer`、`vector_projection_writer`、`index_projection_writer`、`memory_projection_writer`、`event_projection_router`、`memory_contract_adapter`、`memory_contract`、`memory_cli`、`event_log_store` |

### 3.6 逐模块判定表

| 模块 | A 派发 | A3 字符串 | B 导入段 | C AST | D 文本 | 判定 |
|---|---|---|---|---|---|---|
| chapter_commit_service | 0 | 0 | 0 | 0 | 0 | **无引用** |
| chapter_commit | 0 | 0 | 0 | 0 | 25 | 无引用（D 命中为数据值 / 守卫名单 / 仿真，见 §3.5） |
| projections | 0 | 0 | 0 | 0 | 20 | 无引用（D 命中为已撤命令词汇，见 §3.5） |
| state_projection_writer | 0 | 0 | 0 | 0 | 1 | 无引用（负向断言文案） |
| summary_projection_writer | 0 | 0 | 0 | 0 | 0 | **无引用** |
| vector_projection_writer | 0 | 0 | 0 | 0 | 0 | **无引用** |
| index_projection_writer | 0 | 0 | 0 | 0 | 0 | **无引用** |
| memory_projection_writer | 0 | 0 | 0 | 0 | 0 | **无引用** |
| event_projection_router | 0 | 0 | 0 | 0 | 0 | **无引用** |
| memory_contract_adapter | 0 | 0 | 0 | 0 | 0 | **无引用** |
| memory_contract | 0 | 0 | 0 | 0 | 0 | **无引用** |
| memory_cli | 0 | 0 | 0 | 0 | 0 | **无引用** |
| project_memory | 0 | 2 | 0 | 0 | 2 | 无引用（同名数据文件名，见 §3.2） |
| write_gates | 0 | 0 | 0 | 0 | 3 | 无引用（历史注释） |
| prewrite | 0 | 0 | 0 | 0 | 6 | 无引用（键名 / 注释） |
| precommit | 0 | 0 | 0 | 0 | 6 | 无引用（术语注释） |
| postcommit | 0 | 0 | 0 | 0 | 5 | 无引用（v6 词汇文案） |
| event_log_store | 0 | 0 | 0 | 0 | 0 | **无引用** |
| story_events | 0 | 0 | 0 | 0 | 5 | 无引用（SQL 表名） |

## 4 总结论

**0 残留。** 增量 1–3 的 19 个已删模块名在 297 个 Python 文件中——字符串派发实参（A）、点分字符串（A3，2 处均为数据文件名）、导入行按段（B）、AST import（C）四路扫描 **0 命中**；全文本词元扫描（D）的命中经逐条判读，全部为数据值 / SQL 表名 / 文件名 / 注释与历史说明 / 负向测试断言，**无一构成对已删模块的引用**。两个历史盲区（字符串派发、子模块按段）在阳性对照中被复现，零结果可信。

## 5 附加发现（超出本单核心口径；只报告不修复；供编排台判读）

> 以下均为「已撤 **CLI 命令名** / v6 词汇」层面的残留，与 §4 的模块引用结论互不影响。按面分组，全部附证据。

### 5.1 hooks 守卫（活 hook，误导面最直接）

`webnovel-writer/hooks/guard_runtime_write.py`（注册于 `hooks.json:27-47`，PreToolUse 的 `Write|Edit|MultiEdit` 与 `Bash` 两个 matcher 均走它）：

- **死常量**：`ALLOWED_RUNTIME_MARKERS`（24–30 行）含 `"chapter-commit"`、`"write-gate"`、`"projections retry"`、`"projections replay"`；全仓仅定义处 1 行引用（`grep -rn "ALLOWED_RUNTIME_MARKERS"` 单行命中），即**从未被使用**。
- **内联白名单**：`_command_is_runtime_safe`（96–100 行）只认 `chapter-commit` / `projections retry|replay`——四个命令均已撤。
- **拒绝报文**（134 行）：`Use webnovel.py write-gate, chapter-commit, or projections retry/replay instead.`——守卫拦截时教用户执行不存在的命令。
- 117 行还拦 `chapter_commit.py`（文件已不存在）。
- 影响评估：v7 命令不会被误拦（拦截条件依赖受保护路径命中或该文件名），主要危害是**误导性提示**与死代码；测试 `test_hooks.py:90/102`、`test_guard_redirect.py:22/34` 仍以上述命令为样本、全绿。

### 5.2 生产面 repair / suggestion 文案指向已撤命令（用户可见）

| 位置 | 文案要点 | 可达性 |
|---|---|---|
| `project_status.py:57` | phase=READY_TO_COMMIT → `run webnovel.py chapter-commit --chapter N` | `project-status` 为在役命令 |
| `state_manager.py:1485` | SQLITE_SYNC_FAILED → `请运行 webnovel.py projections retry --chapter N` | `state` 在役；`test_state_manager_extra.py:655` 锁定该文案 |
| `doctor.py:425 / 513 / 566` | repair 提及 `projections replay` / `update-state` / `chapter-commit 双写` | doctor 在役（v6 诊断面） |
| `user_report.py:375` | `重新执行 chapter-commit 生成完整 commit。` | 报告生成路径 |
| `artifact_validator.py:261/277/296/319/330` | `chapter-commit` / `projections retry|replay` / `postcommit` 词汇 | **当前仅测试可达**（`validate_chapter_commit` 无生产调用点；该模块被 `run_ledger.py:34/38`、`user_report.py:22/54` 仅按常量与 payload 校验函数引用） |
| `impact_analyzer.py:155` | suggestion 提及 `projections` | 在役（v8 治理） |
| 注释 / 文档串 | `material_usage.py:8/170`、`style_domain.py:432`、`timeline_check.py:13`、`output_guard.py:9`、`webnovel.py:1002`、`commit_artifacts.py:25` | 无行为影响 |

### 5.3 测试与评测面

- `scripts/run_behavior_evals.py:121`：data-agent 边界评测把 `"chapter-commit"` 列为 `agents/data-agent.md` 的**必需字符串**（与同文件 109 行「write-gate 已随 v6 移除」注记并存）。
- `scripts/run_behavior_evals.py:175`：注释称红线由 `write_blocks_before_commit` 守卫——该评测已在增量 2 移除（同文件 109–112 行自述），注释与事实不一致。
- `agents/data-agent.md:120`：`projection 失败……由主流程补跑 projections retry`——**可执行指令形态**，但因无 `webnovel.py --project-root …` 前缀，`test_prompt_integrity._extract_cli_subcommands`（126–131 行正则）抓不到，守卫存在覆盖缺口。
- `test_webnovel_unified_cli.py:312`：测试名 / 文档串仍为「chapter-commit 四 artifact 必填」，实际断言是 exit code 2（命令不在注册表）——语义漂移。
- 已删 3 个测试文件（`test_write_gates.py` / `test_prewrite_timeline_gate.py` / `test_event_log_store.py`）确认**不存在**。
- 已移评测名：`commit_drives_projection` 0 提及、`commit_projection_runtime` 0 提及；`write_blocks_before_commit` 仅 1 处注释提及（见上）。
- 正面确认：`test_prompt_integrity.py:52-81` 的「活注册表」守卫（2026-09-13 改为从源码实提取）仍在役，本单复核其断言集合——19 个已删模块名无一出现在其涉及面。

### 5.4 非 .py 面（README / agents / references / 仓库模板）

- **`README.md:260-264`（外层）**：「常用子命令」表 12 行中 **4 行是已删命令**——`write-gate`(260)、`projections`(261)、`chapter-commit`(263)、`story-events`(264)，该表无 legacy 标注（v6 冻结提示在 184 行，仅覆盖「写章工作流」节）。
- `README.md:88/100/207`：`CHAPTER_COMMIT` 概念与「投影失败后已补跑成功」叙述（架构叙述层面）。
- **内层 `webnovel-writer/README.md`：0 命中（干净）。**
- `skills/`、`commands/`：0 命中（干净；负向守卫在役）。
- `agents/data-agent.md:13/26/67/71/72/120`：v6 命令词汇（chapter-commit 概念 + `projections retry` 指令）。
- `references/index/reference-loading-map.md:92`（learn 追加 `project_memory.json`）与 `skills/webnovel-learn/SKILL.md:24`（「v7 不再有 project_memory.json」）**互相矛盾**。
- `references/author_glossary.json:55/100`（chapter-commit / write-gate 术语）、`references/author_error_catalog.json:19-36`（`write-gate failed` / `chapter-commit rejected` 错误码映射）——面向作者的词汇 / 错误码表。
- `.github/ISSUE_TEMPLATE/bug_report.yml:15/27`、`.github/PULL_REQUEST_TEMPLATE.md:27`：`CHAPTER_COMMIT` 概念、`review-pipeline`。
- 历史记录不动作：`CHANGELOG.md`、`releases/*.md` 中的旧命令 / 旧模块名属发布史，不应改。

### 5.5 数据层命名（判读：非引用，不需动作）

- `story_events` 表名 / 端点（`dashboard/app.py`、`tests/mock_demo.py`）——SQLite 表名，属读侧（Phase 3 范围）。
- `"chapter_commit"` 作为 runtime provenance 值（`story_runtime_sources.py:23` 等）——状态结构数据值。
- `project_memory.json` 文件名——无写入者的可选读取路径。
- `write_gates` 历史注释（`dual_format_guard.py:31-34`）——Phase 1 解耦记录。

## 6 复跑命令（验收用）

> 环境：Git Bash（GNU grep）；工作目录为 worktree 根。以下命令均已原样执行，输出见 §3。本次另用一体化扫描器（五路 + 附加项 + 判定表）留存于执行机临时目录 `%TEMP%\refscan_20260914.py`（非交付物；其核心判定与下列命令等价）。

```bash
cd "C:/lgq/ai-workspace/projects/zcode-plugins/webnovel-writer.pilot-refscan"
NAMES='chapter_commit_service|chapter_commit|projections|state_projection_writer|summary_projection_writer|vector_projection_writer|index_projection_writer|memory_projection_writer|event_projection_router|memory_contract_adapter|memory_contract|memory_cli|project_memory|write_gates|prewrite|precommit|postcommit|event_log_store|story_events'
LIST='chapter_commit_service chapter_commit projections state_projection_writer summary_projection_writer vector_projection_writer index_projection_writer memory_projection_writer event_projection_router memory_contract_adapter memory_contract memory_cli project_memory write_gates prewrite precommit postcommit event_log_store story_events'

# 命令 A：派发实参提取 + 命中判定
grep -rhoE '_run_(data_module|script)\("[^"]+"' --include='*.py' . | sed -E 's/.*\("([^"]+)"$/\1/' | sort -u
grep -rhoE '_run_(data_module|script)\("[^"]+"' --include='*.py' . | sed -E 's/.*\("([^"]+)"$/\1/' | sort -u | grep -E "^($NAMES)(\.py)?$" || echo "0 命中"

# 命令 B：导入行按段匹配（逐名计数；0 即无命中）
for n in $LIST; do c=$(grep -rE "^[[:space:]]*(from|import)[[:space:]]+[A-Za-z_.]*\b$n\b" --include='*.py' . | grep -v __pycache__ | wc -l); echo "$n: $c"; done

# 命令 C：AST import 对照（末段口径 + 任一段口径）
python -X utf8 - <<'PY'
import ast, pathlib
D = {"chapter_commit_service","chapter_commit","projections","state_projection_writer","summary_projection_writer","vector_projection_writer","index_projection_writer","memory_projection_writer","event_projection_router","memory_contract_adapter","memory_contract","memory_cli","project_memory","write_gates","prewrite","precommit","postcommit","event_log_store","story_events"}
n = 0; skipped = 0; hits = []
for p in pathlib.Path('.').rglob('*.py'):
    if '__pycache__' in p.parts: continue
    try: tree = ast.parse(p.read_text(encoding='utf-8-sig'))
    except SyntaxError: skipped += 1; continue
    for x in ast.walk(tree):
        if isinstance(x, ast.Import):
            for a in x.names:
                n += 1
                if any(s in D for s in a.name.split('.')): hits.append((str(p), x.lineno, a.name))
        elif isinstance(x, ast.ImportFrom):
            n += 1
            segs = (x.module or '').split('.')
            if any(s in D for s in segs): hits.append((str(p), x.lineno, f"from {'.'*x.level}{x.module or ''}"))
print(f"AST import 语句数={n} 解析跳过={skipped} 命中={len(hits)}")
for h in hits: print("HIT", h)
PY

# 命令 D：全文本词元提及（逐名计数；计数>0 的逐条判读见 §3.5）
for n in $LIST; do c=$(grep -rnE "(^|[^A-Za-z0-9_])$n([^A-Za-z0-9_]|$)" --include='*.py' . | grep -v __pycache__ | wc -l); echo "$n: $c"; done
```

### 阳性对照复现（先跑样板、再信仓库）

```bash
mkdir -p /tmp/refscan_fixture/pkg && cd /tmp/refscan_fixture
cat > pkg/a.py <<'EOF'
"""阳性对照样板 a。"""
from data_modules.write_gates.prewrite import check
import data_modules.chapter_commit_service
from .memory_cli import main


def f():
    return _run_data_module("chapter_commit_service", []) + _run_script("event_log_store.py", [])
EOF
cat > pkg/b.py <<'EOF'
"""阳性对照样板 b。"""
import importlib

mod = importlib.import_module("data_modules.event_projection_router")
X = "data_modules.write_gates"
# 历史注释：memory_cli / project_memory 已随增量 1 删除
EOF
# 然后对当前目录原样重跑命令 A/B/C/D（变量定义同上）
```

期望输出（实测）：A 命中 `chapter_commit_service`、`event_log_store.py`；B 非零 4 名（`chapter_commit_service`/`memory_cli`/`write_gates`/`prewrite`）；C `语句数=4 解析跳过=0 命中=3`（含 `from data_modules.write_gates.prewrite`）；D 非零 6 名。若样板跑出全零，说明命令（尤其 B 的正则）失效——此时不得采信仓库的零结果。

## 7 边界与未覆盖项

- **只读**：未修改任何生产代码 / 测试；工作区唯一新增文件为本报告。
- 未 push、未合入、未触 `v8-author`/`master`、未动 `docs/plans/` 原文、未删任何文件。
- 未覆盖（申明）：运行期数据文件（`state.json`/`index.db` 等的**内容**）不在代码扫描范围；`dist/` 预打包产物与 `docs/`（含 `docs/plans/`）未纳入证据面；非 Python 文件的扫描（§5.4）为附加项、以「排除 `docs/` 后仍有命中」为准。
- 其它动态通道抽查：`importlib`/`runpy`/`__import__`/`exec`/`eval`/子进程 `python -m` 全仓抽查，未发现指向已删模块的通道（`doctor.py:866/880` 的 `find_spec` 名单仅第三方依赖；`scripts/__init__.py` 懒加载名单与 `data_modules/__init__.py` 惰性导出均无删除名）。
- 附带发现按「只报告不修复」交付；是否立修复单由编排台决定。
