# R13 排序能力是否搬进 v7 pack（设计单）

> 状态：[x] 设计交付（试点分支 `pilot/r13-pack` @ `5fe1026`，2026-09-15）＋ **0915 评审必改已返工**（2026-09-18；编排台评审 §2.5 三条行号勘误）
> 派单方：Hermes 编排台（改派 ZCode / GLM-5.3-Flash）｜ 来源：todohub `t-20260913-b673`
> 基线：任务书起草时写 `v8-author @ 676fc5c`；**现场核对 HEAD = `578b4bf`**（其后又合入 pilot/dataagent-fix、pilot/memcontract 两单，不影响本单对象模块）
> 结论预告：**推荐案 B「冻结、随 context_manager 链处置」，不搬进 pack**。链的去留已由 2026-09-18 退役方案 §3.1 第 4 条裁定；同日技能改指 `v7-write pack` 后已级联删除 `context_ranker` / `context_manager` / `extract-context`。理由与其余未决见 §5/§6。

## 1｜R13 是什么、落在哪里

R13/W8/F-13 同源：排序信号弱且「奖励冗长」。2026-09-12 已实现（提交 `01fe438`），改动分落两处：

- **改动 1**：`context_ranker.py` 的 `_length_score`（len/1200，奖励长摘要）替换为 `_density_score`（关键词组命中数 × 长度 log 稀释，`context_ranker.py:272-292`；关键词组表 `:27-34`）；
- **改动 2**：`memory/orchestrator.py` 的 `_filter_relevant`（定义 `:103`）由整串子串包含改为「实体别名展开 + 词元重合度」（匹配子方法 `:122-168`）。

两处**互不 import**。改动 2 不在「搬 pack」的讨论范围（它属 memory/ 包，且该包归退役方案 §1.5 C 类「待判定」）；本单只裁决改动 1 所在的 `context_ranker` 模块。

## 2｜调用图（生产代码逐处 文件:行号）

全仓 grep（含 py/md/json/yaml/js，排 `.git`）后，`context_ranker` 的**非文档引用**全景如下。

### 2.1 context_ranker 的生产引用者（共 5 处，全部在 data_modules 内）

| # | 引用点 | 内容 |
|---|---|---|
| 1 | `webnovel-writer/scripts/data_modules/context_manager.py:30` | `from .context_ranker import ContextRanker`（唯一生产 import） |
| 2 | `webnovel-writer/scripts/data_modules/context_manager.py:104` | `__init__` 中 `self.context_ranker = ContextRanker(self.config)` |
| 3 | `webnovel-writer/scripts/data_modules/context_manager.py:119-120` | `build_context()` 内 `if context_ranker_enabled: pack = self.context_ranker.rank_pack(pack, chapter)`——**唯一能力调用点**（默认开，`config.py:276` 默认 True） |
| 4 | `webnovel-writer/scripts/data_modules/config.py:276-288` | 6 个配置旋钮：`context_ranker_enabled / recency_weight(0.7) / frequency_weight(0.3) / hook_bonus(0.2) / alert_critical_keywords / debug` |
| 5 | `webnovel-writer/scripts/data_modules/__init__.py:47,86` | `__all__` + `_LAZY_EXPORTS` 导出表 |

### 2.2 上游链（谁触发 rank_pack）

```
data_modules/webnovel.py CLI「context」子命令（data_modules/webnovel.py:1327 定义，:1502 转发 _run_data_module("context_manager")）
  └─→ extract_chapter_context.py:294-301（_load_contract_context 内实例化 ContextManager；
        build_chapter_context_payload 在 :327，本身不含直接实例化）
        └─→ context_manager.build_context()（context_manager.py:108-120）
              ├─→ _build_pack()（:208 起，v6 state.json/SQLite 数据面装配）
              ├─→ ContextRanker.rank_pack()（:120，排序+预算截断）   ← R13 改动 1 的作用点
              └─→ [可选] MemoryOrchestrator（:211-221，context_use_memory_orchestrator
                    默认 False＝config.py:341；R13 改动 2 在 _filter_relevant:103）
```

即整条链是 **v6 装配链**：入口是 v6 CLI `context` / `extract-context`，数据面是 v6 的 state.json + SQLite 投影。

### 2.3 明确无引用的面（反证）

- **v7 写链**：`v7_write.py`、`v7_cache.py`、`migrate_v6_to_v7.py` 中 `context_ranker`/`ContextRanker` **0 命中**。
- **MCP**：`mcp/server.py` 12 个工具（`:194-301`：where/project_status/doctor/setting_read/timeline_check/meter/knowledge/materials_status/materials_assemble/power_check/foreshadow_scan/reader_signals）**不消费 pack，0 命中**。
- **插件面**：skills / agents / commands / hooks **0 命中**。
- **测试锚**（冻结态下继续服役的守护）：`test_context_ranker.py`（11 用例，其中 `:23` R13/F-13「长而空不得压过短而实」）；`test_context_manager.py:969`（S2/C2 大 section 截断，直连 `apply_budget`）。

## 3｜活性判定

**结论：不是独立死代码，但也不是 v7 意义上的活代码——「冻结链上的活组件」：它有唯一生产调用方 `context_manager`，而该调用方所在的整条装配链是 v6 侧（v6 冻结口径下仅维护），v7 写链不经过它。**

证据命令与输出（2026-09-15，基线 `578b4bf`，可复跑）：

```console
$ grep -rn "context_ranker\|ContextRanker" --include="*.py" \
    webnovel-writer/scripts/ webnovel-writer/mcp/ webnovel-writer/hooks/ \
    webnovel-writer/agents/ webnovel-writer/skills/ | grep -vi test
webnovel-writer/scripts/data_modules/config.py:276-288        ← 6 个旋钮（仅配置声明）
webnovel-writer/scripts/data_modules/context_manager.py:30    ← import
webnovel-writer/scripts/data_modules/context_manager.py:104   ← 实例化
webnovel-writer/scripts/data_modules/context_manager.py:119-120 ← rank_pack 调用
webnovel-writer/scripts/data_modules/context_ranker.py:…      ← 自身
webnovel-writer/scripts/data_modules/__init__.py:47,86        ← 导出表
（mcp/hooks/agents/skills 三目录 0 命中）

$ grep -rln "context_ranker\|ContextRanker" --include="*.py" webnovel-writer/scripts/data_modules/tests/
test_context_manager.py
test_context_ranker.py

$ PYTHONUTF8=1 py -3.13 -X utf8 -m pytest data_modules/tests/test_context_ranker.py \
    data_modules/tests/test_memory_orchestrator.py \
    "data_modules/tests/test_context_manager.py::test_ranker_caps_big_section_texts" -q --no-cov
....................  [100%]   ← 20 passed（R13 锚定用例当前全绿）
```

两点必要澄清：

1. **退役方案 §1.5 A 表（`docs/plans/2026-09-10-v6线退役方案.md:49`）写「`context_ranker` 无生产引用（仅测试）」——这是「级联删除」口径**：它的唯一生产引用者 `context_manager` 自己也是 A 类（引用者 `extract_chapter_context.py`）。字面上 `context_manager.py:30` 的 import 是存在的，建议该行勘误为「唯一生产引用者为 context_manager（同 A 类，级联处置）」（文档改动，见 §6 未决 4）。
2. **冻结后仍有维护动作的先例**：`git log -- context_ranker.py` 显示 `01fe438`（2026-09-12，W8/R13 改动 1）落在 2026-09-10 冻结裁决之后。本单不评判该先例，但它说明「冻结 ≠ 无人再碰」，处置决策宜趁早明确，避免继续在该文件上投入。

## 4｜v7 pack 现状：有没有等价的排序/选取能力？

**没有条目级相关性排序。** `build_context_pack`（`v7_write.py:313`）的选取是三种静态机制：

| 机制 | 落点 | 行为 |
|---|---|---|
| 固定近因窗 | `v7_write.py:325-330` | 摘要只取**前 3 章**、每章截 500 字符、按章号升序——不看内容重要性（`:341-345` 是 `prev_chapter_tail`，不是本机制） |
| 决策卡驱动 | `v7_write.py:332-336` | `entities` 完全跟随决策卡实体表顺序，`find_entity`（v7_cache）查名册补齐——无排序（`:347-350` 是 `book_meta`） |
| 静态配额裁剪 | `v7_write.py:29-56, 387-408` | 每节配额 `V7_SECTION_QUOTAS`（`apply_quota` 截断，`context_budget.py:130`）→ 超总预算按 `V7_DROP_ORDER` **整段丢弃**（PROTECTED 四节只截不丢）→ 尾部硬截。丢弃粒度是「整个 section」，不是「section 内低分条目」 |

与 ranker 的能力逐项对照：

| ContextRanker 能力 | v7 pack 是否有等价物 |
|---|---|
| 摘要 recency×密度打分排序（`_combine_score`+`_density_score`，`:252-292`） | ❌（v7 是固定 3 章窗，无打分） |
| hook bonus 加权（`:171,184`） | ❌（v7 有钩子数据面——正文 front matter 钩子类型/强度，`v7_cache._iter_reading_power`——但不进 pack 排序） |
| 出场角色按 recency+频率排序（`rank_appearances`，`:193-207`） | ❌（v7 无出场统计 section；entities 跟决策卡走） |
| story_skeleton / alerts 严重度排序（`:209-250`） | ❌（v7 无这两个 section；歧义警告是 v6 state.json 概念） |
| 条目级预算截断（`apply_budget` P1-4，`:79-159`） | ≈ 有（`apply_quota` 节级截断，但粒度与策略不同，见 §5 案 A 第 5 条） |

## 5｜两案对比

### 案 A「搬进 v7 pack」

| 维度 | 内容 |
|---|---|
| **接口适配** | `rank_pack` 消费 v6 pack 形态（`core.recent_summaries: [{"chapter","summary"}]` 列表等），v7 pack 是 `sections: dict` → 一次性渲染 markdown（`_render_pack_markdown`，`v7_write.py:422`）。**直接调用不可行**，需新适配层（如 `v7_pack_rank.py`）或先把打分核心（`_recency_score`/`_density_score`/`_combine_score`，约 60 行纯函数）抽出共享 |
| **可搬能力** | 只有「摘要打分」落地条件成熟（替代固定窗或支撑「窗 N 章择优 top-k」）；hook bonus 需先把钩子 front matter 数据面接进 pack；出场频率排序需先建 v7 出场统计（数据面不存在）；alerts 排序无对应 section（不适用） |
| **配置面** | 6 个 `context_ranker_*` 旋钮需进入 v7 书仓配置（book.yaml 新键或沿用全局 config），牵动 settings_digest / book-init 播种面 |
| **预算体系冲突** | ranker 的 `apply_budget`（条目级、字符口径、`context_compact_*` 四旋钮）与 v7 的 `apply_quota`（节级、estimate_tokens 口径）**职责重叠且口径不同**——全搬会成双预算体系，只搬排序则预算留在原处，两套并存 |
| **测试影响** | `test_context_ranker.py` 11 用例中排序类 5 个可改造为适配层测试；budget 类 6 个（P1-4）不建议随迁；`test_context_manager.py:969` 留守 v6 侧不动 |
| **成本估算** | 适配层 + 配置面 + 测试 + `pack` stats 扩展 + smoke_v7_newbook 回归 ≈ **1–2 个会话**；且「窗 3 章 → 窗 N 择优」本身是独立特性（要先扩摘要数据面），不是纯搬迁 |
| **验证** | 新增 `test_v7_pack_rank.py` 全绿；`py -3.13 -X utf8 scripts/v7_write.py pack --repo <v7书仓> --chapter N` 的 stats 出现 ranker 字段且顺序变化符合预期；`smoke_v7_newbook.py` 全链绿；全量 pytest + 五校验绿 |

### 案 B「冻结 / 删除」

| 维度 | 内容 |
|---|---|
| **与 v6 冻结口径的关系** | 退役方案 §1.5 已把 `context_ranker` 归 **A 类（v6 独占、级联）**，且 Phase 2 增量 1–4 未动它——它的命运**绑定在 context_manager 链上**（链尾是 `extract-context` CLI），而读侧重建整体是 **Phase 3（待 Human 决策）**。冻结 = 维持现状（锚定测试继续绿、零动作）；删除 = 等 Phase 3 裁决链的去留时级联，不单独立案 |
| **对 KEEP 侧行为的影响** | **零**——v7 写链 / v8 治理 / MCP 12 工具 / 插件面均无引用（§2.3 证据）。冻结期间唯一成本是该文件仍出现在 grep 结果里（心智负担，已由本单 + 勘误建议缓解） |
| **W8 资产沉没问题** | 若将来删除：改动 1（`_density_score`）随文件沉没；改动 2（orchestrator）不在本文件，随 memory/ 包的独立裁决走。R13 的测试用例与关键词组表在本档已存档引用，将来 v7 若做条目级排序可按单移植，不构成不可逆损失 |
| **删除前置条件**（未来执行时） | ① Phase 3 裁决砍 `extract-context`/`context` CLI；② `extract_chapter_context.py`、`context_manager.py` 级联退役；③ 同批清理 `__init__.py:47,86` 导出、`config.py:276-288` 六旋钮、`test_context_ranker.py` 11 用例与 `test_context_manager.py` 相关用例 |
| **验证** | 冻结态：复跑 §3 的 grep + pytest 命令，输出与本档一致即维持冻结有效。删除执行后断言：`grep -rn "context_ranker\|ContextRanker" --include="*.py" webnovel-writer/ | grep -v test` → 0 命中；全量 pytest + 五校验绿 |

## 6｜推荐与未决问题

**推荐：案 B（冻结、随链处置），不搬。** 理由：

1. **没有消费方**：v7 pack、MCP、插件面零引用；「搬」在当前没有需求拉力，属于为搬而搬。
2. **两套预算模型不兼容**：v7 的节配额 + 整段 DROP 是刻意的薄设计（spec §4.2 逐字落地过），塞入条级打分/截断要么重写 `apply_quota`、要么双轨并存，都放大 v7 维护面。
3. **数据面太薄，打分无处施展**：v7 摘要窗只有 3 章 × 500 字符，排序的自由度近乎为零；真正有价值的「超窗择优」要先扩摘要数据面，那是独立特性立项，不是搬 R13。
4. **删除也不是现在的动作**：ranker 挂在 context_manager 链上，Phase 3（读侧，Human 决策）未到；现在单删会制造「链还在、零件没了」的孤岛。冻结成本≈0，锚定测试 20 用例继续绿（§3 实跑证据）。

**未决问题（本单不代拍板）：**

1. ~~**Phase 3 读侧重建时 `extract-context`/`context` CLI 与 context_manager→ranker 链的整体去留**~~ → ✅ **2026-09-18 已裁并执行**：技能改指 `v7-write pack` 后级联删除 `context` / `extract-context` CLI 与 `context_manager` / `context_ranker` / `extract_chapter_context.py`。
2. **若未来 v7 pack 需要「超窗摘要择优」（窗 >3 章）**，是否立项独立特性「v7 pack 条目级排序」（可从本档 §4 能力对照表和案 A 接口清单起步）——当前 3 章窗下无此刚需，不建议预投入。
3. ~~**memory/ 包归属**~~ → ✅ **2026-09-18 已裁**（§3.1 第 2 / 第 4 条）：随 context 链冻结，不单独补生产。
4. ~~**退役方案 §1.5 A 表 `:49` 行的表述勘误**~~ → ✅ **2026-09-18 已改**：该行改为「唯一生产引用者为 context_manager（同 A 类，级联处置）」。

## 7｜证据附录

- 调用图核查命令：§3 引用的两条 grep（全量版含 md/json 见本档 §2 的穷举）；`git log --oneline -- …/context_ranker.py` → `01fe438 / 2a87c3e / 755ffcf / 05e41de`。
- 锚定测试实跑：`PYTHONUTF8=1 py -3.13 -X utf8 -m pytest test_context_ranker.py test_memory_orchestrator.py "test_context_manager.py::test_ranker_caps_big_section_texts" -q --no-cov` → **20 passed**（2026-09-15 @ `578b4bf`；注意本机默认 `python` 指向 hermes venv 无 pytest，须用 `py -3.13`）。
- 本单改动面：仅新增本设计文档；`git status` 除本文档外干净；不改任何生产代码、不 push、不合入。
