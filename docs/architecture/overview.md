# webnovel-writer 系统架构总览（v8.x）

> **v6 写链已冻结（frozen-legacy，2026-09-10 退役方案 Phase 1）**：仅维护、不再演进；本文中 v6 写章六步链与 `.story-system` 运行时合同相关描述，只用于理解**存量 v6 书项目**。**新书写章一律走 v7 写链**（`v7-write decision/pack/check/settle`，操作面见 `docs/guides/v7-write-path.md`）；v6 项目先迁移（`migrate_v6_to_v7.py`）。物理删除见 `docs/plans/2026-09-10-v6线退役方案.md` Phase 2。
>
> 本文描述 v8.1.0 现状（2026-09-10 重写，替代 v6 时代旧版；旧版见 git 历史与 `docs/archive/architecture/`）。
> 详细设计：[webnovel-copilot-300/04-architecture.md](../zcode/webnovel-copilot-300/04-architecture.md)（七层模型 / 数据治理 / 状态机全版）、
> [v7-write-path.md](../guides/v7-write-path.md)（v7 写链操作面）、[story-repo-spec](story-repo-spec-2026-06-10.md)（书仓格式）。

## 七层模型

```
L7  作者主权层    author-sync / journal / freeze / impact / regen 画廊 / author_model·style_profile
L6  会话编排层    ZCode 插件壳：skills×8 / agents×4 / hooks×4 / MCP(12 只读) / /webnovel:* 命令(13)
L5  工作流层      v7 决策卡-机检-settle 链（**新书写章唯一路径**）/ v6 写章六步链（**frozen-legacy**，仅维护）/ plan 规划链 / review 审查链
L4  领域服务层    统一 CLI webnovel.py（治理 / 索引投影 / 记忆 RAG / 战力素材 / 度量报告）
L3  确定性内核    git 事务 / 时间线推演 / 伏笔逾期 / 锚点校验 / 字数占位符 / prose_check（无 LLM）
L2  数据层        git 正典（书仓六域）→ 编译产物（.story-system 合同 / .webnovel 投影 / .cache 索引）
L1  宿主          ZCode（可替换；L4 以下宿主无关）
```

依赖方向：L7 依赖 L3/L2（不依赖 LLM）；L6 只做触发与呈现；一切写正典的操作收口在 L4 的 git 事务（settle / freeze / retcon / 采纳）。

## 真源与编译产物（数据治理核心）

```
作者编辑（任何编辑器，免门禁直写） ／ AI 提案（工坊 / regen / 工作区草稿区）
        │                                    │ settle / freeze / 作者采纳
        ▼                                    ▼
┌───────────── git 正典（书仓六域，唯一真源）─────────────┐
│  大纲域  正文域(定稿)  设定域  素材域  作者域  演化域      │
└────────────────────────────────────────────────────────┘
        │ author-sync（diff→分类→journal→stale→impact）
        ▼
   编译产物（可删可重建）：.story-system/ 合同树、.webnovel/ 投影（index.db 等）、.cache/（v7 缓存）
```

规则：

1. **编译产物不手改**：合同由 `story-system` 从正典编译；`webnovel doctor` 校验「正典→产物」一致性，漂移即报。
2. **AI 提案永不直接进正典**：regen 画廊、v7 工作区都是草稿区；采纳动作 = git 事务。
3. **journal 是唯一 append-only 副本**：作者行为与系统事件（freeze/retcon/stale）同流，可被 `author_model` 归纳。

## 双写链路（L5）

| 链路 | 流程 | 入口 |
|------|------|------|
| v6 写章 | 六步链：context → 起草 → review → 润色 → commit → backup | `/webnovel:write`（无 `book.yaml` 的项目） |
| v7 写章 | `decision → pack →（草稿）→ check → settle`，机检是硬闸，settle 三门禁（审查 / 文笔 / 素材引用）后原子 git commit | `/webnovel:write`（`book.yaml` 存在时转发 `webnovel.py v7-write`） |
| 规划 | 总纲 → 卷纲 → 章纲，增量写回设定集 | `/webnovel:plan` |
| 审查 | 审查 Agent 评估章节质量并写回指标 | `/webnovel:review` |

v7 要点（详见 v7-write-path）：上下文包 20k 字符预算按节配额装配（决策卡 / 章纲节选 / 承诺账本 / stale / 前情 / 上一章结尾 / 实体 / 主角卡 / 视角纪律 / 素材 / 文风层）；`settle` 前经 `dual_format_guard` 保证同一章不在 v6/v7 双写。

## 组件面（L6，ZCode 插件壳）

- **Skills ×8**：`webnovel-init` / `plan` / `write` / `review` / `query` / `learn` / `dashboard` / `doctor`
- **Agents ×4**：`context-agent`（写前任务书）/ `data-agent`（commit artifacts 提取）/ `reviewer`（质量审查）/ `deconstruction-agent`（参考书拆解）
- **斜杠命令 ×13**：dashboard / doctor / forge / init / learn / materials / plan / power / query / review / status / style / write（薄壳，挂到 skills 或 CLI）
- **MCP server ×12 只读工具**（`mcp/server.py`，纯标准库 stdio JSON-RPC；实参拒绝前导 `-`，list 形式拼 `subprocess.run`，无 shell）：
  `where` / `project_status` / `doctor` / `setting_read` / `timeline_check` / `meter` / `knowledge` / `materials_status` / `materials_assemble` / `power_check` / `foreshadow_scan` / `reader_signals`（D-2 乙 2026-09-13 撤出 `rag_search`、`context`）
- **Hooks ×4**：SessionStart / UserPromptSubmit / PreToolUse / PostToolUse（`${ZCODE_PLUGIN_ROOT}` 装载；SessionStart 会写 `.webnovel/` journal）
- **Dashboard**：预打包 `dist/` 只读面板（CORS 白名单 / 只读连库，见 `test_dashboard_security.py`）

## 治理与不变量（L3/L4）

- **write gates**：`prewrite / precommit / postcommit` 三段门（JSON 报告 `ok/errors/warnings`），含 `dual_format_guard` 唯一写入路径检查（v6 侧经 `STORY_REPO_ROOT`，v7 侧经 `decision.v6_project_root` 或 git config `dualformat.v6root`；配置缺失时以 warning 提示而非静默）。
- **doctor**：阶段感知只读体检——目录/文件/JSON/SQLite/RAG/Dashboard + 六域目录契约 + 数据不变量对账。
- **六项数据不变量**（`invariant_check.py`，见 06-data-design §12）：① journal 无未分类积压；② 素材轨迹引用的 (条目， 定版版本) 存在；③ 战力锚点战例章号有定稿、境界链单调；④ 条目状态机合法（retcon 需 journal+演化双记录）；⑤ `.story-system/` 合同与正典重建一致；⑥ stale 无超一卷未消费项。
- **四校验脚本**：`sync_plugin_version`（版本三处一致）/ `validate_release_notes` / `validate_plugin_package` / `validate_reference_wiring`——已接入 CI（`.github/workflows/plugin-tests.yml`，依赖锁定 `requirements.lock`）。

## 工程面

- Python 3.10+，pytest 覆盖率门槛 80%（根 `pytest.ini`：data_modules + scripts + mcp 三处测试）。
- 依赖基线：`requirements.lock`（CI 与发版验证按锁安装；`requirements.txt` 保留宽松范围）。
- 文档分层：ZCode 方案集 `docs/zcode/<任务名>/`，Cursor 产出 `docs/cursor/<任务名>/`，正式设计归 `docs/{architecture,guides,decisions}/`。
