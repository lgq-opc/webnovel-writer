# Spec：阶段二章纲一致性闸（P2-1 / P2-2）

> 状态：**已批准**（Human 2026-09-04；方案 A）
> 依据：`docs/zcode/v8-gap-review-3rounds/README.md` 阶段二 P2-1 / P2-2；`docs/zcode/webnovel-copilot-300/06-data-design.md` §2、§12。

## 1. 背景

详细大纲目前有三类有效路径：

1. v8 规范目标：`大纲/卷纲/第NN卷-详细大纲.md`；
2. 迁移器旧产物：`大纲/卷纲/第NN卷.md`；
3. v6 平铺路径：`大纲/第N卷-详细大纲.md`（含空格变体）。

读取逻辑散落在 `v7_write.py`、`chapter_outline_loader.py`、`chapter_paths.py`，标题正则也不一致。`create_chapter_batch` 不读取详细大纲，现有 `self_check_batch` 只有节点、字数、承诺前缀、批内时间锚重复四项 warning，无法阻止不存在的承诺 ID 和跨批时间倒流。

## 2. 目标

1. 统一详细大纲规范路径、兼容路径和章节标题/正文节选解析。
2. 让 plan skill 与 v6→v7 迁移器写规范路径。
3. 建章纲卡时执行标题、承诺、时间、战力、人物五类一致性检查。
4. 仅对可证明的硬冲突阻断；warning 仍允许生成 draft 卡。
5. 保持旧书仓、旧章纲卡和现有 Python 调用兼容。

## 3. 非目标

- 不删除或自动合并 fantasy01 的重复详细大纲；留给 P3-3。
- 不迁移节拍表、时间线、总纲写回 JSON 的路径；本任务只统一“详细大纲”。
- 不从 `节点` 自由文本猜测人物。
- 不改变 `confirm_chapter_batch` 的人工确认语义。
- 不把 v6 write-gate 移植到 v7。

## 4. 方案

### 4.1 被否方案

| 方案 | 内容 | 裁决 |
|---|---|---|
| A（采纳） | 新增共享路径/标题解析器；P2-1 与 P2-2 作为一个垂直交付 | 路径统一是标题闸前置，复用清晰 |
| B | 在 `create_chapter_batch` 内复制路径和正则 | 否决：形成第四份解析逻辑 |
| C | 同时做自动去重/搬迁 CLI | 否决：内容判别有破坏风险，超出 P2-1 |

### 4.2 共享详细大纲解析器

新增 `scripts/data_modules/outline_paths.py`：

```python
canonical_detailed_outline_path(root: Path, volume: int) -> Path
resolve_detailed_outline(root: Path, volume: int) -> Path | None
extract_chapter_heading(text: str, chapter: int) -> str | None
extract_chapter_section(text: str, chapter: int) -> str | None
```

`resolve_detailed_outline` 候选顺序：

1. `大纲/卷纲/第{NN}卷-详细大纲.md`（唯一规范路径）；
2. `大纲/卷纲/第{NN}卷.md`（迁移器旧产物，只读兼容）；
3. `大纲/第{N}卷-详细大纲.md` 及既有空格变体（v6 只读兼容）。

标题解析兼容：

- H2 / H3；
- 阿拉伯数字或既有中文章号解析能力；
- `第N章：标题`、`第N章: 标题`、`第N章 标题`。

新写入必须使用 H2 `## 第N章：标题`，兼容格式不反向改写。

以下消费者改用共享解析器：

- `v7_write._sec_outline_excerpt`；
- `chapter_outline_loader` 的卷详细大纲定位/章节节选；
- `chapter_paths.extract_chapter_title`；
- `chapter_outline_batch` 的标题检查。

`volume_reconcile` 的 `第NN卷.md` 仍代表卷详案，不在本任务改动。

### 4.3 写入方统一

- `migrate_v6_to_v7._migrate_outlines`：v6 `第N卷-详细大纲.md` 写到规范 `大纲/卷纲/第NN卷-详细大纲.md`，不再剥后缀。
- `skills/webnovel-plan/SKILL.md`：详细大纲输出路径改为规范路径；标题格式固定为 `## 第N章：标题`。
- 对应 prompt integrity 测试同步更新，防止路径回漂。

### 4.4 章纲卡 schema

`人物` 加入 `LIST_FIELDS` 与 `_FIELD_ORDER`，但不加入 `REQUIRED_FIELDS`：

```yaml
人物: ["苏小白", "林知夏"]
```

- 新卡应显式填写本章登场/被提及的重要人物。
- 旧卡无 `人物` 字段时兼容，不警告。
- 未知人物只 warning，允许作者后续补名册或保留新角色。

### 4.5 结构化校验

新增 `scripts/data_modules/chapter_outline_validate.py`：

```python
validate_chapter_batch(project_root, cards) -> {
    "errors": [finding, ...],
    "warnings": [finding, ...],
}
```

finding 至少含：

```json
{
  "code": "promise_not_found",
  "chapter": 43,
  "message": "章43 承诺 F-999 不存在于账本",
  "details": {}
}
```

检查和等级：

| 检查 | 数据源 | 等级 |
|---|---|---|
| 标题与详细大纲不一致 | `outline_paths` | warning |
| 缺详细大纲/找不到本章标题 | `outline_paths` | warning |
| 承诺 ID 不存在 | `promise_ledger.load_entries`；引用取冒号前 ID | **error** |
| 跨批时间倒流 | 已 confirmed 章纲卡 + 已定稿正文 `书内时间` 的最大可解析日 | **error** |
| 时间文本无法解析 | `continuity_check.parse_anchor_day` | warning |
| 战力事件未命中任一境界名 | `power_anchor.load_anchor()["境界链"][].名`，子串匹配 | warning |
| 缺力量锚点但卡含战力事件 | `设定/力量锚点.yaml` | warning |
| `人物` 不在名册正名/别名 | `continuity_check.load_known_names` | warning |

时间语义：

- 只比较可解析的 `第 N 天` / `第 N 日`；
- 同日允许；小于历史最大日才是倒流；
- 历史来源只取章节号小于本批最小章号的 confirmed 卡和定稿正文；
- draft 卡不进入历史基线；
- 批内仍保留现有“完全相同时间锚重复”warning。

### 4.6 `create_chapter_batch` 行为

1. 保留现有字段、批大小、章号重复等前置硬校验。
2. 运行现有 `self_check_batch(cards)`，其字符串结果作为 warning。
3. 运行新结构化校验。
4. 有 error：返回 `ok=False, error="consistency_gate", errors, warnings, checks`，**不建目录、不写卡、不写 journal**。
5. 无 error：照常写 draft 卡，返回 `ok=True, errors=[], warnings, checks`；`checks` 保留为 warning 文本列表兼容旧调用者。

`self_check_batch(cards)` 的签名和返回类型不变，避免破坏既有测试/API。

## 5. 数据与兼容

- `chapter-card/1` 不升版本：`人物` 为可选扩展字段。
- 规范写入与兼容读取分离；本任务不自动移动用户文件。
- 同时存在规范文件和旧文件时只读规范文件，不合并内容。
- 旧迁移测试改为断言规范后缀保留；另增旧路径只读兼容测试。

## 6. 成功标准

1. fantasy01 风格详细大纲 `## 第43章：夜袭` 建同标题卡，无标题 warning。
2. 卡标题改错时 `ok=True` 且 warning 指明期望/实际标题。
3. `F-999` 不存在时 `ok=False`，卡与 journal 均零写入。
4. 历史最大时间为第 42 日、新卡第 41 日时 `ok=False`；不可解析文本只 warning。
5. 未知人物和未知境界均 warning，不阻断。
6. 迁移器输出 `大纲/卷纲/第01卷-详细大纲.md`。
7. v7 context pack 与 v6 outline loader 均能读取规范路径，并继续兼容旧路径。
8. 既有测试全绿，项目覆盖率不低于 80%。

## 7. 约束

- TDD：每类行为先有失败测试。
- 仅修改本任务所需文件，不顺手清理 fantasy01 重复文件。
- Windows 命令统一 `python -X utf8`。
- 实施计划必须把 P2-1/P2-2 每条验收原文映射到测试。
