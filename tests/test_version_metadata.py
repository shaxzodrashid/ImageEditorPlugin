from __future__ import annotations

import json
import tomllib
from pathlib import Path

from image_editor_plugin import __version__
from image_editor_plugin.constants import PLUGIN_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_version_metadata_matches_project_version() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))

    project_version = pyproject["project"]["version"]
    plugin_version = plugin["version"].partition("+")[0]

    assert __version__ == project_version
    assert project_version == PLUGIN_VERSION
    assert plugin_version == project_version
    assert plugin["version"].endswith("+codex.20260801000000")


def test_linux_cpu_compatibility_dependencies_are_pinned_and_native_is_optional() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert "numpy==2.3.5" in dependencies
    assert any(dependency.startswith("psd-tools>=1.10,<2") for dependency in dependencies)
    assert all("PhotoshopAPI" not in dependency for dependency in dependencies)
    assert pyproject["project"]["optional-dependencies"]["photoshopapi"] == ["PhotoshopAPI>=0.9,<1"]
    numpy_package = next(package for package in lock["package"] if package["name"] == "numpy")
    assert numpy_package["version"] == "2.3.5"


def test_mcp_import_path_never_imports_optional_photoshopapi() -> None:
    for relative in (
        "src/image_editor_plugin/server.py",
        "src/image_editor_plugin/project.py",
        "src/image_editor_plugin/psd_export.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8").casefold()
        assert "import photoshopapi" not in source
