# reader_signals 在 v7 接通 — spec（换落点 + 接回生产者）

> 档位：**Architectural**（动决策卡契约与 settle 落盘）。依据：todohub `t-20260913-6202`、
> `docs/reports/2026-09-12-需求与设计对账.md` §D-2 乙「低成本项」。
> **本 spec 订正了原方案的措辞**——原措辞「只需换落点，不需补生产」经实测不成立，见 §1。
> 状态：待 Human 批准后进入 plan。

---

## 0. 一句话

v7 的「追读力 / 读者信号」**从未接通**（写端恒 `skipped`、读端守着一个 v7 上不存在的 v6 库）。
本方案让钩子在写前被**显式声明**、落进 v7 canonical（正文 front matter）、缓存可从源重建、
消费侧（pack 读者信号节 + `index get-reader-signals` + MCP `webnovel_reader_signals`）读到真数据。

## 1. 背景与证据（全部本机实测，2026-09-13）

原方案把本条定性为「v7 生产 / v6 存储」，只差换落点。实测**生产端在 v7 上是死的**：

| # | 证据 | 出处 |
|---|---|---|
| E-1 | 钩子字段只从 **front matter** 提取（`if summary.startswith("---")`） | `reading_power_projection.py:28` |
| E-2 | 无 front matter → `status: "skipped"`（仓内既有断言） | `test_v7_write_post_hooks.py:90-94` |
| E-3 | 只有手工在 `--summary` 里写 front matter 才 `status: "ok"` | 同文件 `:71-87` |
| E-4 | 真实流程传**纯文本** `--summary "{≤200 字章摘要}"` | `skills/webnovel-write/SKILL.md:177` |
| E-5 | 同批 `settle_style_domain` 拿到了 `extraction_file`，`settle_reading_power` 只拿到 `summary_text` | `v7_write.py:656,661` vs `:673` |
| E-6 | v7 写链**全程无 data-agent 步骤**（`extraction_result.json` 无人生产） | `SKILL.md` 全文无匹配；仅 `evals.json:26` 留有 v6 描述 |
| E-7 | 章纲卡模板与真书**都没有** `钩子类型`/`钩子强度` | `templates/`、`webnovel-plan` 全无该标签 |
| E-8 | 真书 directive 探针：`hook_type: None` / `hook_strength: None`（第 41、42 章） | 本机跑 `.tmp/probe-hook-directive.py`（见 §5 探针记录） |
| E-9 | loader 的 `钩子类型→hook_type` 映射**只活在一份手写测试 fixture 里** | `chapter_outline_loader.py:257` vs `test_chapter_outline_directive.py:36` |

**结论**：`钩子类型`/`钩子强度` 没有任何生产者。真书章纲卡的结构化字段是
`章节号/标题/卷/时间锚/节点/禁区/承诺推进/素材引用/字数目标`，钩子只以散文形式出现在
`Quest：…章末危机钩——…` 这类**正文行**里。

> **顺带订正**：`SKILL.md:174` 声称 settle 会「落账…追读力」，该承诺在 v7 上不成立。

## 2. 目标 / 非目标

**目标**

1. v7 写链能产出 `chapter_reading_power` 数据，且**不依赖任何人的自觉**（W 系列：规则离触发点越远越等于不存在）。
2. 「派生物可丢弃」不变量对追读力成立：删 `.cache/` 后 `rebuild_cache` 能全量重算。
3. 消费侧在纯 v7 仓读到真数据；不再往 v6 域落文件。

**非目标（明确不做，避免范围蔓延）**

- `review_trend`：唯一生产者是 `review-pipeline --save-metrics`（v6 模块，方案 §1.5 判过「可删」）→ 无 v7 源，并入 D-2 乙剩余决策。
- `coolpoint_patterns` / `micropayoffs` / `hard_violations` 等 v6 专属列：v7 无源，保持空。
- v6 仓行为：原样不动（冻结而非删除）。
- dashboard 治理面、RAG、`knowledge`：属 D-2 乙高成本项，不在本 spec 内。

## 3. 设计

### 3.1 数据流（唯一事实源 + 纯派生物）

```
决策卡 工作区/决策-NNNN.json        ← 作者/主流程显式声明钩子（可豁免）
        │ settle
        ▼
定稿/正文/NNNN-标题.md front matter  ← 唯一事实源（与 书内时间/推进承诺/合同 同处）
        │ rebuild_cache（settle 后自动触发，失败不阻断）
        ▼
.cache/index.db :: chapter_reading_power   ← 纯派生物，可丢弃
        │
        ▼
pack 读者信号节 / index get-reader-signals / MCP webnovel_reader_signals
```

**为什么落正文 front matter**：settle 已把 `书内时间` / `推进承诺` / `承诺豁免` / `合同`
写进正文 front matter（`v7_write.py:770-780`），钩子与它们同类（都是「本章怎么写」的既定事实）。
这样 `.cache` 的重建源是 canonical 文件，**不需要**去读 `工作区/`（草稿区，可清理）。

### 3.2 决策卡契约（+3 字段）

`docs/guides/v7-write-path.md:66-80` 决策 JSON 字段表新增：

| 字段 | 类型 | 用途 |
|---|---|---|
| `hook_type` | str | 章末钩子类型（taxonomy 见 `references/reading-power-taxonomy.md`） |
| `hook_strength` | str | 钩子强度；缺省 `medium`；中文值 `强/中/弱` 归一为 `strong/medium/weak` |
| `hook_waiver` | str | 显式豁免理由（本章确无钩子时填写） |

**机检（`v7-write check`）**：`hook_type` 非空 **或** `hook_waiver` 非空，否则退出码 2。
沿用既有 `promises` / `waiver` 的同一 idiom（`v7-write-path.md:75`）——**把沉默变成决定**。

> **Ruling（2026-09-13，Human 裁定）**：**采纳硬闸**。理由＝本轮暴露的失效模式正是「静默跳过」，
> warning 会原样复现它。豁免成本极低（一行字符串），故不构成实际负担。
> 配套：测试夹具 `test_v7_write_gates._decision()` 补默认 `hook_waiver`，避免既有用例被新闸误伤。

### 3.3 落点：`.cache/index.db`

- 新表 `chapter_reading_power(chapter INTEGER PRIMARY KEY, hook_type TEXT, hook_strength TEXT)`。
- `rebuild_cache` 新增 `_iter_reading_power()`：从 `定稿/正文/*.md` 的 **front matter** 取
  `钩子类型` / `钩子强度`（复用 `v7_cache._parse_front_matter`）。
- **schema 版本化**：`meta` 表写 `schema_version`；`_cache_intact` 由「4 张核心表齐备」
  升级为「4 张核心表齐备 **且** `schema_version` 匹配」，否则首查自动重建。
  （否则旧缓存 4 表俱全，新表缺失，查询会报错。）
- `snapshot` / `verify_rebuild` 纳入新表——保住「删缓存→重建→快照等价」这条不变量的验收面。

### 3.4 退役 `settle_reading_power` 的写盘职责

形 A 下 rebuild 会从正文 front matter 自动带上钩子，后置钩子**无事可做**。处置：

- 移除 `reading_power_projection.settle_reading_power` 的写盘路径（含 IndexManager 依赖）。
- `post["reading"]` 的**对外报告形状保留**（由决策卡钩子直接构造：`{status, hook_type, chapter}`），
  避免下游与文档漂移；无钩子时仍报 `skipped`。
- 连带影响：`test_v7_write_post_hooks.py` 两条用例需改写（`:71-87` 改为断言 front matter
  + `.cache` 记录；`:90-94` 改为断言豁免路径）。
- `v7_write._SETTLE_ADD_PATHS` 移除 `.webnovel/index.db`（v7 不再产生该文件）——
  顺带消解 `t-20260913-1072` 的一半。

### 3.5 消费侧

| 消费者 | v7 分支 | v6 分支 |
|---|---|---|
| `reader_signal_builder.build_reader_signal` | 读 `.cache/index.db` | 原样（守卫 `.webnovel/index.db`） |
| CLI `index get-reader-signals` | 在 `webnovel.py` 派发处按 `resolve_write_mode` 分流到 v7 实现 | 原样 |
| pack 的 `_sec_reader_signal` | 不变（自动受益） | 不变 |

复用 `domain_contract.resolve_write_mode()` 作形态判据——与 doctor / F1 / F5 同源，
**不另立一套判据**（既有教训：两边各写一套必然漂移）。

## 4. 被否方案（附证伪依据）

| 方案 | 否决理由 |
|---|---|
| **甲·从章纲卡取钩子** | E-7/E-8/E-9：模板无该标签、真书探针 `None`、映射只活在测试 fixture。要成立须改 `/webnovel-plan` 的输出契约 + 全量重规划存量书 |
| **乙·要求主流程在 `--summary` 写 front matter** | E-1/E-4：等于「请模型记得」，正是本项目反复证伪的失效模式（F4 教训） |
| **丙·从 `extraction_result.json` 取** | E-6：v7 写链无 data-agent 步骤，无人生产该文件 |
| **丁·只换落点不接生产** | 等于把一个恒 `skipped` 的写路径从 v6 域搬到 v7 域，功能仍不可用 |
| **戊·把 `reader_signals` 判 unsupported（同 rag/knowledge/context）** | 属 D-2 乙「真砍」选项，是**功能去留**决策而非工程缺陷修复；保留为备选，若 Human 选它则本 spec 作废 |

## 5. 探针记录

```bash
python -X utf8 C:\lgq\ai-workspace\.tmp\probe-hook-directive.py
# === 第 41 章 ===
# directive 键: ['antagonist_tier','cbn','cen','chapter_end_open_question','cost','cpns',
#               'forbidden_zones','goal','key_entities','must_cover_nodes','obstacles',
#               'source','strand','time_anchor']
# hook_type: None
# hook_strength: None
# （第 42 章同）
```

对象＝真书 `fantasy01-pov`（42 章）。该探针为只读，产物在 `.tmp/`（仓外）。

## 6. 风险

| 风险 | 处置 |
|---|---|
| 决策卡加必填项改变既有工作流 | 用 `hook_waiver` 兜底；只对新章卡生效，不回溯存量 40+ 章 |
| 存量章无钩子 → 追读力数据从下一章起才有 | **不回溯**（另行登记待办，与 `migrate_v6_to_v7` 同类问题） |
| 词表不一致（章纲 `中/强/弱` vs 表 `strong/medium/weak`） | 边界处归一；保留 `_validate_reading_power` 的既有警告作兜底 |
| `.cache` schema 升级 | `schema_version` 版本化 + 老缓存首查自动重建 |
| 触碰 settle 的 front matter 写入 | 有既有测试锚定（`test_v7_write.py:113` 断言 front matter 内容），改动可见 |
| 与 D-2 乙「真砍」决策冲突 | 若 Human 最终选戊（砍掉工具），本 spec 的产出作废但**不白做**——决策卡钩子字段仍是写作质量机制，可独立保留 |

## 7. 验收标准

1. **正向**：新 v7 仓 settle 一章（决策卡带 `hook_type`）→ `定稿/正文/NNNN-*.md` front matter 含
   `钩子类型:`；`.cache/index.db` 有该章记录；`index get-reader-signals` 返回非空
   `recent_reading_power`；`v7-cache verify` 仍 `equal=True`（含新表）。
2. **闸门**：无 `hook_type` 且无 `hook_waiver` → `check` 退出码 2；带 `hook_waiver` → 通过且该章 `skipped`。
3. **反向守住**：v6 仓（有 `state.json`）路径行为不变——仍写 `.webnovel/index.db`，读亦原样。
4. **不变量**：删 `.cache/` 后 `rebuild` 重算出的追读力与删除前一致。
5. **端到端**：`smoke_v7_newbook.py` 的 `reader-signals` 步骤由「仅退出 0」升级为**断言内容非空**。
6. 全量 pytest + 四校验 + CI 双平台绿。

## 8. 文档回改（W12：发现与方案冲突先回改方案）

| 文件 | 改什么 |
|---|---|
| `docs/reports/2026-09-12-需求与设计对账.md` §D-2 乙 | 「只需换落点，不需补生产」**就地订正**，附 E-1..E-9 |
| `skills/webnovel-write/SKILL.md:174` | 「落账…追读力」与实现对齐（改为：钩子由决策卡声明、settle 落 front matter、缓存重算） |
| `docs/guides/v7-write-path.md` §3 | 决策卡字段表 +3 行；`_SETTLE_ADD_PATHS` 变化 |
| `docs/reports/2026-09-13-会话交接-v7路径收口.md` | 下会话交接需反映本条已被重新定性 |
| todohub `t-20260913-6202` | 范围由「换落点」更新为「换落点 + 接回生产者」 |

## 9. 另立的待办（不在本 spec 内实现）

1. 存量章（40+）钩子回填：不回溯，需单独排期与工具。
2. `review_trend` 在 v7 无生产者 → 并入 D-2 乙剩余决策。
3. `钩子类型` 的 taxonomy 与 `chapter_outline_loader` 映射表口径统一（本 spec 不动章纲侧）。
