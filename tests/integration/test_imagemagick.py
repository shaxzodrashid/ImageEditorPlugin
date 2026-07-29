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


@pytest.mark.integration
def test_connected_border_mask_preserves_enclosed_background_color(tmp_path: Path) -> None:
    executable = shutil.which("magick")
    if executable is None:
        pytest.skip("ImageMagick 7 is not installed")
    source = tmp_path / "source.png"
    mask = tmp_path / "mask.png"
    cutout = tmp_path / "cutout.png"
    subprocess.run(
        [
            executable,
            "-size",
            "64x64",
            "xc:white",
            "-fill",
            "red",
            "-draw",
            "rectangle 10,10 53,53",
            "-fill",
            "white",
            "-draw",
            "circle 32,32 32,26",
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    engine = ImageMagickEngine(executable)
    engine.selection_mask_border(source, mask, (255, 255, 255), 6, 0)
    engine.apply_selection_mask(source, mask, cutout)
    result = engine.run(
        [
            "identify",
            "-quiet",
            "-format",
            "%[fx:p{0,0}.a],%[fx:p{32,32}.a]",
            str(cutout),
        ]
    )
    corner, enclosed = (float(value) for value in result.stdout.split(","))
    assert corner == 0
    assert enclosed == 1
    assert engine.inspect(cutout).has_alpha


@pytest.mark.integration
def test_cutout_alpha_multiplies_original_alpha(tmp_path: Path) -> None:
    executable = shutil.which("magick")
    if executable is None:
        pytest.skip("ImageMagick 7 is not installed")
    source = tmp_path / "half-alpha.png"
    mask = tmp_path / "half-mask.png"
    cutout = tmp_path / "quarter-alpha.png"
    subprocess.run(
        [executable, "-size", "4x4", "xc:#ff000080", str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [executable, "-size", "4x4", "xc:gray50", str(mask)],
        check=True,
        capture_output=True,
        text=True,
    )
    engine = ImageMagickEngine(executable)
    engine.apply_selection_mask(source, mask, cutout)
    result = engine.run(["identify", "-quiet", "-format", "%[fx:p{2,2}.a]", str(cutout)])
    assert float(result.stdout) == pytest.approx(0.25, abs=0.01)


@pytest.mark.integration
def test_safe_zone_overlay_marks_only_the_perimeter(tmp_path: Path) -> None:
    executable = shutil.which("magick")
    if executable is None:
        pytest.skip("ImageMagick 7 is not installed")
    output = tmp_path / "safe-zone.png"
    engine = ImageMagickEngine(executable)

    engine.render(1080, 1350, "white", [], output, safe_zone_margins=(64, 65, 70, 65))

    result = engine.run(
        [
            "identify",
            "-quiet",
            "-format",
            (
                "%[pixel:p{64,675}]|%[pixel:p{65,675}]|"
                "%[pixel:p{540,63}]|%[pixel:p{540,64}]|"
                "%[pixel:p{540,1279}]|%[pixel:p{540,1280}]"
            ),
            str(output),
        ]
    )
    left_edge, left_inner, top_edge, top_inner, bottom_inner, bottom_edge = (
        result.stdout.casefold().split("|")
    )
    assert left_edge != left_inner
    assert top_edge != top_inner
    assert bottom_edge != bottom_inner
    for inner in (left_inner, top_inner, bottom_inner):
        assert "255,255,255" in inner or "100%,100%,100%" in inner
