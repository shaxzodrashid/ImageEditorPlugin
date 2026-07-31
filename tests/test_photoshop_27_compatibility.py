from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from image_editor_plugin.psd_export import PsdExporter, PsdLayerSource

RUN_NATIVE_PHOTOSHOP_TEST = "IMAGE_EDITOR_RUN_NATIVE_PHOTOSHOP_TEST"


@pytest.mark.native_photoshop
def test_photoshop_27_8_opens_layered_psd_without_repair_dialog(tmp_path: Path) -> None:
    """Use Photoshop COM as the release gate for native Photoshop compatibility.

    This test is deliberately opt-in: it starts and quits Photoshop, so it never touches an
    interactive designer session. Enable it only on a dedicated Windows 27.8 verification host.
    """

    if sys.platform != "win32":
        pytest.skip("Native Photoshop 27.8 verification is a Windows COM test.")
    if os.environ.get(RUN_NATIVE_PHOTOSHOP_TEST) != "1":
        pytest.skip(f"Set {RUN_NATIVE_PHOTOSHOP_TEST}=1 on a dedicated Photoshop 27.8 host.")
    if _photoshop_is_running():
        pytest.skip(
            "Photoshop is already running; native verification must not disrupt a user session."
        )

    lower = tmp_path / "lower.png"
    upper = tmp_path / "upper.png"
    Image.new("RGBA", (12, 8), (230, 40, 60, 180)).save(lower)
    Image.new("RGBA", (6, 11), (20, 90, 240, 255)).save(upper)
    output = tmp_path / "photoshop-27-8-contract.psd"
    PsdExporter().export(
        output,
        width=64,
        height=48,
        canvas_background="#102030",
        layers=[
            PsdLayerSource(lower, "Lower artwork", 4, 5, 0.5, True),
            PsdLayerSource(upper, "Hidden guide", 30, 20, 1.0, False),
        ],
    )

    environment = {**os.environ, "IMAGE_EDITOR_NATIVE_PSD_PATH": str(output)}
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _photoshop_script()],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=environment,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def _photoshop_is_running() -> bool:
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Get-Process Photoshop"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return result.returncode == 0


def _photoshop_script() -> str:
    return """
$ErrorActionPreference = 'Stop'
$application = $null
$document = $null
try {
    $application = New-Object -ComObject Photoshop.Application
    if (-not $application.Version.StartsWith('27.8')) {
        throw "Expected Adobe Photoshop 27.8, found $($application.Version)."
    }
    # psDisplayErrorDialogs; a repair/corruption prompt fails the gate.
    $application.DisplayDialogs = 2
    $path = [Environment]::GetEnvironmentVariable('IMAGE_EDITOR_NATIVE_PSD_PATH')
    $document = $application.Open($path)
    if ($document.Width -ne 64 -or $document.Height -ne 48) {
        throw 'Photoshop opened the PSD with unexpected canvas dimensions.'
    }
    $names = @($document.Layers | ForEach-Object { $_.Name })
    foreach ($expected in @('Canvas Background', 'Lower artwork', 'Hidden guide')) {
        if ($names -notcontains $expected) {
            throw "Photoshop is missing expected layer: $expected"
        }
    }
}
finally {
    if ($null -ne $document) { $document.Close(2) } # psDoNotSaveChanges
    if ($null -ne $application) { $application.Quit() }
}
"""
