# 05 · 卸载与重装 Runbook（文件级操作手册）

> 背景：`zcode` CLI 不存在；GUI 操作无法由 agent 驱动本应用自身。zcode-configuration-guide 授权 agent 直接编辑配置文件。本手册操作对象全部为本机用户目录，**改完必须重启 ZCode（或新开会话）才生效**。
> 新插件源：`C:\lgq\ai-workspace\projects\zcode-plugins\webnovel-writer`（外层仓库；插件本体在内层 `webnovel-writer/`，marketplace source = `./webnovel-writer`）。
> 旧装机：marketplace `webnovel-writer-marketplace` → 旧路径 `C:\lgq\ai-workspace\projects\claude-plugins\webnovel-writer`，插件版本 6.5.0。

## 0. 涉及文件清单

| 路径 | 角色 |
|------|------|
| `~/.zcode/cli/config.json` | `plugins.enabledPlugins` 开关 |
| `~/.zcode/cli/plugins/installed_plugins.json` | 装机登记（版本、installPath、source、cacheTransactionId） |
| `~/.zcode/cli/plugins/known_marketplaces.json` | marketplace 源登记（directory 源记 `source.path`） |
| `~/.zcode/cli/plugins/marketplaces/webnovel-writer-marketplace/` | marketplace 源克隆（含 `.git`） |
| `~/.zcode/cli/plugins/cache/webnovel-writer-marketplace/webnovel-writer/<version>/` | 插件版本化装机副本 |

> Windows 下 `~` = `C:\Users\a6748`。所有 JSON 编辑用 Python（`json` 模块读写，UTF-8，保持既有缩进风格），避免手工编辑引入 BOM/尾逗号。

## 1. 卸载旧插件（v6.5.0）

```powershell
# 1) config.json：删除 enabledPlugins["webnovel-writer@webnovel-writer-marketplace"]
# 2) installed_plugins.json：删除 id=webnovel-writer@webnovel-writer-marketplace 的条目
# 3) 删除缓存目录：cache/webnovel-writer-marketplace/（整目录，含 6.2.1/6.5.0 两个历史版本）
```

marketplace 登记与克隆**保留 id 不动、原地改指向**（见 §2），等效于「换源不换 marketplace」——`webnovel-writer@webnovel-writer-marketplace` 这个组件标识在新装机后保持不变，历史配置（如未来 userConfig 值）不受扰动。

## 2. marketplace 换源（旧路径 → 新路径）

```powershell
# 1) known_marketplaces.json：
#    marketplaces[id=webnovel-writer-marketplace].source.path
#      "C:\\lgq\\ai-workspace\\projects\\claude-plugins\\webnovel-writer"
#      → "C:\\lgq\\ai-workspace\\projects\\zcode-plugins\\webnovel-writer"
#    （name/description 以新源 marketplace.json 为准刷新；lastUpdated 更新为当前时间）
# 2) marketplaces/webnovel-writer-marketplace/：整目录替换为新仓库当前 HEAD 的干净副本（含 .git）
#    —— 与 ZCode「克隆源仓库到该目录」的行为对齐
```

> 注意：新源 marketplace.json 的 `name` 必须仍为 `webnovel-writer-marketplace`（id 稳定的前提）。

## 3. 重装 v8.1.0（模拟 ZCode 安装产物）

> 版本号以 `webnovel-writer/.zcode-plugin/plugin.json` 为准；本文件每次发版需同步。
> 2026-09-13 订正：本文件此前通篇停留在 7.1.0（§3 标题 / 缓存目录 / installed_plugins.json
> 示例 / §4 判据 1），且 §4 判据 2 的「9 条命令」为 v7 旧口径（现为 13 条）。

```powershell
# 1) 建版本缓存目录：
#    cache/webnovel-writer-marketplace/webnovel-writer/8.1.0/
# 2) 复制插件本体（内层目录完整内容，排除 .git / __pycache__ / *.pyc / .pytest_cache）到上述目录
# 3) installed_plugins.json 追加条目：
{
  "id": "webnovel-writer@webnovel-writer-marketplace",
  "name": "webnovel-writer",
  "marketplace": "webnovel-writer-marketplace",
  "version": "8.1.0",
  "installPath": "C:\\Users\\a6748\\.zcode\\cli\\plugins\\cache\\webnovel-writer-marketplace\\webnovel-writer\\8.1.0",
  "installedAt": "<now ISO8601 Z>",
  "updatedAt": "<now ISO8601 Z>",
  "scope": "user",
  "source": "./webnovel-writer",
  "cacheTransactionId": "<新 UUIDv4>"
}
# 4) config.json：plugins.enabledPlugins["webnovel-writer@webnovel-writer-marketplace"] = true
```

复制清单（与 6.5.0 装机副本顶层一致 + 新增件）：
`.zcode-plugin/ · agents/ · commands/ · hooks/ · mcp/ · skills/ · scripts/ · references/ · templates/ · dashboard/ · evals/ · README.md · LICENSE · .gitignore`

## 4. 装机后验证清单（需重启 ZCode / 新会话）

| # | 验证点 | 判据 |
|---|--------|------|
| 1 | 插件版本 | Settings → Plugin Management → webnovel-writer 显示 8.1.0；会话 skill 前缀 `webnovel-writer:` 的 8 个 skill 均可发现 |
| 2 | 斜杠命令 | `/` 菜单出现 `/webnovel:status` … `/webnovel:dashboard` 13 条 |
| 3 | MCP server | Settings → MCP 出现 `webnovel`（built-in 标记）且 connected；会话内可调用 `mcp__webnovel__webnovel_where` 类工具 |
| 4 | hooks | 新会话首条消息后出现 webnovel 项目状态注入（SessionStart/`chapter_meter` 链路）；对运行时文件的直写被 `guard_runtime_write` 阻断（可低风险试探一次） |
| 5 | agents | Agent 工具可用类型含 `webnovel-writer:context-agent` 等 4 个 |
| 6 | userConfig | 插件详情 → Advanced 出现「书项目根目录」directory 字段 |
| 7 | CLI 冒烟 | 在书项目内：`python -X utf8 <installPath>/scripts/webnovel.py preflight` 通过；`webnovel_doctor` MCP 工具返回体检 JSON |

## 4.5 实测教训（2026-09-03 执行记录）

- **不要改名「运行中会话已注册 hook」所依赖的缓存目录**。§1.3 把 `6.5.0` 改名为 `6.5.0.bak` 后，当前会话的 PreToolUse hook（路径已在会话启动时解析为 6.5.0 绝对路径）立即找不到脚本，python 退出码 2 = 阻断语义，导致会话内所有 Bash/Write/Edit 全部被拒。恢复：把目录改回原名（本次经桌面终端执行 `mv 6.5.0.bak 6.5.0` 后即恢复）。
- **最终处置**：`6.5.0` 保留原目录名不动（惰性回滚产物，ZCode 只按 installed_plugins.json 的 installPath 定位，不会被扫描加载）；`6.2.1` 改名 `6.2.1.bak` 无副作用（无会话引用）。需要清理时，在重启 ZCode 后随意处置。

## 5. 回滚方案

- 保留旧缓存即可秒回滚：恢复 `installed_plugins.json` 中 6.5.0 条目（installPath 指回 `…\webnovel-writer\6.5.0`）、config.json 开关键、marketplace source.path 指回旧路径，重启。
- 本 runbook 执行前先备份三个 JSON（`*.bak-zcode-adaptation`）。旧缓存目录（6.5.0）在 §1.3 中删除——**如需保留回滚能力，改为把 6.5.0 目录改名留存（`6.5.0.bak`）而非删除**（ZCode 只按 installed_plugins.json 的 installPath 定位，改名目录不会被扫描）。本任务采用「改名留存」。

## 6. 登记面丢失后的快速重建（2026-09-20 实战补充）

- **症状与定性**：ZCode 更新/迁移后插件整体消失（无 skill/命令/agents，MCP 面板无 webnovel），而 `cache/webnovel-writer-marketplace/` 副本仍在 → 是**登记面丢失**，不是缓存过期。2026-09-16–09-17 的 ZCode 更新曾把三处登记全清掉（known_marketplaces 只剩官方两条、installed_plugins.json 整文件消失、config.json 无 plugins 段）；09-18–09-20 按下述 schema 重建并实测恢复。
- **登记 schema**（从 `D:\lgq\ai-software\Zcode\resources\glm\zcode.cjs` 解析器逆向核实；通用取证办法 `grep -o '.\{N\}<关键字>.\{M\}' zcode.cjs`）：
  - `installed_plugins.json`：顶层 `{"version":1,"plugins":[…]}`（数组或以 id 为键的字典均认）；条目七必填：`id`（`<name>@<marketplace>`）/`name`/`marketplace`/`version`/`installPath`/`installedAt`/`scope`（user|workspace）；`updatedAt`/`source`/`cacheTransactionId` 可选。
  - `known_marketplaces.json`：条目须含 `id`/`name`/`pluginCount`（数字）/`source`；directory 源为 `{"source":"directory","path":"…"}`（strict 校验）。
  - `cli/config.json`：`plugins.enabledPlugins = {"webnovel-writer@webnovel-writer-marketplace": true}`（与 hooks/mcp 同文件）。
- **重建步骤**：缓存副本对源**逐文件字节比对**补齐（比对对象是磁盘工作区而非 git blob——`core.autocrlf=true` 时工作区为 CRLF，对 blob 比会假报几十个差异）；镜像克隆 `git fetch + reset --hard` 对齐源 HEAD；三登记用 Python json 模块写、先备份。
- **MCP「声明了但未成功加载」新坑（2026-09-20）**：mcpServers env 引用 `${user_config.<key>}` 的键必须有 `default` 或用户已设值，否则宿主展开直接 throw，server 未及 spawn 即失败；修复 = plugin.json 给该键补 `"default": ""`。另：3.12.3 起宿主已读 `.zcode-plugin/plugin.json` 内联 mcpServers，**无需根 `.mcp.json`**（§4.5 时代 9/15 的旧结论作废）。
- **验收**：守卫 hook 探针 5 例（直删/复合命令/伪造写链 rc=2、单独写链 rc=0、Write 受保护 rc=2）+ 装机副本 `mcp/server.py` 行分隔 JSON-RPC `tools/list` 计 12 工具 + 重启后按 §4 清单 GUI 复验。
