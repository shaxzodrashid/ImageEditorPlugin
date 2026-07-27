from __future__ import annotations

import json
from pathlib import Path

from .models import ProjectManifest, ToolEnvelope


def export_schemas(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write(output_dir / "project-manifest.schema.json", ProjectManifest.model_json_schema())
    _write(output_dir / "tool-envelope.schema.json", ToolEnvelope.model_json_schema())


def main() -> None:
    export_schemas(Path("schemas"))


def _write(path: Path, schema: dict[str, object]) -> None:
    path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8", newline="\n")
