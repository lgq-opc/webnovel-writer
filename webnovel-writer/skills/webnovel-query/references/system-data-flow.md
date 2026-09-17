---
name: system-data-flow
purpose: 项目初始化和状态查询时加载，理解数据结构
---

<context>
此文件用于 **v7 书仓**的数据结构参考。模型已知一般文件组织，这里只补充本工作流特定的
六域约定、派生缓存与写链数据流。
</context>

<instructions>

> **本文件描述 v7 书仓。** v6 遗留仓（有 `.webnovel/state.json`、`.story-system/` 合同树）
> 的数据结构与写链**已冻结**（2026-09-10 退役方案 Phase 1），其 `state.json` 结构、
> `index.db` 表、双 Agent 架构、Data Agent 直写流程等**不再在本文件描述**——
> 需要时见 `docs/plans/2026-09-10-v6线退役方案.md`。v7 写链一律走 `v7-write`。

## 一、真源层级（查任何东西之前，先定位它属于哪一层）

| 层 | 位置 | 说明 |
|---|---|---|
| 书级声明 | `book.yaml` | 书名 / 题材 / 主角 / 卷规模 / 素材装配条数；**也是 v7 书仓的标志**（v6 看 `.webnovel/state.json`） |
| 写前真源 | `大纲/` | 总纲 / 卷纲（`卷纲/第NN卷-详细大纲.md`、节拍表）/ 章纲 / 条目（`F-*` 伏笔、`S-*` 悬念、感情线） |
| 写前真源 | `设定/` 与 `文风/宪法.md` | 世界观 / 力量体系 / 名册 / 力量锚点 / 风格契约。**作者开写前必须遵守** |
| 写后真源 | `定稿/` | 正文 `NNNN-标题.md`（front matter 含 书内时间 / 推进承诺 / 合同 / 钩子）、`记忆/章摘要/NNNN.md`、`设定/名册/<正名>.md`。**不可篡改** |
| 派生缓存 | `.cache/index.db` | **可丢弃**的查询视图，删光后按需从上面四层重建 |

系统域：`.webnovel/`（仅 `logs/` 与 `tmp/`，均在书仓 `.gitignore` 内）与 `.cache/`。

> 目录约定的权威文档：`docs/zcode/webnovel-copilot-300/05-book-directory-structure.md`。
> 注：`book-init` 实测建 **5/6** 顶层域——`设定/` 不预建（其内容属 advisory，按需创建）。

## 二、写链数据流（v7）

```
准备：判定书仓形态（book.yaml 在场 → v7；否则先 book-init 或 migrate_v6_to_v7）
 1. decision   决策卡 工作区/决策卡-NNNN.md  ← 决策 JSON（含 hook_type / hook_strength）
 2. pack       上下文包 工作区/上下文包-NNNN.md
 3. 起草       草稿 工作区/草稿-NNNN.md
 4. check      机检（字数下限 = 目标×0.75 / 占位符 / 标题 / 承诺或豁免 / 钩子或豁免）
 5. 审查       .webnovel/tmp/review_results.json（缺、章号不符、blocking>0 均拒）
 6. 润色       prose-check 到 flagged 为空
 7. settle     定稿/正文/NNNN-标题.md + 定稿/记忆/章摘要/NNNN.md + 名册新实体
               → 后置：素材轨迹 / 文风指纹 / 追读力回报
               → 原子 git 提交，随后 best-effort 重建 .cache
```

关键：**上下文包是起草的唯一依据**；`pack` 缺决策卡时直接报错退出，不产降级包。
`settle` 的三道门禁（审查 / 文笔 / 素材引用）中，素材引用不可绕过。

## 三、派生缓存 `.cache/index.db`

| 表 | 来源 |
|---|---|
| `chapters` | `定稿/正文/*.md`（标题/卷/字数/正文） |
| `entities` | `定稿/设定/名册/`（正名 / 别名 / 首现章） |
| `summaries` | `定稿/记忆/章摘要/NNNN.md` |
| `chapter_reading_power` | `定稿/正文/*.md` 的 front matter 钩子字段（由 settle 从决策卡写入） |
| `meta` | 含 `schema_version` |

**不变量「派生物可丢弃」**：删 `.cache/` 后 `rebuild_cache` 能从源文件全量重建，
`v7-cache verify` 以「删缓存→重建→查询快照等价」验收。
`meta.schema_version` 与实现常量不匹配时，**首次查询即整库重建**（不写迁移代码）。

## 四、工具 → 取数来源（与能力边界）

| 工具 / 命令 | 取数来源 | v7 上的边界 |
|---|---|---|
| `setting-read --name X` | `设定/`（旧仓 `设定集/` 兜底） | — |
| `knowledge query-entity-state` | `.cache` 的 `entities`（名册级：正名/别名/首现章） | **正式行为**（2026-09-18）：不产逐章状态与关系；`not_covered` 会写明 |
| `foreshadow-scan` / `promise-ledger` | `大纲/条目/` + 账本 | 伏笔/悬念/承诺的现行入口 |
| `index get-reader-signals` | `.cache` 的 `chapter_reading_power` | `review_trend` **恒为空**（v7 无生产者） |
| `meter report` | 宿主用量库（非书仓数据） | — |
| `v7-write pack` | 六域聚合 | 综合/跨类型查询的唯一入口 |
| `rag` / `context` / `status` | — | **v7 明示不支持**（RAG 已于 2026-09-18 正式下线；context 请用 `v7-write pack`） |

静态设定（角色卡 / 力量体系 / 世界观 / 标签格式）直接用 `Grep` 定位行号再 `Read` 取片段。

## 五、v6 遗留仓

有 `.webnovel/state.json` 或 `.story-system/` 合同链的仓按 **v6 形态**处理：
`project-status` / `doctor` 会报 `write_mode: v6`，`knowledge` 恢复答逐章状态与关系。
v6 写链已冻结，仅维护；新书写章一律走 v7。

</instructions>
