---
name: webnovel-learn
description: 从当前会话提取成功写作模式，经 learn 命令归入作者模型（作者/author_model.md）
allowed-tools: Read Bash
argument-hint: "[要记住的写作经验]"
---

# /webnovel-learn

## Project Root Guard（必须先确认）

- 必须在书仓根执行（v7 书仓的标志是 `book.yaml`；v6 遗留仓为 `.webnovel/state.json`）
- 用统一入口解析项目根，避免写错目录：

```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT:?}/scripts"
export PROJECT_ROOT="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
```

## 目标

把本次会话里作者认可的写法提炼成**可复用的作者模型条目**（节奏偏好 / 雷点 / 修改习惯 / 本书特定要求），
经 `learn` 命令归入 `作者/author_model.md`——**v7 不再有 `project_memory.json`**（该文件随 v6 退役 Phase 2 一并删除）。

## 执行流程

学习闭环是**两段式：先归纳出建议，作者确认后才回写**——不得一步直写作者模型。

1. **归纳**：卷级归纳从 `.webnovel/journal` 之外的真源读——v7 的作者行为记录在 `作者/journal.jsonl`：

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" learn --from-journal --volume {volume_id}
```

   产出 `作者/author_model-建议.md`（含证据）。当前章节号取自 `定稿/正文/` 的最大章号或
   `.cache` 的 `chapters` 表；取不到时不阻断。

2. **作者确认**：把建议读给作者看，明确列出「将要写进作者模型的条目」。**作者未确认不得 apply。**

3. **回写**：作者确认后执行

```bash
python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${PROJECT_ROOT}" learn apply --suggestion "${PROJECT_ROOT}/作者/author_model-建议.md"
```

   双层回写：项目层 `作者/author_model.md` + 用户层 `作者/跨书偏好.yaml`（跨书统计）。

4. **查看**（可选）：`learn show` 打印当前作者模型与偏好。

## 约束

- **不得手工编辑或拼接** `作者/author_model.md` / `作者/跨书偏好.yaml`——一律经 `learn apply`，
  否则作者的改动不会走 journal 留痕。
- 不删除旧条目，仅追加。
- 追加前先 `learn show` 或 Read 现有 `作者/author_model.md`；同义条目跳过并告知作者，部分相似不去重。
- 与写作无关的闲聊、一次性偏好不入库。

## 成功标准

- 归纳段：`作者/author_model-建议.md` 存在且含证据。
- 回写段：作者确认后 `作者/author_model.md` 出现新条目，且 `learn apply` 输出 `status: success`。

## 失败恢复

| 故障 | 恢复方式 |
|------|---------|
| `作者/` 目录不存在 | `book-init` 已建；缺失则先跑 `doctor` 查六域骨架，不手工 `mkdir` |
| `作者/journal.jsonl` 为空 | 说明尚无作者行为记录，告知作者「先写几章再学」，不报错退出 |
| 建议文件为空 | 本轮无可复用模式，如实告知，不产出空 apply |
| `learn apply` 报错 | 保留建议文件原样，把报错原文给作者；不得改用手写绕开 |
