# Spec：复合题材播种与浮动名扫描（v8-gap-review 阶段四 P4-3 / N7 / N8）

> 档位：Architectural（播种改传 canonical 并集；name-check 增正文扫描）
> 状态：**已批准**（Human 2026-09-04 确认方案 A 及捆绑默认）
> 上游：`docs/zcode/v8-gap-review-3rounds/README.md` 阶段四 P4-3、§2.4 N7/N8；`material_store.py`；`continuity_check.py`；`genre_taxonomy.py`
> 下游：同目录 `2026-09-04-seed-floaters-plan.md` → TDD → 收尾

## 1. 背景与目标

N7：fantasy01 `题材标签: 都市+仙侠+科幻`。`resolve_genre_input` 已匹配三个 label，但 `_choose_canonical` 只留 **都市**。`init_project` 用 `canonical_genre` 调 `seed_materials`，仙侠/科幻参考行进不去。`_genre_keywords` 已能按 `+` 拆开——缺口在调用方传单键。

N8：`name-check` 只把 `--name` 对名册做编辑距离。正文里未入册绰号（「铁牙」类）不扫。真仓 **铁牙已在名册**，按「未入册」不会再报；「哑巴嗓」在草稿不在定稿。

**目标：** 播种按匹配到的全部 canonical 并集；name-check 可扫最近 N 章定稿里未入册高频专名（warning）。

**成功标准（抄 gap-review 阶段四 P4-3 原文）：**

> ①seed 支持复合键（都市+仙侠+科幻 → 三键并集）；②name-check 增正文浮动名扫描（最近 N 章高频专名，warning 级）
>
> 验收：fantasy01 播种含仙侠素材；「铁牙」类绰号被提示

## 2. 非目标

- 不改 `_choose_canonical` 的单值 `canonical_genre`（Story System / 模板主类型仍一个）。
- 不覆盖已有 `素材/活/*.csv`（既有表 skip；真仓 fantasy01 **不默认播种**）。
- 不把浮动名写入名册；不改草稿/工作区扫描范围（只扫 `定稿/正文`）。
- 不改 doctor、P2-3、v6 写链、dashboard、MCP 签名。
- 不改 T29 `--name` 对名册的撞名语义（exit 码：仅 `--name` 且 `ok=False` 才非 0；浮动名不因此失败）。

## 3. 方案与裁决

| 方案 | 内容 | 裁决 |
|---|---|---|
| **A（采纳，Human 2026-09-04）** | 播种传 canonical 并集；`--scan` 扫近 N 章未入册高频专名，warning | 对准原文；单值 canonical 保留 |
| B | 只补 `_GENRE_KEYWORDS` 中文键，不改 init | 否决：init 仍传「都市」 |
| C | 播种与浮动名拆两个切片 | 否决：P4-3 打包验收 |

捆绑默认（同批批准）：

1. **播种：** `GenreResolution.canonical_genres` 为匹配条目 canonical 去重并集（顺序=首次出现）。`seed_materials` / init 使用 `"+".join(canonical_genres)`（空则退回原字符串）。v7 读 `题材标签` 优先于 `类型`（仅测试/辅助函数；init 仍用用户传入的 genre 字符串经 resolver）。
2. **name-check：** `--scan`；窗口 N=**5**；次数 ≥**2**；2–4 个汉字；排除名册正名与别名。只读。JSON `floaters`。有浮动名 **exit 0**。
3. **验收：** tmp 空仓 `都市+仙侠+科幻` 播种含仙侠适用行（对比单键都市）。真仓不跑 seed。夹具正文未入册「铁牙」应出现在 floaters；真仓扫描不要求再报已入册铁牙，只证明 scan 能跑出未入册浮动名或空列表（无未入册高频则空，不造假）。

## 4. 设计

### 4.1 播种

`genre_taxonomy.GenreResolution` 增加 `canonical_genres: list[str]`。`resolve_genre_input` 在选定单值 `canonical_genre` 之后，按 matched 条目追加去重 canonical（跳过空与「全部」）。

`seed_genre_label(raw: str) -> str`：`"+".join(canonical_genres)` 或 `raw.strip()`。

`init_project`：`seed_materials(..., genre=seed_genre_label(genre))`，**不要**再传单值 `canonical_genre`。

`_genre_keywords` 保持拆 `+`；中文 canonical 不在 `_GENRE_KEYWORDS` 时仍用 `(key,)` 回退，与 CSV「适用题材」中文词对齐。

可选：`genre_from_book_yaml(root) -> str` 读 `题材标签:` 否则 `类型:`，供测试用 fantasy01 标签字符串，不在真仓落盘。

### 4.2 浮动名

`continuity_check.scan_floating_names(root, *, window=5, min_count=2) -> list[dict]`：

- 章号：`max_settled_chapter`；取 `[max(1, latest-window+1), latest]` 的 `定稿/正文/NNNN-*.md`。
- 去掉 front matter（`---` 包裹）后，用 `[\u4e00-\u9fa5]{2,4}` 切分。
- 精确命中 `load_known_names` 的 `name` 则丢弃。
- `count >= min_count` 保留；按 count 降序。
- 每项：`name` / `count` / `chapters`（出现过的章号列表）。

无定稿 → `[]`。不写盘。

`check_name_conflicts` 增加可选 `floaters` 字段（默认 `[]`）。`main`：`--scan`；`--name` 在无 `--scan` 时仍必填。仅 `--scan` 时不做 `--name` 冲突（`name=""`，`conflicts=[]`）。两者都给：conflicts + floaters。`--format json` 必须从 `webnovel.py name-check` 转发出去（现状未转 `--format`，本切片补上）。

text：浮动名打印 `WARNING 浮动名 N 个：` 行，不改无冲突时的 `OK 无撞名`（若同时有 conflicts 仍先打撞名）。

### 4.3 代码落点

| 文件 | 动作 |
|---|---|
| `webnovel-writer/scripts/genre_taxonomy.py` | `canonical_genres`；`seed_genre_label` |
| `webnovel-writer/scripts/init_project.py` | 播种改传并集标签 |
| `webnovel-writer/scripts/tests/test_genre_taxonomy.py` | 复合键并集 / 单值 canonical 仍为都市 |
| `webnovel-writer/scripts/tests/test_material_store.py` | 并集多种到仙侠行 |
| `webnovel-writer/scripts/data_modules/continuity_check.py` | `scan_floating_names`；CLI `--scan` |
| `webnovel-writer/scripts/data_modules/webnovel.py` | 转发 `--scan` / `--format`；`--name` 非必填 |
| `webnovel-writer/scripts/tests/test_continuity_check.py` | 未入册铁牙提示；入册不报；CLI |

## 5. 数据与兼容

- 单题材 `genre=都市` 行为与现在一致（并集仅一项）。
- `ambiguous_canonical` warning 可继续出现，不影响并集。
- schema：continuity 仍 `continuity-check/1`（加键）。

## 6. 验收清单（W1：引用方案原文）

| # | 方案原文 | 验证 |
|---|---|---|
| 1 | seed 支持复合键（都市+仙侠+科幻 → 三键并集） | `canonical_genres` 含三键；`seed_materials` 并集行 ⊃ 单键都市行，且含仙侠适用 id |
| 2 | name-check 增正文浮动名扫描（最近 N 章高频专名，warning 级） | 未入册「铁牙」出现 ≥2 次 → floaters；已入册不报；exit 0 |
| 3 | fantasy01 播种含仙侠素材 | 用其 `题材标签` 在 **空 tmp** 播种（不写真仓）；桥段含仙侠适用行 |
| 4 | 「铁牙」类绰号被提示 | 夹具未入册「铁牙」；真仓 scan 只读跑通（铁牙已入册则不应在 floaters） |
| 5 | 回归 | 定点全绿；全量 pytest；cov ≥80；evals 23/23；三校验器 OK |

## 7. 约束

- TDD：先失败测试再实现。
- Windows：`python -X utf8`。
- 提交：spec/plan 与实现分开；播种与浮动名可两个 feat；中文 message 走 UTF-8 + `git commit -F`。
- 无 ruling ledger，除非改走 SDD。
- 不 push，除非 Human 再批。
