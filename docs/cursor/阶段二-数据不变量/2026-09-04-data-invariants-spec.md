# Spec：阶段二数据不变量校验器（P2-3）

> 状态：**已批准**（Human 2026-09-04；方案 A）
> 依据：`docs/zcode/v8-gap-review-3rounds/README.md` 阶段二 P2-3；`docs/zcode/webnovel-copilot-300/06-data-design.md` §12。

## 1. 背景

`06-data-design.md` §12 定义六条数据不变量，但当前没有统一校验器或 `webnovel.py invariants`。现有代码只有可复用的局部能力：

- journal 枚举字段校验、watermark、待语义补全；
- 素材引用实时解析与定版 manifest；
- 境界链校验、战例账本、定稿正文探测；
- 承诺条目写入时状态迁移校验；
- `RuntimeContractBuilder` 的 runtime contract 重建；
- stale 的读写与消费。

因此当前无法一次回答“六条是否成立”，后续 P4-1 doctor 也没有可复用的数据源。

## 2. 目标

1. 新增只读 `invariant_check.py`，逐条输出 §12 六项结论。
2. 新增统一 CLI `webnovel.py invariants --format text|json`。
3. 每项结论使用 `pass/fail/warn/skip`，不把“无法证明”伪装为通过。
4. 为 P4-1 doctor 提供稳定、无打印副作用的 Python API。
5. 为 stale 增加可计算卷龄的兼容字段 `since_chapter`。

## 3. 非目标

- 不在本任务内接入 doctor；P4-1 直接复用本模块。
- 不自动修复任何发现。
- 不修改素材、条目、合同或定稿正文。
- 不给纯 v7 书仓补造 `.story-system`。
- 不实现完整历史事件溯源数据库；只基于现有正典文件和 journal/演化记录判定。

## 4. 方案

### 4.1 被否方案

| 方案 | 内容 | 裁决 |
|---|---|---|
| A（采纳） | 独立 `invariant_check.py`，六项纯函数 + 汇总 API + CLI | 可被 P4-1 直接复用；一次命令满足验收 |
| B | 分散扩展 author/material/power/promise 各 CLI | 否决：无统一报告，doctor 仍需二次编排 |
| C | 直接内嵌到 doctor | 否决：P4-0 未完成时纯 v7 跑不到，也违反 P2-3 独立 CLI |

### 4.2 公共 API

新增 `scripts/data_modules/invariant_check.py`：

```python
SCHEMA_VERSION = "invariants/1"

check_journal(root: Path) -> dict
check_material_trajectory(root: Path) -> dict
check_power_anchor(root: Path) -> dict
check_promise_states(root: Path) -> dict
check_contract_rebuild(root: Path) -> dict
check_stale_age(root: Path) -> dict

run_invariants(root: Path, *, only: list[str] | None = None) -> dict
format_text(report: dict) -> str
main(argv: list[str] | None = None) -> int
```

单项结果：

```json
{
  "id": "inv-1-journal",
  "title": "journal 无未分类事件积压",
  "status": "pass|fail|warn|skip",
  "findings": [
    {"code": "unclassified_event", "ref": "event#42", "path": "...", "message": "..."}
  ],
  "counts": {},
  "repair": "..."
}
```

汇总结果：

```json
{
  "schema_version": "invariants/1",
  "ok": false,
  "project_root": "...",
  "summary": {"pass": 3, "fail": 1, "warn": 1, "skip": 1},
  "invariants": []
}
```

`ok` 仅在无 `fail` 时为 true；`warn/skip` 不使 CLI 失败。

### 4.3 Inv-1：journal 无未分类事件积压

复用 `author_journal.read_journal`、`validate_journal`、`pending_semantic`、`read_watermark`。

- 非法 actor/action/domain/change_kind：fail。
- 普通事件 `domain == "其他"`：fail。
- 明确 migration 汇总事件豁免：`path == "(bulk)"` 且 `impact` 含 `"migration"`。
- `edit` 事件 summary 为空且尚无 enrich：warn（规范允许 summary 异步）。
- watermark 小于 journal 事件数：记录 counts/信息，但不单独 fail；它表示消费水位，不等于未分类。
- 无 journal：pass（零积压），counts 全零。

### 4.4 Inv-2：素材使用轨迹与来源一致

复用 `material_usage.read_trajectory`、`material_store` 路径/CSV 读取能力。

- `定版版本 == "live"`：条目 ID 必须仍存在于任一 `素材/活/*.csv`，否则 fail。
- `定版版本 == "vNN"`：
  1. `素材/定版/vNN/manifest.json` 必须存在且可读；
  2. 条目必须存在于该目录某个 CSV；
  3. 该 CSV 文件名必须在 manifest `source_files[].path` 中。
- 未知版本格式、空条目 ID、坏 JSON 行：fail；finding 指明轨迹行号。
- 无轨迹：pass（零引用）。

manifest 只能证明文件快照，条目存在性通过同目录 CSV 补证。

### 4.5 Inv-3：力量锚点战例与境界链

复用 `power_anchor.load_anchor`、`validate_chain` 与 `dual_format_guard.has_v7_settled_chapter`。

- 无 `设定/力量锚点.yaml`：skip。
- 每个 `战例账本[].章` 必须有 `定稿/正文/{NNNN}-*.md`：缺失 fail。
- 境界链序号单调、名称唯一：复用 `validate_chain`；任一问题 fail。
- 战例章号无法转 int：fail。

本项不重复 `power_check` 的越级依据/通胀业务规则。

### 4.6 Inv-4：承诺条目状态机与 retcon 双记录

复用 `promise_ledger.load_entries`、`STATUS_VALUES` 和 `LEGAL_TRANSITIONS`，并读取 journal 与 `演化/retcon-vNN-*.json`。

- 每个条目状态必须在 `STATUS_VALUES`：否则 fail。
- `已回收` 必须有合法 `回收章`，且不早于 `埋设章`：否则 fail。
- `open/推进中/逾期` 不应带 `回收章`：带值则 fail。
- `作废` 条目按 `埋设章` 与 `book.yaml` `卷规模`（默认 50）推算所属卷；同卷必须同时存在：
  - journal `action=retcon` 且 path 指向该卷定版；
  - `演化/retcon-vNN-*.json`。
  缺任一 fail。
- 现有 `update_status` 的合法迁移表保持不变；本任务不改写历史。

由于当前 journal 不逐条记录“from→to”，校验器不声称能重放全部历史迁移，只验证当前状态约束与 `作废` 的双记录前提。

### 4.7 Inv-5：`.story-system` runtime contract 重建对账

- 无 `.story-system/`：skip（纯 v7 正常状态）。
- 有目录但缺/坏 `MASTER_SETTING.json`：fail。
- 对每个已存在 `.story-system/reviews/chapter_NNN.review.json`：
  1. 用 `RuntimeContractBuilder(root).build_for_chapter(N)` 重建 volume/review；
  2. 与磁盘 `.story-system/volumes/volume_NNN.json`、review JSON 做规范化对象比较（忽略 JSON 缩进/键序，不忽略业务字段）；
  3. 缺文件或对象不等均 fail。
- seed 层 `MASTER_SETTING`、`chapter brief`、`anti_patterns` 只做现有 schema/JSON 合法性校验；它们依赖原始 query/route 生成过程，现有仓库不能无损重建，报告中以 `counts.seed_schema_checked` 明示，不伪称完成重编译。
- 没有任何 review runtime contract 时：warn（目录存在但无可重建样本），不是 pass。

### 4.8 Inv-6：stale 不超过一卷

现有 stale 只有 ISO `since`，无法换算章节。采用 Human 批准的兼容演进：

- `author_journal.mark_stale` 新建项时增加可选 `since_chapter`，值为当时最大定稿章号（无定稿则 0）。
- 同 target 覆盖时视为新 stale，刷新 `since` 与 `since_chapter`，保持现有语义。
- 当前章 = 最大定稿章号；卷规模 = `book.yaml` `卷规模`，缺失/非法时 50。
- 未消费项满足 `current_chapter - since_chapter > 卷规模`：fail。
- 旧项无 `since_chapter`：warn，finding code=`unknown_stale_age`。
- 未消费但未超一卷：pass；已消费项忽略。

新增共享的小函数读取最大定稿章号，避免在多个检查中复制 glob 规则。

### 4.9 CLI

`webnovel.py` 新增：

```text
webnovel.py --project-root <book> invariants [--format text|json] [--only inv-1,inv-2,...]
```

- 根解析使用 `_resolve_root_lenient`，纯 v7 `book.yaml` 书仓可直接运行，不依赖 P4-0。
- text 首行：`OK invariants: 6 checked` 或 `ERROR invariants: N failed`；其后每项一行。
- JSON 输出完整 report。
- exit 0：无 fail；exit 1：至少一个 fail；不用 exit 2（2 保留写入门禁）。
- `--only` 主要供单测与后续 doctor 定点复用；未知 ID 参数错误。

## 5. 数据与兼容

- 保持 `stale/1`：`since_chapter` 是可选字段，不升 schema。
- 校验器只读；唯一写入变化发生在未来调用 `mark_stale` 时补充字段。
- 旧 stale 不回填、不猜测，明确 warn。
- finding 不写绝对秘密数据，只记录相对路径、ID、章号和错误摘要。

## 6. 成功标准

1. 六项检查恒各有一条结果，不因数据缺失静默消失。
2. fantasy01 执行 `invariants --format json` 输出六项 `status` 与汇总；纯 v7 合同项为 skip。
3. journal 普通 `domain=其他` 被 fail；migration 汇总豁免；待语义补全只 warn。
4. live 轨迹丢失条目、vNN 缺 manifest/CSV/manifest 文件项均被 fail。
5. 战例章号无定稿正文、境界链不单调均被 fail。
6. 作废条目缺 journal 或演化任一 retcon 记录被 fail。
7. runtime review/volume contract 被篡改后重建对账 fail；纯 v7 无 `.story-system` skip。
8. 新 stale 自动带 `since_chapter`；超过卷规模 fail；旧项 unknown-age warn。
9. CLI 退出码符合 0/1 约定。
10. 全量测试通过，覆盖率不低于 80%。

## 7. 约束

- TDD：每条不变量至少一个 pass 与一个 fail/warn/skip 用例。
- 不复用私有函数时复制复杂逻辑；若需素材 CSV/卷规模/最大章号解析，提取最小公共 helper。
- 不执行自动修复、冻结、retcon、合同持久化或 git 操作。
- 实施计划必须逐字引用 §12 六条和 P2-3 验收“fantasy01 跑出六条各自结论”。
