#!/usr/bin/env python3
"""纯 v7 新书端到端冒烟（2026-09-12，需求与设计对账 §D-2 讨论第 1 项）。

目的：摸清「book-init 新建纯 v7 书仓 → 成章」链路上的**断点**，产出可复用的
冒烟脚本（候选 CI 门）。背景见 docs/reports/2026-09-12-需求与设计对账.md §D-2：
v8.1.0 发版链全绿（pytest 1452 / 行为评测 22 / 四校验），但该链**没有任何一层
跑在纯 v7 书仓上**——本脚本补这一格。

判定口径（三态，勿混）：
  PASS   退出码 0
  BREAK  非 0 且原因是**入口/环境**（Traceback / Not a webnovel project root /
         FileNotFoundError / ModuleNotFoundError …）——**只有此类计入缺陷**
  BIZ    非 0 但原因是**内容或门禁判定**（字数、占位符、blocking、数据为空）

只读性：书仓建在临时目录，默认跑完即删；`--keep` 保留并打印路径。
用法：
    python -X utf8 scripts/smoke_v7_newbook.py [--keep] [--json-out PATH]

轮次（2026-09-13 增轮 C）：主链 1-8 + 轮 B（按 skill 真实行为取 PROJECT_ROOT）+ 轮 C。
轮 C 专测追读力链路：主链 settle 被 prose 门禁拒时定稿无文件、`.cache` 追读力表为空，
故另用 `--force-review-bypass`（只放行审查与文笔两道门禁）再 settle 一次，
再断言 `index get-reader-signals` 的 `recent_reading_power` **非空**。
绕过只用于「造出可验证的数据」，主链对真实链路的判定口径不变。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
ENTRY = SCRIPTS_DIR / "webnovel.py"

# 入口/环境级失败的指纹——命中即判 BREAK
_BREAK_MARKERS = (
    "Traceback (most recent call last)",
    "Not a webnovel project root",
    "FileNotFoundError",
    "ModuleNotFoundError",
    "No such file or directory",
    "未找到有效书项目根目录",
)

TARGET_WORDS = 2000  # → check 下限 = 2000*0.75 = 1500（v7_write.py:443）


def _run(name: str, args: list[str], *, cwd: Path | None = None) -> dict[str, Any]:
    """跑一条 CLI，返回结构化结果（含三态判定）。"""
    cmd = [sys.executable, "-X", "utf8", str(ENTRY), *args]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=300, cwd=str(cwd) if cwd else None,
        )
        code, out = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
        stdout = proc.stdout or ""
    except subprocess.TimeoutExpired:
        code, out, stdout = 124, "TIMEOUT", ""

    first = next((ln for ln in out.splitlines() if ln.strip()), "")
    if code == 0:
        # 码 0 但业务层自报错误（如 context 的 {"status":"error","error":{"code":...}}）
        # 不算通过——否则"码0即 PASS"会在 CI 里漏掉这类假绿。
        verdict = "BIZ" if re.search(r'"status"\s*:\s*"error"', out) else "PASS"
    elif any(m in out for m in _BREAK_MARKERS):
        verdict = "BREAK"
    else:
        verdict = "BIZ"
    return {
        "step": name, "code": code, "verdict": verdict,
        "first_line": first[:100], "output": out, "stdout": stdout,
    }


def _run_assert(name: str, args: list[str], predicate) -> dict[str, Any]:
    """跑一条 CLI 并**断言其 stdout**——通过但断言不成立时判 BREAK（计入缺陷）。

    断言只解析 stdout：`output` 是 stdout+stderr 合并流，混入任何告警就不是合法 JSON。
    """
    result = _run(name, args)
    if result["verdict"] == "PASS" and not predicate(result):
        result["verdict"] = "BREAK"
        result["first_line"] = "断言失败：" + result["first_line"][:80]
    return result


def _reading_power_non_empty(result: dict[str, Any]) -> bool:
    """reader-signals 的 data.recent_reading_power 非空。"""
    try:
        payload = json.loads(result.get("stdout") or "")
    except json.JSONDecodeError:
        return False
    return bool((payload.get("data") or {}).get("recent_reading_power"))


def _make_decision(chapter: int) -> dict[str, Any]:
    """最小决策 JSON（字段见 v7_write.py:93-117 的 write_decision_card）。"""
    return {
        "chapter": chapter,
        "title": "初入宗门",
        "pov": "主角",
        "time_anchor": "第一日",
        "target_words": TARGET_WORDS,
        "goal": "主角抵达宗门，完成入门考验。",
        "nodes": ["抵达山门", "接受考验", "获得入门资格"],
        "forbidden": ["不得出现超纲境界"],
        "promises": [],
        # 承诺结转豁免：第 1 章无前序承诺可推进。check 要求 promises 或 waiver 二者必有其一
        # （`promise_ok = bool(promises) or bool(decision.get("waiver"))`）
        "waiver": "smoke：新书首章，无既有承诺可结转",
        # 钩子硬闸（reader_signals 接通 spec §3.2）：check 要求 hook_type 或 hook_waiver。
        # 这里给真钩子（强度写中文「中」），顺带在端到端上覆盖词表归一。
        "hook_type": "危机钩",
        "hook_strength": "中",
        "entities": ["主角"],
    }


def _make_draft(chapter: int, title: str) -> str:
    """最小合法草稿：标题行 + 足量正文（≥1500 字）、无占位符。"""
    body = (
        "清晨的雾还没散，山门前的石阶湿得发亮。主角背着一只旧布包，站在阶下抬头望，"
        "只见两扇朱漆大门半掩着，门楣上的匾额被岁月磨得发白。他攥了攥拳，抬脚踏上第一级石阶。"
        "石阶比想象中要陡。走到一半时，他听见身后有人跟上来，脚步不急不缓，却始终离他三步远。"
        "他没有回头，只是把步子放稳了些。山风从谷底卷上来，带着松针和湿土的气味，"
        "把他额前的碎发吹得贴在皮肤上。他数着石阶，一级，两级，三级，数到第八十级时，"
        "雾忽然薄了一层，门里的景象一寸寸露出来。"
        "门内是一片极开阔的青石场院，场院中央立着一口巨大的铜钟，钟身上刻满了密密麻麻的纹路。"
        "十来个和他年纪相仿的少年已经站在那里，各自隔着一段距离，谁也不看谁。"
        "他走过去，站定，把布包从肩上卸下来，放在脚边。"
        "不多时，一个穿灰袍的中年人从侧殿走出来。那人步子很轻，走到铜钟前停下，"
        "环视一圈，目光在每个人脸上停了一瞬。"
        "“入门考验只有一项。”灰袍人说，“钟响之前，谁能把这块碑上的字认全，谁就留下。”"
        "他抬手一指，场院东侧立着一块半人高的青石碑，碑面被青苔盖住大半，隐约能看见几行刻痕。"
        "少年们呼啦一下围过去。主角没有动，他先看了看那口钟，又看了看灰袍人的手——"
        "那只手的食指和中指并拢着，指节上有很厚的一层茧。他忽然明白了什么，"
        "这才慢慢走过去，蹲下身，用袖子一点点擦碑上的青苔。"
        "青苔很滑，擦开一层，底下还有一层。他没有急，一行一行地擦，一个字一个字地看。"
        "碑上的字是古体，笔画繁复，但写法并不生僻，反而规整得像是有人刻意描过。"
        "他擦到第三行时，旁边已经有人报出了答案，灰袍人摇了摇头。又有人报，还是摇头。"
        "钟声始终没有响。他擦完最后一行，站起身，把碑上的字从头到尾念了一遍。"
        "念到最后一句时，他顿了一下——那句话的意思，和前面几句并不连贯。"
        "他抬起头，看向灰袍人。灰袍人也在看他，眼里有一点极淡的笑意。"
        "“钟不会响。”他说，“碑上最后一句写的是：钟不响，人自明。”"
        "场院里静了一瞬。灰袍人点了点头，从袖中取出一枚青色的木牌递给他。"
        "木牌很轻，边缘磨得圆润，正面刻着一个字：内。他接过来，握在手心，"
        "掌心那块地方慢慢暖起来。"
        "后来他才知道，那口钟已经三十年没有响过了。而每一个真正入门的人，"
        "都是在认出那一句之后，才把手放在木牌上的。"
        "青石场院里的雾在这时候彻底散了。阳光从东边的山脊上斜斜地照下来，"
        "把铜钟的影子拉得很长，一直铺到阶前。那些没有认出碑文的少年陆续被带了下去，"
        "没有人争辩，也没有人哭闹，只是低着头走过他身边，脚步很轻。"
        "他站在原地，把手里的木牌翻过来看了看，背面是空的，什么也没有刻。"
        "灰袍人已经转身往侧殿走了，走了几步又停下，没回头，只说了一句：“跟上。”"
        "他弯腰拾起脚边的布包，拍了拍上面的灰，跟了上去。侧殿的门槛很高，"
        "他抬脚跨过去的时候，听见身后那口铜钟发出一声极轻的嗡鸣，像是有什么东西"
        "在钟身里动了一下，又很快静下来。他没有回头。"
        "侧殿里比外头暗得多，只有几缕光从高处的窗棂漏进来，落在青砖地上，"
        "切成一块一块的方格。灰袍人走到一张长案前停下，案上摊着一卷名册，"
        "纸页泛黄，边角卷起。那人提笔，在名册末尾添了一行，笔尖在纸上走得极慢。"
        "“姓名。”灰袍人问。他报了名字。那人写完，把笔搁下，抬起眼来看他。"
        "“从今日起，你是内门弟子。规矩有三条：不得私斗，不得擅入后山，不得"
        "对外人提起今日碑上的话。”他一条一条记下来，点了头。"
        "“记住了。”他说。灰袍人似乎笑了一下，又似乎没有，只是抬手往殿后一指："
        "“你的住处在这条路尽头，最里面那间。”"
        "他沿着那条路走过去时，天色已经大亮。路两旁种着一种他不认得的树，"
        "叶子细长，风一吹就翻出银白的背面，像一层层涌动的浪。"
        "走到尽头，他推开那扇木门，屋里只有一张板床、一张矮几、一只水瓮，"
        "墙上挂着一把没有开刃的木剑。他把布包放在板上，坐下来，"
        "这才觉出掌心里那块木牌一直暖着，暖得有些发烫。"
        "他摊开手。木牌上那个“内”字，比他第一次看时似乎亮了一点。"
    )
    return f"# 第{chapter:04d}章 {title}\n\n{body}\n"


def _write_minimal_review(repo: Path, chapter: int) -> None:
    """--minimal 的 no-review artifact（skills/webnovel-write/SKILL.md:148-151）。"""
    p = repo / ".webnovel" / "tmp" / "review_results.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "chapter": chapter, "issues": [], "issues_count": 0, "blocking_count": 0,
        "has_blocking": False,
        "summary": "smoke: reviewer skipped",
        "review_skipped": True, "review_mode": "minimal",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="纯 v7 新书端到端冒烟")
    ap.add_argument("--keep", action="store_true", help="保留临时书仓")
    ap.add_argument("--json-out", default="", help="把结果写成 JSON")
    ap.add_argument(
        "--allow-break", action="append", default=[], metavar="STEP", dest="allow_break",
        help="已知断点的步骤名前缀，不计入失败；可重复。用于 CI：只放过已登记项，"
             "新断点仍判失败（不要用数量阈值——那会掩盖新问题）。",
    )
    args = ap.parse_args()

    root = Path(tempfile.mkdtemp(prefix="smoke-v7-"))
    ws = root / "ws"            # 工作区根（≠ 书仓根，刻意如此，以复现 U-7 遗留）
    book = ws / "我的书"         # 书仓根
    ws.mkdir(parents=True)
    results: list[dict[str, Any]] = []

    # ---- 0. 建仓 ----
    results.append(_run("0 book-init", [
        "book-init", str(book), "冒烟测试书",
        "--genre", "玄幻", "--target-words", "200000",
        "--target-chapters", "100", "--no-git",
    ]))
    if not (book / "book.yaml").is_file():
        print("建仓失败，后续步骤无法进行", file=sys.stderr)
        _report(results, args, root)
        return 1

    # 造一个设定文件：book-init 只建空的 设定/（advisory 文件不自动生成），
    # 不造文件则 setting-read 恒报「未找到」——那是业务正常，验不出 U-8/B1 是否生效。
    (book / "设定").mkdir(parents=True, exist_ok=True)
    (book / "设定" / "世界观.md").write_text(
        "# 世界观\n\n修炼体系：练气、筑基、金丹。\n", encoding="utf-8"
    )

    # ---- 1. 预检：刻意传「工作区根」，检查 PROJECT_ROOT 解析成什么（U-7）----
    pre = _run("1 preflight(工作区根)", ["--project-root", str(ws), "preflight", "--all"])
    m = re.search(r"^PROJECT_ROOT=(.*)$", pre["output"], re.M)
    resolved = (m.group(1).strip() if m else "")
    pre["resolved_root"] = resolved
    pre["root_correct"] = Path(resolved).resolve() == book.resolve() if resolved else False
    results.append(pre)

    # 后续步骤按 skill 的真实行为：用 preflight 给出的 PROJECT_ROOT
    P = ["--project-root", str(book)]  # 主链固定用书仓根，保证能测链路本身

    # ---- 2~3. 根解析与体检 ----
    results.append(_run("2 where", P + ["where"]))
    results.append(_run("3 doctor", P + ["doctor", "--format", "json"]))

    # ---- 4~5. 决策卡与上下文包 ----
    dec_file = book / "工作区" / "决策-1.json"
    dec_file.parent.mkdir(parents=True, exist_ok=True)
    dec_file.write_text(json.dumps(_make_decision(1), ensure_ascii=False, indent=2), encoding="utf-8")
    results.append(_run("4 decision", P + ["v7-write", "decision", "--json", str(dec_file)]))
    results.append(_run("5 pack", P + ["v7-write", "pack", "--chapter", "1", "--json", str(dec_file)]))

    # ---- 6. 机检（fixture 草稿）----
    draft = book / "工作区" / "草稿-0001.md"
    draft.write_text(_make_draft(1, "初入宗门"), encoding="utf-8")
    results.append(_run("6 check", P + [
        "v7-write", "check", "--chapter", "1", "--draft", str(draft), "--json", str(dec_file),
    ]))

    # ---- 7. settle（--minimal 的 no-review artifact）----
    _write_minimal_review(book, 1)
    results.append(_run("7 settle", P + [
        "v7-write", "settle", "--chapter", "1", "--draft", str(draft),
        "--json", str(dec_file), "--summary", "主角抵达宗门，通过认碑考验取得入门木牌。",
    ]))

    # ---- 8. 只读工具面 ----
    # reader-signals 不在此列：它要断言**内容非空**，见下方轮 C（reader_signals 接通 spec §7 判据 5）。
    for name, argv in (
        ("setting-read", ["setting-read", "--name", "世界观"]),
        ("timeline-check", ["timeline-check", "--volume", "1", "--format", "json"]),
        ("knowledge", ["knowledge", "query-entity-state", "--entity", "主角", "--at-chapter", "1"]),
        ("context", ["context", "--chapter", "1"]),
        ("meter", ["meter", "report"]),
        ("materials", ["materials", "list", "--format", "json"]),
        ("power-check", ["power", "check", "--format", "json"]),
        ("foreshadow-scan", ["foreshadow-scan", "scan", "--chapter", "1", "--no-apply"]),
        ("rag-search", ["rag", "search", "--query", "宗门"]),
    ):
        results.append(_run(f"8 {name}", P + argv))

    # ---- 轮 C：追读力链路（reader_signals 接通 spec §3.4 / §7 判据 1、5）----
    # 步骤 7 的 settle 通常被 prose 门禁拒（fixture 正文命中 Anti-AI 词库，是既有 BIZ 基线），
    # 故定稿无文件、.cache 追读力表为空——此时断言非空必然失败。
    # 处置：**不改变步骤 7 对真实链路的监测语义**，另用显式绕过（--force-review-bypass 只放行
    # 审查与文笔两道门禁）再 settle 一次，让钩子真正落盘，才验得到端到端。
    if not list((book / "定稿" / "正文").glob("0001-*.md")):
        results.append(_run("C1 settle(绕过)", P + [
            "v7-write", "settle", "--chapter", "1", "--draft", str(draft),
            "--json", str(dec_file), "--summary", "主角抵达宗门，通过认碑考验取得入门木牌。",
            "--force-review-bypass", "smoke：绕过审查与文笔门禁，以验证追读力落账链路",
            # 本冒烟的书仓是 book-init --no-git 建的（见步骤 0），无 .git；
            # settle 默认 commit=True 会做 git add/commit 并因「not a git repository」失败。
            # 本轮只验追读力落盘，故显式 --no-commit（写盘与缓存重建照常发生）。
            "--no-commit",
        ]))
    results.append(_run_assert(
        "C2 reader-signals",
        P + ["index", "get-reader-signals", "--limit", "5", "--last-n", "20"],
        _reading_power_non_empty,
    ))

    # ---- 轮 B：完全按 skill 的真实行为（后续步骤沿用 preflight 给出的 PROJECT_ROOT）----
    # skills/webnovel-write/SKILL.md:58-60 —— skill 正是这样取 PROJECT_ROOT 的
    if resolved:
        Q = ["--project-root", resolved]
        results.append(_run("B1 decision(preflight值)", Q + ["v7-write", "decision", "--json", str(dec_file)]))
        results.append(_run("B2 pack(preflight值)", Q + ["v7-write", "pack", "--chapter", "1", "--json", str(dec_file)]))

    _report(results, args, root)
    has_unexpected = any(
        r["verdict"] == "BREAK"
        and not any(r["step"].startswith(p) for p in args.allow_break or [])
        for r in results
    )
    if not args.keep:
        shutil.rmtree(root, ignore_errors=True)
    else:
        print(f"\n书仓保留在：{book}")
    return 1 if has_unexpected else 0


def _report(results: list[dict[str, Any]], args: argparse.Namespace, root: Path) -> None:
    print("\n" + "=" * 78)
    print("纯 v7 新书端到端冒烟 — 结果")
    print("=" * 78)
    for r in results:
        mark = {"PASS": "✅", "BREAK": "🔴", "BIZ": "🟡"}[r["verdict"]]
        extra = ""
        if r["step"].startswith("1 preflight"):
            extra = f"  [PROJECT_ROOT={r.get('resolved_root','')!r} 正确={r.get('root_correct')}]"
        print(f"{mark} {r['step']:<22} 码={r['code']:<4} {r['first_line'][:56]}{extra}")

    breaks = [r for r in results if r["verdict"] == "BREAK"]
    biz = [r for r in results if r["verdict"] == "BIZ"]
    unexpected = [
        r for r in breaks
        if not any(r["step"].startswith(p) for p in getattr(args, "allow_break", []) or [])
    ]
    print("-" * 78)
    print(f"PASS {len(results)-len(breaks)-len(biz)} ｜ 🔴 BREAK {len(breaks)} ｜ 🟡 BIZ {len(biz)}")
    if breaks:
        print("\n🔴 断点清单（入口/环境级）：")
        for r in breaks:
            mark = "（已登记）" if r not in unexpected else ""
            print(f"  - {r['step']}：{r['first_line'][:80]}{mark}")
    if unexpected:
        print(f"\n❌ 其中 {len(unexpected)} 个**未在 --allow-break 名单内** → 退出码 1（CI 判失败）")
    elif breaks:
        print(f"\n✅ {len(breaks)} 个断点全部已登记（--allow-break），退出码 0")
    if biz:
        print("\n🟡 业务级（非缺陷，需人工判读）：")
        for r in biz:
            print(f"  - {r['step']}：{r['first_line'][:80]}")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON 已写入 {args.json_out}")


if __name__ == "__main__":
    raise SystemExit(main())
