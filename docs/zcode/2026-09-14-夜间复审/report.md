# 夜间复审报告（编排台夜审 · ZCode 侧）

> 任务书：`C:\lgq\a-hermes-space\.tmp\night-brief-zcode.md`
> 派单方：Hermes 编排台 ｜ 执行：ZCode 会话 ｜ 日期：2026-09-14（夜）
> 工作区：`C:\lgq\ai-workspace\projects\zcode-plugins\webnovel-writer.pilot-night-zcode`（worktree）
> 分支：`pilot/night-review-zcode`（自 `v8-author@428850e` 检出；开工核对 `git branch --show-current` ✓、工作树干净 ✓）
> 口径：**只读复审 + 本报告**；不改生产代码、不 push、不合入、不动主检出。

## 0 范围与增量声明

**本报告做增量，不重复今日已有三份产物**（均已通读原文）：

| 产物 | 分支 @ 提交 | 已覆盖（本报告不重复展开，仅引用） |
|---|---|---|
| 引用盲区复查 | `pilot/zcode-refscan` @ `86266fd` | 19 个已删模块名 0 残留（五路技法+阳性对照）；附带发现 hooks 死常量 `ALLOWED_RUNTIME_MARKERS`、README:260-264 已删命令表、`agents/data-agent.md` v6 词汇、learn 技能与 reference 索引的 `project_memory.json` 矛盾等 |
| Phase 2 三增量独立核验 | `pilot/verify-phase2` @ `58b2b9e` | KEEP 侧未削弱（131/131 可导入、`_issue` 等价、doctor 面完好）；死引用 P1/P2 清单（`project_status.py:57`、guard deny 文案、`state_manager.py:1485`、README/commands.md/operations.md）；worktree 下 1 failed 归因 MAX_PATH 260；BOM/管道两扫描坑 |
| continuity 拆分 | `pilot/continuity-split` @ `9190301`（任务书写的 `484f9f7` 后又前进一提交：提交号已回填） | §1.5 B 类第 1 条拆出 `continuity_shared.py`，全量 1550 passed |

复审基线 = 本 worktree（`428850e`，即 v8-author HEAD，**不含**上述三个试点分支的改动）。
本单自查口径：每条给证据（文件:行号 或 命令+输出）；推断标注「推断」；不确定进 §4 待确认。

---

## 1 问题一：现状与文档的不一致清单（增量）

### I-1 MCP 工具数「14」残留三处，与已落地的 14→12 收缩不同步

D-2 乙（2026-09-13）把 MCP 工具面 14 → 12（撤 `rag_search`、`context`），代码已落地、`README.md:77` 已同步为「12 个只读工具」并附差异说明。但以下三处仍写 14：

| 位置 | 原文 | 证据 |
|---|---|---|
| `AGENTS.md:41` | 目录树「`mcp/` ← webnovel MCP server（stdio 只读查询 **×14**）+ tests」 | 与同文件 `AGENTS.md:52`「MCP 工具面 14 → 12」**自相矛盾**——同一份文件一页纸内两个数 |
| `docs/architecture/overview.md:13` | 「L6 会话编排层 …MCP(**14 只读**)…」 | 活文档（非历史报告） |
| `docs/architecture/overview.md:59` | 「MCP server **×14 只读工具**」 | 同上 |
| `docs/guides/commands.md:3` | 「会话自动挂载的 webnovel MCP 服务（**14 只读工具**）」 | 该文件另有已删命令残留（refscan/verify 已列） |

实测（`webnovel-writer/mcp/server.py:192-306` 的 `TOOLS` 列表）：恰 **12** 个——where / project_status / doctor / setting_read / timeline_check / meter / knowledge / materials_status / materials_assemble / power_check / foreshadow_scan / reader_signals，无 `rag_search`、无 `context`。

> 对照组证明这是「收口做了一半」而非「代码未落地」：README:77 的 12 名清单与 server.py 逐一对应。

### I-2 marketplace.json 双位置已漂移，且校验器对漂移不设防

`AGENTS.md:34` 约定「marketplace.json 双位置：根 + `.claude-plugin/`」。实测两份**内容不等**：

```text
$ python -X utf8 -c "…深度比对两份 JSON…"
VALUE DIFF at .plugins[0].homepage :
  'https://github.com/lgq-opc/webnovel-writer'      ← 根 marketplace.json
  vs 'https://github.com/lingfengQAQ/webnovel-writer' ← .claude-plugin/marketplace.json
（其余字段全等；两份均 version 8.1.0）
```

且 `validate_plugin_package.py:83` `MARKETPLACE_RELATIVE_PATHS = ("marketplace.json", ".claude-plugin/marketplace.json")`、`:102-103` `_find_marketplace`（注释原文：「双位置：仓库根 marketplace.json 优先，.claude-plugin/marketplace.json 兼容」）——**只读先找到的那份，从不比对两份一致性**。本单实测四校验全绿（见 §5.1）的同时两份 marketplace 悄然不同：「双位置」约定没有任何机器守护。

### I-3 v6 退役方案文档的状态行滞后于自身正文

`docs/plans/2026-09-10-v6线退役方案.md`：

- `:3` 状态行只认「**Phase 2 第 1 条（v7-native init）已完成**，其余条目等 §1.5 三分类落定后执行」；
- 但同一文档 `§1.6` 已记录**增量 1/2/3 全部「2026-09-10 已完成」**（`:94`/`:118`/`:155` 三个小节标题），且 `AGENTS.md:60` 的对外口径是「Phase 1 与 Phase 2 增量 1-3 已完成」。
- 另 `:214`（§3 Phase 2 条目 4「doctor 砍 v6 合同树检查组；invariant 六条变五条」）与 `:144-151`「contract_migrations **暂缓，不随本轮删**，建议合并到 Phase 3」的裁决**方向相反**，条目 4 未标 `[superseded]`——违反本仓 AGENTS.md「文档状态统一使用 [superseded]」的约定。

（注：`pilot/continuity-split` 分支已修订 `:3` 状态行，但未合入 v8-author；本基线上它仍是滞后状态。）

### I-4 AGENTS.md 对 SessionStart hook 的描述与实现不符

`AGENTS.md:40`：「hooks/ ← 4 个 hook 脚本 + hooks.json（…；**SessionStart 会写 .webnovel/ journal**）」。

实测 `webnovel-writer/hooks/session_start.py:58-72`：SessionStart 只**串行跑两个 CLI 并把输出 print 注入会话**（`author-sync --format text` + `project-status --format summary`），自身不写任何文件；`grep -rn "journal" webnovel-writer/hooks/` 零命中。journal 实体是 v7 作者域的 `作者/journal.jsonl`（`data_modules/author_journal.py:3`），路径域也不是 `.webnovel/`（那是 v6 运行时目录）。就算把「author-sync 留账可能间接 append journal」算作善意解读，`.webnovel/` 这个路径也是错的。

### I-5 「全量 pytest 绿」是路径敏感的陈述，文档未记载该前提

AGENTS.md 给出的全量命令（`$env:PYTHONUTF8=1; python -X utf8 -m pytest`）在本 worktree 实测**不是全绿**：

```text
$ python -X utf8 -m pytest "webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py::test_webnovel_skill_flow_runs_story_contract_context_and_review_pipeline_with_stubbed_vector_model" -p no:cacheprovider --no-cov -q
FAILED webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py::test_webnovel_skill_flow_...
PYTEST_EXIT=1
E  FileNotFoundError: …webnovel-writer.pilot-night-zcode\.tmp\pytest\…\book\.claude\references\genre-profiles.md
```

verify 报告把这归因为「worktree 路径比原仓长 13 字符 + MAX_PATH 260」。本单补上它没点到的那一层：**tmp 落在仓内不是运行者的选择，是 `webnovel-writer/scripts/conftest.py` 强制的**——`_tmp_root()`（`:147-150`）返回 `<仓库根>/.tmp/pytest`，`_install_safe_tempfile()`（`:171-178`）把 `TMP/TEMP/TMPDIR`、`tempfile.tempdir`、`tempfile.mkdtemp`、`tempfile.TemporaryDirectory` 全部指到那里。因此：

- **任何比主检出路径长的检出/worktree，按文档命令跑全量必挂这条测试**，无需任何人传错参数；
- 失败的 fixture 文件随路径长度**漂移**：pilot-verify 挂 `reading-power-taxonomy.md`（verify 实测），本 worktree（更长 5 字符）挂更早一步的 `genre-profiles.md`（本单实测）——长度模型与两处实测精确吻合（见 §5.2 表）。

### I-6 （现状登记，非缺陷）continuity 拆分只在试点分支

本基线上 `data_modules/continuity_shared.py` 不存在、`timeline_view.py`/`chapter_outline_validate.py` 仍从 `continuity_check.py` 导入共享函数——§1.5 B 类第 1 条在 v8-author 上**未合入**。这是试点流程的预期状态（不合入是纪律），登记为「现状与 pilot 分支方案的差量」，避免下一个人在主线上找不到 `continuity_shared`。

---

## 2 问题二：最值得做的 5 件事（按收益/成本排序）

| # | 事项 | 一句话理由 | 落点 |
|---|---|---|---|
| 1 | **conftest 临时根与长路径解耦**：`_tmp_root()` 改用短根（如 `%TEMP%` 下短名目录）或 `\\?\` 前缀 | 一处几行的改动，永久消灭「长路径检出必挂 1 测试」这一整类环境性失败，让「全量绿」在任何 worktree 可复现——本单证明该失败是 conftest 强制行为而非误用（I-5） | `webnovel-writer/scripts/conftest.py:147-150`（必要时连带 `:171-178`） |
| 2 | **已删命令的用户可见文案收口**（前置两单已点名清单，本单补排序理由：SessionStart 每次开会话都跑 `project-status`，`READY_TO_COMMIT` 阶段的 next_action 当场把代理引向不存在的命令——是**每日可达面最大**的一处） | 三处运行时可达（deny 文案 / next_action / state 错误建议）+ 文档表，全部指向 `rc=2 invalid choice` 的死命令 | `hooks/guard_runtime_write.py:96-100,117,134`、`data_modules/project_status.py:57`、`state_manager.py:1485`、`README.md:260-264`、`docs/guides/commands.md`、`docs/operations/operations.md`（清单见 refscan §5、verify §4.2，不重复） |
| 3 | **MCP「14」残留三处清零 + commands.md 由 CLI 实况生成**：手改三处之外，更耐久的做法是从 `webnovel.py` argparse 提取子命令/工具表生成 `commands.md` 的表格，并在 `validate_plugin_package` 里加 drift 校验 | 承诺面对齐 D-2 乙已落地的 12 工具；机器生成+校验让「文档写 14、代码是 12」这类漂移从此被 CI 拦住（I-1 的根因是**没有防漂机制**，不是某次手滑） | `AGENTS.md:41`、`docs/architecture/overview.md:13,59`、`docs/guides/commands.md:3`、`scripts/validate_plugin_package.py`（新增校验） |
| 4 | **marketplace.json 双位置一致性纳入校验**：两份并存时必须 JSON 相等，不等即 error；顺带把 `.claude-plugin/` 副本的 homepage 统一为 `lgq-opc` | 把 AGENTS.md 的「双位置」约定从口头变成机器守护——本单实测它已漂移且四校验照样全绿（I-2）；修复成本 = 校验函数十几行 + 一行 homepage | `scripts/validate_plugin_package.py:83,102-145`、`.claude-plugin/marketplace.json`（homepage 一行） |
| 5 | **本地资产收口**：push 主检出的 `master`（`origin/master..master` 领先 1：`10db9f9` docs 提交）；四个 pilot 分支建远端备份，或约定「试点验收即合入、不合入即删除」 | 全部 6 个 worktree 的产出（含今晚三份试点报告）只存在于本机一块盘上，机器故障即清零；成本是一次 push + 一行约定 | git 远端操作；约定落 `AGENTS.md` 或退役方案 §5 执行纪律 |

> 排序逻辑：#1 改动最小、消除的是「测试证据本身不可信」这个元问题（本仓纪律以测试为完成证据）；#2/#3/#4 是文档-代码收口（#2 已有现成清单，执行即可）；#5 是资产安全，成本最低但需要人拍板 push 策略。

---

## 3 问题三：风险与坑清单（含「看起来没问题、但下一个人会踩」）

- **R-1 主检出仓的绿线余量只有 8 个字符**（推断·计算值）：同一条测试在主检出路径下 `reading-power-taxonomy.md` 全长 **252**（悬崖 260，§5.2 表）。更长的测试名、把仓库挪深一层目录、用户目录改名，任何一项都会让**主线**挂同一条测试——现在没事只因为恰好站在悬崖内侧。按纪律本单未在主检出实跑验证（见 U-1）。
- **R-2 conftest 的 tempfile 猴补会传染子进程**（推断）：`_install_safe_tempfile()` 改的是 `TMP/TEMP/TMPDIR` 环境变量 + `tempfile` 模块全局（`conftest.py:171-178`），测试内启动的子进程会继承这些 env——任何依赖临时目录的子进程工具都被拉进「仓内 .tmp/pytest」深路径。机制上成立，未构造实验（不做断言）。
- **R-3 长路径失败的「漂移性」会误导排障**：同一个测试在不同长度 worktree 挂在**不同 fixture 文件**（verify 仓挂 `reading-power-taxonomy.md`、本仓挂 `genre-profiles.md`，两处实测）。看到 `FileNotFoundError` 换了个文件名，很容易误判成「代码回归」而非同一环境问题。建议：提交信息/报告里的「环境性失败」必须附 worktree 全路径。
- **R-4 hooks 超时预算内外矛盾**（待确认 U-2）：`hooks.json` 给 SessionStart 的 `timeout` 是 **5s**，但 `session_start.py:28` 的 `_run_webnovel` 默认 4s、`:59` 给 `author-sync` 显式 **6s**——内部预算超过外层限额，超时行为（截断？放行？静默？）未实测。Windows 冷启动下两个 CLI 串行 5s 并不宽裕。
- **R-5 `.claude-plugin/marketplace.json` 的 homepage 指上游**：顺着链接找源码/开 issue 会落在本仓 2026-09 之前就已分叉的 `lingfengQAQ/webnovel-writer`（AGENTS.md:56 明言「上游 v7/v8 路线与本仓无关」）——误导面小但方向完全错。
- **R-6 CI 路径过滤不含 `docs/**`**（`.github/workflows/plugin-tests.yml:8-25`）：纯文档改动不触发 CI，而四校验也不校验 md 文档一致性——I-1/I-3 这类文档漂移既没人肉拦截也没有机器拦截；同时 pilot 分支不 push ⇒ CI 永不跑，「四校验全绿」在试点语境下只能是本地声明。
- **R-7 已知项不重复**（引用前置单）：guard 白名单/死常量、13 个 BOM 文件的扫描器坑、PowerShell 管道吞输出、dashboard `/api/story-events` 读侧恒空、`.tmp/` 不自动清理（`7bc7ef8` 已记录边界说明）。

---

## 4 待确认

| # | 项 | 为什么没确认 |
|---|---|---|
| U-1 | 主检出仓（`…\webnovel-writer`）全量 pytest 是否全绿 | 纪律禁动主检出；计算推断绿（最长 fixture 252 < 260，余量 8 字符），未实跑 |
| U-2 | ZCode hook 超时的确切行为，及 `hooks.json` 5s vs `session_start.py` 内部 6s 预算的真实交互 | 需要构造慢 CLI + 观察 ZCode 客户端处理，本单未做 |
| U-3 | 装机链路实际消费哪份 marketplace.json | 推断根优先（`validate_plugin_package.py:102-103` 如此实现），ZCode 客户端侧未实测 |
| U-4 | 与 opencode 侧夜审（worktree `webnovel-writer.pilot-night-opencode`，分支 `pilot/night-review-opencode`）的交叉比对 | 并行会话的未提交产物，本单不读取；留给编排台比对 |
| U-5 | CI（GitHub Actions）实跑结果 | 不 push 触发不了（与 verify 报告 U-5 同因） |

---

## 5 复跑命令（验收用）

### 5.1 四校验（本单实测全绿）

```bash
cd "C:\lgq\ai-workspace\projects\zcode-plugins\webnovel-writer.pilot-night-zcode"
export PYTHONUTF8=1
python -X utf8 webnovel-writer/scripts/sync_plugin_version.py --check   # Versions are in sync: 8.1.0  EXIT=0
python -X utf8 webnovel-writer/scripts/validate_release_notes.py        # OK release notes / 8.1.0      EXIT=0
python -X utf8 webnovel-writer/scripts/validate_plugin_package.py       # OK plugin package 0/0         EXIT=0
python -X utf8 webnovel-writer/scripts/validate_reference_wiring.py     # assets=63 consumers=53 drift=0 EXIT=0
```

### 5.2 MAX_PATH 长度模型（与两处实测精确吻合）

```bash
python -X utf8 - <<'PY'
bases = {
 'main(主检出)': r'C:\lgq\ai-workspace\projects\zcode-plugins\webnovel-writer',
 'pilot-verify': r'C:\lgq\ai-workspace\projects\zcode-plugins\webnovel-writer.pilot-verify',
 'pilot-night-zcode': r'C:\lgq\ai-workspace\projects\zcode-plugins\webnovel-writer.pilot-night-zcode',
}
mid = (r'\.tmp\pytest\test_webnovel_skill_flow_runs_story_contract_context_and_review_pipeline_with_stubbed_vector_model_'
       + 'h'*32 + chr(92) + r'book' + chr(92) + r'.claude' + chr(92) + r'references' + chr(92))
for k, b in bases.items():
    p = len(b) + len(mid)
    print(f'{k:18s} prefix={p}  genre={p+17}  reading-power={p+25}  (悬崖=260)')
PY
# 期望输出（实测）：
#   main(主检出)      prefix=227  genre=244  reading-power=252   → 双双通过（余量 8）
#   pilot-verify      prefix=240  genre=257  reading-power=265   → verify 报告实测 257 OK / 265 FAIL，与本表一致
#   pilot-night-zcode prefix=245  genre=262  reading-power=270   → 本单实测 genre 262 FAIL（更早一步）
```

### 5.3 单测复跑（I-5 证据）

```bash
python -X utf8 -m pytest "webnovel-writer/scripts/data_modules/tests/test_webnovel_unified_cli.py::test_webnovel_skill_flow_runs_story_contract_context_and_review_pipeline_with_stubbed_vector_model" -p no:cacheprovider --no-cov -q
# 本 worktree 期望：FAILED …FileNotFoundError: …\book\.claude\references\genre-profiles.md，PYTEST_EXIT=1
```

### 5.4 marketplace 双位置比对（I-2 证据）

```bash
python -X utf8 -c "import json; a=json.load(open('marketplace.json',encoding='utf-8')); b=json.load(open('.claude-plugin/marketplace.json',encoding='utf-8')); print(a['plugins'][0]['homepage']); print(b['plugins'][0]['homepage']); print('equal:', a==b)"
# 期望：lgq-opc… / lingfengQAQ… / equal: False
```

---

## 6 边界与未覆盖项

- **只读**：本 worktree 唯一新增文件即本报告；未改任何生产代码/测试/文档原文；未 push、未合入、未触主检出与其他 worktree。
- 未覆盖（申明）：CI 实跑（U-5）、主检出实跑（U-1）、opencode 并行夜审产物（U-4）、运行期书仓数据内容（与 refscan 同边界）。
- 本报告引用的前置产物结论以其原文为准；若编排台后续合入 `pilot/continuity-split`，I-3 中「:3 状态行滞后」一项将被该分支部分修复，I-6 自动消解。
