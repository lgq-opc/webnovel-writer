"""
Dashboard 启动脚本

用法：
    python -m dashboard.server --project-root /path/to/novel-project
    python -m dashboard.server                   # 自动从 .claude 指针读取
"""

import argparse
import os
import sys
import webbrowser
from pathlib import Path


_V7_UNSUPPORTED_MSG = (
    "Dashboard 不支持纯 v7 书仓。本面板读的是 v6 投影（.webnovel/state.json 与 index.db），"
    "v7 没有这些文件。请用 doctor / project-status / setting-read，或直接打开 定稿/ 大纲/ 设定/。"
    "存量 v6 仓仍可启动。"
)


def refuse_v7_dashboard(project_root: Path) -> str | None:
    """纯 v7 书仓返回拒绝理由；v6 仓返回 None。

    2026-09-18 退役方案 §3.1 第 1 条：dashboard 对纯 v7 明示不支持，不接 .cache、不另建读侧。
    """
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    scripts_entry = str(scripts_dir)
    if scripts_entry not in sys.path:
        sys.path.insert(0, scripts_entry)
    from data_modules.domain_contract import resolve_write_mode

    if resolve_write_mode(project_root) == "v7":
        return _V7_UNSUPPORTED_MSG
    return None


def _resolve_project_root(cli_root: str | None) -> Path:
    """按优先级解析 PROJECT_ROOT：CLI > 环境变量 > .claude 指针 > CWD。"""
    if cli_root:
        return Path(cli_root).resolve()

    env = os.environ.get("WEBNOVEL_PROJECT_ROOT")
    if env:
        return Path(env).resolve()

    # 尝试从 .claude 指针读取
    cwd = Path.cwd()
    pointer = cwd / ".claude" / ".webnovel-current-project"
    if pointer.is_file():
        target = pointer.read_text(encoding="utf-8").strip()
        if target:
            p = Path(target)
            if p.is_dir() and (p / ".webnovel" / "state.json").is_file():
                return p.resolve()

    # 最终兜底：当前目录
    if (cwd / ".webnovel" / "state.json").is_file():
        return cwd.resolve()

    print("ERROR: 无法定位 PROJECT_ROOT（需要包含 .webnovel/state.json 的目录）", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Webnovel Dashboard Server")
    parser.add_argument("--project-root", type=str, default=None, help="小说项目根目录")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8765, help="监听端口")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument(
        "--allow-nonlocal",
        action="store_true",
        help="显式允许绑定非回环地址（Dashboard 无鉴权，暴露到局域网风险自担）",
    )
    args = parser.parse_args()

    # 增量审阅 P2-6：无鉴权服务禁止默认暴露到局域网，必须显式确认
    if args.host not in {"127.0.0.1", "localhost", "::1"} and not args.allow_nonlocal:
        parser.error(
            f"拒绝绑定 {args.host}：Dashboard 无鉴权，非回环绑定会把全书内容暴露到网络。\n"
            "确需局域网访问请加 --allow-nonlocal（风险自担）。"
        )

    project_root = _resolve_project_root(args.project_root)
    blocked = refuse_v7_dashboard(project_root)
    if blocked:
        print(f"ERROR: {blocked}", file=sys.stderr)
        sys.exit(1)
    print(f"项目路径: {project_root}")

    # 延迟导入，以便先处理路径
    import uvicorn
    from .app import create_app

    app = create_app(project_root)

    url = f"http://{args.host}:{args.port}"
    print(f"Dashboard 启动: {url}")
    print(f"API 文档: {url}/docs")

    if not args.no_browser:
        webbrowser.open(url)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
