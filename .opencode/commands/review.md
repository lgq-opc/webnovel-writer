---
description: 只读审阅本项目（P0/P1/P2 分级 + 文件:行号 证据）
---
# 注意：不要设 agent: plan —— 它是只读代理，产不出报告文件。
# 若要减小主上下文污染，另加 subtask: true（可选）。
当前分支与近期提交：
!`git log --oneline -20`
工作区状态：
!`git status --short`

# 全项目只读审阅（Architectural 档）

本任务 = 全项目只读审阅。点名技能：code-review。

## 第一步：复述与边界确认
开工第一句复述「审什么、依据哪份文件」，并先确认以下边界，确认不了就停下来问：
- 项目根 = 本仓库根（含 marketplace.json、opencode.json）
- 插件本体在同名内层目录 webnovel-writer/（skills、agents、commands、hooks、mcp、scripts 都在内层）
- 当前分支、最近 20 条提交、git status 是否干净

## 事实源优先级（不可颠倒）
代码 + 测试实跑输出 + git 记录 > 文档声称。
计划/审计/清单文档单独不能证明功能已完成。文档标 [x] 而代码里没有实现 = P0。

## 范围与不计入项
- v6 写链是 frozen-legacy（2026-09-10 起只维护不演进），v6 缺 v7 特性不算缺陷
- 不比对上游 lingfengQAQ/webnovel-writer（与本仓 v7/v8 路线无关）
- 不审 .tmp/、__pycache__/、.opencode/node_modules/、dashboard 预打包 dist/

## 必跑验证（引用真实输出，禁止"应该通过"）
```powershell
$env:PYTHONUTF8=1; python -X utf8 -m pytest
python -X utf8 webnovel-writer/scripts/validate_plugin_package.py
python -X utf8 webnovel-writer/scripts/validate_release_notes.py
python -X utf8 webnovel-writer/scripts/sync_plugin_version.py --check
python -X utf8 webnovel-writer/scripts/smoke_v7_newbook.py
```
跑不动的如实说跑不动，不许跳过不报。

## 审阅维度
1. 状态漂移：待办入口 `docs/plans/2026-09-10-v6线退役方案.md` 与现状截面
   `docs/reports/2026-09-12-需求与设计对账.md` 里每个 [x]/[~] 与代码、测试实际对账；
   spec 的每个 F-项在 plan 里是否有对应 T-项或显式「不覆盖」声明——缺对应实现的 [x] 是 P0。
2. 对外承诺的兑现：文档承诺的能力（14 个 MCP 只读工具、13 条命令、六域书仓）在代码里
   是否真有消费者；零引用的承诺要单独标出。
3. v6/v7 双布局路径收口：凡"按路径找文件"的函数是否同时支持
   v6（正文/第NNNN章*.md）与 v7（定稿/正文/NNNN-标题.md）。
   已知风险点：chapter_paths、backup_manager、placeholder_scanner、settings_digest、project_locator。
4. 测试是否测行为而非实现：测试是围绕方案条目建的，还是围绕现有实现建的。
5. 常规维度：正确性、安全性（密钥硬编码）、性能、风格一致性。

## 纪律
- 只读。除最终报告外不改任何文件；不 git add / commit / push；不删文件。
- 每条结论必须附 `文件:行号`。写不出出处的标「未验证」并说明为何没查到——不允许猜测后当结论。
- 区分「我实跑看到的」与「我读代码推断的」，两者分栏。
- 子代理给出的结论，自己核验一遍再写进报告。

## 输出
先给 ≤200 字总体判断（能否发版 / 卡在哪），再给：
一、P0 阻塞（有则必须修）：表格 [# | 位置 | 问题 | 证据（命令输出或文件:行号） | 建议]
二、P1 应尽快修
三、P2 可选优化
四、文档自述的未完成/待定/不做项（逐条列原文编号，只提炼不评价）
五、本次未能验证的部分

报告落盘：`docs/opencode/项目复审/<日期>-项目复审报告.md`
（新建 `docs/opencode/` 宿主分目录，沿用 `docs/zcode/`、`docs/cursor/` 的既有约定）

P0 非空时，禁止出现「可以合并」「可以发版」。
