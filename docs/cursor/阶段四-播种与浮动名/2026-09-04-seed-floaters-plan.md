# 复合题材播种与浮动名扫描 实施计划

> **执行者注意：** 按任务逐个实施。步骤用 checkbox 跟踪，完成即勾选。
>
> 我在用 writing-plans 技能写实施计划。

**目标：** 播种按 canonical 并集；name-check `--scan` 报未入册高频专名（warning，exit 0）。
**架构：** `GenreResolution.canonical_genres` + `seed_genre_label`；init 改传并集。`scan_floating_names` 扫近 5 章定稿。
**技术栈：** Python 3.10+、pytest。
**Spec：** `docs/cursor/阶段四-播种与浮动名/2026-09-04-seed-floaters-spec.md`

## 全局约束

- 不改单值 `canonical_genre`。
- 不覆盖已有素材表；真仓 fantasy01 不跑 seed。
- 浮动名只读，不写名册；只扫 `定稿/正文`。
- 浮动名不把 CLI 打成失败。
- Windows：`python -X utf8`；覆盖率不低于 80%。

## 执行总览

| 序号 | 任务名 | 依赖 | 验证方式 |
|---|---|---|---|
| 1 | 失败测试：canonical_genres 并集 + 播种含仙侠行 | — | `test_genre_taxonomy.py` / `test_material_store.py` RED |
| 2 | `seed_genre_label` + init 接线 + 播种 GREEN | 依赖 Task 1 | 定点 GREEN |
| 3 | 失败测试：未入册铁牙 / 入册不报 / `--scan` | — | `test_continuity_check.py` RED |
| 4 | `scan_floating_names` + CLI 转发 GREEN | 依赖 Task 3 | 定点 GREEN |
| 5 | 提交实现（不含 spec/plan） | 依赖 Task 2、4 | 两个 feat |

Task 1 与 Task 3 可并行。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `webnovel-writer/scripts/tests/test_genre_taxonomy.py` | 修改 | 并集 vs 单值 |
| `webnovel-writer/scripts/tests/test_material_store.py` | 修改 | 复合键多种仙侠行 |
| `webnovel-writer/scripts/genre_taxonomy.py` | 修改 | `canonical_genres`；`seed_genre_label` |
| `webnovel-writer/scripts/init_project.py` | 修改 | 播种改并集标签 |
| `webnovel-writer/scripts/tests/test_continuity_check.py` | 修改 | 浮动名 |
| `webnovel-writer/scripts/data_modules/continuity_check.py` | 修改 | scan + CLI |
| `webnovel-writer/scripts/data_modules/webnovel.py` | 修改 | `--name` 可选；转发 `--scan`/`--format` |

README / 交接留收尾。

---

## Task 1：播种失败测试

**文件：** `test_genre_taxonomy.py`、`test_material_store.py`

- [ ] `test_genre_taxonomy.py` 增加：

```python
def test_compound_label_keeps_union_and_single_canonical():
    from genre_taxonomy import resolve_genre_input, seed_genre_label

    resolved = resolve_genre_input("都市+仙侠+科幻")
    assert resolved.canonical_genre == "都市"
    assert resolved.canonical_genres == ["都市", "仙侠", "科幻"]
    assert seed_genre_label("都市+仙侠+科幻") == "都市+仙侠+科幻"
```

- [ ] 在 `test_material_store.py` 的夹具源 CSV 增加仅 `仙侠` 适用的桥段行（如 `TR-XIAN`），并增加：

```python
def test_seed_compound_genre_includes_xianxia_rows(self, book: Path, source_dir: Path):
    from data_modules.material_store import seed_materials
    from genre_taxonomy import seed_genre_label

    urban = seed_materials(book / "u", genre="都市", source_dir=source_dir)
    mixed = seed_materials(
        book / "m",
        genre=seed_genre_label("都市+仙侠+科幻"),
        source_dir=source_dir,
    )
    urban_ids = {r["id"] for r in urban["rows"]["桥段"]}
    mixed_ids = {r["id"] for r in mixed["rows"]["桥段"]}
    assert "TR-XIAN" in mixed_ids
    assert "TR-XIAN" not in urban_ids
    assert urban_ids <= mixed_ids
```

夹具 `book / "u"` 与 `book / "m"` 需 `mkdir`；`source_dir` 的桥段表必须能按「适用题材」筛到 `TR-XIAN`（`仙侠`）与都市行。若现有夹具列名不同，按该文件已有 `_write_csv` 格式追加一行，不要另造一套列。

- [ ] RED：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_genre_taxonomy.py webnovel-writer/scripts/tests/test_material_store.py -q --no-cov -p no:cacheprovider -k "compound_label or compound_genre or seed_"
```

---

## Task 2：播种实现

- [ ] `GenreResolution` 增加 `canonical_genres: list[str] = field(default_factory=list)`。在 `resolve_genre_input` 填完 `canonical_genre` 后：

```python
    for entry in matched:
        canon = entry.canonical_genre
        if canon and canon != "全部" and canon not in resolution.canonical_genres:
            resolution.canonical_genres.append(canon)
```

- [ ] 增加：

```python
def seed_genre_label(raw: str) -> str:
    resolved = resolve_genre_input(raw)
    if resolved.canonical_genres:
        return "+".join(resolved.canonical_genres)
    return str(raw or "").strip()
```

- [ ] `init_project.py` 将 `seed_materials(project_path, genre=canonical_genre)` 改为 `seed_materials(project_path, genre=seed_genre_label(genre))`（`from genre_taxonomy import seed_genre_label`，已有 `resolve_genre_input` 导入处并列）。

- [ ] GREEN：Task 1 命令去掉 RED 预期。既有 `test_seed_filters_by_genre_and_caps` 仍绿。

---

## Task 3：浮动名失败测试

**文件：** `test_continuity_check.py`

- [ ] 增加：

```python
def _plant_settled_chapter(root: Path, chapter: int, body: str) -> None:
    folder = root / "定稿" / "正文"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{chapter:04d}-测.md").write_text(
        f"---\n章: {chapter}\n---\n{body}\n", encoding="utf-8"
    )


def test_scan_flags_unlisted_nickname(book: Path):
    from data_modules.continuity_check import scan_floating_names

    _plant_settled_chapter(book, 41, "铁牙守门。铁牙又来了。")
    found = {item["name"]: item for item in scan_floating_names(book, window=5, min_count=2)}
    assert "铁牙" in found
    assert found["铁牙"]["count"] >= 2


def test_scan_skips_rostered_name(book: Path):
    from data_modules.continuity_check import scan_floating_names

    _plant_settled_chapter(book, 41, "苏小白走了。苏小白又回来。")
    names = [item["name"] for item in scan_floating_names(book, window=5, min_count=2)]
    assert "苏小白" not in names


def test_cli_scan_exit_zero_with_warning(book: Path, capsys):
    from data_modules.continuity_check import main

    _plant_settled_chapter(book, 41, "铁牙守门。铁牙又来了。")
    code = main(["--scan", "--project-root", str(book), "--format", "json"])
    assert code == 0
    import json
    payload = json.loads(capsys.readouterr().out)
    assert any(item["name"] == "铁牙" for item in payload.get("floaters") or [])
```

`book` 夹具已有名册苏小白、无铁牙。

- [ ] RED：

```powershell
python -X utf8 -m pytest webnovel-writer/scripts/tests/test_continuity_check.py -q --no-cov -p no:cacheprovider -k "scan_ or cli_scan"
```

---

## Task 4：浮动名实现

- [ ] `continuity_check.py`：

```python
FLOATER_WINDOW = 5
FLOATER_MIN_COUNT = 2
_FLOATER_RE = re.compile(r"[\u4e00-\u9fa5]{2,4}")


def scan_floating_names(
    project_root: str | Path,
    *,
    window: int = FLOATER_WINDOW,
    min_count: int = FLOATER_MIN_COUNT,
) -> list[dict[str, Any]]:
    from data_modules.dual_format_guard import max_settled_chapter

    root = Path(project_root)
    latest = max_settled_chapter(root)
    if latest <= 0:
        return []
    start = max(1, latest - max(1, int(window)) + 1)
    known = {item["name"] for item in load_known_names(root)}
    counts: dict[str, dict[str, Any]] = {}
    body_dir = root / "定稿" / "正文"
    for chapter in range(start, latest + 1):
        matches = list(body_dir.glob(f"{chapter:04d}-*.md"))
        if not matches:
            continue
        text = matches[0].read_text(encoding="utf-8")
        if text.startswith("---"):
            parts = text.split("---", 2)
            text = parts[2] if len(parts) >= 3 else text
        for token in _FLOATER_RE.findall(text):
            if token in known:
                continue
            slot = counts.setdefault(token, {"name": token, "count": 0, "chapters": []})
            slot["count"] += 1
            if chapter not in slot["chapters"]:
                slot["chapters"].append(chapter)
    return sorted(
        (item for item in counts.values() if item["count"] >= int(min_count)),
        key=lambda item: (-item["count"], item["name"]),
    )
```

`check_name_conflicts` 返回值加 `"floaters": []`。`main`：`--scan`；无 `--scan` 且无 `--name` 仍 error。有 `--scan` 时把 `scan_floating_names` 写入 `floaters`。json 整份 dump。text 在冲突块之后若 floaters 非空则打印 `WARNING 浮动名 {n} 个：` 及名单。仅 scan、无冲突、有浮动名 → 仍 exit 0。

- [ ] `webnovel.py`：`p_name_check` 的 `--name` 改为 `default=""`、去掉 `required=True`；增加 `--scan`。`cmd_name_check` 转发 `--format`；`--scan` 时 argv 加 `--scan`；有 name 才加 `--name`。

- [ ] GREEN：Task 3 命令 + 既有 `TestNameConflict`。

---

## Task 5：提交

- [ ] 播种（taxonomy + init + 两份测试）：

```text
feat(materials): 复合题材按 canonical 并集播种
```

- [ ] 浮动名（continuity + webnovel + 测试）：

```text
feat(name-check): 扫描近章未入册高频专名
```

不要 stage spec/plan。

---

## 完成定义（实现期）

- 复合标签：单值 canonical 仍为都市；并集三键；播种多种仙侠行。
- 未入册铁牙 ≥2 → floaters；名册名不报；`--scan` exit 0。
- fantasy01：tmp 用其题材标签播种含仙侠；真仓不写素材。
- 全量回归与 README W1 留收尾。
