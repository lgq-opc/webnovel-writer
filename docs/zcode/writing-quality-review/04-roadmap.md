# 04 · 实施路线图（W1-W10 串行队列）

> 对齐项目既有「单线执行队列」模式：严格串行，一步一验证，不并行铺开。每步含改动面、验收命令、预计触碰文件。执行前须按项目惯例出各步 spec 增补；本路线图只锁定顺序与范围。
> 依赖关系：W1→W2→W4 有数据依赖（R4 消费 R2 的维度与 R1 的 section 框架）；其余按价值排序。

## 状态回填（2026-09-12 补）

> **本节是后补的，且是本文档唯一的进度事实源。**
> 本报告原为**零勾选**——文档里根本没有复选框，`04:63` 要求「每步完成后勾选并回写证据」但从未执行过。后果是它**会被读成「W1-W10 一步都没做」**，而事实相反：十条已被 `webnovel-copilot-300` 的 **M5「质量轨整编（吸收 W1-W10）」** 吸收执行（见 `../webnovel-copilot-300/08-implementation-plan.md:4,104`）。下表是逐条对账结果；**`## 队列` 各节保留原文，不再各挂状态行**，避免两处漂移。

| W | R 组成 | 实现任务 | 提交 | 状态 |
|---|---|---|---|---|
| W1 | R1+R10+R5 | T22 | `8d95bf6` | ✅ |
| W2 | R2 | T23 | `bb01308` | ✅ |
| W3 | R3 | T24 | `83907be`（+`3d59991`） | ✅ |
| W4 | R4 | T25 | `b439d50` | ✅ |
| W5 | R6+R7+R8 | T17（R6）+ T26（R7+R8） | `729a505` + `0046dd7` | ✅ |
| **W6** | **R9** | **无对应任务** | — | ❌ **未实现** |
| W7 | R12 | T27 | `3dde421` | ✅ |
| W8 | R13 | **本次补做** | `01fe438` | ✅ |
| W9 | R11+R14 | T27 | `3dde421` | ✅ |
| W10 | R15+R16+R17+R18 | T27（**仅 R15**） | `3dde421` | ⚠️ **部分** |

**合计 9/10 完成。**

⚠️ **对账时必须按 R 编号对齐，不要采信 `08` 自带的 W 标签**——它有错位与悬空：T17 标「W6」（内容实为 W5 的 R6）、T26 标「W7/W8」（内容实为 W5 的 R7+R8）、T27 标「W11-W15」（**本报告只到 W10，该区间不存在**）。

⚠️ **W6 不能照本节原施工指引执行**：`### W6` 的「预计触碰」把落点写成 `scripts/project_memory.py`，而该文件**已被 `511531e`（v6 退役 Phase 2 增量 1）删除**；`evidence_excerpt` / `metrics_snapshot` 全仓零命中。补做需**先定新落点与数据 schema**（学习闭环现挂 `author_model.py`，语义是"作者模型"而非"写作 pattern 库"）。

⚠️ **W10 的 R16 / R17 / R18 未定论**（methodology 节拍接卷纲 / trend 报告接入入口 / 死旋钮清理），**勿当作已完成**。

> **本次回填的性质**：`08:4` 的「吸收并取代质量审阅 W1-W10」应读作**「吸收了其中 9 条」**。详细对账、证据与未核项见 [`../../reports/2026-09-12-需求与设计对账.md`](../../reports/2026-09-12-需求与设计对账.md) §2.2.1–2.2.3。

## 队列

### W1 · 上下文连续性包（R1 + R10 + R5）
- 改动：`load-context` 新增 `prev_chapter_tail`（默认 1600 字，不可 DROP）；recent_summaries 截断方向改「新章优先」；DROP_ORDER 把 author_style_patterns/style_contract 提入永不丢弃集合；饱和策略改为按比例压缩 memory_pack 子层。
- 验收：饱和压力测试（合同+记忆全满构造）断言三段保全；`python -m pytest scripts/data_modules/tests/test_context_budget.py test_memory_contract_adapter.py`；真实书项目 `memory-contract load-context --chapter N` 输出含原文尾段。
- 预计触碰：`context_budget.py`、`memory_contract_adapter.py`、`context_manager.py`（对齐）、两处测试文件。

### W2 · 文笔度量两件套（R2）
- 改动：新 `scripts/prose_check.py`（词库数据化：polish-guide 十四类词表抽成 `references/csv/anti-ai-lexicon.csv`；检测项：高频词命中/长句比例/said tag 占比/同句式连击/解释段长度/段落方差）；reviewer 增第 6 维 prose（category 产出集加入 ai_flavor）；Step 4 契约改为附 prose_check 结果；review-pipeline 激活 ai_flavor→anti_patterns.json 既有回流。
- 验收：构造含已知套话的样章，prose_check 报出位置与计数；reviewer 六维输出；`run_behavior_evals.py` 更新对应断言全绿。
- 预计触碰：新脚本+词库 CSV、`reviewer.md`、`webnovel-write/SKILL.md`、`review_schema.py`（若需扩枚举说明）、行为评测 fixture。

### W3 · 多稿迭代（R3）
- 改动：`/webnovel-write --drafts N`（默认 2）；新 `references/draft-rubric.md`（6 项 rubric）；择优与定向重写一次的流程段；`draft_evaluations` 落库。
- 验收：`--drafts 2` 真书实跑一章，产出两稿+择优记录+落库行；`--fast/--minimal` 行为不变（回归）。
- 预计触碰：`webnovel-write/SKILL.md`、新 rubric 文件、`index_manager.py`（表）。

### W4 · 反馈断源闭合（R4，依赖 W1/W2）
- 改动：chapter-commit 投影链新增 reading_power 投影（从 data-agent front matter + 合同兑现数据）；`load-context` 新增 `reader_signal` section（追读力/钩子分布/爽点统计/审查趋势，各 ≤400 字）；`get-reader-signals` 补 review_trend；context-agent 第 4 段消费说明更新。
- 验收：写一章后 `chapter_reading_power` 自动有记录；连续同型钩子两章后第三章任务书出现差异化提醒；checklist_score 无恒 False 项。
- 预计触碰：投影路由/`index_projection_writer.py`、`index_reading_mixin.py`、`memory_contract_adapter.py`、`context-agent.md`。

### W5 · 文风锚点与孤儿接线（R6 + R7 + R8）
- 改动：高分章投影自动 style extract + `style_anchor` section 注入；naming-and-voice-gaps/golden-finger-templates/desire-description 三孤儿接线；write CSV 触发条件 5→9；loading-map 同步登记。
- 验收：三章后新章上下文含本书高分样本；触发场景可见对应内容；loading-map 对账零漂移（暂以 R15 脚本或人工核对）。
- 预计触碰：`style_sampler.py` 接线、`context-agent.md`、`webnovel-init/SKILL.md`、`webnovel-write/SKILL.md`、`reference-loading-map.md`。

### W6 · 学习闭环升级（R9）

> ✅ **2026-09-13 结案：按「已被取代」结案，不补做**（todohub `t-20260912-ac94`）。

- 改动：pattern 结构化（evidence_excerpt/metrics_snapshot）；高分章自动候选 pattern；近重复合并；注入 10→20；学习有效性对比报告。
- 验收：`/webnovel-review` 高分章后收到候选建议；注入扩容生效；报告可生成。
- 预计触碰：`project_memory.py`、`webnovel-learn/SKILL.md`、`memory_contract_adapter.py`、新报告脚本。

**结案依据**：学习闭环**已以另一形态存在**——`learn --from-journal`（卷级归纳 →
`作者/author_model-建议.md`，0-token 脚本统计 + 留白给 LLM 归纳）→ 作者确认 →
`learn apply`（回写 `作者/author_model.md` + `作者/跨书偏好.yaml`）。实现于
`author_model.py`（F-12 / M3-T16），CLI 接在 `data_modules/webnovel.py:1139`，
技能指引已于同日按此重写（`skills/webnovel-learn/SKILL.md`）。
**2026-09-13 实测**：`learn --from-journal` 与 `learn apply` 均码=0、建议文件与
author_model 正常产出（含「已确认」标记）。

**与 W6 原描述的差异（等价替换而非原样实现）**：原「pattern 库」（`project_memory.py`
的 `patterns` 数组 + `evidence_excerpt`/`metrics_snapshot` 字段）已随文件删除而不存在；
现形态是**作者模型**（节奏偏好 / 雷点 / 修改习惯 / 本书特定要求）——语义是「作者是谁」
而非「写作 pattern 库」，但覆盖了「从会话与作者行为中学习并影响后续写作」这一目标。
「预计触碰」四个落点中三个已不存在，施工指引作废；**不补做的依据是目标已由 F-12 达成**，
不是工期。

**未覆盖**：验收第一条「`/webnovel-review` 高分章后自动候选 pattern」在 v7 **无对应物**——
如需，属新需求而非 W6 补做。

**另立核验项**（todohub `t-20260913-02e7`）：实测中 `learn` 报「事件范围：**0/2** 条」，
说明它对 journal 行有筛选口径；真书的 `作者/journal.jsonl` 主要由审查绕过留痕产生、量可能很薄。
**闭环的输入端够不够料**是比「W6 是否补做」更实际的问题，需在真书仓上核。

### W7 · 机检加强与字数口径（R12）
- 改动：v7 上限告警/承诺推进存在性检查/占位符正则扩展/字数口径统一/机检回退对齐书史；v6 write-gate 同源上限告警。
- 验收：v7_write 单测新增四分支；超长与空承诺样文被报出。
- 预计触碰：`v7_write.py`、`prewrite_validator.py`、相关测试。

### W8 · 排序信号升级（R13）

> ✅ **已实现**（2026-09-12，提交 `01fe438`）。附带裁定（2026-09-13）：**D-8「`memory_pack`
> 是否进排序」不补做，随 v6 冻结**（todohub `t-20260912-8f3e`）。

- 改动：orchestrator 语义过滤改实体+关键词组重合度；删 `_length_score`；主路径引入排序。
- 验收：代称召回对比测试；长而空 vs 短而实排序断言。
- 预计触碰：`memory/orchestrator.py`、`context_ranker.py`、测试。

**D-8 不补做的依据**：`memory_pack` 只出现在 **v6 模块**——`context_manager.py:219`
（→ `memory/orchestrator.py:53 build_memory_pack`）与 `context_budget.py` 的配额/子配额表；
排序主体 `context_ranker.py` 的生产引用者也只有 v6 的 `context_manager`。
而 v7 的 `pack` 有**独立的 section 表**（`v7_write.V7_SECTION_QUOTAS/TITLES`，不含
`memory_pack`），且 v7 上 `context` 命令已明示不支持。即 D-8 是**纯 v6 域内**的排序问题，
补它没有 v7 消费者。

**附带发现（另立议题，不在 D-8 内）**：W8 的成果 `_density_score` 落在 `context_ranker.py`，
而该模块**无 v7 生产引用**——那部分工作目前只服务 v6 域，而 v6 写链已 frozen-legacy。
是否把 R13 的排序能力搬进 v7 的 `pack`，见 todohub `t-20260913-b673`。

### W9 · 技法盲区与结构补齐（R11 + R14）
- 改动：幽默/POV/修辞/亲密戏/商业文案五类条目与共享 md；系统流/都市异能模板补厚；CSV 分类收敛。
- 验收：`validate_csv.py` 0 错；检索命中抽测；模板行数达标。
- 预计触碰：CSV×N、`shared/`、`templates/genres/`。

### W10 · 卫生收尾（R15 + R16 + R17 + R18）
- 改动：引用接线对账脚本并入发版校验；methodology 节拍接卷纲；trend 报告接入 `/webnovel:status`；死旋钮实现或删除（倾向实现场景类型感知组装）。
- 验收：对账脚本报出并清零既有 22 项漂移；策略卡与卷纲一致；`/webnovel:status` 含趋势行。
- 预计触碰：新校验脚本、`writing_guidance_builder.py`、`commands/webnovel/status.md`、`context_weights.py`。

## 排期建议与风险

- **首月聚焦 W1-W4**（P0 全量）：这四步完成后，「写得好」才第一次拥有与「不写崩」对等的基础设施（连续性输入 + 度量 + 迭代 + 反馈）。
- **W3 的默认档位**需要作者决策：`--drafts 2` 作为默认会翻倍起草成本——本任务准绳是不考虑 token，但落地时建议 book.yaml 可配 `write.drafts`，作者按书选择。
- **W2 的 rubric 校准**依赖 W3 落库数据（rubric 分 vs 审查分相关性），首轮先人工复盘，数据够后再调权重。
- 每步完成后在本文档勾选并回写证据；发现顺序需要调整时在 [任务 README](README.md) 登记变更理由。
