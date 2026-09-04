# 阶段二章纲一致性闸 实施计划

> **执行者注意：** 按任务逐个实施，用 subagent-driven-development（推荐）或逐批人工执行。
> 步骤用 checkbox（`- [ ]`）语法跟踪，完成即勾选。

**目标：** 统一详细大纲路径与章节标题解析，并在章纲卡落盘前完成标题、承诺、时间、战力、人物一致性校验。
**架构：** `outline_paths.py` 统一规范路径与兼容读取；`chapter_outline_validate.py` 输出结构化 errors/warnings；`create_chapter_batch` 保留旧 `self_check_batch` API，只负责组合校验与事务边界。
**技术栈：** Python 3.10+、pytest、标准库 `pathlib/re/json`。
**Spec：** `docs/cursor/阶段二-章纲一致性闸/2026-09-04-chapter-outline-consistency-spec.md`

## 全局约束

- 规范写路径固定为 `大纲/卷纲/第NN卷-详细大纲.md`。
- 兼容读顺序固定为：规范路径 → `大纲/卷纲/第NN卷.md` → v6 平铺路径及空格变体。
- 标题兼容 H2/H3、阿拉伯/中文章号、全角/半角冒号与空格；新写固定 `## 第N章：标题`。
- 只有不存在的承诺 ID、可证明的跨批时间倒流是 error；其余新增检查均 warning。
- error 时整批零落盘、零 journal；warning 仍生成 draft 卡。
- `self_check_batch(cards) -> list[str]` 签名不变；`checks` 返回字段继续表示 warning 文本。
- `人物` 为 `chapter-card/1` 可选列表字段，不升级 schema。
- 不自动移动/删除旧详细大纲，不清理 fantasy01 重复文件。
- Windows 命令统一 `python -X utf8`；覆盖率不低于 80%。

## 执行总览

| 序号 | 任务名 | 依赖 | 验证方式 |
|---|---|---|---|
| 1 | 共享详细大纲路径、标题与节选解析器 | — | `test_outline_paths.py`：规范优先、三类兼容路径、标题格式矩阵 |
| 2 | 迁移器与 plan skill 改写规范路径 | 依赖 Task 1 | `test_migrate_v6_to_v7.py` + prompt integrity 定点测试 |
| 3 | v7/v6 读取链改用共享解析器 | 依赖 Task 1；可与 Task 2 并行 | v7 pack section + chapter outline directive/path 测试 |
| 4 | 章纲卡 `人物` 字段 + 标题/承诺一致性闸 | 依赖 Task 1 | `test_chapter_outline_batch.py`：错标题 warning、F-999 零落盘 |
| 5 | 时间/战力/人物一致性闸 | 依赖 Task 4 | 同测试文件：倒流 error、未知境界/人物 warning |
| 6 | fantasy01 冒烟、全量回归、状态回写 | 依赖 Task 1-5 | 只读副本建卡 43；全量 pytest ≥1483、cov ≥80 |

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `webnovel-writer/scripts/data_modules/outline_paths.py` | 新增 | 详细大纲规范路径、兼容解析、章节标题/节选 |
| `webnovel-writer/scripts/data_modules/chapter_outline_validate.py` | 新增 | P2-1/P2-2 结构化 errors/warnings |
| `webnovel-writer/scripts/data_modules/chapter_outline_batch.py` | 修改 | 可选 `人物` 字段；组合 legacy warning 与结构化闸 |
| `webnovel-writer/scripts/migrate_v6_to_v7.py` | 修改 | 保留 `-详细大纲` 后缀 |
| `webnovel-writer/scripts/v7_write.py` | 修改 | `_sec_outline_excerpt` 复用共享解析器 |
| `webnovel-writer/scripts/chapter_outline_loader.py` | 修改 | v6 loader 复用共享解析器 |
| `webnovel-writer/scripts/chapter_paths.py` | 修改 | 标题解析复用共享解析器 |
| `webnovel-writer/skills/webnovel-plan/SKILL.md` | 修改 | 详细大纲写规范路径和规范标题 |
| `webnovel-writer/scripts/tests/test_outline_paths.py` | 新增 | Task 1 单测 |
| `webnovel-writer/scripts/tests/test_chapter_outline_batch.py` | 修改 | Task 4-5 闸测试 |
| `webnovel-writer/scripts/data_modules/tests/test_migrate_v6_to_v7.py` | 修改 | Task 2 迁移测试 |
| `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py` | 修改 | plan skill 路径防漂 |
| `docs/zcode/v8-gap-review-3rounds/README.md` | 修改 | P2-1/P2-2 状态与验收证据 |
| `docs/cursor/项目复审/2026-09-04-会话交接.md` | 修改 | 会话交接 |

---

## Task 1：共享详细大纲解析器

**文件：**
- 新增 `webnovel-writer/scripts/data_modules/outline_paths.py`
- 新增 `webnovel-writer/scripts/tests/test_outline_paths.py`

- [ ] 写失败测试：

```python
from pathlib import Path

from data_modules.outline_paths import (
    canonical_detailed_outline_path,
    extract_chapter_heading,
    extract_chapter_section,
    resolve_detailed_outline,
)


def test_canonical_path_is_zero_padded(tmp_path: Path):
    assert canonical_detailed_outline_path(tmp_path, 2) == tmp_path / "大纲" / "卷纲" / "第02卷-详细大纲.md"


def test_resolver_prefers_canonical_then_legacy_nested_then_v6_flat(tmp_path: Path):
    canonical = tmp_path / "大纲" / "卷纲" / "第01卷-详细大纲.md"
    nested = tmp_path / "大纲" / "卷纲" / "第01卷.md"
    flat = tmp_path / "大纲" / "第1卷-详细大纲.md"
    for path in (flat, nested, canonical):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.name, encoding="utf-8")
    assert resolve_detailed_outline(tmp_path, 1) == canonical
    canonical.unlink()
    assert resolve_detailed_outline(tmp_path, 1) == nested
    nested.unlink()
    assert resolve_detailed_outline(tmp_path, 1) == flat


def test_heading_compatibility_matrix():
    cases = [
        ("## 第43章：夜袭", 43, "夜袭"),
        ("### 第43章: 夜袭", 43, "夜袭"),
        ("## 第43章 夜袭", 43, "夜袭"),
        ("### 第四十三章：夜袭", 43, "夜袭"),
    ]
    for text, chapter, expected in cases:
        assert extract_chapter_heading(text, chapter) == expected


def test_extract_section_stops_at_same_or_higher_heading():
    text = "# 卷二\n\n## 第42章：前夜\n旧\n\n## 第43章：夜袭\n目标段\n\n### 场景\n细节\n\n## 第44章：余波\n不应包含"
    section = extract_chapter_section(text, 43)
    assert "目标段" in section and "### 场景" in section
    assert "第44章" not in section
```

- [ ] 运行 RED：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_outline_paths.py -q --no-cov -p no:cacheprovider
```

预期：`ModuleNotFoundError: data_modules.outline_paths`。

- [ ] 实现 `outline_paths.py`：

```python
from __future__ import annotations

import re
from pathlib import Path

_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_HEADING_RE = re.compile(r"^(#{2,3})\s*第\s*([0-9零一二三四五六七八九十百]+)\s*章(?:\s*[：:]\s*|\s+)(.+?)\s*$", re.M)


def _cn_number(raw: str) -> int | None:
    if raw.isdigit():
        return int(raw)
    total, current = 0, 0
    for char in raw:
        if char in _CN_DIGITS:
            current = _CN_DIGITS[char]
        elif char == "十":
            total += (current or 1) * 10
            current = 0
        elif char == "百":
            total += (current or 1) * 100
            current = 0
        else:
            return None
    return total + current


def canonical_detailed_outline_path(root: str | Path, volume: int) -> Path:
    return Path(root) / "大纲" / "卷纲" / f"第{int(volume):02d}卷-详细大纲.md"


def detailed_outline_candidates(root: str | Path, volume: int) -> list[Path]:
    root, volume = Path(root), int(volume)
    return [
        canonical_detailed_outline_path(root, volume),
        root / "大纲" / "卷纲" / f"第{volume:02d}卷.md",
        root / "大纲" / f"第{volume}卷-详细大纲.md",
        root / "大纲" / f"第{volume}卷 - 详细大纲.md",
        root / "大纲" / f"第{volume}卷 详细大纲.md",
    ]


def resolve_detailed_outline(root: str | Path, volume: int) -> Path | None:
    return next((path for path in detailed_outline_candidates(root, volume) if path.is_file()), None)


def _match(text: str, chapter: int):
    return next((m for m in _HEADING_RE.finditer(text) if _cn_number(m.group(2)) == int(chapter)), None)


def extract_chapter_heading(text: str, chapter: int) -> str | None:
    match = _match(text, chapter)
    return match.group(3).strip() if match else None


def extract_chapter_section(text: str, chapter: int) -> str | None:
    match = _match(text, chapter)
    if not match:
        return None
    level = len(match.group(1))
    rest = text[match.end():]
    stop = re.search(rf"^#{{1,{level}}}\s", rest, re.M)
    return (match.group(0) + (rest[:stop.start()] if stop else rest)).strip()
```

- [ ] 运行 GREEN，并补测 1–99 中文章号边界：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_outline_paths.py -q --no-cov -p no:cacheprovider
```

- [ ] 提交：

```text
feat(outline): 统一详细大纲路径与章节标题解析
```

## Task 2：迁移器与 plan skill 写规范路径

**文件：**
- `webnovel-writer/scripts/migrate_v6_to_v7.py`
- `webnovel-writer/scripts/data_modules/tests/test_migrate_v6_to_v7.py`
- `webnovel-writer/skills/webnovel-plan/SKILL.md`
- `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py`

- [ ] 先改失败断言：迁移测试将原 `卷纲/第01卷.md` 改为 `卷纲/第01卷-详细大纲.md`，并断言旧无后缀文件不存在。
- [ ] 新增 prompt integrity 断言：

```python
def test_plan_skill_writes_canonical_detailed_outline_path():
    text = (PLUGIN_ROOT / "skills" / "webnovel-plan" / "SKILL.md").read_text(encoding="utf-8")
    assert "大纲/卷纲/第{volume_id}卷-详细大纲.md" in text
    assert "## 第N章：标题" in text
```

- [ ] 运行 RED：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_migrate_v6_to_v7.py webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py -q --no-cov -p no:cacheprovider
```

- [ ] 最小实现：
  - `_migrate_outlines` 目标从 `f"{stem}.md"` 改为 `f"{stem}-详细大纲.md"`；
  - plan skill 的详细大纲路径改为规范路径；
  - 输出格式处增加 `## 第N章：标题` 硬约束；
  - 节拍表/时间线/总纲写回路径不改。
- [ ] 运行上述定点测试和 `validate_reference_wiring.py`。
- [ ] 提交：

```text
fix(migrate): 详细大纲保留后缀并统一 plan 输出路径
```

## Task 3：读取链复用共享解析器

**文件：**
- `webnovel-writer/scripts/v7_write.py`
- `webnovel-writer/scripts/chapter_outline_loader.py`
- `webnovel-writer/scripts/chapter_paths.py`
- 相关既有测试

- [ ] 在 `test_v7_write_pack_sections.py` 新增旧 nested fallback 与规范路径优先测试。
- [ ] 在 `test_chapter_outline_directive.py` 新增仅存在 `大纲/卷纲/第01卷-详细大纲.md` 时仍能加载 directive 的测试。
- [ ] 为 `chapter_paths.extract_chapter_title` 增加 space/H2/中文章号测试。
- [ ] 运行 RED：至少 v6 loader 的规范 nested 路径用例失败。
- [ ] 实现：
  - `v7_write._sec_outline_excerpt` 用 `resolve_detailed_outline` + `extract_chapter_section`；
  - `chapter_outline_loader._find_volume_outline_file` 先调用共享 resolver；
  - `_extract_outline_section` 调共享节选函数，保留 split-outline 高优先级；
  - `chapter_paths._extract_title_from_outline_text` 调共享标题函数。
- [ ] 运行：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_v7_write_pack_sections.py webnovel-writer/scripts/data_modules/tests/test_chapter_outline_directive.py webnovel-writer/scripts/data_modules/tests/test_outline_label_matching.py -q --no-cov -p no:cacheprovider
```

- [ ] 提交：

```text
refactor(outline): v6/v7 读取链复用统一详细大纲解析器
```

## Task 4：人物字段、标题 warning、承诺 error

**文件：**
- 新增 `webnovel-writer/scripts/data_modules/chapter_outline_validate.py`
- 修改 `chapter_outline_batch.py`
- 修改 `test_chapter_outline_batch.py`

- [ ] 扩展测试夹具：创建规范详细大纲和承诺条目。
- [ ] 新增测试：

```python
def test_title_mismatch_is_warning_but_card_is_written(book):
    _write_outline(book, "## 第43章：夜袭\n目标")
    report = create_chapter_batch(book, [_card(43, 标题="错名", 人物=["苏小白"])])
    assert report["ok"] is True
    assert any(item["code"] == "outline_title_mismatch" for item in report["warnings"])
    assert (book / "大纲" / "章纲" / "0043.md").is_file()


def test_missing_promise_is_error_with_zero_side_effects(book):
    report = create_chapter_batch(book, [_card(43, 承诺推进=["F-999: 推进"])])
    assert report["ok"] is False and report["error"] == "consistency_gate"
    assert any(item["code"] == "promise_not_found" for item in report["errors"])
    assert not (book / "大纲" / "章纲" / "0043.md").exists()
    assert not (book / "作者" / "journal.jsonl").exists()


def test_people_round_trip_as_json_list(book):
    report = create_chapter_batch(book, [_card(43, 人物=["苏小白", "林知夏"])])
    assert report["ok"] is True
    fields, _ = parse_chapter_card((book / "大纲" / "章纲" / "0043.md").read_text(encoding="utf-8"))
    assert fields["人物"] == ["苏小白", "林知夏"]
```

- [ ] 运行 RED。
- [ ] 实现 `chapter_outline_validate.py` 的 finding helper、标题与承诺检查：

```python
def finding(code: str, chapter: int, message: str, **details) -> dict[str, Any]:
    return {"code": code, "chapter": int(chapter), "message": message, "details": details}


def validate_chapter_batch(project_root, cards) -> dict[str, list[dict[str, Any]]]:
    errors, warnings = [], []
    # 按 card["卷"] 解析详细大纲；标题缺失/不一致进 warnings。
    # load_entries 建 ID 集；承诺取 ":" 前 ID，不存在进 errors。
    return {"errors": errors, "warnings": warnings}
```

- [ ] `chapter_outline_batch`：
  - `LIST_FIELDS` / `_FIELD_ORDER` 加 `人物`；
  - 调 `validate_chapter_batch`；
  - errors 非空立即返回，且在 `_chapter_dir(...).mkdir` 之前；
  - 成功返回 `errors=[]`, `warnings`, `checks=[message...]`。
- [ ] 运行定点测试。
- [ ] 提交：

```text
feat(chapter-batch): 新增人物字段与标题/承诺一致性闸
```

## Task 5：时间、战力、人物检查

**文件：**
- `chapter_outline_validate.py`
- `test_chapter_outline_batch.py`

- [ ] 新增测试：
  - confirmed `0042.md` 时间锚 `第42日·夜`，新卡 43 为 `第41日·晨` → `time_regression` error、零落盘；
  - 历史定稿 front matter `书内时间: 末世第42天` 同样形成基线；
  - 新卡时间 `灾变后第三周` → `time_unparseable` warning、仍落盘；
  - 境界链含 `聚气/凝罡`，事件 `筑基突破` → `unknown_realm` warning；
  - 无力量锚点但有事件 → `power_anchor_missing` warning；
  - 名册只有苏小白，`人物=["苏小白","林知夏"]` → 只对林知夏 `unknown_character` warning；
  - 旧卡无 `人物` → 无人物 warning。
- [ ] 运行 RED。
- [ ] 实现：
  - `_max_prior_anchor_day(root, before_chapter)` 扫 confirmed 卡和更早定稿正文；
  - 使用 `parse_anchor_day`，同日允许；
  - `load_anchor` 后取 `境界链[].名`，事件子串匹配；
  - `load_known_names` 提供正名/别名集合。
- [ ] 运行：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_chapter_outline_batch.py webnovel-writer/scripts/tests/test_continuity_check.py webnovel-writer/scripts/tests/test_power_anchor.py webnovel-writer/scripts/tests/test_promise_ledger.py -q --no-cov -p no:cacheprovider
```

- [ ] 提交：

```text
feat(chapter-batch): 增加跨批时间、战力境界与人物一致性检查
```

## Task 6：冒烟、回归、状态回写

- [ ] 复制 fantasy01 到临时目录，保留规范 `第02卷-详细大纲.md`，调用 `create_chapter_batch` 构造第 43 章「夜袭」测试卡；断言标题无 warning。
- [ ] 构造错标题副本，断言 `outline_title_mismatch` 且仍写 draft 卡。
- [ ] 运行：

```powershell
python -X utf8 -m pytest -o addopts="" -q
python -X utf8 -m pytest -q -p no:cacheprovider
python -X utf8 webnovel-writer/scripts/run_behavior_evals.py --suite fast
python -X utf8 webnovel-writer/scripts/validate_plugin_package.py
python -X utf8 webnovel-writer/scripts/validate_reference_wiring.py
python -X utf8 webnovel-writer/scripts/sync_plugin_version.py --check
```

- [ ] 在 `docs/zcode/v8-gap-review-3rounds/README.md` 对 P2-1/P2-2 写入验收原文、commit 和实际输出；更新交接文件。
- [ ] 提交：

```text
docs: 阶段二 P2-1/P2-2 验收对账与交接
```
