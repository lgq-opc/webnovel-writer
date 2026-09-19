# 插件发版指南

本项目的发布说明优先面向中文网文作者：先说明这版对写书有什么帮助，再补维护者关心的 CLI、schema、测试和 CI 细节。

## 发版前审计

发布说明必须覆盖“上一个正式版本 tag 到本次发布提交”的全部变化，而不是只写最后一次提交。

发版前先确认版本边界：

```bash
git tag --list "v*" --sort=-v:refname
git log --oneline v上一版本..HEAD
git diff --stat v上一版本..HEAD
```

把变化分成四类：

- 给作者看的变化：写章、审查、规划、查询、恢复、文档等用户能感受到的变化。
- 兼容性：是否需要迁移旧书项目，是否改变现有 `/webnovel-*` 命令习惯。
- 已知影响：跳过项、限制、需要注意的风险。
- 给维护者：新增 CLI、schema、helper、测试、CI、内部重构。

## 发布说明来源

每个正式版本都必须有两份文档：

- `CHANGELOG.md`：长期更新日志。
- `releases/vX.Y.Z.md`：GitHub Release 正文的唯一来源。

README 只保留一句中文用户收益摘要，例如：

```md
| **v6.2.0 (当前)** | 写章结果更清楚，失败后更好恢复 |
```

不要把 README 当完整 changelog。

## 版本同步

写好 `CHANGELOG.md` 和 `releases/vX.Y.Z.md` 后，再同步版本号和 README 摘要：

```bash
python -X utf8 webnovel-writer/scripts/sync_plugin_version.py --version X.Y.Z --release-notes "一句中文用户收益"
```

该命令会更新：

- `webnovel-writer/.zcode-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `README.md` 版本徽章
- `README.md` 当前版本行

## 本地校验

提交前至少运行：

```bash
python -X utf8 webnovel-writer/scripts/sync_plugin_version.py --check --expected-version X.Y.Z
python -X utf8 webnovel-writer/scripts/validate_release_notes.py --version X.Y.Z
python -X utf8 webnovel-writer/scripts/validate_plugin_package.py
git diff --check
```

涉及代码或提示词变化时，还要运行对应 pytest、行为评估或 smoke test，并把结果写进 `releases/vX.Y.Z.md` 的“验证”小节。

## 自动发版

1. 确认本地校验通过。
2. 提交并推送版本说明和版本元数据到 `master`。
3. `Plugin Release` 工作流会自动：
   - 校验 `plugin.json`、`marketplace.json`、README 版本一致。
   - 校验 `CHANGELOG.md` 和 `releases/vX.Y.Z.md` 存在且覆盖上个 tag。
   - 校验插件包结构。
   - 创建并推送 `vX.Y.Z` tag。
   - 使用 `releases/vX.Y.Z.md` 创建 GitHub Release。

如果对应 tag 已存在，工作流不会重复打 tag；如果 GitHub Release 已存在，也会自动跳过。若之前只创建了 tag 但 Release 缺失，重跑工作流会补建 Release。

也可以在 Actions 页面手动选择 `Plugin Release` 兜底触发。手动运行时可以输入 `version`，也可以留空让工作流从 `plugin.json` 读取当前版本。

## 自动版本校验

`Plugin Version Check` 工作流会在 Push / PR 时自动检查：

- 版本元数据一致。
- README 版本徽章一致。
- 当前版本有 release note。
- `CHANGELOG.md` 包含当前版本。

触发文件：

- `.claude-plugin/marketplace.json`
- `webnovel-writer/.zcode-plugin/plugin.json`
- `webnovel-writer/scripts/sync_plugin_version.py`
- `webnovel-writer/scripts/validate_release_notes.py`
- `README.md`
- `CHANGELOG.md`
- `releases/**`
