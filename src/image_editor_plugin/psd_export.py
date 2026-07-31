from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .constants import OPERATION_TIMEOUT_SECONDS
from .errors import EditorError

PSD_MAX_DIMENSION = 30_000
PSD_ROUNDTRIP_TIER = "photoshopapi-roundtrip"
PSD_COMPATIBILITY_WARNING = (
    "The PSD was structurally re-opened with PhotoshopAPI; native Adobe Photoshop and third-party "
    "reader compatibility were not verified."
)


@dataclass(frozen=True, slots=True)
class PsdLayerSource:
    """A validated project pixel layer to encode into a PSD."""

    source: Path
    name: str
    x: int
    y: int
    opacity: float
    visible: bool


class PsdExporter:
    """Run PhotoshopAPI export in a bounded child process.

    PhotoshopAPI is a native extension that emits progress logs. The MCP server communicates over
    stdio, so the worker's output is captured instead of allowing native logs to corrupt the MCP
    protocol. The worker writes and reopens the staged PSD before this method returns successfully.
    """

    def export(
        self,
        output: Path,
        width: int,
        height: int,
        canvas_background: str,
        layers: list[PsdLayerSource],
    ) -> None:
        if width > PSD_MAX_DIMENSION or height > PSD_MAX_DIMENSION:
            raise EditorError(
                "UNSUPPORTED_FEATURE",
                f"PSD export is limited to {PSD_MAX_DIMENSION:,} pixels per dimension.",
                False,
                ("Export as PSB when that format is available.",),
            )

        payload = {
            "output": str(output),
            "width": width,
            "height": height,
            "canvas_background": canvas_background,
            "layers": [{**asdict(layer), "source": str(layer.source)} for layer in layers],
        }
        try:
            result = subprocess.run(
                [sys.executable, "-m", "image_editor_plugin.psd_worker"],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=OPERATION_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise EditorError(
                "EXPORT_FAILED",
                "PSD export exceeded its time limit.",
                True,
                ("Reduce the canvas or layer dimensions and retry.",),
            ) from exc
        except OSError as exc:
            raise EditorError(
                "EXPORT_FAILED",
                "Could not start the isolated PSD export worker.",
                False,
                ("Restart the plugin and retry the export.",),
            ) from exc

        if result.returncode != 0:
            raise EditorError(
                "EXPORT_FAILED",
                "Could not create a structurally valid layered PSD.",
                False,
                (
                    "Check that every project layer asset is a readable PNG or JPEG.",
                    "Reduce the canvas or layer dimensions and retry.",
                ),
            )
