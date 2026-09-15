# 项目结构与运维

## 目录层级

## 运维口径

- `.story-system/`：主链真源
- accepted `CHAPTER_COMMIT`：唯一写后事实入口
- `.webnovel/state.json`、`index.db`、`summaries/`、`memory_scratchpad.json`：投影/read-model
- `references/genre-profiles.md`：fallback-only
- `preflight` 与 dashboard 的 `story_runtime` / `story-runtime/health` 是第一观察点

系统涉及 4 层目录，使用前需要了解它们的区别：

| 层级 | 说明 | 示例 |
|------|------|------|
| `WORKSPACE_ROOT` | Claude Code 工作区根目录 | `D:\wk\novels` |
| `.claude/` | 工作区级配置与项目指针 | `D:\wk\novels\.claude\` |
| `PROJECT_ROOT` | 某本书的项目根目录（由 `/webnovel-init` 创建） | `D:\wk\novels\凡人资本论` |
| `CLAUDE_PLUGIN_ROOT` | 插件缓存目录（不在项目内，由 Marketplace 安装管理） | 自动管理 |

### 工作区目录

```text
workspace-root/
├── .claude/
│   ├── .webnovel-current-project   # 指向当前书项目根
│   └── settings.json
├── 小说A/                          # PROJECT_ROOT
├── 小说B/
└── ...
```

一个工作区可以包含多本书，通过 `.webnovel-current-project` 指针切换当前操作的书。

### 书项目目录（PROJECT_ROOT）

```text
project-root/
├── .webnovel/            # 运行时数据
│   ├── state.json        # 项目状态
│   ├── index.db          # SQLite 索引（实体/关系/章节数据）
│   ├── vectors.db        # 向量索引
│   ├── projection_log.jsonl # 投影执行日志
│   ├── summaries/        # 章节摘要
│   ├── backups/          # 自动备份
│   └── archive/          # 归档
├── .story-system/        # Story System 数据
│   ├── MASTER_SETTING.json
│   ├── chapters/
│   ├── volumes/
│   ├── reviews/
│   ├── commits/
│   └── events/
├── 正文/                  # 正文章节
├── 大纲/                  # 总纲与卷纲
├── 设定集/                # 世界观、角色、力量体系
└── 审查报告/              # 审查输出
```

### 插件目录

插件安装在 Claude 插件缓存目录，不在书项目内。运行时通过 `CLAUDE_PLUGIN_ROOT` 引用：

```text
${CLAUDE_PLUGIN_ROOT}/
├── skills/       # 8 个 Skill 命令定义
├── agents/       # 4 个 Agent 定义
├── scripts/      # Python 脚本与数据模块
├── hooks/        # Claude Code 会话钩子
├── references/   # 参考文档（题材画像、追读力分类法等）
├── templates/    # 初始化模板
├── genres/       # 精调题材配置
└── dashboard/    # 可视化面板前端
```

### 用户级全局映射

当工作区指针不可用时，系统会从用户级 registry 查找 workspace → project 映射：

```text
${CLAUDE_HOME:-~/.claude}/webnovel-writer/workspaces.json
```

## 常用运维命令

### 环境预检

```bash
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${WORKSPACE_ROOT}" preflight
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${WORKSPACE_ROOT}" project-status --format summary
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${WORKSPACE_ROOT}" doctor --format text
```

`preflight` 是快速检查，`project-status` 给短状态和下一步，`doctor` 是阶段感知体检。

检查项：插件脚本路径 / 项目根是否可解析 / Skill 目录是否存在 / 阶段应有文件 / JSON / SQLite / RAG 配置 / Python 依赖 / Dashboard 产物。

若 `story_runtime.mainline_ready=false`，说明当前项目仍在 legacy fallback 或 commit 主链不完整。

### 写章关卡（v7 书仓）

```bash
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${PROJECT_ROOT}" v7-write check --chapter 12 --draft "${PROJECT_ROOT}/工作区/草稿-0012.md" --json "${PROJECT_ROOT}/工作区/决策-12.json"
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${PROJECT_ROOT}" v7-write settle --chapter 12 --draft "${PROJECT_ROOT}/工作区/草稿-0012.md" --json "${PROJECT_ROOT}/工作区/决策-12.json" --summary "<≤200 字章摘要>"
```

- `check`：机检字数 / 占位符 / 标题 / 承诺 / 钩子；退出码 2 = 拒绝进入落定。
- `settle`：三门禁（审查 `.webnovel/tmp/review_results.json` / 文笔 `prose-check` / 素材引用）→ 原子 git commit（正文 + 章摘要 + 名册新实体）→ 刷新 `.cache/` 缓存。

> **v6 写链已冻结（frozen-legacy，2026-09-10 退役方案 Phase 1）**：存量 v6 书项目的写章关卡与章节提交步骤已随写链撤出 CLI，不再提供。v7 写链完整说明见 [`../guides/v7-write-path.md`](../guides/v7-write-path.md)。

### 索引重建

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index process-chapter --chapter 1
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" index stats
```

### 健康报告

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" status -- --focus all
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" status -- --focus urgency
```

`status` 保留宏观创作健康报告语义；需要机器可读短状态时使用 `project-status`。

### 向量重建

```bash
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" rag index-chapter --chapter 1
python "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" rag stats
```

### 缓存重建（v7 书仓）

```bash
python "${SCRIPTS_DIR}/v7_cache.py" rebuild --repo "${PROJECT_ROOT}"
python "${SCRIPTS_DIR}/v7_cache.py" verify  --repo "${PROJECT_ROOT}"
```

`.cache/` 是 v7 唯一的持久派生物（实体 / 章摘要 / 追读力查询面），可随时整目录删除后重建；`v7-write settle` 成功后会自动 rebuild（best-effort，失败不影响已完成的 settle）。存量 v6 书仓的 `.webnovel/*` 投影/read-model 由已冻结的投影链维护，投影重放命令已随写链撤出 CLI。

### 作者友好报告与恢复

主 Skill 的最终报告统一使用四种总状态：已完成、部分完成、需要你处理、未完成。报告只给作者需要知道的结论、产物、问题和下一步建议；内部 JSON、traceback 和长命令日志不直接展示。

异常分三类处理：

- **已自动处理**：幂等、可重试、不碰作者内容的问题，例如 projection retry 成功、缺失 runtime contract 后重新生成。流程默认继续，但最终报告必须说明处理过什么。
- **需要确认**：会影响创作方向、事实取舍、是否覆盖文件或断点续跑边界的问题，例如正文被手动改过、章纲更新晚于正文、本章已 accepted 后再次写章。系统应给 2-3 个有限选项。
- **必须处理**：blocking 审查问题、关键产物缺失、commit 被拒、投影补跑仍失败等。系统停在安全位置，报告说明已完成内容、卡点和恢复建议。

`/webnovel-write` 会记录写章断点，用于重跑时判断可信完成项：

```bash
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${PROJECT_ROOT}" run-ledger write-resume --chapter 12 --format text
```

断点建议只负责判断和提示，不自动覆盖文件。凡是涉及作者手改正文、旧正文是否沿用、accepted commit 是否重做，都必须先询问。

不可恢复故障会提示查看：

```text
.webnovel/logs/run_last.log
```

该日志用于保留最近一次运行的脱敏技术细节，便于排查。写入日志时会遮蔽常见敏感字段和值，包括 `api_key`、`secret`、`token`、`authorization`、`password`、`passwd`、`credential` 以及形如 `KEY=value` 的内联密钥片段。日志仍可能包含文件路径和错误上下文，提交 issue 前建议再人工扫一眼。

### 测试

```bash
pwsh "${CLAUDE_PLUGIN_ROOT}/scripts/run_tests.ps1" -Mode smoke
pwsh "${CLAUDE_PLUGIN_ROOT}/scripts/run_tests.ps1" -Mode full
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/run_behavior_evals.py" --format text
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_plugin_package.py" --format text
```

`run_behavior_evals.py` 是快速行为契约检查；`validate_plugin_package.py` 按 plugin-dev 思路检查 manifest、Skill / Agent frontmatter、hooks wrapper、README 版本和路径可移植性。

### Hook 开关

插件级 hook 默认很轻：

- `SessionStart`：只运行 `project-status --format summary`，不写文件、不启动服务。
- `PreToolUse`：对直接写主链 / read-model 文件和绕过 runtime 的危险命令做兜底阻断。

需要临时关闭时设置环境变量：

```bash
WEBNOVEL_DISABLE_SESSION_STATUS_HOOK=1
WEBNOVEL_DISABLE_RUNTIME_GUARD_HOOK=1
```

## Story System 运维

### 健康检查

```bash
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${PROJECT_ROOT}" preflight --format json
python -X utf8 "${CLAUDE_PLUGIN_ROOT}/scripts/webnovel.py" --project-root "${PROJECT_ROOT}" doctor --format text
```

`preflight` 返回 `story_runtime` 主链健康，`doctor` 给阶段感知的目录 / 文件 / DB / RAG / 依赖体检。

重点关注：

- v7 书仓：`book.yaml` 存在、`.cache/` 可重建（`v7_cache.py verify --repo "${PROJECT_ROOT}"`）
- v6 书仓：`.story-system/commits/chapter_XXX.commit.json` 是否存在且为 accepted、`projection_status` 是否全部为 `done` / `skipped`

> 存量 v6 书仓的事件链健康检查命令已随 v6 写链冻结撤出 CLI；本节字段仅作历史排查参考。

### 备份

做 Story System 相关备份时，至少同时备份以下内容：

```text
.story-system/
.webnovel/index.db
```

如果要做章节级回溯，建议连同 `.webnovel/summaries/` 一起备份。
