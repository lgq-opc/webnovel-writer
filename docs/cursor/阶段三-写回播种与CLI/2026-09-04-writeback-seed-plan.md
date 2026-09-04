# 写回播种 + learn CLI + 重复大纲去重 实施计划

> **执行者注意：** 按任务逐个实施。步骤用 checkbox 跟踪，完成即勾选。
>
> 我在用 writing-plans 技能写实施计划。

**目标：** `promise-ledger seed-from-writeback` 把写回 JSON 的伏笔种进账本；`learn --from-journal` 可直接跑；fantasy01 去掉无后缀详细大纲副本。
**架构：** 在 `promise_ledger.py` 新增 `seed_from_writeback`（复用 `create_entry`）；`learn`/`author_model` 的 action 改为可选默认 `learn`；书仓删除与插件仓分开提交。
**技术栈：** Python 3.10+、pytest、标准库 `json` / `re` / `argparse`。
**Spec：** `docs/cursor/阶段三-写回播种与CLI/2026-09-04-writeback-seed-spec.md`

## 全局约束

- 只读 `foreshadow_writeback`，不播种 `open_loop_writeback`。
- 空 `payoff_chapter` → `due_chapter=0`；名称用 `content` 全文；同名 skip。
- 真仓 fantasy01 **不跑** seed（spec §2）。
- 验收条数 = JSON 数组长度（真仓 7，不造第 8 条）。
- 不改 `create_entry` 的 `action=add`；不改 CLI `create` 的 due 非 0 门。
- 不改 v6 `context_manager` / write-gate / `chapter_commit.py` / `outline_paths.py` 读序。
- 插件仓与 `loom-books/fantasy01` 分开 commit；中文 message 走 UTF-8 文件 + `git commit -F`。
- Windows：`python -X utf8`；覆盖率不低于 80%。

## 执行总览

| 序号 | 任务名 | 依赖 | 验证方式 |
|---|---|---|---|
| 1 | 失败测试：写回播种 | — | `test_writeback_seed.py` RED |
| 2 | `seed_from_writeback` + promise-ledger CLI | 依赖 Task 1 | 同文件 GREEN |
| 3 | `learn` 默认 action + commands.md | —（可与 1–2 并行） | `test_learn_cli.py` GREEN；`learn --from-journal` 可跑 |
| 4 | fantasy01 删除 `第01卷.md` | —（可与 1–3 并行，书仓） | SHA-256 相同后删除；`resolve_detailed_outline(..., 1)` 指向带后缀版 |

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `webnovel-writer/scripts/tests/test_writeback_seed.py` | 新增 | spec §6 #1–3 与额外必测 |
| `webnovel-writer/scripts/data_modules/promise_ledger.py` | 修改 | `seed_from_writeback` + `crud_main` |
| `webnovel-writer/scripts/data_modules/webnovel.py` | 修改 | `seed-from-writeback` 转发 `--volume`；`learn` action 可选 |
| `webnovel-writer/scripts/tests/test_learn_cli.py` | 新增 | spec §6 #4–5 |
| `webnovel-writer/scripts/data_modules/author_model.py` | 修改 | `action` 可选默认 `learn` |
| `docs/guides/commands.md` | 修改 | learn 去 N9 警告；promise-ledger 补 seed |
| `projects/loom-books/fantasy01/大纲/卷纲/第01卷.md` | 删除 | 书仓去重（Task 4） |

README「8 条」旁注与 P3-3 勾选留在收尾（`finishing-a-development-branch`），本计划不提前改 gap-review README。

---

## Task 1：失败测试（写回播种）

**文件：** 新增 `webnovel-writer/scripts/tests/test_writeback_seed.py`

- [ ] 写失败测试（完整文件）：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""写回 JSON 播种承诺账本（v8-gap-review 阶段三 P3-3）。

spec：docs/cursor/阶段三-写回播种与CLI/2026-09-04-writeback-seed-spec.md
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent

FORESHADOW = [
    {"content": "江岸仓库地底上古遗迹与妖王颈上铁链（有人把妖王拴在灾源旁，链连石门）", "buried_chapter": "第17章", "payoff_chapter": "", "level": "核心"},
    {"content": "熔炉残响说出'天劫'：灾难是人引来的，三百年前他们成功过一次", "buried_chapter": "第76章", "payoff_chapter": "", "level": "核心"},
    {"content": "林知夏家族身世（家族式管理熟悉/市政图纸/儿时见过大阵仗）", "buried_chapter": "第19章", "payoff_chapter": "", "level": "卷级"},
    {"content": "新安城觊觎吞灾能力，程卫东将亲自来", "buried_chapter": "第79章", "payoff_chapter": "", "level": "卷级"},
    {"content": "熊铁山败逃被新安城收留", "buried_chapter": "第79章", "payoff_chapter": "", "level": "卷级"},
    {"content": "苏小白丹田内的未知之物（灾源残留，熔炉回避不答）", "buried_chapter": "第80章", "payoff_chapter": "", "level": "核心"},
    {"content": "铁门青光与敲击声实为灾源脉动", "buried_chapter": "第32章", "payoff_chapter": "第60章", "level": "卷级"},
]
OPEN_LOOP = [
    {"content": "三百年前上一次灵气潮汐与引劫真相", "buried_chapter": "第18章", "payoff_chapter": "", "level": "持续开放环"},
]


def _writeback(book: Path, items: list[dict], extra: dict | None = None) -> Path:
    payload = {"foreshadow_writeback": items, "open_loop_writeback": OPEN_LOOP}
    if extra:
        payload.update(extra)
    path = book / "大纲" / "卷纲" / "第01卷-总纲写回.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@pytest.fixture()
def book(tmp_path: Path) -> Path:
    from data_modules.domain_contract import init_domain_skeleton

    init_domain_skeleton(tmp_path)
    (tmp_path / "book.yaml").write_text("书名: 测试书\n", encoding="utf-8")
    _writeback(tmp_path, FORESHADOW)
    return tmp_path


def _cli(book: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(_SCRIPTS / "webnovel.py"), "--project-root", str(book), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_seeds_seven_foreshadow_entries(book: Path):
    from data_modules.promise_ledger import load_entries, seed_from_writeback

    report = seed_from_writeback(book, volume=1)
    entries = load_entries(book, kind="伏笔")
    names = [e["名称"] for e in entries]
    assert report["ok"] is True and report.get("exit", 0) == 0
    assert report["created"] == [f"F-{i:03d}" for i in range(1, 8)]
    assert names == [item["content"] for item in FORESHADOW]
    assert entries[0]["最晚回收章"] == 0
    assert entries[-1]["最晚回收章"] == 60
    assert entries[0]["埋设章"] == 17
    assert "level: 核心" in entries[0]["正文"]
    assert load_entries(book, kind="悬念") == []


def test_idempotent_skips_duplicate_names(book: Path):
    from data_modules.promise_ledger import seed_from_writeback

    first = seed_from_writeback(book, volume=1)
    second = seed_from_writeback(book, volume=1)
    assert first["created"] and not second["created"]
    assert len(second["skipped"]) == 7
    assert all(s["reason"] == "duplicate_name" for s in second["skipped"])
    assert second.get("exit", 0) == 0


def test_ignores_open_loop_writeback(book: Path):
    from data_modules.promise_ledger import load_entries, seed_from_writeback

    seed_from_writeback(book, volume=1)
    assert [e["名称"] for e in load_entries(book, kind="悬念")] == []
    assert len(load_entries(book, kind="伏笔")) == 7


def test_bad_buried_chapter_fails_item_keeps_rest(book: Path):
    from data_modules.promise_ledger import load_entries, seed_from_writeback

    _writeback(book, [
        {"content": "好伏笔", "buried_chapter": "第10章", "payoff_chapter": "", "level": "卷级"},
        {"content": "坏伏笔", "buried_chapter": "不明", "payoff_chapter": "", "level": "卷级"},
        {"content": "另一条", "buried_chapter": "第12章", "payoff_chapter": "", "level": "卷级"},
    ])
    report = seed_from_writeback(book, volume=1)
    assert report["ok"] is False and report.get("exit") == 1
    assert len(report["created"]) == 2 and len(report["failed"]) == 1
    assert report["failed"][0]["error"] == "unparseable_buried_chapter"
    assert [e["名称"] for e in load_entries(book, kind="伏笔")] == ["好伏笔", "另一条"]


def test_missing_file_exit_2_no_write(book: Path):
    from data_modules.promise_ledger import load_entries, seed_from_writeback

    report = seed_from_writeback(book, volume=9)
    assert report["ok"] is False and report.get("exit") == 2
    assert report["error"] == "missing_file"
    assert load_entries(book, kind="伏笔") == []


def test_cli_seed_and_help(book: Path):
    help_proc = _cli(book, "promise-ledger", "-h")
    assert help_proc.returncode == 0 and "seed-from-writeback" in help_proc.stdout
    missing = _cli(book, "promise-ledger", "seed-from-writeback", "--format", "json")
    assert missing.returncode != 0
    proc = _cli(book, "promise-ledger", "seed-from-writeback", "--volume", "1", "--format", "json")
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0 and len(payload["created"]) == 7
```

- [ ] 运行 RED：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_writeback_seed.py -q --no-cov -p no:cacheprovider
```

期望：`ImportError` 或失败断言（`seed_from_writeback` 尚不存在 / CLI 无该 action）。

---

## Task 2：实现播种

**文件：** `promise_ledger.py`、`webnovel.py`

- [ ] 在 `promise_ledger.py` 顶部补 `import json`。新增：

```python
_CHAPTER_INT = re.compile(r"(\d+)")


def writeback_json_path(project_root: str | Path, volume: int) -> Path:
    return Path(project_root) / "大纲" / "卷纲" / f"第{int(volume):02d}卷-总纲写回.json"


def parse_chapter_ref(raw: Any, *, empty_means_zero: bool) -> int | None:
    text = str(raw or "").strip()
    if not text:
        return 0 if empty_means_zero else None
    match = _CHAPTER_INT.search(text)
    if not match:
        return None
    value = int(match.group(1))
    return value if value >= 1 else None


def seed_from_writeback(project_root: str | Path, *, volume: int) -> dict[str, Any]:
    """读第NN卷-总纲写回.json 的 foreshadow_writeback，经 create_entry 建伏笔账本。"""
    root = Path(project_root)
    source_rel = f"大纲/卷纲/第{int(volume):02d}卷-总纲写回.json"
    source = writeback_json_path(root, volume)
    empty = {"volume": int(volume), "source": source_rel, "created": [], "skipped": [], "failed": []}
    if not source.is_file():
        return {**empty, "ok": False, "error": "missing_file", "exit": 2}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {**empty, "ok": False, "error": "invalid_json", "exit": 2}
    if not isinstance(payload, dict):
        return {**empty, "ok": False, "error": "invalid_root", "exit": 2}
    items = payload.get("foreshadow_writeback")
    if not isinstance(items, list):
        return {**empty, "ok": False, "error": "invalid_foreshadow_writeback", "exit": 2}

    existing = {str(e["名称"]).strip(): str(e["编号"]) for e in load_entries(root, kind="伏笔")}
    created: list[str] = []
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            failed.append({"name": "", "error": "invalid_item"})
            continue
        name = str(item.get("content") or "").strip()
        if not name:
            failed.append({"name": "", "error": "missing_name"})
            continue
        if name in existing:
            skipped.append({"name": name, "id": existing[name], "reason": "duplicate_name"})
            continue
        planted = parse_chapter_ref(item.get("buried_chapter"), empty_means_zero=False)
        if planted is None:
            failed.append({"name": name, "error": "unparseable_buried_chapter"})
            continue
        payoff_text = str(item.get("payoff_chapter") or "").strip()
        due = 0 if not payoff_text else parse_chapter_ref(item.get("payoff_chapter"), empty_means_zero=False)
        if due is None:
            failed.append({"name": name, "error": "unparseable_payoff_chapter"})
            continue
        level = str(item.get("level") or "").strip()
        note = f"level: {level}" if level else ""
        result = create_entry(
            root, kind="伏笔", name=name,
            planted_chapter=planted, due_chapter=due, note=note,
        )
        if not result.get("ok"):
            failed.append({"name": name, "error": str(result.get("error") or "create_failed")})
            continue
        created.append(str(result["id"]))
        existing[name] = str(result["id"])
    exit_code = 1 if failed else 0
    return {
        "ok": exit_code == 0,
        "volume": int(volume),
        "source": source_rel,
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "exit": exit_code,
    }
```

- [ ] `crud_main`：`action` choices 加 `seed-from-writeback`；加 `--volume`（type=int, default=0）。`seed-from-writeback` 时若 `not args.volume` → `parser.error`。调用 `seed_from_writeback`。json 打印 report；text 打印 `OK seed-from-writeback volume=N created=A skipped=B failed=C` 再列出 created 的 `id「name」`（name 从 skipped/created 对应条目或 report）。**返回 `report.get("exit", 0 if report.get("ok") else 1)`**，不要一律用 ok→0/1（缺文件必须 2）。json 分支同样按 `exit` 返回。`create`/`list`/`update` 分支保持原返回。

- [ ] `webnovel.py`：`p_ledger` 的 action choices 加 `seed-from-writeback`；`add_argument("--volume", type=int, default=0)`；`cmd_promise_ledger` 在 `args.action == "seed-from-writeback"` 时 `argv.extend(["--volume", str(args.volume)])`。help 文案改为含 seed。

- [ ] 运行 GREEN：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_writeback_seed.py webnovel-writer/scripts/tests/test_promise_ledger.py -q --no-cov -p no:cacheprovider
```

- [ ] 提交（仅插件仓、仅本任务实现文件 + 测试；不含 spec/plan）：

```text
feat(ledger): 从总纲写回 JSON 播种伏笔账本
```

---

## Task 3：learn 默认 action

**文件：** `test_learn_cli.py`、`webnovel.py`、`author_model.py`、`docs/guides/commands.md`

- [ ] 写失败测试 `webnovel-writer/scripts/tests/test_learn_cli.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""learn CLI 默认 action（v8-gap-review 阶段三 P3-3 / N9）。

spec：docs/cursor/阶段三-写回播种与CLI/2026-09-04-writeback-seed-spec.md
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent


@pytest.fixture()
def book(tmp_path: Path) -> Path:
    from data_modules.author_journal import append_events
    from data_modules.domain_contract import init_domain_skeleton

    init_domain_skeleton(tmp_path)
    (tmp_path / "book.yaml").write_text('spec_version: "7.0"\n卷规模: 40\n', encoding="utf-8")
    append_events(
        tmp_path,
        [
            {
                "actor": "author", "action": "edit", "domain": "章纲",
                "path": "大纲/章纲/0001.md", "change_kind": "content",
                "diff_stat": {"ins": 1, "del": 0}, "summary": "对峙提前", "impact": [],
            }
        ],
    )
    return tmp_path


def _cli(book: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(_SCRIPTS / "webnovel.py"), "--project-root", str(book), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_learn_from_journal_without_nested_action(book: Path):
    proc = _cli(book, "learn", "--from-journal", "--format", "json")
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert payload["ok"] is True
    assert (book / "作者" / "author_model-建议.md").is_file()


def test_learn_learn_from_journal_still_works(book: Path):
    proc = _cli(book, "learn", "learn", "--from-journal", "--format", "json")
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["ok"] is True


def test_learn_without_from_journal_still_errors(book: Path):
    proc = _cli(book, "learn", "--format", "json")
    assert proc.returncode != 0


def test_learn_apply_still_requires_explicit_action(book: Path):
    proc = _cli(book, "learn", "apply", "--format", "json")
    payload = json.loads(proc.stdout or "{}") if proc.stdout.strip().startswith("{") else {}
    assert proc.returncode != 0 or payload.get("ok") is False
```

`test_learn_apply_still_requires_explicit_action`：无建议文件时 `apply` 应失败（现有 `apply_suggestion` 行为）。不要把缺 action 的 `learn` 误当成 apply。

- [ ] 先跑 RED：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_learn_cli.py -q --no-cov -p no:cacheprovider
```

期望：`learn --from-journal` usage error（缺 action）。

- [ ] `webnovel.py` 与 `author_model.py`：

```python
parser.add_argument("action", nargs="?", default="learn", choices=["learn", "apply", "show"], help="子动作（默认 learn）")
```

`cmd_learn` 仍按 `args.action` 转发；默认已是 `"learn"`。

- [ ] `docs/guides/commands.md` learn 行改为不再提 `learn learn` / N9；promise-ledger 行补 `seed-from-writeback`。

- [ ] GREEN：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_learn_cli.py webnovel-writer/scripts/tests/test_author_model.py -q --no-cov -p no:cacheprovider
```

- [ ] 提交：

```text
fix(learn): 默认 action 为 learn，去掉冗余位置参数
```

Task 2 与 Task 3 若同一次做完，可合成一个 feat commit，message：

```text
feat(cli): 写回播种账本并修复 learn 默认动作
```

不要把 fantasy01 文件推进插件仓。

---

## Task 4：fantasy01 去重（书仓）

**仓库：** `c:\lgq\ai-workspace\projects\loom-books\fantasy01`  
**文件：** 删除 `大纲/卷纲/第01卷.md`（保留 `第01卷-详细大纲.md`）

- [ ] 再算整文件哈希，必须相等才删：

```powershell
python -X utf8 -c "from pathlib import Path; import hashlib; root=Path(r'c:\lgq\ai-workspace\projects\loom-books\fantasy01'); a=root/'大纲'/'卷纲'/'第01卷.md'; b=root/'大纲'/'卷纲'/'第01卷-详细大纲.md'; ha=hashlib.sha256(a.read_bytes()).hexdigest(); hb=hashlib.sha256(b.read_bytes()).hexdigest(); print(ha==hb, ha, a.stat().st_size, b.stat().st_size)"
```

哈希不同 → **停止**，不删、不改内容，回报 Human。

- [ ] 相等则只删副本：

```powershell
git -C "c:\lgq\ai-workspace\projects\loom-books\fantasy01" rm -- "大纲/卷纲/第01卷.md"
```

- [ ] 验证解析器仍指向规范路径（插件仓，只读该书路径）：

```powershell
python -X utf8 -c "from pathlib import Path; import sys; sys.path.insert(0, r'c:\lgq\ai-workspace\projects\zcode-plugins\webnovel-writer\webnovel-writer\scripts'); from data_modules.outline_paths import resolve_detailed_outline; p=resolve_detailed_outline(Path(r'c:\lgq\ai-workspace\projects\loom-books\fantasy01'), 1); print(p); assert p and p.name=='第01卷-详细大纲.md'"
```

- [ ] 只 stage 该删除。书仓其它脏文件不碰。提交（UTF-8 文件 + `-F`）：

```text
chore(outline): 删除与详细大纲重复的第01卷.md
```

- [ ] `git -C ... status`：该删除已提交；其它预先存在的脏文件如实报告，不代交。

插件仓 `test_outline_paths.py` 已覆盖「仅规范路径」回退，不必再加用例。

---

## 完成定义（实现期；全量回归留收尾）

- Task 1–3：`test_writeback_seed.py` + `test_learn_cli.py` + `test_promise_ledger.py` + `test_author_model.py` 全绿。
- `webnovel.py promise-ledger -h` 含 `seed-from-writeback`；`webnovel.py learn --from-journal` 在夹具书仓可跑。
- Task 4：fantasy01 无 `第01卷.md`，规范路径仍在。
- 不改真仓账本；不 push。
