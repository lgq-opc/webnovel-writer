---
name: webnovel-write
description: 产出可发布章节（v7 书仓写链）：决策卡/上下文包 → 起草 → 机检 → 审查 → 润色与文笔检测 → settle。v6 写链已冻结，v6 项目先迁移。
allowed-tools: Read Write Edit Grep Bash Agent AskUserQuestion
argument-hint: "[章号] [--fast|--minimal]"
---

# 写章流程（v7 写链）

> **v6 写链已冻结**（2026-09-10，退役方案 Phase 1）：仅维护、不再演进；**新书写章一律走本技能描述的 v7 写链**。
> v6 项目请先迁移（见「准备：书仓形态判定」）。

## 目标

产出可发布章节到 `定稿/正文/{NNNN}-{title}.md`。默认 2000-2500 字，用户/大纲另有要求时从之。

## 模式

| 模式 | 流程 |
|------|------|
| 默认 | 决策/上下文包 → 起草 → 机检 → 审查 → 润色与文笔检测 → settle |
| `--fast` | 同上，但审查只查 setting/timeline/continuity |
| `--minimal` | 不调 reviewer（写 no-review artifact）→ 润色仅排版 → 跳过文笔检测 → settle |

## 硬规则

- 禁止并步、跳步、伪造审查
- 必须使用 `Agent` 工具调用指定 subagent；不得用主流程口头代替 subagent 输出
- 审查只跑一轮；blocking issue 定点修复或经用户裁决后才进 settle
- 失败只补跑失败步骤，不回退
- 参考资料按步骤按需加载

## 优先级

用户要求 > 状态机硬门槛 > 项目约束（总纲/设定/记忆）> skill 流程 > reference 建议

## CSV 检索（起草按需）

```bash
python -X utf8 "${SCRIPTS_DIR}/reference_search.py" --skill write --table {表名} --query "{关键词}" --genre {题材}
```

触发条件（M5/T26 扩容 5→9，R8）：新角色→命名规则，战斗→场景写法，多角色对话→写作技法，情感描写→写作技法，高频桥段→场景写法，高潮/打脸/兑现场景→爽点与节奏，进入已知桥段（章纲标注或决策卡命中）→桥段套路，新配角/关系冲突→人设与关系，金手指/设定展开→金手指与设定。

## 执行流程

### 准备：预检

```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT:?}/scripts"
export SKILL_ROOT="${CLAUDE_PLUGIN_ROOT:?}/skills/webnovel-write"
```

S9/D2 三查合一：preflight + where + placeholder-scan 一次往返完成（占位符存在时退出码 1，输出含 `PROJECT_ROOT=` 行）：

```bash
PREFLIGHT_ALL="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" preflight --all)"
echo "$PREFLIGHT_ALL"
export PROJECT_ROOT="$(echo "$PREFLIGHT_ALL" | grep '^PROJECT_ROOT=' | head -1 | cut -d= -f2-)"
```

### 准备：书仓形态判定

`${PROJECT_ROOT}/book.yaml` 存在 → 本书是 v7 story-repo，按下文流程走。

**不存在**时分两种：
- **全新的书** → 用 `book-init` 直接建 v7 书仓（不需要先建 v6 再迁移）：

  ```bash
  python -X utf8 "${SCRIPTS_DIR}/webnovel.py" book-init "<新书目录>" "<书名>" --genre "<题材>" --target-words <总字数> --target-chapters <总章数>
  ```

- **既有的 v6 书项目** → v6 写链已冻结，先迁移再回来：

  ```bash
  python -X utf8 "${SCRIPTS_DIR}/migrate_v6_to_v7.py" --project-root "<v6 项目根>" --output "<新的 v7 书仓目录>"
  ```

### 1. 决策卡与上下文包

决策 JSON 字段以 `docs/guides/v7-write-path.md` §3 为准。需要写前 research 时，用 `Agent` 工具按注册名调 `webnovel-writer:context-agent` 起草决策 JSON（可选步骤）——但**不得由它替代上下文包**：起草只以 `pack` 产出的包为依据。

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" v7-write decision --json "${PROJECT_ROOT}/工作区/决策-{chapter_num}.json"
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" v7-write pack --chapter {chapter_num} --json "${PROJECT_ROOT}/工作区/决策-{chapter_num}.json"
```

上下文包落 `工作区/上下文包-{NNNN}.md`，含：决策卡 / 本章章纲节选 / 本章应推进（承诺账本）/ 作者修改未消费（stale）/ 前情摘要 / 上一章结尾 / 本章实体 / 主角卡 / 视角纪律（pov ≠ 主角时）/ 名册清单 / 素材装配 / 文风宪法 / 文风锚点 / 作者模型 / 读者信号。起草只以此包为依据；stdout 的 `used=` 与包内缺节属正常降级（对应域为空），不是错误。

> `pack` **必须**带 `--json`。既无 `--json` 又无对应决策卡时会直接报错退出（不会静默产出缺决策卡的降级包）。

### 2. 起草

只根据上下文包起草，草稿写 `工作区/草稿-{NNNN}.md`。只输出纯正文，无占位符。有结构化节点时围绕 CBN→CPNs→CEN 展开。中文思维写作。

**多稿择优（webnovel-copilot-300 M5/T24，R3/D0-4）**：默认 `--drafts 2`（`--fast/--minimal` 保持 1）：
1. 每稿独立起草（同上下文包，稿间互不可见）；
2. 按 `references/draft-rubric.md` 对每稿自评（六维 1-5 分 + 一句话理由），逐稿落库
   `webnovel.py drafts record --chapter {N} --draft {i} --scores "..." --rationale "..."`；
3. `webnovel.py drafts choose --chapter {N}` 择优：取均分最高稿进入机检；
   均分 <3.5 时按返回的最弱项定向重写一次（`--rationale "（rewrite_done）..."` 重新登记）；
4. 审查完成后 `webnovel.py drafts link --chapter {N} --score {审查分}` 回填对照（rubric 长期校准）。

### 3. 机检

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" v7-write check --chapter {chapter_num} --draft "${PROJECT_ROOT}/工作区/草稿-{NNNN}.md" --json "${PROJECT_ROOT}/工作区/决策-{chapter_num}.json"
```

退出码 2 = 字数 / 占位符 / 标题 / 承诺未过，回到起草。

### 4. 审查

必须使用 `Agent` 工具调用 `reviewer`，不得由主流程伪造审查 JSON。

Use the Agent tool to run `webnovel-writer:reviewer`.

Task:
- chapter={chapter_num}
- chapter_file=${PROJECT_ROOT}/工作区/草稿-{NNNN}.md
- project_root=${PROJECT_ROOT}
- scripts_dir=${SCRIPTS_DIR}
- 只返回严格的 reviewer schema JSON，不写任何文件。
- 不评分、不口头总结。

reviewer 持受限 `Write`（唯一允许写入的文件）：它自己把审查 JSON 写入 `${PROJECT_ROOT}/.webnovel/tmp/review_results.json`（顶层 `chapter` + `blocking_count`），最终回复只给一行汇总；**主流程只检查文件存在与 schema**，不代写、不重写、不口头替代 artifact。**settle 门禁会读这个文件**：缺失、章号不符或 `blocking_count > 0` 都拒绝。

调用后主流程必须记录 `SubagentRun` 汇总（仅供最终报告使用）：

```json
{
  "name": "reviewer",
  "user_label": "写作检查",
  "status": "completed | partial | failed | skipped",
  "problems": [],
  "auto_handled": [],
  "needs_user_action": false,
  "duration_ms": 0,
  "outputs": []
}
```

reviewer 跳过、失败、输出不完整、`--minimal` 写 no-review artifact、blocking issue、维度跳过或耗时异常，必须写入 `problems` / `auto_handled`，不得在最终报告中静默。

审查只跑一轮，reviewer 只调用一次。`blocking=true` 的问题在不改剧情、不破设定的前提下定点修复后直接进润色，不重新调用 reviewer；确实无法修复的 blocking 问题用 `AskUserQuestion` 让用户裁决（接受当前版本 / 手动修复 / 放弃）。非 blocking issue 交给润色处理。`--fast` 只检查 setting/timeline/continuity。

`--minimal` 不调用 reviewer，但必须**覆盖写入**本章新的 no-review `review_results.json`（禁止复用旧 artifact），使 settle 有有效的门禁输入：

```bash
python -X utf8 -c "import json,os; from pathlib import Path; root=Path(os.environ['PROJECT_ROOT']); ch=int('{chapter_num}'); p=root/'.webnovel'/'tmp'/'review_results.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps({'chapter':ch,'issues':[],'issues_count':0,'blocking_count':0,'has_blocking':False,'summary':'minimal mode: reviewer skipped by user-selected --minimal flow','review_skipped':True,'review_mode':'minimal'},ensure_ascii=False,indent=2),encoding='utf-8')"
```

### 5. 润色与文笔检测

`references/polish-guide.md` 区段读：先 `Grep` 匹配 `^#{1,3} ` 定位锚点行号，再 `Read` 的 offset/limit 取段——主路径取 `## 2. 执行顺序（必须按序）`；Anti-AI 终检单独区段取 `## 2A. Anti-AI 检测细则` 与 `## Phase 1 增补：Anti-AI 规范（7层，原版）`（词库段），不全文读。`references/writing/typesetting.md`、`references/style-adapter.md` 短文件，全文读。

顺序：修复非 blocking issue → 风格适配 → 排版 → Anti-AI 终检。

只改表达不改事实。`anti_ai_force_check=fail` 时不进 settle。`--minimal` 仅排版。

言情/狗血/情感浓度高的章（题材标签或章纲含情感戏）：区段读 `references/writing/desire-description.md`（M5/T26，R7 接线）——亲密戏尺度分级写法与欲念描写技法，润色时按需对照。

**程序化文笔检测（webnovel-copilot-300 M5/T23，R2）**：Anti-AI 终检完成后必须运行

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" prose-check --file "${PROJECT_ROOT}/工作区/草稿-{NNNN}.md" --format json
```

`anti_ai_force_check` 从自报改为**必附 prose_check 结果**——`flagged` 非空时逐项修复命中（或写入 deviation：位置+原因+代价）后复跑至 `flagged: []`（或仅剩已记录 deviation 的提醒级项）；`--fast/--minimal` 可跳过检测但不产出 pass 结论。

### 6. settle

原子提交（含正文 / 章摘要 / 新实体），随后自动刷新 v7 缓存，并落账素材轨迹、文风指纹/采样。

**章末钩子**由决策卡的 `hook_type` 声明（`hook_strength` 可省，缺省 medium）；本章确无钩子时用 `hook_waiver` 写豁免理由——**两者皆空时 `check` 会拒绝**（退出码 2）。settle 把钩子写进正文 front matter，追读力表由随后的缓存刷新从那里重算，**不需要**任何手动落账：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" v7-write settle --chapter {chapter_num} --draft "${PROJECT_ROOT}/工作区/草稿-{NNNN}.md" --json "${PROJECT_ROOT}/工作区/决策-{chapter_num}.json" --summary "{≤200 字章摘要}"
```

退出码 2 = 门禁拒绝，stderr 有 JSON 明细（`review` / `prose` / `materials`）。处理顺序：**改稿 → 重审 → 再 settle**。`materials.unresolved` 非空（素材引用 ID 不存在）只能改决策 JSON 的 `material_refs` 或章纲卡的 `素材引用`，**不可绕过**。仅当作者明确要求发布时，加 `--force-review-bypass "<理由>"`——理由必须来自作者原话，不得由主流程代拟；绕过会写进正文 front matter（`审查绕过:`）与 `作者/journal.jsonl`，最终报告必须如实列出。

> **步骤落账（F4，2026-09-10）**：本流程**不需要**主流程手调 `run-log --append`。
> `v7-write decision / pack / check / settle` **由 CLI 自己落账**——每次执行成功/失败都会往
> `.webnovel/logs/run_last.log` 追加一条 `v7-*` 事件（同章追加、换章自动重开），
> 崩溃后靠最后一条判断卡在哪。起草与审查不经 CLI，才需要主流程自行
> `run-log --event <step> --append`。

## 作者友好过程提示与恢复契约

开始写章前先用作者语言说明本次目标、主要阶段和是否需要守在旁边，不承诺固定耗时。过程提示只说当前在做什么和会产生什么，不直接输出原始 JSON、traceback 或长命令日志；技术详情写入 `.webnovel/logs/run_last.log`：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" run-log \
  --event write-start \
  --payload-json "{\"chapter\": {chapter_num}, \"mode\": \"{mode}\"}" \
  --format text
```

同一时点建立章级计量标记（D1：只读 ZCode 本地用量库 `turn_usage` 表，时间窗聚合主会话 + 全部子代理轮次；非 ZCode 宿主无用量库时自动降级跳过）：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" meter start --chapter {chapter_num}
```

`write-start` 用覆盖模式（清空旧日志开新一次写章）。

少打扰确认策略：默认继续推进；只有创作方向、事实一致性、文件覆盖风险或 blocking issue 无法定点处理时才问。需要用户裁决时给 2-3 个有限选项，并说明每个选项影响。

重复执行同一章时**不得覆盖作者手改**：正文被手动改过、章纲更新晚于正文时，必须停下用有限选项询问（沿用当前草稿 / 重新起草 / 只查看状态），由作者决定。

卡住时必须说明卡点、已完成内容和恢复建议：例如“草稿和审查结果已保留，落定失败；修掉门禁问题后重新运行 `/webnovel-write {chapter_num}` 会从 settle 继续”。不可恢复故障才在最终报告提示 `.webnovel/logs/run_last.log`；平时只保留日志，不打扰作者。

收尾必须调用作者报告 helper，优先以 helper 输出组织最终回复：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" user-report \
  --stage write \
  --chapter {chapter_num} \
  --format text
```

随后关账章级计量，并把得到的一行「本章总消耗」（总计 + 新增 tokens，含子代理）原样并入最终回复，作为本验收口径的章级成本数据：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" meter stop
```

## 充分性闸门

1. 草稿文件存在且非空
2. `v7-write check` 通过（退出码 0：字数 / 占位符 / 标题 / 承诺均过）
3. 审查已落库：`.webnovel/tmp/review_results.json` 存在、章号相符且 `blocking_count == 0`（`--minimal` 写 no-review artifact）
4. `prose-check` 的 `flagged` 为空，或仅剩已记录 deviation 的提醒级项（`--minimal` 除外）
5. `v7-write settle` 退出码 0（门禁 `review` / `prose` / `materials` 全部通过）
6. 章摘要非空且 ≤200 字

## 失败恢复

草稿不合格 → 重跑机检并按提示改稿。审查缺失/章号不符 → 重跑审查。`materials.unresolved` → 改决策 JSON 的 `material_refs` 或章纲卡的 `素材引用`。settle 门禁拒绝 → 改稿 → 重审 → 再 settle。

`settle` 报「该书仓不是 git 仓库」→ 这是一本用 `book-init --no-git` 建的书，`settle` 默认要提交但无处可提交。二选一并在报告里如实告诉作者：① 在书仓执行 `git init` 后重跑（此后每章自动提交）；② 本次加 `--no-commit`（只落盘、不提交，每次都需带）。**不要**替作者静默选择——这关系到他要不要版本控制。

## 作者友好最终报告契约

最终回复必须面向作者，不输出原始 JSON、traceback 或长命令日志。使用固定三段式，并以一句总状态开头：

```text
总状态：已完成 / 部分完成 / 需要你处理 / 未完成。

一、产生的文件与完成情况
- ...

二、过程中遇到的问题与异常耗时
- 已自动处理：...
- 建议确认：...
- 必须处理：...

三、下一步建议
- ...
```

必须汇报：
- 正文文件路径（`定稿/正文/{NNNN}-{title}.md`）。
- 决策卡与决策 JSON（`工作区/决策卡-{NNNN}.md`、`工作区/决策-{chapter_num}.json`）。
- 上下文包（`工作区/上下文包-{NNNN}.md`）与草稿（`工作区/草稿-{NNNN}.md`）。
- `.webnovel/tmp/review_results.json`。
- settle 的后置落账结果（素材轨迹 / 文风指纹 / 追读力 各自 ok / skipped / error）——失败或跳过**不得在最终报告中静默**，必须写入问题清单。
- 是否可以继续写下一章。

状态规则：
- settle 门禁拒绝（退出码 2）、任一机检未过时，最终状态不得写“已完成”。
- `--fast` 和 `--minimal` 的跳过项必须说明；`--minimal` 跳过审查时归入“已自动处理”或“建议确认”，不得假装已完成完整审查。
- 使用 `--force-review-bypass` 时必须在报告中如实列出，并附作者原话给出的理由。

异常分类：
- 已自动处理：settle 后置落账某项 skipped/error 但不影响正文落定、旧 no-review artifact 被本章新 artifact 覆盖。
- 建议确认：新增角色名 / 设定名、低置信歧义但不阻断、非阻断审查建议。
- 必须处理：blocking issue 未裁决、`materials.unresolved`、settle 门禁拒绝。

下一步建议必须使用任务化语言 + 可复制命令，例如：

```text
- 接下来可以写下一章：
  /webnovel-write {next_chapter}
```

不写 token 统计（章级消耗那一行按上文如实并入即可）；如需排查故障，只给日志路径或建议运行 `/webnovel-doctor`。
