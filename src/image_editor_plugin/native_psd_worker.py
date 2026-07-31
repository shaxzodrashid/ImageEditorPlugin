from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from math import isclose
from pathlib import Path
from typing import Any, cast

# This module is intentionally the *only* code path that imports PhotoshopAPI. It is launched by
# PsdExporter in a bounded child; a native SIGILL from an incompatible wheel cannot affect MCP.
import numpy as np
import photoshopapi as psapi  # type: ignore[import-not-found]
from numpy.typing import NDArray
from PIL import Image, ImageColor

PSD_MAX_BYTES = 2 * 1024**3 - 1


@dataclass(frozen=True, slots=True)
class _ExpectedLayer:
    name: str
    x: int
    y: int
    width: int
    height: int
    opacity: int
    visible: bool


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        if payload.get("action") == "probe":
            return 0
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
    expected: list[_ExpectedLayer] = []

    api: Any = psapi
    color_mode = api.enum.ColorMode.rgb
    document: Any = api.LayeredFile_8bit(color_mode, width, height)
    if canvas_background != "transparent":
        background = cast(tuple[int, int, int, int], ImageColor.getcolor(canvas_background, "RGBA"))
        document.add_layer(
            api.ImageLayer_8bit(
                _solid_rgba(width, height, background),
                "Canvas Background",
                width=width,
                height=height,
                color_mode=color_mode,
            )
        )
        expected.append(_ExpectedLayer("Canvas Background", 0, 0, width, height, 255, True))

    for source in layers:
        path = Path(cast(str, source["source"]))
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
            image.load()
        x = cast(int, source["x"])
        y = cast(int, source["y"])
        opacity = cast(float, source["opacity"])
        visible = cast(bool, source["visible"])
        name = cast(str, source["name"])
        document.add_layer(
            api.ImageLayer_8bit(
                _image_to_channels(image),
                name,
                width=image.width,
                height=image.height,
                pos_x=x + image.width / 2 - width / 2,
                pos_y=y + image.height / 2 - height / 2,
                opacity=opacity,
                color_mode=color_mode,
                is_visible=visible,
            )
        )
        expected.append(
            _ExpectedLayer(name, x, y, image.width, image.height, int(opacity * 255), visible)
        )

    document.write(output)
    if output.stat().st_size > PSD_MAX_BYTES:
        raise ValueError("PSD exceeds file-size limit")
    _validate(output, width, height, expected)


def _validate(output: Path, width: int, height: int, expected: list[_ExpectedLayer]) -> None:
    api: Any = psapi
    document: Any = api.LayeredFile.read(output)
    actual: list[Any] = list(document.layers)
    if (
        document.width != width
        or document.height != height
        or document.bit_depth != api.enum.BitDepth.bd_8
        or len(actual) != len(expected)
    ):
        raise ValueError("PSD document did not round-trip")
    for actual_layer, expected_layer in zip(actual, expected, strict=True):
        if (
            actual_layer.name != expected_layer.name
            or not isclose(
                actual_layer.center_x,
                expected_layer.x + expected_layer.width / 2 - width / 2,
                abs_tol=1e-6,
            )
            or not isclose(
                actual_layer.center_y,
                expected_layer.y + expected_layer.height / 2 - height / 2,
                abs_tol=1e-6,
            )
            or actual_layer.width != expected_layer.width
            or actual_layer.height != expected_layer.height
            or int(actual_layer.opacity * 255) != expected_layer.opacity
            or actual_layer.is_visible != expected_layer.visible
        ):
            raise ValueError("PSD layer did not round-trip")


def _image_to_channels(image: Image.Image) -> NDArray[np.uint8]:
    return np.ascontiguousarray(np.asarray(image, dtype=np.uint8).transpose(2, 0, 1))


def _solid_rgba(width: int, height: int, color: tuple[int, int, int, int]) -> NDArray[np.uint8]:
    channels = np.empty((4, height, width), dtype=np.uint8)
    for index, component in enumerate(color):
        channels[index].fill(component)
    return channels


if __name__ == "__main__":
    raise SystemExit(main())
