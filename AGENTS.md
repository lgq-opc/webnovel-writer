# webnovel-writer — 项目约定

> 继承全局 AGENTS.md 和工作区 AGENTS.md，以下规则优先。

## 技术栈

- Python 3.10+ / pytest
- ZCode Plugin（`.zcode-plugin/` 清单：skills + agents + hooks + commands + MCP server）
- MCP server：纯标准库 stdio JSON-RPC（`mcp/server.py`，零第三方依赖）
- Dashboard 前端：预打包 dist/，不需要 npm build

## 常用命令

```powershell
# 运行测试（根 pytest.ini：data_modules + scripts + mcp 三处，覆盖率门槛 80）
# 必须带 PYTHONUTF8=1（N-1）：中文 Windows 上少了它会因父子进程编码不一致而假失败。
$env:PYTHONUTF8=1; python -X utf8 -m pytest

# smoke 快速子集
powershell -File webnovel-writer/scripts/run_tests.ps1 -Mode smoke

# 打包校验 + 发版说明校验 + 版本三处一致性检查
python -X utf8 webnovel-writer/scripts/validate_plugin_package.py
python -X utf8 webnovel-writer/scripts/validate_release_notes.py
python -X utf8 webnovel-writer/scripts/sync_plugin_version.py --check

# CLI 预检（替换 <book-root> 为实际书项目路径）
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "<book-root>" preflight
```

## 目录结构

```
webnovel-writer/              ← 外层仓库根（marketplace.json 双位置：根 + .claude-plugin/）
└── webnovel-writer/          ← 内层插件本体（.zcode-plugin 清单）
    ├── .zcode-plugin/        ← plugin.json（组件声明 + mcpServers + userConfig）
    ├── skills/               ← 8 个 skill
    ├── agents/               ← 4 个子代理
    ├── commands/webnovel/    ← 13 个 /webnovel:* 斜杠命令（薄壳）
    ├── hooks/                ← 4 个 hook 脚本 + hooks.json（${ZCODE_PLUGIN_ROOT}；SessionStart 会写 .webnovel/ journal）
    ├── mcp/                  ← webnovel MCP server（stdio 只读查询 ×12）+ tests
    ├── scripts/              ← 统一 CLI webnovel.py + data_modules
    └── references/ templates/ dashboard/ evals/
```

⚠️ 插件本体在内层目录；装机走 marketplace（源=外层仓库根），文件级装卸见
`docs/zcode/zcode-native-adaptation/05-install-reinstall-runbook.md`。

## 当前状态

- 当前版本：v8.1.0（作者主权 + 300 章连贯：六域书仓治理 + MCP 12 只读工具 + 13 条命令；`v8-author` 分支，tag `v8.1.0` 已推送远端）
- MCP 工具面 14 → 12（D-2 乙，2026-09-13）：撤出 `rag_search`（v7 无向量库）与 `context`（已被 `v7-write pack` 取代）；`knowledge` 保留但按书仓形态分流（v7 只答名册级）。
- 领先 master 的提交数**不在此处写死**（N-3：这是个滚动快照，写下的数字第二天就过期）——需要时现算：
  `git log --oneline origin/master..HEAD | wc -l`
- **v6 写链已冻结（frozen-legacy，2026-09-10 退役方案 Phase 1）**：仅维护、不再演进。**新书写章一律走 v7 写链**（`v7-write decision/pack/check/settle`，见 `skills/webnovel-write/SKILL.md`）。**新书用 `book-init` 直接建 v7 书仓**（`python -X utf8 webnovel-writer/scripts/webnovel.py book-init <目录> <书名> --genre <题材>`，播种 book.yaml + 六域骨架，无 v6 遗留）；既有 v6 书项目先迁移：`python -X utf8 webnovel-writer/scripts/migrate_v6_to_v7.py --project-root <v6根> --output <新 v7 书仓>`。v6 代码与测试**保留但不再新增**；Phase 2 已于 2026-09-18 按「冻结而非删除」收口，见 `docs/plans/2026-09-10-v6线退役方案.md` §3.1。
- 上游：lingfengQAQ/webnovel-writer（v6.2.1 起分叉；上游 v7/v8 路线与本仓无关）
- 远程：git@github.com:lgq-opc/webnovel-writer.git
- CI：`.github/workflows/plugin-tests.yml`（push master/v8-author 与 PR 按 scripts/mcp/dashboard 路径触发全量 pytest + 四校验脚本；依赖按 `requirements.lock` 锁定）
- ZCode 装机：marketplace `webnovel-writer-marketplace` → 本仓库根（directory 源）
- 当前待办入口：~~`docs/plans/2026-09-10-v6线退役方案.md`~~ **该方案已于 2026-09-18 按六条裁决收官**（权威口径见方案 **§3.1**：dashboard 对 v7 冻结下线 / RAG 正式下线 / `knowledge` 名册级定为正式 / context 链现在冻结、目标退役 / doctor 的 v6 体检保留 / Phase 2 冻结收口）。同日 `d075fdf` 的「选项 A 四项一律不接不删不改造」简写已作废。§3.1 第 ① 条对外口径、第 ② 条技能改指 `extract-context` → `v7-write pack` 均已落地。两份 0915 设计返工（`t-20260913-b673` / `t-20260913-25f8`）已按评审必改改完。剩余：D-4 装机验证（`t-20260913-012e`）、context 链级联删除（改指完成后另开）、D-5（R16/R17/R18）。以下三份**已清空或降为历史**：`docs/TODO-from-v8-author-review.md`（2026-09-12 实测 24 项全 `[x]`）、`docs/zcode/v8-gap-review-3rounds/README.md`（P1-1~P4-3 全 ✅，2026-09-04 收官）、`docs/plans/2026-08-25-status-and-pending-work.md`（superseded）。现状截面见 `docs/reports/2026-09-12-需求与设计对账.md`

## OpenCode 工作区规则：任务状态必须与代码同步

- 本项目的代码、测试结果和 Git 提交记录是状态判断的事实依据；计划、审计和清单文档不能单独证明功能已完成。
- 每个 OpenCode 任务 / todo 必须写清 WHERE、HOW、WHY、EXPECTED RESULT，并在任务开始前核对 `git status`、相关代码和现有测试。
- 文档状态统一使用：`[x]` 已完成且有代码/测试证据，`[~]` 部分完成并注明剩余项，`[ ]` 未完成，`[blocked]` 被明确阻塞，`[superseded]` 被新方案取代。
- 完成代码、修复或迁移后，必须在同一任务中更新对应清单和计划的状态、证据（文件/测试/commit）及剩余工作；不得只改代码不改状态文档。
- 发现文档与代码不一致时，先在当前待办入口（见「当前状态」）登记实际状态，再同步相关文档；历史方案只保留设计背景。方案集（`docs/zcode/<任务名>/`）的 spec 每个 F-项都必须在 plan 里有对应 T-项或显式「不覆盖」声明，宣告「全队列完毕」前先做 F→T 反向对账。
- `[x]` 只能在相关测试或可复现命令通过后标记；未验证的实现只能标为 `[~]` 或 `[ ]`。提交前再次检查文档状态、代码差异和测试结果。
- 不新增未被项目要求支持的状态文件或 `code_state` 字段；使用 OpenCode 原生 todo 状态和 Git/测试证据即可。

## 注意事项

- Windows 下运行 Python 脚本必须加 `-X utf8` 避免 GBK 编码问题
- 中文 commit message 用 UTF-8 文件 + `git commit -F` 方式提交
- `.tmp/` 和 `.tmp_story_system_engine/` 是临时目录，已在 .gitignore 中
- 宿主产出文档按宿主分目录：ZCode 方案集放 `docs/zcode/<任务名>/`，Cursor 产出（审查报告 / 分析 / 计划）放 `docs/cursor/<任务名>/`，OpenCode 产出（审阅报告 / 分析）放 `docs/opencode/<任务名>/`；跨宿主的正式产出仍按工作区分级归 `docs/{research,reports,plans,decisions}/`
- ADR 约定：重大架构决策分散记录在各 `docs/zcode/<任务名>/` spec 的「理由」小节，不单独抽 ADR 文件；`docs/decisions/` 只收跨任务的里程碑级决策——检索不到 ADR 不代表决策缺失
- 修改插件组件（skills/hooks/commands/MCP）后需重启 ZCode 会话生效；改 scripts/*.py 则即时生效（每次调用都是新进程）
