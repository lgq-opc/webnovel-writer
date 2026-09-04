# 阶段二数据不变量校验器 实施计划

> **执行者注意：** 按任务逐个实施，用 subagent-driven-development（推荐）或逐批人工执行。
> 步骤用 checkbox（`- [ ]`）语法跟踪，完成即勾选。

**目标：** 实现 `06-data-design.md` §12 六条不变量的只读统一报告与 `webnovel.py invariants` CLI。
**架构：** `invariant_check.py` 每项一个纯检查函数，统一 finding/result/report schema；现有模块只作为数据源。`author_journal.mark_stale` 仅新增可选 `since_chapter`，使第六项未来可计算。
**技术栈：** Python 3.10+、pytest、标准库 `json/csv/pathlib/re`。
**Spec：** `docs/cursor/阶段二-数据不变量/2026-09-04-data-invariants-spec.md`

## 全局约束

- 六项检查恒各返回一个 `pass/fail/warn/skip` 结果。
- `ok` 只受 fail 影响；warn/skip 的 CLI 退出码仍为 0。
- 纯 v7 无 `.story-system` 时合同项必须 skip，不得伪造合同。
- 校验器只读；不执行冻结、retcon、合同持久化、素材/条目修复或 git 操作。
- journal migration 汇总事件豁免 `domain=其他`；待语义补全只 warning。
- 素材 `live` 查活层，`vNN` 同时查 manifest、对应定版 CSV 和条目。
- 作废条目按埋设章推算卷，必须有同卷 journal+演化 retcon 双记录。
- stale 新增可选 `since_chapter`；旧项无字段只 warning。
- Windows 命令统一 `python -X utf8`；覆盖率不低于 80%。

## 执行总览

| 序号 | 任务名 | 依赖 | 验证方式 |
|---|---|---|---|
| 1 | `invariants/1` 报告骨架 + CLI 接线 | — | 六项基线结果、筛选、text/json、退出码测试 |
| 2 | Inv-1 journal + Inv-2 素材轨迹 | 依赖 Task 1 | unclassified/migration/semantic；live/vNN manifest 矩阵 |
| 3 | Inv-3 战例/境界链 + Inv-4 条目/retcon | 依赖 Task 1；可与 Task 2 并行 | 无正文、坏链、作废缺双记录测试 |
| 4 | stale `since_chapter` + Inv-6 卷龄 | 依赖 Task 1；可与 Task 2-3 并行 | 新字段、超卷 fail、旧项 warn |
| 5 | Inv-5 runtime contract 重建对账 | 依赖 Task 1、章纲路径计划 Task 3 | 纯 v7 skip、篡改 review/volume fail、无样本 warn |
| 6 | fantasy01 六项冒烟、全量回归、状态回写 | 依赖 Task 1-5 | `invariants --format json` 恰有 6 项；全量 pytest/cov |

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `webnovel-writer/scripts/data_modules/invariant_check.py` | 新增 | 六项检查、汇总、格式化、CLI |
| `webnovel-writer/scripts/data_modules/author_journal.py` | 修改 | stale 新增 `since_chapter` |
| `webnovel-writer/scripts/data_modules/webnovel.py` | 修改 | `invariants` 子命令与宽松 v7 根解析 |
| `webnovel-writer/scripts/tests/test_invariant_check.py` | 新增 | 六项行为与 CLI 核心测试 |
| `webnovel-writer/scripts/tests/test_author_journal.py` | 修改 | `since_chapter` 兼容测试 |
| `webnovel-writer/scripts/tests/test_webnovel_unified_cli.py` | 修改 | 统一 CLI 转发/退出码 |
| `webnovel-writer/scripts/data_modules/tests/test_prompt_integrity.py` | 修改 | CLI 注册表登记 `invariants` |
| `docs/zcode/v8-gap-review-3rounds/README.md` | 修改 | P2-3 验收证据 |
| `docs/cursor/项目复审/2026-09-04-会话交接.md` | 修改 | 交接 |

---

## Task 1：报告骨架与 CLI

**文件：**
- 新增 `invariant_check.py`
- 新增 `test_invariant_check.py`
- 修改 `webnovel.py`
- 修改 prompt integrity / unified CLI 测试

- [ ] 写失败测试：

```python
from data_modules import invariant_check


def test_empty_v7_book_always_returns_six_results(tmp_path):
    (tmp_path / "book.yaml").write_text("书名: 测试\n", encoding="utf-8")
    report = invariant_check.run_invariants(tmp_path)
    assert report["schema_version"] == "invariants/1"
    assert [item["id"] for item in report["invariants"]] == [
        "inv-1-journal", "inv-2-material-trajectory", "inv-3-power",
        "inv-4-promises", "inv-5-contracts", "inv-6-stale-age",
    ]
    assert report["summary"] == {"pass": 5, "fail": 0, "warn": 0, "skip": 1}
    assert report["ok"] is True


def test_summary_fails_only_on_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(invariant_check, "CHECKS", (
        ("a", lambda _root: invariant_check.result("a", "A", "warn")),
        ("b", lambda _root: invariant_check.result("b", "B", "skip")),
        ("c", lambda _root: invariant_check.result("c", "C", "fail")),
    ))
    report = invariant_check.run_invariants(tmp_path)
    assert report["ok"] is False
    assert report["summary"] == {"pass": 0, "fail": 1, "warn": 1, "skip": 1}


def test_only_filters_and_rejects_unknown_id(tmp_path):
    assert len(invariant_check.run_invariants(tmp_path, only=["inv-1-journal"])["invariants"]) == 1
    with pytest.raises(ValueError, match="unknown invariant"):
        invariant_check.run_invariants(tmp_path, only=["inv-999"])
```

- [ ] 运行 RED：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_invariant_check.py -q --no-cov -p no:cacheprovider
```

- [ ] 实现报告骨架：

```python
SCHEMA_VERSION = "invariants/1"


def finding(code, message, *, ref="", path="", **details):
    return {"code": code, "ref": ref, "path": path, "message": message, "details": details}


def result(check_id, title, status, *, findings=None, counts=None, repair=""):
    return {
        "id": check_id, "title": title, "status": status,
        "findings": list(findings or []), "counts": dict(counts or {}), "repair": repair,
    }


def run_invariants(root, *, only=None):
    selected = CHECKS if only is None else _select_checks(only)
    items = [check(Path(root)) for _, check in selected]
    summary = {status: sum(i["status"] == status for i in items) for status in ("pass", "fail", "warn", "skip")}
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": summary["fail"] == 0,
        "project_root": str(Path(root)),
        "summary": summary,
        "invariants": items,
    }
```

初始六个检查函数返回：无数据的 journal/material/power/promises/stale 为 pass，contracts 为 skip。Task 2-5 替换实现。

- [ ] `webnovel.py` 新增：

```python
def cmd_invariants(args):
    from data_modules import invariant_check
    root = _resolve_root_lenient(args.project_root)
    only = [part.strip() for part in args.only.split(",") if part.strip()]
    return invariant_check.main([
        "--project-root", str(root), "--format", args.format,
        *(["--only", ",".join(only)] if only else []),
    ])
```

parser 注册 `invariants --format text|json --only ""`；prompt CLI 注册表加 `"invariants"`。

- [ ] 新增 subprocess 测试：纯 v7 book 调 `webnovel.py --project-root <root> invariants --format json` 返回 0、JSON 有 6 项。
- [ ] 运行 GREEN。
- [ ] 提交：

```text
feat(invariants): 添加六项报告骨架与统一 CLI
```

## Task 2：Inv-1 journal 与 Inv-2 素材轨迹

- [ ] 新增 journal 测试：
  - 合法 journal → pass；
  - 普通 `domain=其他` → fail；
  - `(bulk)` + `impact=["migration"]` → pass；
  - 空 summary edit → warn；
  - 非法枚举 → fail。
- [ ] 新增素材测试：
  - live ID 存在 → pass，删除行后 fail；
  - v01 manifest + CSV + ID 齐全 → pass；
  - 分别删除 manifest、CSV、manifest source_files 项、CSV 中 ID → fail；
  - 无轨迹 → pass。
- [ ] 运行 RED。
- [ ] 实现 `check_journal`：

```python
events = read_journal(root)
schema_problems = validate_journal(root)
unclassified = [
    (index, event) for index, event in enumerate(events, 1)
    if event.get("domain") == "其他"
    and not (event.get("path") == "(bulk)" and "migration" in (event.get("impact") or []))
]
semantic = pending_semantic(root)
status = "fail" if schema_problems or unclassified else ("warn" if semantic else "pass")
```

- [ ] 实现 `check_material_trajectory`：
  - 用 `read_trajectory`，另逐行读取原文件以保留行号和坏 JSON finding；
  - live 在 `素材/活/*.csv` 全表按 `id` 查；
  - `vNN` 校验 manifest、source filename、同目录 CSV ID；
  - 结果 counts 含 `rows/live/frozen/invalid`。
- [ ] 运行：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_invariant_check.py webnovel-writer/scripts/tests/test_author_journal.py webnovel-writer/scripts/tests/test_material_usage.py -q --no-cov -p no:cacheprovider
```

- [ ] 提交：

```text
feat(invariants): 校验 journal 积压与素材轨迹来源
```

## Task 3：Inv-3 力量与 Inv-4 条目

- [ ] 力量测试：
  - 无 anchor → skip；
  - 战例章有 `定稿/正文/0037-*.md` 且链合法 → pass；
  - 缺正文 → fail；
  - 境界序重复/名称重复 → fail；
  - 非整数战例章 → fail。
- [ ] 条目测试：
  - 无条目 → pass；
  - `已回收` 缺回收章、回收章早于埋设章 → fail；
  - open 带回收章 → fail；
  - 作废条目同卷 journal+演化 retcon 齐全 → pass；
  - 分别缺一侧 → fail。
- [ ] 运行 RED。
- [ ] 实现 `check_power_anchor`：

```python
path = root / "设定" / "力量锚点.yaml"
if not path.is_file():
    return result("inv-3-power", TITLE, "skip", repair="先运行 power anchor extract/apply")
anchor = load_anchor(root)
problems = list(validate_chain(anchor))
for battle in anchor.get("战例账本") or []:
    try:
        chapter = int(battle.get("章"))
    except (TypeError, ValueError):
        problems.append("战例章号非整数")
        continue
    if not has_v7_settled_chapter(root, chapter):
        problems.append(f"战例章 {chapter} 无定稿正文")
```

- [ ] 实现 `check_promise_states`：
  - `load_entries` 的 parse 结果逐项验证字段约束；
  - `_volume_of_chapter(chapter, size)` 统一 `(chapter-1)//size+1`；
  - journal retcon 卷从 path `vNN` 解析；
  - evolution retcon 卷从文件名解析；
  - 作废条目要求卷同时属于两集合。
- [ ] 运行定点测试。
- [ ] 提交：

```text
feat(invariants): 校验战例正文、境界链与条目 retcon 状态
```

## Task 4：stale `since_chapter` 与 Inv-6

**文件：**
- `author_journal.py`
- `invariant_check.py`
- `test_author_journal.py`
- `test_invariant_check.py`

- [ ] 写失败测试：

```python
def test_mark_stale_records_current_max_settled_chapter(tmp_path):
    body = tmp_path / "定稿" / "正文" / "0042-夜袭.md"
    body.parent.mkdir(parents=True)
    body.write_text("---\n章号: 42\n---\n正文", encoding="utf-8")
    mark_stale(tmp_path, target="timeline:recheck", reason="卷纲变更")
    assert read_stale(tmp_path)[0]["since_chapter"] == 42


def test_old_stale_without_since_chapter_is_warn(tmp_path):
    _write_stale_fixture(tmp_path, [{"target": "x", "since": "2026-09-01T00:00:00+08:00", "consumed": False}])
    assert invariant_check.check_stale_age(tmp_path)["status"] == "warn"


def test_stale_older_than_one_volume_fails(tmp_path):
    (tmp_path / "book.yaml").write_text("卷规模: 40\n", encoding="utf-8")
    _write_settled_chapter(tmp_path, 82)
    _write_stale_fixture(tmp_path, [{"target": "x", "since_chapter": 41, "consumed": False}])
    report = invariant_check.check_stale_age(tmp_path)
    assert report["status"] == "fail"
    assert report["findings"][0]["code"] == "stale_over_one_volume"
```

- [ ] 运行 RED。
- [ ] 提取 `max_settled_chapter(root)`（建议放 `invariant_check.py` 不合适，因为 author_journal 不能反向依赖校验器；放 `dual_format_guard.py` 的公共 helper 或 `chapter_paths.py`）。
- [ ] `mark_stale` 写 `since_chapter=max_settled_chapter(root)`。
- [ ] `check_stale_age`：卷规模读 `book.yaml` 顶层标量，非法回退 50；差值严格 `>` 才 fail。
- [ ] 运行定点测试。
- [ ] 提交：

```text
feat(stale): 记录起始章并校验未消费项是否超过一卷
```

## Task 5：Inv-5 runtime contract 重建对账

**前置：** 章纲一致性计划 Task 3 已让 `RuntimeContractBuilder` 间接使用统一详细大纲路径。

- [ ] 新增测试夹具：按 `test_runtime_contract_builder.py` 建合法 `.story-system/MASTER_SETTING.json`、`anti_patterns.json`、state 和详细大纲；调用 builder 生成并持久化 volume/review。
- [ ] 测试：
  - 纯 v7 无 `.story-system` → skip；
  - 合同刚生成 → pass；
  - 修改 review `must_check` → fail；
  - 修改 volume `selected_scenes` → fail；
  - 有 `.story-system` 但无 review 文件 → warn；
  - 坏 MASTER_SETTING → fail，不抛出到 CLI。
- [ ] 运行 RED。
- [ ] 实现：
  - 用 `StoryContractPaths` 枚举 `reviews/chapter_*.review.json`；
  - 从文件名取 chapter；
  - `RuntimeContractBuilder(root).build_for_chapter(chapter)`；
  - `read_json_if_exists` 后做 dict/list 对象相等比较；
  - 同一 volume 多章时，磁盘 volume 应等于最后一次/当前 builder 的确定性结果；每个 review 都比较，volume 只按去重卷比较一次，并在 finding 标 chapter/volume；
  - 捕获 schema/JSON/build 异常转 finding，单项 fail。
- [ ] 运行：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_invariant_check.py webnovel-writer/scripts/data_modules/tests/test_runtime_contract_builder.py webnovel-writer/scripts/data_modules/tests/test_story_contracts.py -q --no-cov -p no:cacheprovider
```

- [ ] 提交：

```text
feat(invariants): 重建并对账 runtime story contracts
```

## Task 6：fantasy01 冒烟与收尾

- [ ] 复制 fantasy01 到临时目录；运行：

```powershell
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root "$env:TEMP/fantasy01-invariants" invariants --format json
```

- [ ] 验收“fantasy01 跑出六条各自结论”：断言 `len(invariants)==6`，逐项记录真实 status/findings；合同项应 skip。
- [ ] 运行全量验证：

```powershell
python -X utf8 -m pytest -o addopts="" -q
python -X utf8 -m pytest -q -p no:cacheprovider
python -X utf8 webnovel-writer/scripts/run_behavior_evals.py --suite fast
python -X utf8 webnovel-writer/scripts/validate_plugin_package.py
python -X utf8 webnovel-writer/scripts/validate_reference_wiring.py
python -X utf8 webnovel-writer/scripts/sync_plugin_version.py --check
```

- [ ] 在 gap-review README 的 P2-3 行写六项真实结果、commit、测试与覆盖率；更新交接。
- [ ] 提交：

```text
docs: 阶段二 P2-3 六项不变量验收对账与交接
```
