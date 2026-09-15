#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[1]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


_ensure_scripts_on_path()

from validate_plugin_package import validate_package  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_minimal_package(
    root: Path,
    *,
    plugin_version: str = "1.2.3",
    marketplace_version: str = "1.2.3",
    manifest_dir: str = ".claude-plugin",
    marketplace_relative: str = ".claude-plugin/marketplace.json",
) -> None:
    _write_json(
        root / "webnovel-writer" / manifest_dir / "plugin.json",
        {"name": "webnovel-writer", "version": plugin_version, "description": "desc"},
    )
    _write_json(
        root / marketplace_relative,
        {
            "plugins": [
                {
                    "name": "webnovel-writer",
                    "version": marketplace_version,
                    "source": "./webnovel-writer",
                }
            ]
        },
    )
    (root / "README.md").write_text(
        "\n".join(
            [
                "# Test",
                "",
                f"[![Version](https://img.shields.io/badge/version-{plugin_version}-brightgreen.svg)]({marketplace_relative})",
                "",
                "| 版本 | 说明 |",
                "|------|------|",
                f"| **v{plugin_version} (当前)** | test |",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "webnovel-writer" / "LICENSE").parent.mkdir(parents=True, exist_ok=True)
    (root / "webnovel-writer" / "LICENSE").write_text("license\n", encoding="utf-8")
    skill = root / "webnovel-writer" / "skills" / "demo" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("---\nname: demo\ndescription: demo\n---\n\n# Demo\n", encoding="utf-8")
    agent = root / "webnovel-writer" / "agents" / "demo.md"
    agent.parent.mkdir(parents=True, exist_ok=True)
    agent.write_text("---\nname: demo\ndescription: demo\ntools: Read\n---\n\n# Demo\n", encoding="utf-8")


def test_validate_plugin_package_passes_minimal_package(tmp_path):
    _write_minimal_package(tmp_path)

    report = validate_package(tmp_path)

    assert report["ok"] is True
    assert report["error_count"] == 0


def test_validate_plugin_package_accepts_plugin_root(tmp_path):
    _write_minimal_package(tmp_path)

    report = validate_package(tmp_path / "webnovel-writer")

    assert report["ok"] is True
    assert report["error_count"] == 0


def test_validate_plugin_package_detects_version_mismatch(tmp_path):
    _write_minimal_package(tmp_path, plugin_version="1.2.3", marketplace_version="1.2.4")

    report = validate_package(tmp_path)

    assert report["ok"] is False
    assert any(item["code"] == "version.marketplace" for item in report["issues"])


def test_validate_plugin_package_detects_readme_badge_mismatch(tmp_path):
    _write_minimal_package(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8").replace("version-1.2.3", "version-1.2.2"), encoding="utf-8")

    report = validate_package(tmp_path)

    assert report["ok"] is False
    assert any(item["code"] == "version.readme_badge" for item in report["issues"])


def test_validate_plugin_package_detects_missing_skill_frontmatter(tmp_path):
    _write_minimal_package(tmp_path)
    skill = tmp_path / "webnovel-writer" / "skills" / "demo" / "SKILL.md"
    skill.write_text("---\nname: demo\n---\n\n# Demo\n", encoding="utf-8")

    report = validate_package(tmp_path)

    assert report["ok"] is False
    assert any(item["code"] == "skill.frontmatter" for item in report["issues"])


def test_validate_plugin_package_accepts_zcode_plugin_layout(tmp_path):
    # ZCode 原生布局：.zcode-plugin/plugin.json + 仓库根 marketplace.json
    _write_minimal_package(tmp_path, manifest_dir=".zcode-plugin", marketplace_relative="marketplace.json")

    report = validate_package(tmp_path)

    assert report["ok"] is True
    assert report["error_count"] == 0


def test_validate_plugin_package_accepts_zcode_plugin_root(tmp_path):
    _write_minimal_package(tmp_path, manifest_dir=".zcode-plugin", marketplace_relative="marketplace.json")

    report = validate_package(tmp_path / "webnovel-writer")

    assert report["ok"] is True
    assert report["error_count"] == 0


def test_validate_plugin_package_prefers_zcode_plugin_manifest(tmp_path):
    # 双清单并存时以 .zcode-plugin 为准（版本取自 .zcode-plugin）
    _write_minimal_package(tmp_path, manifest_dir=".zcode-plugin", marketplace_relative="marketplace.json", plugin_version="2.0.0", marketplace_version="2.0.0")
    _write_json(
        tmp_path / "webnovel-writer" / ".claude-plugin" / "plugin.json",
        {"name": "webnovel-writer", "version": "0.0.1", "description": "stale"},
    )

    report = validate_package(tmp_path)

    assert report["ok"] is True
    assert report["error_count"] == 0


def _mirror_marketplace_to_repo_root(root: Path) -> None:
    """把 .claude-plugin/marketplace.json 原样复制到仓库根（双位置等价态）。"""
    source = root / ".claude-plugin" / "marketplace.json"
    (root / "marketplace.json").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _marketplace_issue_paths(report: dict, code: str) -> list[Path]:
    return [Path(item["path"]) for item in report["issues"] if item["code"] == code]


def test_validate_plugin_package_dual_marketplace_equal_passes(tmp_path):
    _write_minimal_package(tmp_path)
    _mirror_marketplace_to_repo_root(tmp_path)

    report = validate_package(tmp_path)

    assert report["ok"] is True
    assert report["error_count"] == 0


def test_validate_plugin_package_dual_marketplace_drift_detected(tmp_path):
    _write_minimal_package(tmp_path)
    _mirror_marketplace_to_repo_root(tmp_path)
    payload = json.loads((tmp_path / "marketplace.json").read_text(encoding="utf-8"))
    payload["plugins"][0]["homepage"] = "https://example.invalid/drift"
    _write_json(tmp_path / "marketplace.json", payload)

    report = validate_package(tmp_path)

    assert report["ok"] is False
    assert any(item["code"] == "marketplace.dual_location" for item in report["issues"])


def test_validate_plugin_package_dual_marketplace_second_copy_broken_json(tmp_path):
    # CC 评审 A-2：第二份（.claude-plugin/）坏 JSON 必须点名报错，不得静默全绿。
    _write_minimal_package(tmp_path)
    _mirror_marketplace_to_repo_root(tmp_path)
    broken = tmp_path / ".claude-plugin" / "marketplace.json"
    broken.write_text("{ this is not json", encoding="utf-8")

    report = validate_package(tmp_path)

    assert report["ok"] is False
    issues = [item for item in report["issues"] if item["code"] == "marketplace.json"]
    assert broken in [Path(item["path"]) for item in issues], report["issues"]
    assert any(item["message"].startswith("invalid_json") for item in issues)


def test_validate_plugin_package_dual_marketplace_second_copy_bom(tmp_path):
    _write_minimal_package(tmp_path)
    _mirror_marketplace_to_repo_root(tmp_path)
    bom = tmp_path / ".claude-plugin" / "marketplace.json"
    bom.write_text(bom.read_text(encoding="utf-8"), encoding="utf-8-sig")

    report = validate_package(tmp_path)

    assert report["ok"] is False
    assert bom in _marketplace_issue_paths(report, "marketplace.json")


def test_validate_plugin_package_dual_marketplace_root_copy_broken_json(tmp_path):
    # 根那份坏了：单份检查会报，双位置检查也不得把整体错误吞掉。
    _write_minimal_package(tmp_path)
    _mirror_marketplace_to_repo_root(tmp_path)
    (tmp_path / "marketplace.json").write_text("{ broken", encoding="utf-8")

    report = validate_package(tmp_path)

    assert report["ok"] is False
    assert tmp_path / "marketplace.json" in _marketplace_issue_paths(report, "marketplace.json")


def test_validate_plugin_package_single_copy_root_only_keeps_compat(tmp_path):
    """CC 复评 R-2（取「改修文案」支）：仓库根单份（仅 marketplace.json，与「第二份缺失」
    同形状）保持既有兼容放行，且不得出现与闸门放行行为相反的门禁文案。"""
    _write_minimal_package(tmp_path, manifest_dir=".zcode-plugin", marketplace_relative="marketplace.json")

    report = validate_package(tmp_path)

    assert report["ok"] is True
    assert report["error_count"] == 0
    assert not any("两份必须存在" in (item.get("repair") or "") for item in report["issues"]), report["issues"]


def test_validate_plugin_package_broken_copy_repair_scoped_to_existing(tmp_path):
    """R-2：双位置 repair 文案只对「两份都已存在」提等价要求，不再宣称「两份必须存在」——
    否则与单份兼容放行（:182）脱钩，正是本项缺陷的形状。"""
    _write_minimal_package(tmp_path)
    _mirror_marketplace_to_repo_root(tmp_path)
    broken = tmp_path / ".claude-plugin" / "marketplace.json"
    broken.write_text("{ not json", encoding="utf-8")

    report = validate_package(tmp_path)

    repairs = [item.get("repair", "") for item in report["issues"] if item["code"] == "marketplace.json"]
    assert repairs, report["issues"]
    assert all("两份必须存在" not in repair for repair in repairs), repairs
    assert any("已存在" in repair for repair in repairs), repairs
