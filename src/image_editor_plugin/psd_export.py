from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast

from .constants import OPERATION_TIMEOUT_SECONDS
from .errors import EditorError

PSD_MAX_DIMENSION = 30_000
PSD_PORTABLE_BACKEND = "psd-tools"
PSD_NATIVE_BACKEND = "photoshopapi"
PSD_ROUNDTRIP_TIER = "psd-tools-roundtrip"
PSD_NATIVE_ROUNDTRIP_TIER = "photoshopapi-roundtrip"
PSD_COMPATIBILITY_WARNING = (
    "The PSD was structurally re-opened with psd-tools. Native Adobe Photoshop and third-party "
    "reader compatibility were not verified."
)

PsdBackendPreference = Literal["auto", "portable", "native"]


@dataclass(frozen=True, slots=True)
class PsdLayerSource:
    """A validated project pixel layer to encode into a PSD."""

    source: Path
    name: str
    x: int
    y: int
    opacity: float
    visible: bool


@dataclass(frozen=True, slots=True)
class PsdExportResult:
    """Non-secret PSD provenance recorded with the delivery export."""

    backend: str
    validation: str
    fallback_from: str | None = None


class PsdExporter:
    """Export through an isolated portable or optional native PSD worker.

    `psd-tools` is the required, pure-Python backend. PhotoshopAPI is never imported by the MCP
    server: both its compatibility probe and its export run in a bounded child, so a SIGILL from a
    wheel compiled for a newer CPU cannot terminate or wedge the server process.
    """

    def __init__(self, preference: PsdBackendPreference | None = None) -> None:
        configured = preference or os.environ.get("IMAGE_EDITOR_PSD_BACKEND", "auto")
        resolved: PsdBackendPreference = "auto"
        if configured in {"auto", "portable", "native"}:
            resolved = cast(PsdBackendPreference, configured)
        self.preference = resolved

    def export(
        self,
        output: Path,
        width: int,
        height: int,
        canvas_background: str,
        layers: list[PsdLayerSource],
    ) -> PsdExportResult:
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
        if self._should_try_native():
            if self._native_probe_succeeds():
                if self._run_export_worker("image_editor_plugin.native_psd_worker", payload):
                    return PsdExportResult(PSD_NATIVE_BACKEND, PSD_NATIVE_ROUNDTRIP_TIER)
                output.unlink(missing_ok=True)
            result = self._run_portable(payload)
            return PsdExportResult(result.backend, result.validation, PSD_NATIVE_BACKEND)
        return self._run_portable(payload)

    def _should_try_native(self) -> bool:
        # Linux is portable-first. Native acceleration requires an explicit opt-in there because
        # compiler support for AVX2 says nothing about the deployed CPU feature set.
        return self.preference == "native" or (
            self.preference == "auto" and sys.platform != "linux"
        )

    def _native_probe_succeeds(self) -> bool:
        return self._run_worker("image_editor_plugin.native_psd_worker", {"action": "probe"})

    def _run_portable(self, payload: dict[str, object]) -> PsdExportResult:
        if not self._run_export_worker("image_editor_plugin.psd_worker", payload):
            raise EditorError(
                "EXPORT_FAILED",
                "Could not create a structurally valid layered PSD with the portable backend.",
                False,
                (
                    "Check that every project layer asset is a readable PNG or JPEG.",
                    "Reduce the canvas or layer dimensions and retry the export.",
                ),
            )
        return PsdExportResult(PSD_PORTABLE_BACKEND, PSD_ROUNDTRIP_TIER)

    def _run_export_worker(self, module: str, payload: dict[str, object]) -> bool:
        return self._run_worker(module, payload)

    def _run_worker(self, module: str, payload: dict[str, object]) -> bool:
        try:
            result = subprocess.run(
                [sys.executable, "-m", module],
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
                ("Reduce the canvas or layer dimensions and retry the export.",),
            ) from exc
        except OSError as exc:
            raise EditorError(
                "EXPORT_FAILED",
                "Could not start the isolated PSD export worker.",
                False,
                ("Restart the plugin and retry the export.",),
            ) from exc
        # A SIGILL exits non-zero (commonly 132 on Linux). It is intentionally indistinguishable
        # from other native-worker failures to callers and triggers the portable fallback.
        return result.returncode == 0
