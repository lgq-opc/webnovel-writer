---
name: webnovel-query
description: 查询项目设定、角色、力量体系、势力、伏笔等信息。支持紧急度分析与金手指状态查询。
allowed-tools: Read Grep Bash
argument-hint: "[查询词，如 角色名/伏笔/境界]"
---

# Information Query Skill

## Use when

用户询问关于故事设定、角色、力量体系、势力、伏笔、金手指、节奏等项目内信息时触发。

## 项目根保护

```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT}/scripts"
export SKILL_ROOT="${CLAUDE_PLUGIN_ROOT}/skills/webnovel-query"
export PROJECT_ROOT="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
```

- `PROJECT_ROOT` 由 `where` 解析。**v7 书仓的标志是 `book.yaml`**（v6 遗留仓为 `.webnovel/state.json`），两者都是合法项目根
- **禁止**在 `${CLAUDE_PLUGIN_ROOT}/` 下读取或写入项目文件

## 查询分类 → 最窄工具

先识别查询类型，再用下表最窄工具。不默认全量加载，只在综合 / 跨多类型查询时用 `v7-write pack`（装配上下文包）。

| 查询类型 | 关键词 | 最窄工具 |
|---------|--------|---------|
| 角色名册信息 | 某角色是谁 / 别名 / 首现章 | `knowledge query-entity-state`（v7 答**名册级**）或 Read `定稿/设定/名册/<正名>.md` |
| 角色逐章状态 | 某角色在第N章时 / 时间点状态 / 境界变化 | Read `定稿/正文/`；v6 遗留仓可用 `knowledge query-entity-state` |
| 世界规则 | 力量规则 / 设定铁律 / 境界体系约束 | `setting-read --name <设定名>`，或 Read `设定/` 对应文件 |
| 伏笔 / open loop | 伏笔 / 紧急伏笔 / 未闭合悬念 | `foreshadow-scan` / `promise-ledger`，或读 `大纲/条目/` |
| 综合 / 复杂 | 跨多类型、需要时间线 + 长期记忆联合 | `v7-write pack --chapter {N}`（产出上下文包） |
| 静态设定 | 角色卡 / 力量体系 / 世界观 / 势力 / 标签格式 | `Grep` + `Read` `设定/` |

> **v7 的 `knowledge` 是正式行为，不是临时缺口**（2026-09-18 裁决）：只答名册级（正名/别名/首现章）。
> v7 写链**不产**实体逐章状态与关系，返回体的 `not_covered` 会写明。设定全文走 `setting-read` / 六域文件。
> **没有** `knowledge query-relationships` 的 v7 等价物——关系从 `定稿/正文/` 与 `大纲/条目/` 判读。

## 引用加载策略

按查询类型按需加载，先识别再加载。路径说明：`references/` 指 skill 私有 `skills/webnovel-query/references/`；`../../references/` 指共享 references。

| 查询类型 | Reference | 实际路径 |
|---------|-----------|---------|
| 数据流 / 优先级 | 数据流规范 | `${SKILL_ROOT}/references/system-data-flow.md` |
| 伏笔分析 | 伏笔分析 | `${SKILL_ROOT}/references/advanced/foreshadowing.md` |
| 节奏分析 | Strand 模式 | `${SKILL_ROOT}/../../references/shared/strand-weave-pattern.md` |
| 格式查询 | 标签规范 | `${SKILL_ROOT}/references/tag-specification.md` |

不得同时加载两个以上 reference，除非用户请求明确跨多类型。

## 查询流程

1. **识别查询类型**：按「查询分类 → 最窄工具」表匹配关键词。
2. **按优先级定位真源**（写前真源 → 写后真源 → 投影层）。v7 的写前真源是**六域**，
   **没有** `.story-system/` 合同树（那是 v6 写链产物，已冻结）：
   1. `book.yaml` — 书级声明（书名 / 题材 / 主角 / 卷规模 / 素材装配条数）
   2. `大纲/` — 总纲 / 卷纲（详细大纲、节拍表）/ 章纲 / 条目（`F-*` 伏笔、`S-*` 悬念）
   3. `设定/` 与 `文风/宪法.md` — 世界观 / 力量体系 / 名册 / 力量锚点 / 风格契约（作者开写前必须遵守）
   4. `定稿/` — **写后真源**，不可篡改：正文 `NNNN-标题.md`（front matter 含 书内时间 / 推进承诺 / 合同 / 钩子）、`记忆/章摘要/`、`设定/名册/`
   5. `.cache/index.db` — **投影层**：chapters / entities / summaries / chapter_reading_power，
      由 `rebuild_cache` 从 1-4 重算，**可随时整目录删除**（下次查询自动重建）

3. **调用最窄工具检索**：按类型只调用所需命令，不默认装配整包。

```bash
# 角色名册信息（v7 答名册级：正名/别名/首现章；返回体 not_covered 写明边界）
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" knowledge query-entity-state --entity "{entity_id}" --at-chapter {N}

# 世界规则 / 设定原文
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" setting-read --name "{设定名}"

# 伏笔 / open loop（跨卷未回收）
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" foreshadow-scan scan --chapter {N} --no-apply
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" promise-ledger list

# 仅综合 / 复杂查询：需要时间线 + 长期记忆联合时才用（装配上下文包）
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" v7-write pack --chapter {chapter_num} --json "${PROJECT_ROOT}/工作区/决策-{chapter_num}.json"
```

   静态设定（角色卡 / 力量体系 / 世界观 / 标签格式）直接用 `Grep` 定位行号再 `Read` 取片段。

   `query-relationships` 只在 v6 遗留仓可用；v7 仓请按上方「能力边界」自行判读，不要臆造关系。

4. **格式化输出**：按下方模板输出。

## 输出格式

```markdown
# 查询结果：{关键词}

## 概要
- **匹配类型**: {type}
- **数据源**: {实际命中的真源 / 投影层}
- **匹配数量**: X 条

## 详细信息
{结构化数据，含文件路径和行号}

## 数据一致性检查
{state.json 与静态文件的差异，若无差异则省略}
```

## 边界与失败恢复

- 只读操作，不修改任何项目文件
- 若数据源缺失，明确告知用户缺少什么文件
- 若查询无匹配，返回空结果并建议检查范围
- 若 `book.yaml` 或六域目录缺失，**先跑 `doctor`** 看骨架缺哪一块，如实转述给作者，不要凭猜测作答
- v6 遗留仓（有 `.webnovel/state.json` 但无 `book.yaml`）仍走 `.story-system/` 合同与 accepted commit；
  合同缺失时须显式说明该查询已降级到 legacy fallback
