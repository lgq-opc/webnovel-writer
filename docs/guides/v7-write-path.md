# v7 Story-Repo 写路径使用指南

> 适用：v7 story-repo 仓库（`book.yaml` + `定稿/` 结构，见 [story-repo-spec](../architecture/story-repo-spec-2026-06-10.md)）。
> v6 链路（`/webnovel-write` 全流程）不受本页影响；v7 三脚本位于插件 `webnovel-writer/scripts/` 下，是 v6 命令面之外的新入口。

## 一页流程

```
迁移（一次性）          缓存（可随时删）         写一章（每章循环）
migrate_v6_to_v7  →   v7_cache rebuild    →   v7_write decision → pack → (草稿) → check → settle
```

## 1. 迁移：`migrate_v6_to_v7.py`

```bash
python migrate_v6_to_v7.py --project-root <v6书仓> --output <v7仓路径>
```

- 只读源书仓（零写入）；输出目录已存在则拒绝。
- 生成 `book.yaml`、`定稿/`（正文 spec 命名 `NNNN-标题.md` + 中文键 front matter）、`设定/`、`记忆/章摘要/`、`大纲/`、git 初始提交。
- 自动在 v7 仓落 `git config dualformat.v6root`（settle 的唯一写入路径守卫兜底读取）；加 `--link-back` 可把 `STORY_REPO_ROOT` 写进 v6 项目 `.env` 激活 v6 侧守卫（默认不写，保持零写入）。
- ≥3 章的书自动预填 `context_budget.sections.prev_chapter_tail`（按书史章均字数，clamp 1200–3000）。

## 2. 缓存：`v7_cache.py`

```bash
python v7_cache.py rebuild --repo <v7仓>    # 从源文件全量重建 .cache/index.db
python v7_cache.py verify  --repo <v7仓>    # 删缓存→重建→快照等价（CI 验收项）
python v7_cache.py snapshot --repo <v7仓>   # 打印查询面快照
```

- `.cache/` 是唯一持久派生物，**可随时整目录删除**，下次查询自动重建。
- 查询面：`get_chapter` / `find_entity` / `get_summary` / `get_recent_reading_power` / `get_hook_type_usage`（Python API）。实体来源 = `名册.md` 单表 + `名册/<正名>.md` 目录（同名目录优先）；追读力来源 = `定稿/正文/*.md` 的 front matter 钩子字段（由 settle 从决策卡写入）。
- **schema 版本化**：`meta.schema_version` 与实现常量不匹配时，首次查询即整库重建——旧缓存的表结构差异不会变成查询期报错。

## 3. 写一章：`v7_write.py`

```bash
# ① 决策卡（作者界面单位；JSON 字段见下方决策卡节）
python v7_write.py decision --repo <v7仓> --json 决策内容.json
# ② 上下文包（20,000 字符预算；stats 含 truncated_sections / dropped_sections / section_errors / budget_used_ratio）
python v7_write.py pack --repo <v7仓> --chapter 38 --json 决策内容.json   # --json 可省，省略时从决策卡回退解析实体
# ③ 草稿落 工作区/草稿-NNNN.md（LLM/作者）
# ④ 机检（字数契约 / 占位符 / 标题一致 / 承诺或豁免 / 钩子或豁免 / 名册 advisory）
python v7_write.py check --repo <v7仓> --chapter 38 --draft 工作区/草稿-0038.md --json 决策内容.json
# ⑤ reviewer 直写 .webnovel/tmp/review_results.json（顶层 chapter + blocking_count）；prose-check 到 flagged 为空
# ⑥ settle（三门禁 → 原子 git commit：正文+章摘要+名册新实体 → 刷新缓存）
python v7_write.py settle --repo <v7仓> --chapter 38 --draft 工作区/草稿-0038.md --json 决策内容.json --summary "≤200 字章摘要"
#    退出码：0 成功 / 2 门禁或机检拒绝（stderr 有 JSON 明细）/ 1 其他错误
#    仅作者明确要求时：--force-review-bypass "作者原话理由"
```

以上每条都可经统一入口转发：`python webnovel.py --project-root <v7仓> v7-write <pack|check|settle|decision> ...`（`/webnovel:write` 在 `book.yaml` 存在时即走这条链）。

上下文包 section（v8 阶段一起）：决策卡 / 字数契约（书史章数·均值·中位 + 本章目标字数与下限）/ 本章章纲节选（`大纲/卷纲/第NN卷-详细大纲.md` 中本章小节，回退 `第NN卷.md`）/ 本章应推进（承诺账本，`大纲/条目`）/ 作者修改未消费（stale）/ 前情摘要 / 上一章结尾 / 本章实体 / 主角卡（需 `book.yaml` 声明 `主角:`）/ 视角纪律（pov ≠ 主角时）/ 名册清单 / 素材装配（`素材/`，条数 `book.yaml` `素材装配条数:` 默认 3）/ 文风宪法 / 文风锚点 / 作者模型 / 读者信号。域为空则整节省略；读函数出错记 `stats.section_errors`，不阻断。超总预算时按 materials → reader_signal → style_contract → outline_excerpt → protagonist → pov_discipline → style_anchor → author_model → roster → recent_summaries → entities 顺序整段丢弃，决策卡 / 上一章结尾 / stale / 承诺账本只截不丢。

要点：

- **机检是硬闸**：下限 = 目标字数×0.75；钩子须由 `hook_type` 或 `hook_waiver` 声明（二者皆空即拒）；`check` 退出码 2 = 拒绝 settle。
- **settle 三门禁**：① 审查——`.webnovel/tmp/review_results.json` 缺失、`chapter` 与本章不符、或 `blocking_count > 0` 均拒；② 文笔——`prose_check` 的 `flagged` 非空拒；③ 素材引用——决策 JSON `material_refs` ∪ 章纲卡 `素材引用` 中任一 ID 解析不到即拒，**不可绕过**。
- **显式绕过**：`--force-review-bypass "<理由>"` 只放行 ①②；放行后正文 front matter 加 `审查绕过: <理由>`，`作者/journal.jsonl` 追加 `actor=author action=settle domain=正文` 事件。门禁本来全绿时不写痕迹。
- **唯一写入路径**：settle 前经 `dual_format_guard` 校验同一章节未在 v6 侧落定（`STORY_REPO_ROOT` 配置）。
- **settle 原子性**：任一步失败自动回滚（定稿零变更），git index 一并清理。
- **名册新实体**：决策卡 `new_entities` 列表 → settle 写 `定稿/设定/名册/<正名>.md` → 重建缓存后可查询。
- **配额按书覆盖**（可选）：`book.yaml` 增 `context_budget:` 节（`total:` 总预算 / `sections:` 节配额），优先级 显式参数 > book.yaml > 内置默认。

决策 JSON 字段（`decision` / `pack --json` / `check` / `settle` 共用；`chapter` 以命令行 `--chapter` 为准覆盖）：

| 字段 | 类型 | 用途 |
|---|---|---|
| `chapter` | int | 章号 |
| `title` | str | 标题（机检核对首行；settle 文件名 `NNNN-标题.md`） |
| `pov` / `time_anchor` | str | 视角 / 书内时间（写入 front matter；pov ≠ `book.yaml` `主角` 时上下文包注入视角纪律） |
| `target_words` | int | 目标字数（机检下限 ×0.75；缺省用书史均值） |
| `goal` / `nodes` / `forbidden` / `contract` | str / list | 决策卡正文：目标 / 必须覆盖节点 / 禁区 / 合同断言 |
| `promises` / `waiver` | list / str | 推进承诺（机检做关键词存在性）/ 承诺结转豁免理由 |
| `hook_type` | str | 章末钩子类型（taxonomy 见 `references/reading-power-taxonomy.md`）；settle 写入正文 front matter |
| `hook_strength` | str | 钩子强度，缺省 `medium`；`强/中/弱` 由 settle 归一为 `strong/medium/weak` |
| `hook_waiver` | str | 钩子豁免理由——机检要求 `hook_type` 与它**二者必有其一** |
| `entities` | list[str] | 本章实体（上下文包名册查询；机检新名 advisory 白名单） |
| `new_entities` | list[{name,type,aliases}] | settle 写入名册 |
| `material_refs` | list[str] | 素材引用 `表:ID` 或裸 ID；settle 门③校验存在性（与章纲卡 `素材引用` 取并集） |
| `volume` | int | 卷号（front matter；缺省按 `book.yaml` `卷规模` 推算，用于定位详细大纲） |
| `v6_project_root` | str | 双格式并存时 v6 根（唯一写入路径校验；缺省读 git config `dualformat.v6root`） |

## 已知边界（v7.0）

- 承诺结转：账本读写已由 T28 实现（`promise-ledger` / `foreshadow-scan`），上下文包「本章应推进」直接读账本；机检仍只校验「承诺非空或显式豁免」+ 关键词存在性，语义复核交 reviewer。
- 缓存同步：settle 成功后自动 rebuild（best-effort，失败不影响已完成的 settle）；缓存文件缺失**或损坏**（零字节/坏库/缺表）时首查自动重建，无需手动干预。
