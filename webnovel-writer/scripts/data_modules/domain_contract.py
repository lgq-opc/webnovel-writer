"""书仓六域目录契约（webnovel-copilot-300 · M0/T1）。

六域 = 大纲 / 正文(定稿) / 设定 / 素材 / 作者 / 文风(+演化事件域)，
系统域（.story-system/.webnovel/.cache）为编译产物不在本契约内。

- ``init_domain_skeleton``：幂等创建缺失骨架，**永不覆盖既有内容**（作者主权 P1/P2）。
- ``check_domain_contract``：结构化契约报告（required 缺失 = warning；advisory 缺失 = info 建议）。
- doctor 经 ``domain_contract_checks`` 接线（要求项目可解析，见 doctor.build_doctor_report）。

目录契约权威文档：docs/zcode/webnovel-copilot-300/05-book-directory-structure.md。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

DOMAIN_SCHEMA_VERSION = "domains/1"

# 必备目录（相对书项目根）
REQUIRED_DIRS: tuple[str, ...] = (
    "大纲/章纲",
    "大纲/条目/伏笔",
    "大纲/条目/悬念",
    "大纲/条目/感情线",
    "素材/活",
    "素材/定版",
    "作者",
    "文风",
)

# 必备文件（缺失 = warning）
REQUIRED_FILES: tuple[str, ...] = (
    "作者/journal.jsonl",
    "素材/活/README.md",
)

# 建议文件（缺失 = info，随各自里程碑落地：锚点/信息差=M4，宪法/指纹=M3）
ADVISORY_FILES: tuple[str, ...] = (
    "设定/力量锚点.yaml",
    "设定/信息差.md",
    "文风/宪法.md",
    "文风/指纹.yaml",
)

_GITIGNORE_LINES: tuple[str, ...] = (
    ".cache/",
    "工作区/",
    ".webnovel/tmp/",
    ".webnovel/logs/",
)

_MATERIAL_README = """# 活层素材（作者主战场）

本目录是**活层素材**：作者可自由编辑，AI 归纳与拆书投喂的条目先进画廊、
经作者采纳后才进入此处。卷收尾时由 `webnovel.py freeze` 快照到 `素材/定版/v{NN}/`。

支持的表（CSV，列约定见插件 docs/zcode/webnovel-copilot-300/06-data-design.md §7）：
桥段 / 爽点节奏 / 人设关系 / 场景写法 / 写作技法 / 命名风格 / 金手指零件 / 世界观零件 / 台词金句 / 梗与反差

统一列骨架：`id,名称,分类,核心摘要,详细展开,正例,反例,来源,状态,备注`
- `来源`：作者手写 | AI归纳 | 拆书:<出处> | 工坊采纳:<提案id> | 播种:<题材包>
- `状态`：active | 衰减 | 归档（material-review 维护）
"""

_JOURNAL_SEED = ""  # 空文件即合法（append-only 流）


def is_story_repo(project_root: str | Path) -> bool:
    """v7 story-repo 判定：存在 book.yaml（独立于 .webnovel 的 phase 解析）。"""
    return (Path(project_root) / "book.yaml").is_file()


# v6 runtime 合同链锚点（相对 .story-system）：MASTER_SETTING 是主锚，卷/章/审查目录是分锚。
_V6_CONTRACT_ANCHOR = "MASTER_SETTING.json"
_V6_CONTRACT_DIRS: tuple[str, ...] = ("volumes", "chapters", "reviews")


def has_v6_contract_chain(project_root: str | Path) -> bool:
    """仓库是否携带 v6 runtime 合同链（MASTER_SETTING.json 或 volumes/chapters/reviews）。

    只认 `.story-system` 目录本身会把「迁移残留」误判成 v6：放弃 v6 线的纯 v7 仓
    可能仍留着 commits/events（历史落定记录），却已无合同链。

    **锚点目录必须非空**（2026-09-10 独立核验补齐）：空目录同样是迁移残留，不是合同链。
    原先只看目录存在，导致「book.yaml + 空的 .story-system/volumes/」的纯 v7 仓被判回
    v6，doctor 重新输出「补齐 Story System 合同…」并让 Inv-5 fail——即 F1 缺陷原样复现。
    残留里只要有一份真合同文件（如 volumes/volume_001.json），仍判 v6，保守方向不变。
    """
    story_root = Path(project_root) / ".story-system"
    if not story_root.is_dir():
        return False
    if (story_root / _V6_CONTRACT_ANCHOR).is_file():
        return True
    for rel in _V6_CONTRACT_DIRS:
        candidate = story_root / rel
        if candidate.is_dir() and any(candidate.iterdir()):
            return True
    return False


def resolve_write_mode(project_root: str | Path) -> str:
    """书仓写链形态：``"v7"`` = 纯 v7 书仓；``"v6"`` = 走 .story-system 合同链的仓。

    判据全部取自仓库实际形态（不看书名、不看硬编码路径）：

    1. 无 book.yaml → v6（v7 书仓以 book.yaml 为标志，见 :func:`is_story_repo`）；
    2. 有 ``.webnovel/state.json`` → v6（state.json 是 v6 生命周期锚，与
       ``resolve_project_phase`` 判定 ``PHASE_V7_STORY_REPO`` 同源）；
    3. 有 v6 合同链（:func:`has_v6_contract_chain`）→ v6。

    三者皆不成立才判 v7。**宁可判 v6**：误判为 v6 只会多报告警，误判为 v7 等于拆闸门。
    """
    root = Path(project_root)
    if not is_story_repo(root):
        return "v6"
    if (root / ".webnovel" / "state.json").is_file():
        return "v6"
    return "v6" if has_v6_contract_chain(root) else "v7"


def _item(item_id: str, status: str, expected: str, actual: str) -> dict[str, str]:
    return {"id": item_id, "status": status, "expected": expected, "actual": actual}


def init_domain_skeleton(project_root: str | Path) -> dict[str, Any]:
    """幂等创建六域骨架。返回 {created_dirs, created_files, skipped}。

    红线：既有文件内容一律不动（journal 里有作者事件时绝不截断）。
    """
    root = Path(project_root)
    created_dirs: list[str] = []
    created_files: list[str] = []
    skipped: list[str] = []

    for rel in REQUIRED_DIRS:
        target = root / rel
        if target.is_dir():
            skipped.append(rel)
            continue
        target.mkdir(parents=True, exist_ok=True)
        created_dirs.append(rel)

    file_seeds: dict[str, str] = {
        "素材/活/README.md": _MATERIAL_README,
        "作者/journal.jsonl": _JOURNAL_SEED,
    }
    for rel in REQUIRED_FILES:
        target = root / rel
        if target.is_file():
            skipped.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file_seeds.get(rel, ""), encoding="utf-8", newline="\n")
        created_files.append(rel)

    # M7/T31：书项目 AGENTS.md 模板（作者主权速览 + 常用命令；已存在永不覆盖）
    agents_md = root / "AGENTS.md"
    if not agents_md.is_file():
        template = Path(__file__).resolve().parent.parent.parent / "templates" / "book-AGENTS.md"
        agents_md.write_text(
            template.read_text(encoding="utf-8") if template.is_file() else "",
            encoding="utf-8",
            newline="\n",
        )
        created_files.append("AGENTS.md")
    else:
        skipped.append("AGENTS.md")

    _ensure_gitignore(root)

    return {
        "schema_version": DOMAIN_SCHEMA_VERSION,
        "project_root": str(root),
        "created_dirs": created_dirs,
        "created_files": created_files,
        "skipped": skipped,
    }


def _ensure_gitignore(root: Path) -> None:
    gi = root / ".gitignore"
    existing = gi.read_text(encoding="utf-8") if gi.is_file() else ""
    lines = [ln for ln in existing.splitlines()]
    changed = False
    for needed in _GITIGNORE_LINES:
        if needed not in lines:
            lines.append(needed)
            changed = True
    if changed:
        content = "\n".join(lines).strip()
        content = (content + "\n") if content else ""
        gi.write_text(content, encoding="utf-8", newline="\n")


def check_domain_contract(project_root: str | Path) -> dict[str, Any]:
    """六域契约检查（只读）。required 缺失 = warning；advisory 缺失 = info。"""
    root = Path(project_root)
    items: list[dict[str, str]] = []
    missing_required: list[str] = []

    for rel in REQUIRED_DIRS:
        ok = (root / rel).is_dir()
        items.append(_item(f"domains.dir.{rel}", "ok" if ok else "warning", "directory exists", "exists" if ok else "missing"))
        if not ok:
            missing_required.append(rel)

    for rel in REQUIRED_FILES:
        ok = (root / rel).is_file()
        items.append(_item(f"domains.file.{rel}", "ok" if ok else "warning", "file exists", "exists" if ok else "missing"))
        if not ok:
            missing_required.append(rel)

    for rel in ADVISORY_FILES:
        ok = (root / rel).is_file()
        # advisory 命名空间与 required 区分，便于测试与呈现分组
        items.append(_item(f"advisory.{rel}", "ok" if ok else "info", "file exists (随里程碑落地)", "exists" if ok else "missing"))

    return {
        "schema_version": DOMAIN_SCHEMA_VERSION,
        "project_root": str(root),
        "ok": not missing_required,
        "missing_required": missing_required,
        "story_repo": is_story_repo(root),
        "items": items,
    }


def domain_contract_checks(project_root: str | Path) -> list[dict[str, str]]:
    """doctor 接线形态：单项汇总（避免 doctor 报告膨胀触发 CLI 外置化）。

    详情用 `webnovel.py domains check` 获取逐项报告。
    """
    report = check_domain_contract(project_root)
    missing = report["missing_required"]
    advisory_missing = [
        item["id"].removeprefix("advisory.")
        for item in report["items"]
        if item["id"].startswith("advisory.") and item["status"] != "ok"
    ]
    actual = "complete"
    if missing:
        actual = "missing: " + "、".join(missing[:6]) + ("…" if len(missing) > 6 else "")
    elif advisory_missing:
        actual = "required ok; advisory pending: " + str(len(advisory_missing))
    return [
        {
            "id": "domains.contract",
            "status": "ok" if not missing else "warning",
            "severity": "info" if not missing else "warning",
            "message": "六域目录契约",
            "expected": "六域骨架完整（素材/作者/文风等）",
            "actual": actual,
        }
    ]


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：python -X utf8 domain_contract.py {init|check} [--project-root P] [--format json|text]"""
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(description="书仓六域目录契约（webnovel-copilot-300 T1）")
    parser.add_argument("action", choices=["init", "check"])
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    root = Path(args.project_root)
    if args.action == "init":
        report = init_domain_skeleton(root)
    else:
        report = check_domain_contract(root)

    if args.format == "json":
        print(_json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if args.action == "init":
            print(
                f"domains init: +{len(report['created_dirs'])} dirs, +{len(report['created_files'])} files, "
                f"{len(report['skipped'])} skipped (已存在不动)"
            )
        else:
            status = "OK" if report["ok"] else "WARN"
            print(f"{status} domains check ({report['project_root']})")
            for item in report["items"]:
                if item["status"] != "ok":
                    print(f"  {item['status'].upper()} {item['id']}: {item['actual']}")
    return 0 if report.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
