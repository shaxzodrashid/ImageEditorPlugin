from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from PIL import Image, ImageChops, ImageColor
from psd_tools import PSDImage

PSD_MAX_BYTES = 2 * 1024**3 - 1


@dataclass(frozen=True, slots=True)
class _ExpectedLayer:
    name: str
    x: int
    y: int
    image: Image.Image
    opacity: int
    visible: bool


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        _write_and_validate(payload)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):
        return 1
    return 0


def _write_and_validate(payload: dict[str, Any]) -> None:
    output = Path(cast(str, payload["output"]))
    width = cast(int, payload["width"])
    height = cast(int, payload["height"])
    canvas_background = cast(str, payload["canvas_background"])
    layers = cast(list[dict[str, Any]], payload["layers"])
    document = PSDImage.new(mode="RGBA", size=(width, height), depth=8)
    expected: list[_ExpectedLayer] = []

    if canvas_background != "transparent":
        background = cast(tuple[int, int, int, int], ImageColor.getcolor(canvas_background, "RGBA"))
        image = Image.new("RGBA", (width, height), background)
        document.create_pixel_layer(image, name="Canvas Background", top=0, left=0, opacity=255)
        expected.append(_ExpectedLayer("Canvas Background", 0, 0, image, 255, True))

    for source in layers:
        path = Path(cast(str, source["source"]))
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
            image.load()
        x = cast(int, source["x"])
        y = cast(int, source["y"])
        opacity = int(cast(float, source["opacity"]) * 255)
        visible = cast(bool, source["visible"])
        name = cast(str, source["name"])
        layer = document.create_pixel_layer(image, name=name, top=y, left=x, opacity=opacity)
        layer.visible = visible
        expected.append(_ExpectedLayer(name, x, y, image, opacity, visible))

    document.save(output)
    if output.stat().st_size > PSD_MAX_BYTES:
        raise ValueError("PSD exceeds file-size limit")
    _validate(output, width, height, expected)


def _validate(output: Path, width: int, height: int, expected: list[_ExpectedLayer]) -> None:
    document = PSDImage.open(output)
    actual = list(document)
    if (
        document.size != (width, height)
        or document.depth != 8
        or document.color_mode != 3  # Photoshop RGB color mode.
        or document.channels != 4  # RGB plus alpha channels preserve transparent pixel layers.
        or len(actual) != len(expected)
    ):
        raise ValueError("PSD document did not round-trip")

    for actual_layer, expected_layer in zip(actual, expected, strict=True):
        if (
            actual_layer.name != expected_layer.name
            or actual_layer.left != expected_layer.x
            or actual_layer.top != expected_layer.y
            or actual_layer.width != expected_layer.image.width
            or actual_layer.height != expected_layer.image.height
            or actual_layer.opacity != expected_layer.opacity
            or actual_layer.visible != expected_layer.visible
        ):
            raise ValueError("PSD layer structure did not round-trip")
        actual_image = actual_layer.topil()
        if actual_image is None:
            raise ValueError("PSD layer pixels were unavailable")
        actual_image = actual_image.convert("RGBA")
        if (
            actual_image.size != expected_layer.image.size
            or ImageChops.difference(actual_image, expected_layer.image).getbbox() is not None
        ):
            raise ValueError("PSD layer pixels did not round-trip")


if __name__ == "__main__":
    raise SystemExit(main())
