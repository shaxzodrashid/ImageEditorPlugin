from __future__ import annotations

import json
import tomllib
from pathlib import Path

from image_editor_plugin import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_version_metadata_matches_project_version() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = json.loads(
        (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    project_version = pyproject["project"]["version"]
    plugin_version = plugin["version"].partition("+")[0]

    assert __version__ == project_version
    assert plugin_version == project_version
