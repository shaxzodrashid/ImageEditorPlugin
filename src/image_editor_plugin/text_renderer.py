from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont
from PIL import __version__ as PILLOW_VERSION

from .constants import MAX_DECODED_PIXELS, MAX_DIMENSION
from .errors import EditorError, invalid
from .models import RichTextLayerOptions, RichTextStyle, TextFontFamily, TextGradientStop

RENDERER_NAME = "Pillow"
RENDERER_VERSION = PILLOW_VERSION


@dataclass(frozen=True, slots=True)
class RenderedText:
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class _Token:
    text: str
    style: RichTextStyle
    font: ImageFont.FreeTypeFont
    advance: int


@dataclass(slots=True)
class _Line:
    tokens: list[_Token]
    width: int = 0
    ascent: int = 0
    descent: int = 0

    def append(self, token: _Token) -> None:
        self.tokens.append(token)
        self.width += token.advance
        ascent, descent = token.font.getmetrics()
        self.ascent = max(self.ascent, ascent)
        self.descent = max(self.descent, descent)


class RichTextRenderer:
    """Render validated rich text to a transparent, portable PNG asset."""

    def render(self, options: RichTextLayerOptions, output: Path) -> RenderedText:
        lines = self._layout(options)
        padding = options.padding
        content_width = max(line.width for line in lines)
        content_height = sum(
            max(1, math.ceil((line.ascent + line.descent) * options.line_spacing)) for line in lines
        )
        width = content_width + padding * 2
        height = content_height + padding * 2
        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            raise invalid(f"Rendered text dimensions cannot exceed {MAX_DIMENSION} pixels.")
        if width * height > MAX_DECODED_PIXELS:
            raise invalid("Rendered text exceeds the 100 million decoded-pixel limit.")

        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        top = padding
        for line in lines:
            available = content_width - line.width
            offset = 0
            if options.alignment.value == "center":
                offset = available // 2
            elif options.alignment.value == "right":
                offset = available
            baseline = top + line.ascent
            cursor = padding + offset
            for token in line.tokens:
                mask = Image.new("L", (width, height), 0)
                draw = ImageDraw.Draw(mask)
                left, upper, right, lower = draw.textbbox(
                    (cursor, baseline), token.text, font=token.font, anchor="ls"
                )
                draw.text((cursor, baseline), token.text, font=token.font, fill=255, anchor="ls")
                self._draw_decorations(draw, cursor, baseline, token)
                self._composite_fill(
                    canvas,
                    mask,
                    token.style,
                    (left, upper, max(1, right - left), max(1, lower - upper)),
                )
                cursor += token.advance
            top += max(1, math.ceil((line.ascent + line.descent) * options.line_spacing))

        output.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output, format="PNG", optimize=False)
        return RenderedText(width, height)

    def _layout(self, options: RichTextLayerOptions) -> list[_Line]:
        if not "".join(run.text for run in options.runs).strip():
            raise invalid("Rich text must contain at least one non-whitespace character.")
        lines: list[_Line] = []
        current = _Line([])
        for run in options.runs:
            font = self._font(run.style)
            for piece in re.findall(r"[^\s]+|[ \t]+|\r?\n", run.text):
                if piece in {"\n", "\r\n"}:
                    lines.append(current)
                    current = _Line([])
                    continue
                token = _Token(piece, run.style, font, math.ceil(font.getlength(piece)))
                is_space = piece.isspace()
                if is_space and not current.tokens:
                    continue
                if (
                    options.max_width is not None
                    and token.advance > options.max_width
                    and not is_space
                ):
                    raise invalid(
                        "A word is wider than max_width; increase max_width or reduce font_size."
                    )
                if (
                    options.max_width is not None
                    and current.tokens
                    and current.width + token.advance > options.max_width
                    and not is_space
                ):
                    lines.append(current)
                    current = _Line([])
                if (
                    is_space
                    and options.max_width is not None
                    and current.width + token.advance > options.max_width
                ):
                    continue
                current.append(token)
        if current.tokens or not lines:
            lines.append(current)
        for line in lines:
            if not line.tokens:
                fallback = self._font(options.runs[0].style)
                ascent, descent = fallback.getmetrics()
                line.ascent, line.descent = ascent, descent
        return lines

    @staticmethod
    def _draw_decorations(draw: ImageDraw.ImageDraw, x: int, baseline: int, token: _Token) -> None:
        ascent, descent = token.font.getmetrics()
        thickness = max(1, token.style.font_size // 18)
        if token.style.underline:
            y = baseline + max(1, descent // 2)
            draw.line((x, y, x + token.advance, y), fill=255, width=thickness)
        if token.style.strikethrough:
            y = baseline - round(ascent * 0.32)
            draw.line((x, y, x + token.advance, y), fill=255, width=thickness)

    @staticmethod
    def _composite_fill(
        canvas: Image.Image,
        mask: Image.Image,
        style: RichTextStyle,
        gradient_bounds: tuple[float, float, float, float],
    ) -> None:
        if style.gradient is None:
            assert style.color is not None
            color = _rgba(style.color)
            alpha = mask.point(lambda value: value * color[3] // 255)
            fill = Image.new("RGBA", canvas.size, color[:3] + (0,))
            fill.putalpha(alpha)
        else:
            fill = _linear_gradient(
                canvas.size,
                style.gradient.angle_degrees,
                style.gradient.stops,
                gradient_bounds,
            )
            fill.putalpha(ImageChops.multiply(fill.getchannel("A"), mask))
        canvas.alpha_composite(fill)

    @staticmethod
    def _font(style: RichTextStyle) -> ImageFont.FreeTypeFont:
        for candidate in _font_candidates(style.font_family, style.bold, style.italic):
            try:
                return ImageFont.truetype(candidate, style.font_size)
            except OSError:
                continue
        raise EditorError(
            "DEPENDENCY_UNAVAILABLE",
            f"No installed font is available for the '{style.font_family.value}' family.",
            False,
            ("Install DejaVu fonts or an equivalent system sans, serif, and monospace font.",),
        )


def _font_candidates(family: TextFontFamily, bold: bool, italic: bool) -> tuple[str, ...]:
    suffix = "BoldOblique" if bold and italic else "Bold" if bold else "Oblique" if italic else ""
    windows_suffix = "bi" if bold and italic else "bd" if bold else "i" if italic else ""
    if family is TextFontFamily.SANS:
        base = "DejaVuSans"
        windows = f"arial{windows_suffix}.ttf" if windows_suffix else "arial.ttf"
    elif family is TextFontFamily.SERIF:
        base = "DejaVuSerif"
        windows = f"times{windows_suffix}.ttf" if windows_suffix else "times.ttf"
    else:
        base = "DejaVuSansMono"
        windows = f"consola{'z' if bold and italic else 'b' if bold else 'i' if italic else ''}.ttf"
    filename = f"{base}{('-' + suffix) if suffix else ''}.ttf"
    candidates = [
        filename,
        str(Path("C:/Windows/Fonts") / windows),
        str(Path("/usr/share/fonts/truetype/dejavu") / filename),
        str(Path("/usr/local/share/fonts") / filename),
        str(Path("/Library/Fonts") / filename),
    ]
    usable: list[str] = []
    for candidate in candidates:
        path = Path(candidate)
        if not path.is_absolute() or path.is_file():
            usable.append(candidate)
    return tuple(usable)


def _rgba(value: str) -> tuple[int, int, int, int]:
    hex_value = value.removeprefix("#")
    if len(hex_value) == 6:
        hex_value += "FF"
    red, green, blue, alpha = (
        int(hex_value[index : index + 2], 16) for index in range(0, 8, 2)
    )
    return red, green, blue, alpha


def _linear_gradient(
    size: tuple[int, int],
    angle_degrees: float,
    stops: list[TextGradientStop],
    bounds: tuple[float, float, float, float],
) -> Image.Image:
    typed_stops = [(item.position, _rgba(item.color)) for item in stops]
    width, height = size
    left, top, bounds_width, bounds_height = bounds
    radians = math.radians(angle_degrees)
    direction_x, direction_y = math.cos(radians), math.sin(radians)
    x = np.arange(width, dtype=np.float32)
    y = np.arange(height, dtype=np.float32)
    projection = y[:, None] * direction_y + x[None, :] * direction_x
    bounds_projection = np.array(
        [
            top * direction_y + left * direction_x,
            top * direction_y + (left + bounds_width) * direction_x,
            (top + bounds_height) * direction_y + left * direction_x,
            (top + bounds_height) * direction_y + (left + bounds_width) * direction_x,
        ],
        dtype=np.float32,
    )
    minimum, maximum = float(bounds_projection.min()), float(bounds_projection.max())
    ratio = (projection - minimum) / (maximum - minimum) if maximum > minimum else projection * 0
    positions = np.array([item[0] for item in typed_stops], dtype=np.float32)
    channels = [
        np.interp(ratio, positions, [item[1][channel] for item in typed_stops]).astype(np.uint8)
        for channel in range(4)
    ]
    return Image.fromarray(np.stack(channels, axis=-1), "RGBA")
