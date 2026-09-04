# 工坊同步执行器 实施计划

> **执行者注意：** 按任务逐个实施。步骤用 checkbox 跟踪，完成即勾选。
>
> 我在用 writing-plans 技能写实施计划。

**目标：** 新增 `webnovel.py forge-sync`，扫 journal 未消费的工坊同步标记并引导作者；显式 `mark-cleared` 后追加 `*:cleared`。
**架构：** 新模块 `forge_sync.py` 只读扫描 + FIFO 配对 + append-only 消费；`webnovel.py` 顶层子命令转发；不改 `setting_forge.py`。
**技术栈：** Python 3.10+、pytest、标准库 `re` / `json` / `argparse`。
**Spec：** `docs/cursor/阶段三-工坊同步执行器/2026-09-04-forge-sync-spec.md`

**执行记录（2026-09-04，Cursor）**：Task 1–3 完成。实现 commit `f23eeb5`；spec `aa8947a`；plan `23c9bb7`。无 ledger（未走 SDD）。`test_forge_sync.py` 8 例 + `test_setting_forge.py` 全绿。全量 `1558 passed` / cov 82.85%。`webnovel.py forge-sync -h` 可解析。

## 全局约束

- 生产者是 `forge confirm`，不是 `adopt`。
- status 绝不写 journal；cleared 必须显式 `mark-cleared`。
- journal append-only；cleared 用 `action=edit` + 非空 summary；不扩 `VALID_ACTIONS`。
- 不代跑 `power validate` / `master-outline-sync`，不改锚点文件。
- `--kind all` 只消费当前队列非空的 kind；两队列都空或显式 kind 队列空或缺 `--kind` → exit 2、不写盘。
- 多余 `cleared` 不产生负余额、不吞后续 `required`。
- 不改 `setting_forge.py`、v6 `chapter_commit.py` / write-gate / `context_manager`。
- Windows：`python -X utf8`；覆盖率不低于 80%。

## 执行总览

| 序号 | 任务名 | 依赖 | 验证方式 |
|---|---|---|---|
| 1 | 失败测试：pending / 引导 / cleared / FIFO / CLI | — | `test_forge_sync.py` RED |
| 2 | `forge_sync.py` 扫描与 mark-cleared | 依赖 Task 1 | 同文件 GREEN |
| 3 | `webnovel.py forge-sync` + commands.md | 依赖 Task 2 | CLI 子进程 + `test_setting_forge.py` 全绿 |

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `webnovel-writer/scripts/data_modules/forge_sync.py` | 新增 | 扫描 pending、status 文案、mark-cleared、`main` |
| `webnovel-writer/scripts/tests/test_forge_sync.py` | 新增 | spec §6 行为测试 |
| `webnovel-writer/scripts/data_modules/webnovel.py` | 修改 | `cmd_forge_sync` + `forge-sync` 解析器 |
| `docs/guides/commands.md` | 修改 | 表中 `forge-sync` 一行 |

---

## Task 1：失败测试

**文件：** 新增 `webnovel-writer/scripts/tests/test_forge_sync.py`

- [x] 写失败测试（完整文件；夹具复用 `test_setting_forge._proposal_doc` 与同等 `book` 骨架）：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工坊同步执行器（v8-gap-review 阶段三 P3-2）。

spec：docs/cursor/阶段三-工坊同步执行器/2026-09-04-forge-sync-spec.md
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_setting_forge import _proposal_doc

_SCRIPTS = Path(__file__).resolve().parent.parent


@pytest.fixture()
def book(tmp_path: Path) -> Path:
    from data_modules.author_model import write_preferences
    from data_modules.domain_contract import init_domain_skeleton
    from data_modules.material_store import append_entries

    init_domain_skeleton(tmp_path)
    (tmp_path / "定稿" / "设定").mkdir(parents=True, exist_ok=True)
    append_entries(tmp_path, "金手指零件", [{"id": "GF-001", "名称": "代价转化", "核心摘要": "吃灾转化"}])
    write_preferences(tmp_path, {"节奏": {"冲突前置": True}, "雷点": ["无代价金手指"], "审稿习惯": {}})
    return tmp_path


def _confirm(book: Path, tmp_path: Path, category: str) -> dict:
    from data_modules.setting_forge import forge_adopt, forge_confirm, forge_save

    proposal_file = tmp_path / f"{category}.md"
    proposal_file.write_text(_proposal_doc(category), encoding="utf-8")
    forge_save(book, category=category, file=proposal_file)
    adopt = forge_adopt(book, category=category, version=1, proposal=1)
    return forge_confirm(book, category=category, draft=adopt["draft"])


def _cli(book: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(_SCRIPTS / "webnovel.py"), "--project-root", str(book), "forge-sync", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_empty_journal_status_ok(book: Path):
    from data_modules.forge_sync import main

    assert main(["status", "--project-root", str(book), "--format", "json"]) == 0


def test_confirm_gongfa_lists_both_kinds(book: Path, tmp_path: Path, capsys):
    from data_modules.forge_sync import main

    _confirm(book, tmp_path, "功法")
    code = main(["status", "--project-root", str(book), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    kinds = {item["kind"] for item in payload["pending"]}
    assert code == 1 and payload["ok"] is False
    assert kinds == {"power_anchor_sync", "contract_rebuild"}
    joined = " ".join(payload["next"])
    assert "power validate" in joined and "master-outline-sync" in joined


def test_confirm_fabao_only_contract(book: Path, tmp_path: Path, capsys):
    from data_modules.forge_sync import main

    _confirm(book, tmp_path, "法宝")
    main(["status", "--project-root", str(book), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert {item["kind"] for item in payload["pending"]} == {"contract_rebuild"}


def test_status_does_not_write_journal(book: Path, tmp_path: Path):
    from data_modules.author_journal import read_journal
    from data_modules.forge_sync import main

    _confirm(book, tmp_path, "功法")
    before = read_journal(book)
    main(["status", "--project-root", str(book), "--format", "json"])
    assert read_journal(book) == before


def test_mark_cleared_all_after_gongfa(book: Path, tmp_path: Path, capsys):
    from data_modules.author_journal import read_journal
    from data_modules.forge_sync import main

    _confirm(book, tmp_path, "功法")
    assert main(["mark-cleared", "--kind", "all", "--project-root", str(book), "--format", "json"]) == 0
    impacts = [token for event in read_journal(book) for token in (event.get("impact") or [])]
    assert "power_anchor_sync:cleared" in impacts and "contract_rebuild:cleared" in impacts
    capsys.readouterr()
    assert main(["status", "--project-root", str(book), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True and payload["pending"] == []


def test_mark_cleared_rejects_when_empty(book: Path):
    from data_modules.author_journal import read_journal
    from data_modules.forge_sync import main

    before = read_journal(book)
    assert main(["mark-cleared", "--kind", "all", "--project-root", str(book)]) == 2
    assert read_journal(book) == before


def test_extra_cleared_does_not_swallow_later_required(book: Path, tmp_path: Path, capsys):
    from data_modules.author_journal import append_events
    from data_modules.forge_sync import main

    append_events(
        book,
        [{
            "actor": "author",
            "action": "edit",
            "domain": "设定",
            "path": "作者/journal.jsonl",
            "change_kind": "structure",
            "diff_stat": {"ins": 0, "del": 0},
            "summary": "历史脏 cleared",
            "impact": ["power_anchor_sync:cleared"],
        }],
    )
    _confirm(book, tmp_path, "功法")
    main(["status", "--project-root", str(book), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert "power_anchor_sync" in {item["kind"] for item in payload["pending"]}


def test_webnovel_cli_forge_sync(book: Path, tmp_path: Path):
    _confirm(book, tmp_path, "功法")
    proc = _cli(book, "--format", "json")
    assert proc.returncode == 1 and "power validate" in proc.stdout
    cleared = _cli(book, "mark-cleared", "--kind", "all", "--format", "json")
    assert cleared.returncode == 0
    again = _cli(book, "status", "--format", "json")
    assert again.returncode == 0
```

- [x] 运行 RED：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_forge_sync.py -q --no-cov -p no:cacheprovider
```

预期：`ModuleNotFoundError: data_modules.forge_sync` 或 `webnovel.py` 不认 `forge-sync`。

---

## Task 2：实现 `forge_sync.py`

**文件：** `webnovel-writer/scripts/data_modules/forge_sync.py`

- [x] 写入完整模块：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工坊同步执行器（v8-gap-review 阶段三 P3-2）。

扫 journal impact 中 power_anchor_sync / contract_rebuild 的 required/cleared，
FIFO 配对 pending；status 只读；mark-cleared 追加 edit 事件。
"""
from __future__ import annotations

import argparse
import json
import re
from collections import deque
from pathlib import Path
from typing import Any

from .author_journal import append_events, read_journal

SCHEMA_VERSION = "forge-sync/1"
KINDS = ("power_anchor_sync", "contract_rebuild")
_IMPACT_RE = re.compile(r"^(power_anchor_sync|contract_rebuild)\s*:\s*(required|cleared)$")
_VOLUME_PLACEHOLDER = "<已完成规划的卷号>"


def _tokens(event: dict[str, Any]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for raw in event.get("impact") or []:
        match = _IMPACT_RE.match(str(raw).strip())
        if match:
            found.append((match.group(1), match.group(2)))
    return found


def scan_pending(project_root: str | Path) -> list[dict[str, Any]]:
    queues: dict[str, deque] = {kind: deque() for kind in KINDS}
    for index, event in enumerate(read_journal(project_root), start=1):
        for kind, state in _tokens(event):
            if state == "required":
                queues[kind].append(
                    {
                        "kind": kind,
                        "index": index,
                        "path": str(event.get("path") or ""),
                        "ts": str(event.get("ts") or ""),
                        "summary": str(event.get("summary") or ""),
                    }
                )
            elif queues[kind]:
                queues[kind].popleft()
    pending: list[dict[str, Any]] = []
    for kind in KINDS:
        pending.extend(queues[kind])
    return pending


def _next_steps(project_root: Path, pending: list[dict[str, Any]]) -> list[str]:
    root = str(project_root)
    steps: list[str] = []
    kinds = {item["kind"] for item in pending}
    if "power_anchor_sync" in kinds:
        steps.append(f"手改力量锚点后：python -X utf8 webnovel.py --project-root {root} power validate")
    if "contract_rebuild" in kinds:
        steps.append(
            f"python -X utf8 webnovel.py --project-root {root} master-outline-sync --volume {_VOLUME_PLACEHOLDER}"
        )
    if pending:
        steps.append(f"python -X utf8 webnovel.py --project-root {root} forge-sync mark-cleared --kind all")
    return steps


def status_report(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root)
    pending = scan_pending(root)
    return {
        "ok": not pending,
        "schema_version": SCHEMA_VERSION,
        "pending": pending,
        "next": _next_steps(root, pending),
    }


def format_status_text(report: dict[str, Any]) -> str:
    pending = report.get("pending") or []
    lines = [f"PENDING forge-sync n={len(pending)}"]
    if not pending:
        lines.append("  (无未消费标记)")
    for item in pending:
        lines.append(f"  {item['kind']}  journal#{item['index']}  {item.get('path') or '-'}")
    nxt = report.get("next") or []
    if nxt:
        lines.append("NEXT")
        for index, step in enumerate(nxt, start=1):
            lines.append(f"  {index}. {step}")
    return "\n".join(lines)


def mark_cleared(project_root: str | Path, kind: str) -> dict[str, Any]:
    root = Path(project_root)
    kind = (kind or "").strip()
    if kind not in (*KINDS, "all"):
        return {"ok": False, "error": "invalid_kind", "kind": kind}
    pending = scan_pending(root)
    if kind == "all":
        requested = [k for k in KINDS if any(item["kind"] == k for item in pending)]
    else:
        requested = [kind] if any(item["kind"] == kind for item in pending) else []
    if not requested:
        return {"ok": False, "error": "nothing_pending"}
    heads = []
    for current in requested:
        heads.append(next(item for item in pending if item["kind"] == current))
    path = heads[0].get("path") or "作者/journal.jsonl"
    impact = [f"{current}:cleared" for current in requested]
    append_events(
        root,
        [
            {
                "actor": "author",
                "action": "edit",
                "domain": "设定",
                "path": path,
                "change_kind": "structure",
                "diff_stat": {"ins": 0, "del": 0},
                "summary": "forge-sync 消费 " + ",".join(requested),
                "impact": impact,
            }
        ],
    )
    return {"ok": True, "cleared": requested, "schema_version": SCHEMA_VERSION}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="工坊同步执行器（P3-2）：status / mark-cleared")
    parser.add_argument("action", nargs="?", default="status", choices=["status", "mark-cleared"])
    parser.add_argument("--kind", default="", help="mark-cleared：power_anchor_sync / contract_rebuild / all")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    root = Path(args.project_root)
    if args.action == "mark-cleared":
        if not str(args.kind).strip():
            report = {"ok": False, "error": "missing_kind"}
            print(json.dumps(report, ensure_ascii=False) if args.format == "json" else "ERROR missing --kind")
            return 2
        report = mark_cleared(root, args.kind)
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False))
        else:
            print("OK forge-sync cleared " + ",".join(report.get("cleared") or []) if report.get("ok") else f"ERROR {report.get('error')}")
        return 0 if report.get("ok") else 2
    report = status_report(root)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(format_status_text(report))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] 运行定点 GREEN（此时 CLI 子进程测试仍红，可临时 skip 或先做 Task 3）：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_forge_sync.py -q --no-cov -p no:cacheprovider -k "not webnovel_cli"
```

- [x] 提交（若与 Task 3 同一次实现，可合并提交，message 仍用下面这一条）：

```text
feat(forge): 扫描并消费工坊同步标记
```

---

## Task 3：CLI 接线与文档

**文件：** `webnovel.py`、`docs/guides/commands.md`

- [x] 在 `cmd_forge` 之后增加：

```python
def cmd_forge_sync(args: argparse.Namespace) -> int:
    """工坊同步执行器（v8-gap-review 阶段三 P3-2）。退出码原样转发。"""
    from data_modules import forge_sync

    root = _resolve_root_lenient(args.project_root)
    argv = [getattr(args, "action", None) or "status", "--project-root", str(root), "--format", args.format]
    kind = getattr(args, "kind", "") or ""
    if kind:
        argv.extend(["--kind", kind])
    return forge_sync.main(argv)
```

- [x] 在 `p_forge` 解析器之后增加：

```python
    p_forge_sync = sub.add_parser("forge-sync", help="工坊同步执行器（P3-2）：扫 pending / mark-cleared")
    p_forge_sync.add_argument("action", nargs="?", default="status", choices=["status", "mark-cleared"])
    p_forge_sync.add_argument("--kind", default="", help="mark-cleared：power_anchor_sync / contract_rebuild / all")
    p_forge_sync.add_argument("--format", choices=["text", "json"], default="text")
    p_forge_sync.set_defaults(func=cmd_forge_sync)
```

- [x] `docs/guides/commands.md` 在 `forge` 行下插入：

```text
| `forge-sync` | `status` / `mark-cleared` | 扫 journal 未消费的 `power_anchor_sync` / `contract_rebuild`；引导 `power validate` 与 `master-outline-sync`；显式 mark-cleared 追加 `*:cleared` |
```

- [x] 运行：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_forge_sync.py webnovel-writer/scripts/tests/test_setting_forge.py -q --no-cov -p no:cacheprovider
```

- [x] 若 Task 2 未提交，此处一并提交 `feat(forge): 扫描并消费工坊同步标记`。
