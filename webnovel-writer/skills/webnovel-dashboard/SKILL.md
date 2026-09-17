---
name: webnovel-dashboard
description: 启动只读小说管理面板（仅存量 v6 仓；纯 v7 明示不支持）。
allowed-tools: Bash Read
---

# Webnovel Dashboard

## 目标

- **仅存量 v6 仓**：在本地启动只读 Web 面板，查看创作进度、设定词典、关系图谱、章节内容与追读力数据。
- 暴露 Story Runtime 主链状态：`/api/story-runtime/health`、latest commit、fallback 情况。
- 可监听 `.webnovel/` 变化，但不修改任何项目文件。
- **纯 v7 书仓明示不支持**（2026-09-18 裁决）：本面板读 v6 投影（`.webnovel/state.json` / `index.db`），不接 `.cache`、不另建 v7 读侧。v7 请用 `doctor` / `project-status` / `setting-read`，或直接打开 `定稿/` `大纲/` `设定/`。

## 执行流程

### Step 1：确认环境与模块目录

```bash
export WORKSPACE_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"

if [ -z "${CLAUDE_PLUGIN_ROOT}" ] || [ ! -d "${CLAUDE_PLUGIN_ROOT}/dashboard" ]; then
  echo "ERROR: 未找到 dashboard 模块: ${CLAUDE_PLUGIN_ROOT}/dashboard" >&2
  exit 1
fi

export DASHBOARD_DIR="${CLAUDE_PLUGIN_ROOT}/dashboard"
export SCRIPTS_DIR="${CLAUDE_PLUGIN_ROOT}/scripts"
```

### Step 2：解析项目根目录

```bash
export PROJECT_ROOT="$(python -X utf8 "${SCRIPTS_DIR}/webnovel.py" --project-root "${WORKSPACE_ROOT}" where)"
echo "项目路径: ${PROJECT_ROOT}"
```

`PROJECT_ROOT` 必须解析成功。

### Step 2.5：纯 v7 仓不要启动

若书仓有 `book.yaml` 且没有 `.webnovel/state.json`，这是纯 v7 仓。**向作者说明 Dashboard 不支持纯 v7，然后退出**，不要进入 Step 4。启动脚本本身也会拒绝，本步是为了先用自然语言交代替代入口。

### Step 3：校验前端产物与依赖

```bash
if [ -n "${PYTHONPATH:-}" ]; then
  export PYTHONPATH="${CLAUDE_PLUGIN_ROOT}:${PYTHONPATH}"
else
  export PYTHONPATH="${CLAUDE_PLUGIN_ROOT}"
fi

if [ ! -f "${DASHBOARD_DIR}/frontend/dist/index.html" ]; then
  echo "ERROR: 缺少前端构建产物 ${DASHBOARD_DIR}/frontend/dist/index.html（dist 应随插件打包，确认插件完整安装）" >&2
  exit 1
fi
```

不默认安装依赖。仅当 Step 4 因缺依赖启动失败时，提示用户手动执行：

```bash
python -m pip install -r "${DASHBOARD_DIR}/requirements.txt"
```

### Step 4：启动 Dashboard

```bash
python -X utf8 -m dashboard.server --project-root "${PROJECT_ROOT}"
```

不自动打开浏览器时加 `--no-browser`；自定义端口加 `--port 9000`。

启动后优先确认接口可用：`/api/story-runtime/health`、`/api/preflight`。

## 成功标准

- **v6 仓**：Dashboard 进程已启动并输出可访问 URL；页面显示项目数据（章节列表、实体图谱等）。
- **纯 v7 仓**：未启动进程，已向作者说明不支持及替代入口（doctor / 六域文件）。这是预期行为，不是故障。

## 失败恢复

| 故障 | 恢复方式 |
|------|---------|
| 报「不支持纯 v7 书仓」 | 预期。改用 `doctor` / `project-status` / `setting-read` 或打开六域目录 |
| 启动报缺依赖 | 手动 `pip install -r "${DASHBOARD_DIR}/requirements.txt"`，检查 Python 版本与网络 |
| 前端 `dist/` 缺失 | 确认插件完整安装，dist 应随插件打包 |
| 项目根解析失败 | 检查 `book.yaml`（v7）或 `.webnovel/state.json`（v6）是否存在，确认 `WORKSPACE_ROOT` 正确 |
| 端口占用 | 用 `--port <其他端口>` 或关闭占用进程 |
| 页面空白/数据缺失（v6） | 确认 `.webnovel/` 下有 state.json、index.db 等数据文件 |

## 安全边界

- 纯只读面板，不提供修改接口，不修改任何项目文件。
- 文件访问限制在 `PROJECT_ROOT` 范围内，默认仅监听 localhost。
