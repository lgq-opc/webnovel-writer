# 夜间复审报告（编排台夜审 · opencode 侧）

> 派单方：Hermes 编排台 ｜ 执行：opencode（本机）｜ 日期：2026-09-14
> 工作区：`C:\lgq\ai-workspace\projects\zcode-plugins\webnovel-writer.pilot-night-opencode`（worktree）
> 分支：`pilot/night-review-opencode` ｜ 基点：`v8-author` @ `428850e`（开工 `git status` 干净）
> 口径：**只读复审 + 报告**；不改生产代码、不 push、不合入、不动主检出
> 依据：本报告**不复述**以下三份产物的既有结论，只做**增量**

| 基线产物 | 分支 | 提交 | 它已经说了什么（我不重复） |
|---|---|---|---|
| 引用盲区复查 | `pilot/zcode-refscan` | `86266fd` | 增量 1–3 的 19 个已删**模块名**在 297 个 `.py` 中 0 残留（五路技法 + 阳性对照）；已撤**命令名**的活引用清单（hooks/生产面/readme/agents） |
| Phase 2 三增量独立核验 | `pilot/verify-phase2` | `58b2b9e` | 删除未削弱 KEEP 侧（12 成立 / 5 反例 / 2 存疑）；`dual_format_guard._issue` 解耦等价；**其 worktree 下全量 pytest `1 failed / 1546 passed`**，根因 MAX_PATH 260 |
| continuity 拆分（增量 4） | `pilot/continuity-split` | `484f9f7`→`9190301` | `continuity_check` → `continuity_shared` 拆出 4 函数，2 个引用点改指，测试留存 |

---

## 0｜结论先行

本次增量集中在**四类三份产物都没覆盖的面**（它们要么明确排除了 `docs/`，要么结论是 worktree 相对的）：

1. **`docs/` 面从未被证据覆盖**——refscan 的扫描面明确声明「`docs/`（含 `docs/plans/`）未纳入证据面」。本轮在 `docs/` 与仓库根文档里实测到 **4 处口径陈旧/自相矛盾**（§1）。
2. **AGENTS.md 自相矛盾**：同一文件里「MCP ×14」（`:41`）与「MCP 12」（`:51-52`）并存，而实测 **12**（§1.1）。
3. **verify 报告的「1 failed」是 worktree 相对量，不是全局事实**：在**本** worktree（名更长）全量 pytest 为 **`2 failed / 1545 passed`**，多出的一个是 `test_conftest_tmp_cleanup.py::test_rmtree_safely_removes_readonly_tree`，同样是 MAX_PATH 260（§1.5、§3.1）。
4. **退役方案自己的头部状态落后于自己的正文**（`:3` vs `§1.6`）（§1.4）。

**第一手复跑**（本 worktree）：全量 pytest `2 failed / 1545 passed`、覆盖率 `82.65%`（门槛 80 达到）、**EXIT=1**；四校验 **4/4 EXIT=0**。详见 §4。

---

## 1｜现状与文档的不一致清单（Q1）

> 每条给出 `文件:行号` + 原文片段 + 与什么事实不一致。**推断** 显式标注。

### 1.1 AGENTS.md 自相矛盾：MCP 工具面 `×14` vs `12`（实测 12）

- `AGENTS.md:41`（目录树注释）：

  ```
  │   ├── mcp/                ← webnovel MCP server（stdio 只读查询 ×14）+ tests
  ```

- `AGENTS.md:51`（当前状态）：

  ```
  - 当前版本：v8.1.0（作者主权 + 300 章连贯：六域书仓治理 + MCP 12 只读工具 + 13 条命令；...）
  ```

- `AGENTS.md:52`：

  ```
  - MCP 工具面 14 → 12（D-2 乙，2026-09-13）：撤出 `rag_search` ... 与 `context` ...
  ```

- **实测**：`webnovel-writer/mcp/server.py` 的 `TOOLS`（`:192`）实际声明 **12** 个 `name`：
  `webnovel_where / project_status / doctor / setting_read / timeline_check / meter / knowledge / materials_status / materials_assemble / power_check / foreshadow_scan / reader_signals`。
- **不一致**：`:41` 的「×14」是 D-2 乙之前的陈旧值；同一文件 `:51/:52` 已写 12。**结论：AGENTS.md 内部自相矛盾，应以 12 为准。**

### 1.2 `docs/guides/commands.md:3` 双陈旧：版本 `v8.0.0` + 工具面 `14`

- `docs/guides/commands.md:3`：

  ```
  > 口径：v8.0.0（ZCode 插件）。三层命令面：① 8 个 skill（`/webnovel-<name>`）；② 13 条 `/webnovel:<name>` 短名命令（...）；③ 统一 CLI `webnovel.py` 子命令；另有会话自动挂载的 `webnovel` MCP 服务（14 只读工具）。
  ```

- **实测**：`marketplace.json` 与 `webnovel-writer/.zcode-plugin/plugin.json` 均为 `"version": "8.1.0"`；MCP 工具面 **12**（§1.1）。
- **不一致**：该「口径」行同时写错了版本（8.0.0）与工具数（14）；而本文档正是 `README.md`「命令详解」链接的落点。

### 1.3 `README.md` 自相矛盾：正文/表写 `v8.0.0`，徽章/更新表写 `8.1.0`

- `README.md:4`：`[![Version](...version-8.1.0...)]` — **8.1.0**
- `README.md:371`：`| **v8.1.0 (当前)** | 40 项缺口四阶段修复...` — **8.1.0**
- `README.md:11`：`...长篇网文创作插件（v8.0.0「作者主权+300章连贯」...` — **v8.0.0（陈旧）**
- `README.md:23`：`| \`v8-author\` | v8.0.0 · ZCode 插件（MCP 12 只读工具 + 13 条...）| **当前主线**...` — **v8.0.0（陈旧）**
- **不一致**：同一文件里 v8.0.0 与 v8.1.0 并存；`AGENTS.md:51`、`docs/architecture/overview.md:5` 均为 v8.1.0。正文两处未随 8.1.0 发版同步。

### 1.4 退役方案「头部状态」落后于「自身正文」

- `docs/plans/2026-09-10-v6线退役方案.md:3`（头部状态行）：

  ```
  > 状态：[~] **Phase 1 已完成**；**Phase 2 第 1 条（v7-native init）已完成**，其余条目等 §1.5 三分类落定后执行。
  ```

- 同一文件正文：`§1.6` 已记 **增量 1（`:94`）/ 增量 2（`:118`）/ 增量 3（`:155`）均「2026-09-10 已完成」**；`AGENTS.md:60` 亦记「Phase 2 增量 1-3 已完成」。
- **不一致**：头部行仍停在「第 1 条已完成、其余待落定」，读者若只看头部会低估进度。**推断**：该行是 §1.6 书写前所留，未回填。

### 1.5 verify 报告的「1 failed」不是全局结论（worktree 相对）

- `pilot/verify-phase2` @ `58b2b9e` 报告 §2.1：`1 failed, 1546 passed ... EXIT=1`（其 worktree = `...pilot-verify`）。
- **本 worktree 实测**：`2 failed / 1545 passed`（总收集 1547）。第 2 个失败：

  ```
  FAILED webnovel-writer/scripts/tests/test_conftest_tmp_cleanup.py::test_rmtree_safely_removes_readonly_tree
  ```

  失败点 `test_conftest_tmp_cleanup.py:43` `obj.write_bytes(b"\x00")`，路径
  `...\.tmp\pytest\test_rmtree_safely_removes_readonly_tree_<hex>\leak-<hex>\repo\.git\objects\13\<40位sha>`
  **长度 = 263**（> 260）。同一测试在 `pilot-verify` 下同路径为 **255**（< 260，故它那里不失败）。
- **不一致**：两份报告若被当作「全量测试只有 1 个环境失败」的全局事实，会漏掉「失败数随 worktree 名长度增长」这一定性。**详见 §3.1。**

### 1.6 `docs/README.md:40` 把 opencode 09-13 复审的 P1 三项当作现行，未标注其中 P1-2 已被 D-2 乙部分消解

- `docs/README.md:40`：`| 📋 复审报告 | .../opencode/项目复审/2026-09-13-项目复审报告.md | v8.1.0 全项目只读复审（P0 为空；P1 三项：备份漏 v7 域 / MCP 工具面名实落差 / W6 学习闭环未实现）|`
- 该报告 `:44` 的 P1-2 主张「MCP 承诺 14、实际可消费 5」，而当前 `AGENTS.md/README.md` 承诺面已是 **12**、`server.py` 也是 **12**（D-2 乙，2026-09-13），另有 `_V7_UNSUPPORTED`（`webnovel.py:186`）。
- **不一致（轻）**：索引条目仍是「P1 三项」的旧描述，未反映 D-2 乙撤出 `rag_search`/`context` 后的工具面变化。**待确认**：P1-1（备份漏 v7 域）、P1-3（W6）现状见 §5。

### 1.7 交叉确认：三份产物与代码不冲突的部分（正向）

- `docs/README.md` 的相对链接 **0 缺链**（脚本核对 43 条 `./(...)`）；`docs/opencode/` 仅收 `项目复审/2026-09-13-项目复审报告.md`。
- 计数核对（实测）：`skills/` = **8**、`agents/` = **4**、`commands/webnovel/` = **13**、`hooks/` = 5 文件（4 脚本 + `hooks.json`），与 `AGENTS.md:37-40` 一致。
- continuity 拆分**自洽**：`continuity_shared.py` 4 函数逐字迁出；`timeline_view.py:84`、`chapter_outline_validate.py:12` 引用点已改指；`test_continuity_check.py:90` 直导亦改指，并新增 `test_continuity_shared.py`。**未发现漏改引用**（与 explore 子代理的「未落地」说法相反——那是它只看了本 worktree，而拆分在另一分支）。

---

## 2｜最值得做的 5 件事（Q2，按 收益/成本 排序）

| # | 做什么 | 一句话理由 | 落点文件:行 | 成本 |
|---|---|---|---|---|
| 1 | 把 MCP 工具面统一成 **12** | 消除 AGENTS.md 自查即矛盾，避免下一个核对者反复确认 | `AGENTS.md:41`（`×14`→`×12`） | 1 行 |
| 2 | 同步版本号与工具面口径 | `README` 正文/表与 `commands.md` 口径行是**对外承诺面**，写错会让使用者按不存在的功能去找 | `README.md:11`、`README.md:23`（v8.0.0→v8.1.0）；`docs/guides/commands.md:3`（v8.0.0→v8.1.0、14→12） | 3 行 |
| 3 | 给 MAX_PATH 悬崖做**单点加固** | 让失败不再随 worktree 名长度漂移；否则「本地全量」结果不可比 | `webnovel-writer/scripts/tests/test_conftest_tmp_cleanup.py:43`（缩短对象名）；或 `scripts/conftest.py` 的 `tmp_path` 走长路径前缀（`\\?\`） | 小 |
| 4 | 回写退役方案状态（W12） | 头部状态落后于正文，会让「退役进度」被低估；并应把「未同步的 KEEP 面引用」显式登记而非留白 | `docs/plans/2026-09-10-v6线退役方案.md:3`（校正）；`§1.6` 增量 1/2/3 末尾补登记 | 数行 |
| 5 | 收口 3 处**用户可见**的死命令引用 | 三处运行时可达，会把用户/代理引向不存在的命令 | `scripts/data_modules/project_status.py:57`；`hooks/guard_runtime_write.py:134`（并删 `:24` 死常量）；`README.md:260-264` | 中 |

> 说明：#5 的根因清单已由 refscan §5.1/§5.2 与 verify D1/D2/D3 给出，此处只把它排进**执行序**（P1，建议收尾时一并修）。

---

## 3｜风险与坑清单（Q3）

### 3.1 路径长度悬崖是「随 worktree 名增长」的活风险（**本仓实证**）

- worktree 根路径长度实测（`C:\...\projects\zcode-plugins\` 下的目录名）：

  | worktree 目录名 | 名长度 | 同一条 F7 测试的落盘路径长度 | 是否越 260 |
  |---|---|---|---|
  | `webnovel-writer`（主检出） | 15 | 242（**推算**） | 否 |
  | `webnovel-writer.pilot-verify` | 28 | 255（**推算**） | 否 |
  | `webnovel-writer.pilot-split` | 27 | 254（**推算**） | 否 |
  | `webnovel-writer.pilot-refscan` | 29 | 256（**推算**） | 否 |
  | `webnovel-writer.pilot-night-zcode` | 33 | 260（**推算**） | **是**（verify 实测 260 即失败） |
  | **`webnovel-writer.pilot-night-opencode`** | **36** | **263（实测）** | **是** |

  （锚点 = 本 worktree 实测失败路径长 **263**；其余行按同一路径仅换 worktree 目录名所得长度**推算**，因为同一条 `_make_readonly_tree` 的模板固定，唯一变量就是 worktree 名长度。**推断**：任何使该路径 ≥ 260 的后续 worktree 都会触发同一失败。）
- **坑**：这不是「一个坏测试」，而是**一整类**「在 `tmp_path` 下建深层目录树」的测试都会在更长的 worktree 名下滑向 260。下一个建更长 worktree 的人会看到「失败数又多了」而无从解释。
- **反直觉点**：`pilot/night-review-opencode` 与 `pilot/night-review-zcode` **这两个夜审 worktree 恰好是最长的两个**——夜审流程自身最容易踩。

### 3.2 「0 残留」不等于「仓库干净」——因为两份产物都排除了 `docs/`

- refscan §7 明写未覆盖 `docs/`；verify 的 A5/D5 只点了 `README.md` 与 `docs/guides|operations` 的部分行。
- 后果：任何据「0 残留」推断「收口完成」的读者，会漏掉本报告 §1 的 4 处文档面不一致。

### 3.3 CI 绿 / 本地绿 不是一回事（MAX_PATH）

- CI 在 GitHub runner 的**短路径**下跑；本机在**长路径 worktree** 下跑。实测评测：同一份代码，`pilot-verify` 下 1 失败、`pilot-night-opencode` 下 2 失败、主检出下**很可能 0 失败**（verify §5 U-1 未实跑，本单同样未跑主检出）。
- **坑**：把「CI 绿」当成本地可复现的绿，或反过来把本地 `2 failed` 当回归，都会误判。

### 3.4 分支分叉的合并冲突面（增量 4 未合）

- 增量 4（`continuity_shared`）目前**只在** `pilot/continuity-split`；该分支同时改了 `docs/plans/2026-09-10-v6线退役方案.md`（`:51` 的 §1.5 B 行 + 新增 §1.6 增量 4 节）。
- **坑**：若后续把增量 4 合回时**不先 rebase 到 `v8-author` 现行 HEAD**，会在方案文档 §1.5/§1.6 处产生冲突；且合并后**必须同步 `9190301` 这一「回填提交号」提交**，否则方案里会出现两个互指的提交号。
- **推断**：其余 5 个 worktree 各自独立从 `428850e` 分叉，彼此无重叠文件（refscan/verify 只加各一份报告），合并冲突面小；唯一有代码+文档双重改动的是 `continuity-split`。

### 3.5 长路径会让 F7「守卫」本身失效，可能**掩盖真回归**

- `test_conftest_tmp_cleanup.py` 是 F7（tmp 泄漏 + 只读 git 对象 + 长路径）的**回归守卫**。但在长 worktree 下，它**因建不出夹具而失败**（环境），不是**因 rmtree 回归而失败**（代码）。
- **坑**：若把它当噪声忽略，真出回归时这条守卫也发不出正确信号；若把它当回归，又误判。

### 3.6 两处 `docs` 承诺面与实现漂移的**次生**风险

- `docs/guides/commands.md:3` 与 `README.md` 的版本/工具面是**使用者第一眼读到的口径**。D-2 乙（撤 2 个 MCP 工具）改了 `AGENTS.md:51` 与 `README.md:77`，但**未同步** `commands.md:3` 与 `README:11/23`——说明这类「口径行」没有单一事实源、易漏改。**推断**：需要一个「口径行清单」或校验项。

### 3.7 重复劳动面（流程层）

- `pilot/night-review-opencode` 与 `pilot/night-review-zcode` 基于同一基点做同类夜审。若不做分工约定，会重复扫描同一批面。建议下轮按面切分（如一侧专攻 `docs/`、一侧专攻代码面）。

---

## 4｜复跑记录（第一手证据）

### 4.1 环境与基线

```
$ git branch --show-current
pilot/night-review-opencode
$ git log -1 --format="%H %s"
428850e76b13cce2531c8d854ac88f965d3fa1f5 docs(quality): 回填 learn 闭环输入端核验——够用，无缺陷
$ git status --porcelain      # 开工时为空
（空）
```

### 4.2 全量 pytest（本 worktree）

```
命令：$env:PYTHONUTF8=1; python -X utf8 -m pytest -q --no-cov -p no:cacheprovider --tb=no
退出码：EXIT=1
收集总数：1547（--co -q 逐文件计数求和，145 个测试文件）
失败：2

FAILED webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py::test_webnovel_skill_flow_runs_story_contract_context_and_review_pipeline_with_stubbed_vector_model
FAILED webnovel-writer/scripts/tests/test_conftest_tmp_cleanup.py::test_rmtree_safely_removes_readonly_tree
```

带覆盖率的一种跑法（`python -X utf8 -m pytest -q`）末尾原样：

```
TOTAL                                                               22675   3933    83%
Required test coverage of 80% reached. Total coverage: 82.65%
```

- **覆盖率 82.65%**（门槛 80 达到；失败原因是测试而非覆盖率），与 verify 报告同值。
- 第 2 个失败原样（节选）：

  ```
  >  target = _make_readonly_tree(tmp_path / f"leak-{uuid.uuid4().hex}")
  .../test_conftest_tmp_cleanup.py:43: in _make_readonly_tree
      obj.write_bytes(b"\x00")
  E  FileNotFoundError: [Errno 2] No such file or directory: 'C:\...\webnovel-writer.pilot-night-opencode\.tmp\pytest\test_rmtree_safely_removes_readonly_tree_<hex>\leak-<hex>\repo\.git\objects\13\<40位sha>'
  ```
  该路径长度 = **263**。（方法学留痕：PowerShell `>` 默认写 UTF-16，直接读会得 `\x00` 交错；本单用 `subprocess` 捕获或显式解码规避，与 verify §3.5「管道会吃掉输出」同源。）

### 4.3 四校验脚本

```
1) sync_plugin_version --check   →  Versions are in sync: 8.1.0            rc=0
2) validate_release_notes        →  OK release notes / version: 8.1.0      rc=0
3) validate_plugin_package       →  OK plugin package / errors:0 warnings:0 rc=0
4) validate_reference_wiring     →  OK reference wiring: assets=63 consumers=53 drift=0 rc=0
```

**4/4 EXIT=0**。`drift=0` 与 `docs/reports/2026-09-13-会话交接...` 记录一致。

### 4.4 数量与口径实测（用于 §1 对账）

| 项 | 实测 | 出处 |
|---|---|---|
| skills | 8 | `webnovel-writer/skills/` 目录数 |
| agents | 4 | `webnovel-writer/agents/` 文件数 |
| commands | 13 | `webnovel-writer/commands/webnovel/` 文件数 |
| hooks | 5（4 脚本 + `hooks.json`） | `webnovel-writer/hooks/` |
| MCP 工具 | **12** | `webnovel-writer/mcp/server.py:192` `TOOLS` |
| 版本 | **8.1.0** | `marketplace.json`、`webnovel-writer/.zcode-plugin/plugin.json` |
| `_V7_UNSUPPORTED` | 存在（`webnovel.py:186`） | 当前值需按 D-2 乙复核（§5） |

---

## 5｜待确认（本次未取得充分证据，**不猜测**）

| # | 待确认项 | 为何未确认 |
|---|---|---|
| U-1 | 主检出（`...\webnovel-writer`，短路径）下全量 pytest 是否 **0 failed** | 派单禁止动主检出，未实跑；本单只证明「本 worktree 2 failed、pilot-verify 1 failed」，未证主检出 0 |
| U-2 | `pilot/night-review-zcode` 的落盘路径是否真越 260（表中 261 为**推算**） | 未在其 worktree 实跑；按同一夹具路径 + 目录名长度推算 |
| U-3 | `docs/opencode/2026-09-13-项目复审报告.md` 的 P1-1（备份漏 v7 域）/ P1-3（W6 学习闭环）现状 | 本单未逐条复核该报告的三项 P1 是否已闭环；只确认 P1-2 相关工具面已变 12 |
| U-4 | `_V7_UNSUPPORTED` 当前集合（是否仍含 `knowledge`，是否已随 D-2 乙改） | 只确认符号存在（`webnovel.py:186`），未读取集合内容 |
| U-5 | CI（GitHub Actions 双平台）实跑结果 | 派单禁 push，触发不了 CI |
| U-6 | 增量 4（`continuity_shared`）合回时的实际冲突面 | 未做试合并；§3.4 为**推断** |

---

## 6｜交付自检

| 要求 | 状态 |
|---|---|
| 报告落于 `docs/opencode/2026-09-14-夜间复审/report.md`（本 worktree） | ✅ |
| 围绕三问（不一致 / 最值得做 5 件 / 风险与坑）给可执行结论 | ✅ §1 §2 §3 |
| 每条给证据（`文件:行号` 或 命令+输出片段） | ✅ |
| 推断标注「推断」、不确定进「待确认」 | ✅ §1.4/§3.1/§3.4 标推断；§5 共 6 项 |
| 做增量（只说三份产物没说的 / 与它们不一致的） | ✅ §0 先列基线覆盖，§1 全部落在 `docs/` 面与 worktree 相对结论上 |
| 不 push / 不合入 / 不改生产代码 / 不动主检出 | ✅ 仅新增本报告文件 |
