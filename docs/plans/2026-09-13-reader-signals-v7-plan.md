# reader_signals 在 v7 接通 实施计划

> **执行者注意：** 按任务逐个实施。步骤用 checkbox（`- [ ]`）跟踪，完成即勾选。
> **完成注记（2026-09-22 回写）**：Task 1-6 已全部实施落地——`v7_cache.py` 追读力表（建表/INSERT/查询）、`v7_write.py` settle 钩子写 front matter + check 硬闸 + 后置钩子三件套、消费侧 `index` 派发分流均经 2026-09-21 复审核验（硬证据：`v7_cache.py:222/:241/:332-371`、`v7_write.py:455-513/:672`；行为测试 `test_reader_signal.py` 3 用例直接锁定）。落地提交：`1a080a5`（Task 1 追读力表 schema v2）、`2e43209`（Task 5 v7 仓改读 .cache），Task 2-4/6 随 v7-write 系列提交；`releases/v8.1.1.md:25` 已对外宣称该设计单落地。本次回写补勾 35 个步骤 checkbox，两处「实施订正」注记保留原文。
> **先读 spec：** `docs/plans/2026-09-13-reader-signals-v7-spec.md`（本计划从 spec 论证）。
> 测试命令一律 `$env:PYTHONUTF8=1; python -X utf8 -m pytest <路径> -q`（AGENTS.md 口径）。

**目标：** 让 v7 写链真正产出 `chapter_reading_power`，`.cache` 可从 canonical 源重建该数据，消费侧读到真数据——且钩子缺失时由机检拦下而非静默跳过。

**架构：** 钩子由决策卡显式声明（或显式豁免）→ `settle` 写进 `定稿/正文/NNNN-标题.md` 的 front matter（唯一事实源）→ `rebuild_cache` 从其重算进 `.cache/index.db::chapter_reading_power`（纯派生物）→ pack / `index get-reader-signals` / MCP 读取。`settle_reading_power` 的写盘职责退役。

**技术栈：** Python 3.13、sqlite3（stdlib）、pytest；无新增依赖。

**Spec：** `docs/plans/2026-09-13-reader-signals-v7-spec.md`

## 全局约束

- **不新增依赖**；只用 stdlib（sqlite3 / re / pathlib）。
- **中文 commit message 必须 UTF-8 文件 + `git commit -F <file>`**（AGENTS.md）。
- **不动 v6 侧行为**：v6 形态仓（`resolve_write_mode() == "v6"`）读写路径原样保留；每个任务都要有反向守住用例。
- **形态判据统一用 `domain_contract.resolve_write_mode()`**，不另立第二套。
- **钩子强度词表归一**：`强/中/弱` → `strong/medium/weak`；空值 → `medium`。
- **`check` 硬闸**（Human 2026-09-13 裁定）：`hook_type` 非空 **或** `hook_waiver` 非空，否则退出码 2。
- **每任务跑完必须全量 pytest 绿**；`smart-commit.py --check` 对照后再提交。

## 执行总览

| 序号 | 任务 | 依赖 | 验证方式 |
|---|---|---|---|
| Task 1 | `v7_cache` 加表 + schema 版本 + 重建/查询 | — | 新测试文件红→绿；`v7-cache verify` `equal=True` |
| Task 2 | `settle` 把钩子写入正文 front matter | — | `test_v7_write.py` 断言 front matter 含 `钩子类型:` |
| Task 3 | `run_checks` 钩子硬闸 | — | 无钩子无豁免 → 退出码 2；带豁免 → 通过 |
| Task 4 | 退役 `settle_reading_power` 写盘 + `post["reading"]` 形状 | 依赖 Task 2 | `test_v7_write_post_hooks.py` 改写后全绿 |
| Task 5 | 消费侧 v7 分支（`build_reader_signal` + `index` 派发） | 依赖 Task 1 | 端到端断言非空；v6 反向守住 |
| Task 6 | 冒烟断言升级 + 文档回改（W12）+ 提交 | 依赖 Task 1-5 | 冒烟 PASS；四校验；CI 双平台绿 |

可并行：Task 1 / Task 2 / Task 3 互不依赖。

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `webnovel-writer/scripts/v7_cache.py` | v7 派生缓存：表结构、重建、查询 | 改 |
| `webnovel-writer/scripts/v7_write.py` | 写链：机检、settle、front matter、后置钩子 | 改 |
| `webnovel-writer/scripts/data_modules/reading_power_projection.py` | 追读力写盘（退役） | 改 |
| `webnovel-writer/scripts/data_modules/reader_signal_builder.py` | 读者信号装配（消费侧） | 改 |
| `webnovel-writer/scripts/data_modules/webnovel.py` | 统一 CLI 派发（`index` 分流） | 改 |
| `webnovel-writer/scripts/data_modules/tests/test_v7_cache.py` | Task 1 测试 | 改（**2026-09-13 实施订正**：原计划新建 `test_v7_cache_reading_power.py`；实施时改为此文件新增 `TestReadingPowerFromFrontMatter` 类——它已有可复用的 `_raw_v7_repo` 夹具，新建文件会重复造夹具且分散同一模块的测试） |
| `webnovel-writer/scripts/data_modules/tests/test_v7_write_post_hooks.py` | Task 4 改写 | 改 |
| `webnovel-writer/scripts/data_modules/tests/test_v7_write_gates.py` | `_decision()` 夹具补默认豁免 | 改 |
| `webnovel-writer/scripts/smoke_v7_newbook.py` | 端到端断言升级 | 改 |

---

## Task 1：`v7_cache` 追读力表

**验证/MCP：** 无特殊需求（stdlib sqlite3）。

- [x] 写失败测试（**实施订正**：追加到既有 `webnovel-writer/scripts/data_modules/tests/test_v7_cache.py`，
  新增 `TestReadingPowerFromFrontMatter` 类并补两处 import；不新建文件，理由见「文件结构」表）：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Task 1：.cache 追读力表 —— 从 定稿/正文 front matter 重算，schema 版本化。"""
from __future__ import annotations

import sys
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import v7_cache  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "定稿" / "正文").mkdir(parents=True)
    (repo / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    (repo / "定稿" / "正文" / "0001-开篇.md").write_text(
        "---\n章号: 1\n标题: 开篇\n钩子类型: 危机钩\n钩子强度: 强\n---\n正文\n", encoding="utf-8"
    )
    (repo / "定稿" / "正文" / "0002-过渡.md").write_text(
        "---\n章号: 2\n标题: 过渡\n---\n正文\n", encoding="utf-8"
    )
    return repo


def test_rebuild_collects_reading_power_from_front_matter(tmp_path: Path):
    repo = _repo(tmp_path)
    v7_cache.rebuild_cache(repo)
    rows = v7_cache.get_recent_reading_power(repo, limit=5)
    assert rows == [{"chapter": 1, "hook_type": "危机钩", "hook_strength": "strong"}]


def test_rebuild_skips_chapter_without_hook(tmp_path: Path):
    repo = _repo(tmp_path)
    v7_cache.rebuild_cache(repo)
    chapters = {r["chapter"] for r in v7_cache.get_recent_reading_power(repo, limit=10)}
    assert 2 not in chapters


def test_hook_type_usage_counts_within_last_n(tmp_path: Path):
    repo = _repo(tmp_path)
    v7_cache.rebuild_cache(repo)
    assert v7_cache.get_hook_type_usage(repo, last_n=20) == {"危机钩": 1}


def test_verify_rebuild_covers_reading_power(tmp_path: Path):
    """不变量：删缓存 → 重建 → 快照等价（含追读力表）。"""
    repo = _repo(tmp_path)
    v7_cache.rebuild_cache(repo)
    assert v7_cache.verify_rebuild(repo)["equal"] is True


def test_legacy_cache_without_schema_version_is_rebuilt(tmp_path: Path):
    """旧缓存（无 schema_version）不得被判为完好——否则新表缺失、查询报错。"""
    import sqlite3

    repo = _repo(tmp_path)
    cache = v7_cache.cache_path(repo)
    cache.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cache)
    conn.executescript(
        "CREATE TABLE chapters (num INTEGER PRIMARY KEY, title TEXT, volume INTEGER,"
        " words INTEGER, file TEXT, body TEXT);"
        "CREATE TABLE entities (name TEXT PRIMARY KEY, aliases TEXT, first_chapter TEXT NOT NULL DEFAULT '');"
        "CREATE TABLE summaries (num INTEGER PRIMARY KEY, content TEXT);"
        "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);"
    )
    conn.commit()
    conn.close()
    assert v7_cache.get_recent_reading_power(repo, limit=5) == [
        {"chapter": 1, "hook_type": "危机钩", "hook_strength": "strong"}
    ]
```

- [x] 跑它确认失败：
  `$env:PYTHONUTF8=1; python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_v7_cache_reading_power.py -q`
  预期：`AttributeError: module 'v7_cache' has no attribute 'get_recent_reading_power'`。

- [x] 实现。`v7_cache.py` 增常量与函数：

```python
_CACHE_SCHEMA_VERSION = "2"

_HOOK_STRENGTH_ALIASES = {"强": "strong", "中": "medium", "弱": "weak"}
_REQUIRED_TABLES = ("chapters", "entities", "summaries", "meta")


def _normalize_hook_strength(value: str) -> str:
    """钩子强度归一：章纲侧写 强/中/弱，追读力表用 strong/medium/weak。"""
    text = str(value or "").strip()
    if not text:
        return "medium"
    return _HOOK_STRENGTH_ALIASES.get(text, text)


def _iter_reading_power(repo_root: Path):
    """追读力源＝定稿/正文 front matter（钩子由 settle 从决策卡写入）。

    与 书内时间/推进承诺/合同 同处 canonical；不读 工作区/（草稿区可清理）。
    """
    body_dir = Path(repo_root) / "定稿" / "正文"
    if not body_dir.exists():
        return
    for path in sorted(body_dir.glob("*.md")):
        num, _ = _parse_chapter_filename(path.name)
        if num is None:
            continue
        fields, _ = _parse_front_matter(_read(path))
        hook_type = str(fields.get("钩子类型") or "").strip()
        if not hook_type:
            continue
        yield {
            "chapter": num,
            "hook_type": hook_type,
            "hook_strength": _normalize_hook_strength(fields.get("钩子强度", "")),
        }


def get_recent_reading_power(repo_root: Path, limit: int = 5) -> list[dict[str, Any]]:
    conn = _conn(repo_root)
    try:
        rows = conn.execute(
            "SELECT chapter, hook_type, hook_strength FROM chapter_reading_power"
            " ORDER BY chapter DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    finally:
        conn.close()
    return [{"chapter": r[0], "hook_type": r[1], "hook_strength": r[2]} for r in rows]


def get_hook_type_usage(repo_root: Path, last_n: int = 20) -> dict[str, int]:
    conn = _conn(repo_root)
    try:
        rows = conn.execute(
            "SELECT hook_type, COUNT(*) FROM ("
            " SELECT hook_type FROM chapter_reading_power"
            " WHERE hook_type != '' ORDER BY chapter DESC LIMIT ?"
            ") GROUP BY hook_type",
            (int(last_n),),
        ).fetchall()
    finally:
        conn.close()
    return {r[0]: r[1] for r in rows}
```

- [x] `rebuild_cache` 建表并写入。在 `CREATE TABLE meta ...` 后追加：

```sql
CREATE TABLE chapter_reading_power (chapter INTEGER PRIMARY KEY,
                                    hook_type TEXT NOT NULL DEFAULT '',
                                    hook_strength TEXT NOT NULL DEFAULT 'medium');
```

并在 `conn.executemany("INSERT INTO meta VALUES (?,?)", [...])` 的列表里追加两项
`("schema_version", _CACHE_SCHEMA_VERSION)`；在其后追加：

```python
        conn.executemany(
            "INSERT INTO chapter_reading_power VALUES (?,?,?)",
            [(r["chapter"], r["hook_type"], r["hook_strength"]) for r in _iter_reading_power(repo_root)],
        )
```

- [x] `_cache_intact` 改为同时校验 schema 版本：

```python
def _cache_intact(path: Path) -> bool:
    """健康检查：核心表齐备 **且** schema 版本匹配（旧版缓存首查即重建）。"""
    try:
        conn = sqlite3.connect(path)
        try:
            row = conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name IN (?,?,?,?)",
                _REQUIRED_TABLES,
            ).fetchone()
            if not row or row[0] != len(_REQUIRED_TABLES):
                return False
            version = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            return bool(version) and version[0] == _CACHE_SCHEMA_VERSION
        finally:
            conn.close()
    except sqlite3.Error:
        return False
```

- [x] `snapshot` 纳入新表（保住不变量验收面）——在 `summaries = ...` 后追加：

```python
        reading_power = conn.execute(
            "SELECT chapter, hook_type, hook_strength FROM chapter_reading_power ORDER BY chapter"
        ).fetchall()
```
并把返回改为 `{..., "reading_power": reading_power}`。

- [x] 跑测试确认通过（同一命令）；预期 5 passed。

- [x] 全量回归：`$env:PYTHONUTF8=1; python -X utf8 -m pytest -q`
- [x] 提交：`feat(v7-cache): .cache 新增追读力表，从正文 front matter 重算（schema v2）`

## Task 2：`settle` 写钩子进正文 front matter

**验证/MCP：** 无特殊需求。

- [x] 写失败测试。追加到 `webnovel-writer/scripts/data_modules/tests/test_v7_write.py`：

```python
def test_settle_writes_hook_into_front_matter(tmp_path: Path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    d = _decision(hook_type="危机钩", hook_strength="强")
    _settle(repo, d)
    text = next((repo / "定稿" / "正文").glob("0042-*.md")).read_text(encoding="utf-8")
    assert "钩子类型: 危机钩" in text
    assert "钩子强度: strong" in text


def test_settle_omits_hook_lines_when_waived(tmp_path: Path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    _settle(repo, _decision(hook_waiver="本章为过渡章，无钩子"))
    text = next((repo / "定稿" / "正文").glob("0042-*.md")).read_text(encoding="utf-8")
    assert "钩子类型:" not in text
```

- [x] 跑它确认失败：
  `$env:PYTHONUTF8=1; python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_v7_write.py -q -k hook`
  预期：`assert '钩子类型: 危机钩' in ...` 失败。

- [x] 实现。`v7_write.py` 在 `:770`（`书内时间` 之后）插入：

```python
    hook_type = str(decision.get("hook_type") or "").strip()
    if hook_type:
        front.append(f"钩子类型: {hook_type}")
        from data_modules.v7_cache import _normalize_hook_strength
        front.append(f"钩子强度: {_normalize_hook_strength(decision.get('hook_strength', ''))}")
```

> 注：`_normalize_hook_strength` 目前是 `v7_cache` 的私有名。为跨模块复用，Task 1 实现时
> 把它改为公开名 `normalize_hook_strength`（`v7_cache.py` 内两处调用同步改），本任务按公开名导入。

- [x] 跑测试确认通过；预期 2 passed。
- [x] 提交：`feat(v7-write): settle 将决策卡钩子写入正文 front matter`

## Task 3：`run_checks` 钩子硬闸

**验证/MCP：** 无特殊需求。

- [x] 先改夹具，让既有用例不被新闸误伤。`test_v7_write_gates.py:75`：

```python
def _decision(**over) -> dict:
    d = {"chapter": 42, "title": "风暴前夜", "entities": ["苏小白"], "promises": [],
         "waiver": "测试", "hook_waiver": "测试", "contract": []}
    d.update(over)
    return d
```

- [x] 写失败测试。追加到 `test_v7_write.py`：

```python
def test_check_rejects_missing_hook(tmp_path: Path):
    repo = _repo(tmp_path)
    result = run_checks(repo, _decision(hook_waiver=""), "正文" * 800)
    assert result["ok"] is False
    assert any(i["category"] == "hook" for i in result["issues"])


def test_check_accepts_hook_waiver(tmp_path: Path):
    repo = _repo(tmp_path)
    result = run_checks(repo, _decision(hook_type="", hook_waiver="过渡章"), "正文" * 800)
    assert result["hook_ok"] is True
```

（`run_checks` 需已在测试文件顶部导入。）

- [x] 跑它确认失败：
  `$env:PYTHONUTF8=1; python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_v7_write.py -q -k "hook"`
  预期：`KeyError: 'hook_ok'`。

- [x] 实现。`v7_write.py:433` 之后追加：

```python
    hook_type = str(decision.get("hook_type") or "").strip()
    hook_ok = bool(hook_type) or bool(decision.get("hook_waiver"))
```

`:473` 的承诺循环之后追加：

```python
    if not hook_ok:
        issues.append(
            {
                "severity": "high",
                "category": "hook",
                "description": "钩子未声明：决策卡需给出 hook_type 或 hook_waiver（追读力投影据此落账）",
                "evidence": "hook_type 为空且无 hook_waiver",
            }
        )
```

`:484` 的 `ok` 表达式加入 `and hook_ok`；`:493` 附近返回体加入 `"hook_ok": hook_ok,`。

- [x] 跑测试确认通过；再跑全量确认无回归。
- [x] 提交：`feat(v7-write): 决策卡钩子改硬闸（hook_type 或 hook_waiver）`

## Task 4：退役 `settle_reading_power` 写盘

**验证/MCP：** 无特殊需求。

- [x] 改写 `test_v7_write_post_hooks.py:71-94` 两条用例：

```python
def test_reading_reported_from_decision_card(tmp_path: Path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    result = settle(
        repo,
        _decision(hook_type="悬念", hook_strength="strong"),
        draft_path=repo / "工作区" / "草稿-0042.md",
        summary="夜未完。",
        commit=False,
    )
    assert result["post"]["reading"]["status"] == "ok"
    assert result["post"]["reading"]["hook_type"] == "悬念"
    cache = repo / ".cache" / "index.db"
    assert cache.is_file()


def test_reading_skipped_when_waived(tmp_path: Path):
    repo = _repo(tmp_path)
    _review(repo, 0)
    result = _settle(repo, _decision(hook_waiver="过渡章"))
    assert result["post"]["reading"]["status"] == "skipped"
```

- [x] 跑它确认失败：
  `$env:PYTHONUTF8=1; python -X utf8 -m pytest webnovel-writer/scripts/data_modules/tests/test_v7_write_post_hooks.py -q`

- [x] 实现：
  - `reading_power_projection.py`：删除 `settle_reading_power` 的 `IndexManager` 写盘路径与
    `ChapterReadingPowerMeta` 构造；保留一个纯函数
    `reading_status(decision_hook_type: str, decision_hook_strength: str) -> dict`，
    返回 `{"status": "ok", "hook_type": ..., "chapter": ...}` 或 `{"status": "skipped", "reason": "not_required"}`。
  - `v7_write._run_post_hooks(repo, chapter, summary_text)` 增参 `decision: dict`，
    用 `post["reading"] = reading_status(...)` 取代原 `settle_reading_power` 调用。
  - `_SETTLE_ADD_PATHS` 移除 `.webnovel/index.db`（v7 不再产生该文件）。
- [x] 跑测试确认通过；全量回归。
- [x] 提交：`refactor(v7-write): 追读力写盘退役，改由缓存重建（移除 v6 域副作用）`

## Task 5：消费侧 v7 分支

**验证/MCP：** 无特殊需求。

- [x] 写失败测试。新增 `test_reader_signal_builder_v7.py`：

```python
def test_v7_repo_reads_reading_power_from_cache(tmp_path: Path):
    repo = _v7_repo_with_hook(tmp_path)   # 造 book.yaml + 正文含钩子 front matter + .cache
    sig = build_reader_signal(repo)
    assert sig["recent_reading_power"][0]["hook_type"] == "危机钩"


def test_v7_repo_without_cache_degrades_gracefully(tmp_path: Path):
    repo = _v7_repo_with_hook(tmp_path)
    (repo / ".cache" / "index.db").unlink()
    sig = build_reader_signal(repo)
    assert sig["recent_reading_power"] == []
```

- [x] 跑它确认失败。
- [x] 实现：
  - `reader_signal_builder.build_reader_signal`：守卫由「`.webnovel/index.db` 存在」改为
    「v7 形态（`resolve_write_mode() == "v7"`）走 `.cache`，否则原路」。
  - `data_modules/webnovel.py:1426` 前插入：

```python
    if tool == "index" and rest[:1] == ["get-reader-signals"]:
        from data_modules import domain_contract

        if domain_contract.resolve_write_mode(project_root) == "v7":
            from data_modules.reader_signal_builder import build_reader_signal

            print(json.dumps(build_reader_signal(project_root), ensure_ascii=False, indent=2))
            raise SystemExit(0)
```

- [x] 跑测试确认通过；**反向守住**：构造 v6 形态仓（含 `state.json`），断言仍走
  `.webnovel/index.db` 且输出形状不变。
- [x] 提交：`feat(mcp): 读者信号在 v7 仓改读 .cache（含 index 派发分流）`

## Task 6：端到端与文档收口

**验证/MCP：** playwright 不需要（纯 CLI）。

- [x] `smoke_v7_newbook.py`：把 `reader-signals` 移出 `:239` 的通用只读工具循环，单独跑。
  **2026-09-13 实施订正（Human 裁定）**：原计划的「直接断言内容非空」在当前冒烟里**必然失败**——
  主流程的 settle 被 **prose 门禁**拒（实测 `码=2 REJECTED … 门禁拒绝（prose）`，fixture 正文命中
  Anti-AI 词库，是交接文件在案的既有 BIZ 基线）→ 定稿/正文无文件 → `.cache` 追读力表为空。
  改为 **旁路 settle 子步骤**：保持主流程只读真实链路、判据不变（settle 被拒仍计 BIZ），
  另加一段用 `--force-review-bypass "<smoke 理由>"`（该参数只放行 ①② 两门禁）让 settle 真正写章，
  随后断言 `reader-signals` 的 `recent_reading_power` 非空且 `hook_type == "危机钩"`。
  理由：既验到端到端钩子链路，又不篡改冒烟对真实链路的监测语义。
- [x] 跑冒烟：`python -X utf8 webnovel-writer/scripts/smoke_v7_newbook.py`
  预期：`reader-signals` PASS 且内容非空；BREAK 仍为 0。
- [x] 文档回改（spec §8）：对账 §D-2 乙就地订正；`SKILL.md:174` 对齐实现；
  `docs/guides/v7-write-path.md` §3 决策卡字段表 +3 行；todohub `t-20260913-6202` 更新范围。
- [x] 四校验：`python -X utf8 webnovel-writer/scripts/validate_reference_wiring.py` 等
  （按 `AGENTS.md` 当前状态节列出的四条）。
- [x] 提交：`docs(v7): 回改对账与 SKILL，reader_signals 接通落地`

---

## 完成判据（引用 spec §7 条目原文）

1. 「新 v7 仓 settle 一章（决策卡带 `hook_type`）→ 定稿/正文 front matter 含 `钩子类型:`；
   `.cache/index.db` 有该章记录；`index get-reader-signals` 返回非空 `recent_reading_power`；
   `v7-cache verify` 仍 `equal=True`（含新表）」
2. 「无 `hook_type` 且无 `hook_waiver` → `check` 退出码 2；带 `hook_waiver` → 通过且该章 `skipped`」
3. 「v6 仓（有 `state.json`）路径行为不变——仍写 `.webnovel/index.db`，读亦原样」
4. 「删 `.cache/` 后 `rebuild` 重算出的追读力与删除前一致」
5. 「`smoke_v7_newbook.py` 的 `reader-signals` 步骤由「仅退出 0」升级为**断言内容非空**」
   ——**2026-09-13 订正**：改为经**旁路 settle** 造出真实钩子后再断言非空（原因见 Task 6 步骤内）。
6. 「全量 pytest + 四校验 + CI 双平台绿」
