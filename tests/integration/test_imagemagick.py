from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from image_editor_plugin.engine import ImageMagickEngine


@pytest.mark.integration
def test_required_imagemagick_delegates() -> None:
    if shutil.which("magick") is None:
        pytest.skip("ImageMagick 7 is not installed")
    result = ImageMagickEngine().preflight()
    assert result["available"], result


@pytest.mark.integration
def test_image_inspect_with_resource_limits(tmp_path: Path) -> None:
    executable = shutil.which("magick")
    if executable is None:
        pytest.skip("ImageMagick 7 is not installed")
    source = tmp_path / "smoke.jpg"
    subprocess.run(
        [executable, "-size", "64x64", "xc:white", str(source)],
        check=True,
        capture_output=True,
        text=True,
    )

    info = ImageMagickEngine(executable).inspect(source)

    assert info.format == "JPEG"
    assert (info.width, info.height) == (64, 64)
