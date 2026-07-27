from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from image_editor_plugin.schema_export import export_schemas


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as temporary:
        generated = Path(temporary)
        export_schemas(generated)
        for name in ("project-manifest.schema.json", "tool-envelope.schema.json"):
            committed = json.loads((root / "schemas" / name).read_text(encoding="utf-8"))
            current = json.loads((generated / name).read_text(encoding="utf-8"))
            if committed != current:
                print(f"Generated schema is stale: {name}")
                return 1
    print("Generated schemas are current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
