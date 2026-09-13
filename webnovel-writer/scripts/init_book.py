#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7-native 新书初始化。

**为什么需要**（v6 退役方案 §1.2「已知缺口」）：此前新书上 v7 的唯一入口是
`migrate_v6_to_v7`，而它要求先存在一个 **v6 项目**——等于新书无处起步。
本模块补上这条缺口：直接播种 v7 书仓该有的东西，**不产生任何 v6 遗留**
（无 `.story-system`、无 `.webnovel/state.json`）。

产出物与 `migrate_v6_to_v7` 的 v7 输出同构，故 v7 写链
（`v7-write decision/pack/check/settle`）与治理层（doctor / domains / materials）
可直接使用：

    book.yaml                    spec_version 7.0 + 书名/类型/字数/卷规模等
    大纲/ 素材/ 作者/ 文风/        六域骨架（domain_contract.init_domain_skeleton）
    定稿/正文/                    本函数补建（doctor 的 v7 required 检查项，见 :145）
    素材/活/*                    按题材播种（material_store.seed_materials）
    .gitignore                   .cache/ 工作区/ .webnovel/tmp/ .webnovel/logs/
    .git                         初始提交（`--no-git` 可跳过）

    **实测顶层域 5/6**：六域里 `设定/` 不预建（内容属 advisory，按需创建，
    见 domain_contract.ADVISORY_FILES）——t-20260913-3e73 统一口径。

**安全**：目标目录已存在且非空时拒绝执行——绝不在有内容的目录上播种。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# 与 migrate_v6_to_v7 的 v7 输出保持一致的默认值
DEFAULT_CHAPTERS_BUDGET = 40
HIGH_PROMISE_MAX_IDLE = 10
CONSECUTIVE_WEAK_HOOK_LIMIT = 3


def _quote_yaml(value: str) -> str:
    """按需给 YAML 标量加引号，避免标题里的 `:`/`#` 等把结构撑坏。"""
    text = str(value or "").strip()
    if not text:
        return '""'
    if any(ch in text for ch in ':#"\'&*!|>%@`[]{},') or text != text.strip():
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def build_book_yaml(
    *,
    title: str,
    genre: str,
    genre_label: str = "",
    target_words: int = 0,
    target_chapters: int = 0,
) -> str:
    """生成 v7 书仓的 book.yaml 内容。

    `book.yaml` 是 v7 书仓的**唯一形态标志**（`domain_contract.is_story_repo` 只看它，
    `resolve_write_mode` 也据它判 v7），所以字段要一次写全，别留半成品。
    """
    lines = [
        'spec_version: "7.0"',
        f"书名: {_quote_yaml(title)}",
        f"类型: {_quote_yaml(genre)}",
    ]
    if genre_label:
        lines.append(f"题材标签: {_quote_yaml(genre_label)}")

    words = int(target_words or 0)
    chapters = int(target_chapters or 0)
    if words > 0 and chapters > 0:
        lines.append(f"每章目标字数: {max(1, words // chapters)}")
    if chapters > 0:
        lines.append(f"卷规模: {min(chapters, DEFAULT_CHAPTERS_BUDGET)}")

    lines.append(f"高承诺最大搁置章数: {HIGH_PROMISE_MAX_IDLE}")
    lines.append(f"连续弱钩上限: {CONSECUTIVE_WEAK_HOOK_LIMIT}")
    return "\n".join(lines) + "\n"


def _target_must_be_free(target: Path) -> None:
    if target.exists():
        if not target.is_dir():
            raise FileExistsError(f"目标已存在且不是目录：{target}")
        if any(target.iterdir()):
            raise FileExistsError(f"目标目录非空，拒绝在其中初始化（避免覆盖既有内容）：{target}")


def _git_init(target: Path, title: str) -> None:
    def run(*args: str) -> None:
        subprocess.run(
            args, cwd=target, check=True,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )

    run("git", "init")
    run("git", "config", "core.quotepath", "false")
    run("git", "add", "-A")
    run(
        "git", "-c", "user.name=webnovel-init", "-c", "user.email=init@local",
        "commit", "-m", f"ch: v7 书仓初始化（{title}）",
    )


def init_book(
    target_dir: str | Path,
    *,
    title: str,
    genre: str = "都市",
    target_words: int = 0,
    target_chapters: int = 0,
    no_git: bool = False,
) -> dict:
    """在 `target_dir` 播种一个新 v7 书仓；返回结构化的初始化报告。"""
    target = Path(target_dir).expanduser().resolve()
    _target_must_be_free(target)

    # 延迟导入：本模块也可能被直接以脚本方式跑（scripts 目录未必在 sys.path 前端）
    try:
        from data_modules.domain_contract import init_domain_skeleton
        from data_modules.material_store import seed_materials
        from genre_taxonomy import resolve_genre_input, seed_genre_label
    except ImportError:  # pragma: no cover
        scripts_dir = Path(__file__).resolve().parent
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from data_modules.domain_contract import init_domain_skeleton
        from data_modules.material_store import seed_materials
        from genre_taxonomy import resolve_genre_input, seed_genre_label

    target.mkdir(parents=True, exist_ok=True)

    resolved = resolve_genre_input(genre)
    canonical_genre = getattr(resolved, "canonical_genre", "") or genre
    genre_label = seed_genre_label(genre)

    book_yaml = build_book_yaml(
        title=title, genre=canonical_genre, genre_label=genre_label,
        target_words=target_words, target_chapters=target_chapters,
    )
    (target / "book.yaml").write_text(book_yaml, encoding="utf-8", newline="\n")

    domain_report = init_domain_skeleton(target)
    seed_report = seed_materials(target, genre=genre_label)

    # `定稿/正文` 是 v7 落定章的落点（`max_settled_chapter` 与 doctor 的
    # `V7_FILE_CHECKS` 都认它），但它不在六域骨架里——迁移器是单独建的
    # （migrate_v6_to_v7._copy_chapters）。新书必须同样建出来，否则 doctor 一上来
    # 就报 blocker「v7 required directory 定稿/正文」。
    (target / "定稿" / "正文").mkdir(parents=True, exist_ok=True)

    git_done = False
    if not no_git and shutil.which("git"):
        _git_init(target, title)
        git_done = True

    return {
        "book_yaml": str(target / "book.yaml"),
        "target": str(target),
        "canonical_genre": canonical_genre,
        "genre_label": genre_label,
        "domain_dirs": len(domain_report.get("created_dirs") or []),
        "domain_files": len(domain_report.get("created_files") or []),
        "seeded_materials": sum((seed_report.get("seeded") or {}).values()),
        "git_commit": git_done,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="v7-native 新书初始化（播种 book.yaml + 六域骨架）")
    parser.add_argument("project_dir", help="新书目录（必须不存在或为空）")
    parser.add_argument("title", help="书名")
    parser.add_argument("--genre", default="都市", help="题材（默认 都市）")
    parser.add_argument("--target-words", type=int, default=0, help="目标总字数")
    parser.add_argument("--target-chapters", type=int, default=0, help="目标总章节数")
    parser.add_argument("--no-git", action="store_true", help="跳过 git init 与初始提交")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()

    try:
        report = init_book(
            args.project_dir, title=args.title, genre=args.genre,
            target_words=args.target_words, target_chapters=args.target_chapters,
            no_git=args.no_git,
        )
    except (FileExistsError, OSError) as exc:
        raise SystemExit(f"初始化失败：{exc}")

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"OK book-init target={report['target']}")
    print(f"  book.yaml: {report['book_yaml']}")
    print(f"  六域：+{report['domain_dirs']} 目录 / +{report['domain_files']} 文件")
    print(f"  素材播种：{report['seeded_materials']} 条（题材 {report['genre_label']}）")
    print(f"  git 初始提交：{'已生成' if report['git_commit'] else '已跳过'}")


if __name__ == "__main__":
    main()
