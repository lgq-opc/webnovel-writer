# reader_signals 存量章钩子回填 — 设计（design-only）

> 派单：Hermes 编排台设计单①（改派 ZCode / GLM-5.3-Flash）｜2026-09-15
> 基线：`v8-author` @ `578b4bf`（现场 `git log --oneline -1` 核对；任务书起草时的 `676fc5c` 已过期）
> 分支：`pilot/reader-backfill`（设计文档提交 `359383d`，已合入 `v8-author` @ `bce58ea`）
> **0915 评审必改已返工**（2026-09-18；编排台评审 §1.5：① 提交已由 `359383d` 满足；② 命令 A 路径写法见 §2.2）
> 性质：**只出设计，不改代码、不跑真实回填**；不确定项见 §6 未决问题
> 输入：`docs/plans/2026-09-13-reader-signals-v7-plan.md`、`…-v7-spec.md`、
> `webnovel-writer/scripts/data_modules/reader_signal_builder.py`、
> `webnovel-writer/scripts/data_modules/index_manager.py`（chapter_reading_power 表与 `get-reader-signals` 节）、
> `webnovel-writer/scripts/v7_cache.py`、`webnovel-writer/scripts/v7_write.py`（settle/front matter）、
> `docs/guides/v7-write-path.md`、`webnovel-writer/references/reading-power-taxonomy.md`

## 0. 一句话

存量 42 章正文 front matter 全部没有钩子字段（「无」×42，无「有/半」），`.cache` 追读力表 0 行；
可回填的数据源已核实存在——卷纲《第01卷-详细大纲》每章小节的 `- 钩子：<类型>钩——<说明>` 半结构化行
（本卷 80/80 章覆盖）；回填应为**新命令旁路写**（settle 的唯一写入路径守卫禁止对已定稿章双写），
以「front matter 已有 `钩子类型:`」为幂等主键、逐章 git commit + 状态文件双账本支持断点续跑。

## 1. 背景与目标

reader_signals 已在 v7 写链接通（2026-09-13 spec/plan 落地）：钩子由决策卡显式声明 → settle 写进
`定稿/正文/NNNN-标题.md` front matter（唯一事实源）→ `rebuild_cache` 重算进
`.cache/index.db::chapter_reading_power` → pack 读者信号节 / `index get-reader-signals` / MCP 消费。
但该机制**只对落定之后的章生效**；存量章（本样本 42 章）定稿早于特性上线，front matter 无钩子字段，
消费侧对存量区间读到的是空结构。spec §9 待办 1 明确「存量章（40+）钩子回填：不回溯，需单独排期与工具」——
本设计就是那个「工具」的设计。

目标：把存量章的钩子信息补进 canonical（正文 front matter），使 `.cache` 追读力表与消费面对存量区间
产出真数据；全程可重入、可审计、单章失败不放大。

## 2. 现状勘察（可复跑命令 + 实测输出）

### 2.1 样本

- 真书 v7 书仓：`C:\lgq\ai-workspace\.tmp\wn-verify-810\fantasy01-pov`（书名《末世：我靠吃灾修行》，
  42 章定稿，`resolve_write_mode == "v7"`；spec §5 探针同源对象）。**注意**：该样本在 `.tmp` 临时验收区，
  可能随清理消失；清点命令对任意 v7 书仓根可复跑（把 `BOOK` 换成实际仓根即可）。
- 仓内没有成仓的 v7 fixture：`test_v7_cache.py` / `smoke_v7_newbook.py` 都在 `tmp_path` 动态构造书仓，
  `evals/` 只有 behavior 配置。故勘察以真书为准。
- 书仓结构事实：`定稿/正文/` 42 个文件；39 章带 `迁移来源:`（v6 迁移产物）、3 章（40/41/42）带 `书内时间:`
  （v7 settle 产物）；该仓是 git 仓（`git rev-parse --is-inside-work-tree` = true）。

### 2.2 清点命令 A：正文钩子字段现状（自包含，只读）

> **路径写法（0915 评审必改 2）**：给**原生 Windows Python** 的 `BOOK` 必须用 `C:/...`。
> 原文曾写 `BOOK=/c/lgq/...`（MSYS 路径）。Git Bash 的 `grep` 吃 `/c/` 没问题（命令 B 仍可），
> 但 `py -3.13` / 系统 `python` 把 `/c/...` 当成相对路径，`glob` 空转后**正常退出**，输出静默变成
> `0/0/0/0`。0915 评审在同一台机器上对照：`BOOK=/c/...` → `0/0/0/0`；`BOOK=C:/...` →
> `42/0/0/42` + `.cache` 0 行（即下方「实测输出」）。脚本末尾 `assert total > 0` 防呆，避免
> 实施者把空转当成「无事可做」。

```bash
BOOK=C:/lgq/ai-workspace/.tmp/wn-verify-810/fantasy01-pov
python -X utf8 - "$BOOK" <<'PY'
import sys
from pathlib import Path

body_dir = Path(sys.argv[1]) / "定稿" / "正文"
rows = []
for p in sorted(body_dir.glob("*.md")):
    text = p.read_text(encoding="utf-8")
    has_type = has_strength = False
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            has_type = any(l.strip().startswith("钩子类型:") for l in fm.splitlines())
            has_strength = any(l.strip().startswith("钩子强度:") for l in fm.splitlines())
    rows.append((p.name, has_type, has_strength))

total = len(rows)
assert total > 0, (
    f"定稿/正文为空或路径无效: {body_dir} "
    "（Windows 原生 Python 不要用 /c/... MSYS 路径，改用 C:/...）"
)
full = sum(1 for _, t, s in rows if t and s)
half = sum(1 for _, t, s in rows if t != s)
none = sum(1 for _, t, s in rows if not t and not s)
print(f"正文章节总数: {total}")
print(f"钩子类型+强度齐全(有): {full}")
print(f"只有其一(半): {half}")
print(f"全无(无): {none}")

sys.path.insert(0, r"C:\lgq\ai-workspace\projects\zcode-plugins\webnovel-writer\webnovel-writer\scripts")
from v7_cache import _conn
conn = _conn(Path(sys.argv[1]))
try:
    n = conn.execute("SELECT COUNT(*) FROM chapter_reading_power").fetchone()[0]
finally:
    conn.close()
print(f".cache chapter_reading_power 行数: {n}")
PY
```

**实测输出（2026-09-15）：**

```
正文章节总数: 42
钩子类型+强度齐全(有): 0
只有其一(半): 0
全无(无): 42
.cache chapter_reading_power 行数: 0
```

### 2.3 清点命令 B：回填数据源分布（卷纲详细大纲的钩子行）

```bash
BOOK=C:/lgq/ai-workspace/.tmp/wn-verify-810/fantasy01-pov
F="$BOOK/大纲/卷纲/第01卷-详细大纲.md"
grep -c "^## 第[0-9]" "$F"        # 章小节数
grep -c "^- 钩子：" "$F"           # 钩子行数
grep -o "^- 钩子：[^钩]*钩" "$F" | sed 's/- 钩子：//' | sort | uniq -c | sort -rn
```

**实测输出（2026-09-15）：**

```
80      # 章小节（第 1–80 章，含未定稿章）
80      # 钩子行 → 已定稿 42 章所在小节全覆盖
  32 悬念钩
  20 危机钩
   8 渴望钩
   7 情绪钩
   6 冲突钩
   3 选择钩
   3 代价钩
   1 关系钩
```

行形示例（第 1 章小节）：`- 钩子：悬念钩——「想活？先吃下这场灾。」`

### 2.4 勘察结论

| # | 结论 | 证据 |
|---|---|---|
| K-1 | 存量现状为「无」×42，不存在「半」（没有任何章写了钩子强度或豁免类标记） | 命令 A |
| K-2 | 卷纲详细大纲是唯一全覆盖的钩子数据源：每章小节一行 `- 钩子：<类型>钩——<说明>`，类型词形规整可正则抽取 | 命令 B；对照：章纲卡仅 40–49 十张（重规划产物），其中含「钩」的只有 2 张 |
| K-3 | **词表漂移**：大纲在用 `冲突钩/代价钩/关系钩`，不在 taxonomy 主表（危机钩/悬念钩/渴望钩/情绪钩/选择钩）内 | 命令 B 分布 vs `references/reading-power-taxonomy.md` §一 |
| K-4 | 大纲无强度信息 → 回填强度只能缺省 `medium`（`normalize_hook_strength("")` 的既定行为） | `v7_cache.py:34-42` |
| K-5 | settle **不可复用于回填**：`has_v7_settled_chapter` 对已定稿章直接拒绝双写（`v7_write.py:806-807`）；且三门禁需要草稿/review_results 输入，回填场景不存在这些输入 | `v7_write.py:764-807` |
| K-6 | 消费链就绪，回填后无需改任何消费代码：`_iter_reading_power` 只认 front matter 的 `钩子类型:` 非空 | `v7_cache.py:175-199`、`reader_signal_builder.py:70-84` |

## 3. 设计前提与约束

1. **canonical 不动**：钩子的唯一事实源是 `定稿/正文/NNNN-*.md` front matter（spec §3.1）；回填写的是
   canonical 本身，不是 `.cache`。`.cache` 是纯派生物，回填后靠 `rebuild_cache` 自动带上（K-6）。
2. **正文 body 逐字节不变**：回填是元数据操作，只允许在 front matter 块内插行；`迁移来源:`、`推进承诺:`
   列表等既有键值原样保留（注意 front matter 已存在 YAML 列表形态，见 0041 章实测）。
3. **词表归一沿用既有口径**：强度走 `v7_cache.normalize_hook_strength`（强/中/弱 → strong/medium/weak，
   空值 → medium）；类型词表问题见 K-3 与 §6 未决 1。
4. **审计与可回滚**：书仓是 git 仓 → 逐章 commit 可审计可 revert；非 git 仓（`book-init --no-git` 场景）
   用 `--no-commit` 兜底，与 settle 同款约束。

## 4. 回填方案

### a. 回填入口：`v7_write.py` 新增 action `backfill-hook`（新命令，不复用 builder/settle）

- 不复用 `reader_signal_builder`：它是消费侧只读装配器（spec §3.5），无写职责。
- 不复用 `settle`：唯一写入路径守卫禁止已定稿章双写（K-5），且门禁输入不存在。
- 归属 `v7_write.py`：它是 v7 侧唯一动「定稿/正文」的模块，front matter 的写入口径
  （键序、`normalize_hook_strength` 调用）已在其中，回填插入格式与 settle 产出保持逐字节同构
  （`v7_write.py:832-837` 的两行：`钩子类型: <type>`、`钩子强度: <normalized>`）。
  统一入口 `webnovel.py` 的 `v7-write` 子动作 choices（现 `decision|pack|check|settle`，
  `data_modules/webnovel.py:1125-1126`）同步追加 `backfill-hook`。

**命令形状（原文）**：

```bash
# ① 预览：从卷纲详细大纲抽取，不落盘（默认 dry-run）
python v7_write.py backfill-hook --repo <v7仓> --from-outline --volume 1 --chapters 1-42

# ② 落盘：按预览结果整批回填（逐章 commit）
python v7_write.py backfill-hook --repo <v7仓> --from-outline --volume 1 --chapters 1-42 --apply

# ③ 单章显式（人工判读值 / 修订偏差章；--hook-strength 缺省 medium）
python v7_write.py backfill-hook --repo <v7仓> --chapter 41 --hook-type 悬念钩 --hook-strength strong \
    --source "人工判读：正文结尾为车队夜袭逼近"

# 批量模式可加：--report <path.json>（逐章结果落盘）；--no-commit（非 git 仓兜底）
```

语义：`--from-outline` 从 `大纲/卷纲/第NN卷-详细大纲.md` 按 `## 第N章` 分段，只在**该段内**抽
`^- 钩子：` 行（类型词形 `^- 钩子：(<类型>钩)——`；说明文字不进 front matter，只进状态文件的
`source` 字段供审计）。`--chapters 1-42` 的映射口径是**现存** `定稿/正文/NNNN-*.md`：范围内
缺文件的章记该章 `failed`，不按卷纲小节数硬凑。`--chapter` 显式模式跳过大纲，以参数值为准。
两个模式共用同一落盘函数。

### b. 幂等与断点续跑

- **幂等主键＝front matter 已有 `钩子类型:`**（与 `_iter_reading_power` 的入表条件同一条判据，K-6）。
  已有 → 该章 `skipped`，永不二次插入；重复执行整批，结果收敛（第二次全 skipped、0 commit）。
- **断点双账本**：
  1. 状态文件 `.webnovel/tmp/backfill-hook-state.json`（该目录在书仓 `.gitignore` 内；
     **机制先例**在 `chapter_meter.py:9-10,22`——`meter start` 写入 / `stop` 移除活标记。
     0915 评审核对样本现场 `.webnovel/tmp/` 当时只有 `review_results.json`，**无** `chapter_meter.json`），
     逐章记录 `{chapter, status: done|skipped|failed,
     hook_type, hook_strength, source, commit_sha, reason}`；重跑先读它，`done/skipped` 直接跳过。
  2. git 历史：每章独立 commit（`backfill: 第0041章 钩子回填（悬念钩/strong）`）。
     状态文件丢失（tmp 清理）时，`git log --grep=^backfill:` 可重建断点视图。
- **写入原子性（单章粒度）**：读全文 → 内存改写 → 单次 `write_text` → commit；任一步失败则该章
  不产生任何磁盘变化（无半写状态），标 `failed` 留待重跑。

### c. 失败语义

- **单章失败不阻断整批**：逐章 try/except，捕获后写 `failed` + `reason` 进状态文件并继续下一章。
- **失败位置可查**：三处——状态文件（按章号索引）、stderr 末尾汇总表
  （`failed: 3 章 → [12, 37, 39]`）、`--report` JSON（可机读）。
- **预检失败也按章记**：章文件缺失 / 文件名不符 `NNNN-` 模式 / 卷纲小节缺 / 钩子行解析失败 /
  非 git 仓且未给 `--no-commit`，均为该章 `failed`，不放大为整批退出。
- **退出码**：`0` 全成（含全 skipped）/ `1` 部分失败（明细见 report）/ `2` 参数或预检级错误。
  与写链既有退出码语义（0/1/2）同构。

### d. 与 v7 写链的关系：**旁路写**，但带四条底线

不走 `check` / `settle` / 三门禁。理由：门禁的语义是「新章定稿前的质量闸」，其输入（草稿、
`review_results.json`、素材引用校验）在回填场景不存在；settle 本身禁止重入（K-5）；回填只插
front matter 元数据，正文质量不被触碰。**旁路的代价是绕过 gate，用四条底线补偿**：

1. **body 不可变**：解析 `---` 块 → 仅在块内追加两行 → 单次写回；实现时必须有测试断言
   回填前后正文部分逐字节一致（`git diff` 只允许出现 front matter 插入行）。
2. **逐章 git commit 留痕**（见 b）；`审查绕过` 类似的 journal 留痕一并做：
   `append_events(actor="system", action="edit", domain="正文", change_kind="structure",
   summary="钩子回填：<type>/<strength>（<source>）")`——四个字段全部落在
   `author_journal.VALID_*` 白名单内（`author_journal.py:25-28`）。
3. **类型词表校验前置**：插入前校验 `hook_type`；命中 taxonomy 主表直接过；未命中（K-3 的
   冲突钩/代价钩/关系钩）按 §6 未决 1 的裁决执行（默认行为：原样入库 + stderr 逐章警告）。
4. **缓存刷新整批一次**：整批成功后 `rebuild_cache` 一次（best-effort，失败不阻断——与 settle
   末尾同口径），不做逐章 rebuild（42 次×全量重建纯浪费；幂等正确性靠 front matter，不靠缓存）。

回填产出**不过 write-gate**，但回填之后消费侧链路自动受益：`index get-reader-signals` /
pack 读者信号节 / MCP `webnovel_reader_signals` 无需任何改动（K-6）。

### e. 验证方案

| # | 断言 | 做法 |
|---|---|---|
| V-1 | 条数 | 回填 N 章后 `chapter_reading_power` 行数 == 回填成功章数（本样本应为 42）；`get_hook_type_usage(last_n=50)` 分布与命令 B 的已定稿章类型分布一致（经未决 1 裁决后的口径） |
| V-2 | 抽样对照 | 随机抽 `max(3, 10%)` 章：`git show <sha> -- <章文件>` 仅含 front matter 插入行；插入的 `钩子类型` 与该章卷纲小节钩子行一致 |
| V-3 | 不变量 | `v7-cache verify --repo <v7仓>` → `equal=True`（删缓存→重建→快照等价，含追读力表） |
| V-4 | 幂等 | 重跑同参数 `--apply` → 全 `skipped`、0 新 commit |
| V-5 | 消费端 | `webnovel.py --project-root <v7仓> index get-reader-signals` 的 `recent_reading_power` 非空且按章号降序；pack 读者信号节的 `differentiation_reminder` 对连续同型章正常触发 |
| V-6 | 失败语义 | 人工造一章坏文件（如删掉 0037 的 front matter 闭合 `---`）重跑 → 该章 `failed` 且退出码 1，其余章不受影响；修复后重跑收敛 |

**既有测试锚点（实现时不得回退）**：`scripts/data_modules/tests/test_v7_cache.py`
（`TestReadingPowerFromFrontMatter` 等 18 用例）、`scripts/tests/test_reader_signal.py`
（`TestV7Consumption` 5 用例，含 v6 反向守住）、`scripts/smoke_v7_newbook.py`
（reader-signals 非空断言）。**新增测试**（实现单的验收面）：插入位置与格式 / 幂等跳过 /
body 逐字节不变 / 单章失败不阻断 / 状态文件断点续跑 / 非词表类型警告，六类。

## 5. 端到端执行时序（实施时的操作序，非本单范围）

```
裁决 §6 未决 1/2 → dry-run 预览（命令 a-①）→ 人工抽检预览报告
→ --apply 落盘（命令 a-②，逐章 commit + 状态文件）
→ 失败章用命令 a-③ 单章补 → V-1..V-6 验证 → 全量 pytest
```

## 6. 未决问题（需 Human / 编排台裁决，不替拍板）

| # | 问题 | 选项与影响 | 倾向（仅供参考） |
|---|---|---|---|
| 1 | **超词表类型处置**（K-3：冲突钩×6 / 代价钩×3 / 关系钩×1） | A 原样入库（`hook_type_usage` 词表变宽，`derive_differentiation_reminder` 仍可用）；B 映射进主类型（如 冲突钩→危机钩），映射表须由 taxonomy 持有者定；C 这 10 章拒填等人工 | B，但映射表是 taxonomy 共享资产的扩展，须 Human 定 |
| 2 | **强度全缺省 medium**（K-4） | A 接受降级，后续逐章人工修订（front matter 是 canonical，修订即又一次 edit）；B 回填前先人工给 42 章定强度（成本高） | A |
| 3 | **执行主体** | A 机械正则抽取（快，盲信大纲）；B LLM 逐章判读（慢，能发现「正文实际结尾偏离大纲计划」） | A + V-2 抽样人工复核；B 可作为单章模式（命令 a-③）的补充通道，架构不变 |
| 4 | **大纲计划钩子 ≠ 正文实际钩子**的偏差章处置 | 机械抽取以大纲为准；抽样发现的偏差章用命令 a-③ 人工修正 | 同 V-2 流程，无需新机制 |
| 5 | **样本仓转正**：真书在 `.tmp/wn-verify-810/`（临时验收区，清理即失） | 回填实施前确认正式书仓路径，或把该样本转正；否则设计验收无法在真书上执行 | 编排台/Human 明确书仓归属后实施 |
| 6 | **已发布平台章的元数据回填口径** | 回填不改正文只改 front matter，但若这些章已在平台发布，是否算「改动已发布内容」属仓库外语义 | 作者裁决 |

## 7. 任务书 §4 对照

- [x] 分支 `pilot/reader-backfill` 存在，含 1 个提交（本设计文档，`359383d`）
- [x] 设计文档含：现状勘察（可复跑命令 A/B + 原始输出，§2）、回填方案 a–e（§4）、未决问题清单（§6）
- [x] 不改任何生产代码；`git status` 除本设计文档外干净
- [x] 0915 评审必改：① 提交已满足；② 命令 A 改原生 `C:/...` 路径并加 `assert total > 0`（2026-09-18 返工）
