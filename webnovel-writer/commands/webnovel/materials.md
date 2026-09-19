---
description: 素材工作台（十表状态/装配预览/入库三通道/卷审/拆书投喂）
allowed-tools: Bash, Read, Write
---

# /webnovel:materials

素材域工作台（活层 → 定版 → 使用轨迹）。

常用只读入口（优先 MCP 工具 `webnovel_materials_status` / `webnovel_materials_assemble`）：

```bash
python -X utf8 "${ZCODE_PLUGIN_ROOT}/scripts/webnovel.py" materials list --format json
python -X utf8 "${ZCODE_PLUGIN_ROOT}/scripts/webnovel.py" materials assemble --k 20 --format json
python -X utf8 "${ZCODE_PLUGIN_ROOT}/scripts/webnovel.py" materials review --volume {N}
```

入库三通道（AI 归纳/拆书投喂先进画廊，作者采纳才入活层）：

```bash
python -X utf8 "${ZCODE_PLUGIN_ROOT}/scripts/webnovel.py" materials propose --channel "AI归纳" --file {候选.csv}
python -X utf8 "${ZCODE_PLUGIN_ROOT}/scripts/webnovel.py" materials candidates
python -X utf8 "${ZCODE_PLUGIN_ROOT}/scripts/webnovel.py" materials adopt --batch {批号} --ids {ID}
python -X utf8 "${ZCODE_PLUGIN_ROOT}/scripts/webnovel.py" materials discard --batch {批号}
```

拆书投喂（deconstruction-agent 的素材入画廊模式）：用户要求「拆书入素材库」时，用 `Agent` 工具按注册名调 `webnovel-writer:deconstruction-agent` 并传 `mode=materials_feed`——agent 产出 `工作区/素材候选-拆书.csv` 后自行调用上面的 `materials propose --channel "拆书:<书名>"` 入画廊；本命令只负责复核批号（`materials candidates`）与提示作者 adopt/discard。

$ARGUMENTS 按动词路由（list/assemble/review/propose/adopt/discard；拆书走 deconstruction-agent）。红线：LLM 只提议、作者只确认；作者直编 `素材/活/*.csv` 即生效（author-sync 留账）。
