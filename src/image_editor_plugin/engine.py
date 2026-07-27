from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import (
    MAX_COMPRESSED_INPUT_BYTES,
    MAX_DECODED_PIXELS,
    MAX_DIMENSION,
    OPERATION_TIMEOUT_SECONDS,
)
from .errors import EditorError, invalid
from .models import ResizeFilter

_VERSION = re.compile(r"ImageMagick\s+(\d+\.\d+\.\d+(?:-\d+)?)")


@dataclass(frozen=True, slots=True)
class ImageInfo:
    format: str
    width: int
    height: int
    channels: str
    colorspace: str
    profiles: str
    depth: int

    @property
    def has_alpha(self) -> bool:
        return "a" in self.channels.casefold() or "alpha" in self.channels.casefold()

    @property
    def has_icc_profile(self) -> bool:
        return "icc" in self.profiles.casefold() or "icm" in self.profiles.casefold()


class ImageMagickEngine:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("magick")
        self._version: str | None = None

    def preflight(self) -> dict[str, Any]:
        if not self.executable:
            return {
                "available": False,
                "version": None,
                "delegates": [],
                "missing": [
                    "ImageMagick 7 executable",
                    "PNG delegate",
                    "JPEG delegate",
                    "LCMS delegate",
                ],
                "remediation": _install_remediation(),
            }
        result = self._raw(["-version"])
        text = f"{result.stdout}\n{result.stderr}"
        match = _VERSION.search(text)
        version = match.group(1) if match else "unknown"
        major_ok = bool(match and match.group(1).startswith("7."))
        lowered = text.casefold()
        delegates = [name for name in ("png", "jpeg", "lcms") if name in lowered]
        missing = []
        if not major_ok:
            missing.append("ImageMagick 7")
        missing.extend(
            f"{name.upper()} delegate" for name in ("png", "jpeg", "lcms") if name not in delegates
        )
        self._version = version
        return {
            "available": result.returncode == 0 and not missing,
            "version": version,
            "delegates": delegates,
            "missing": missing,
            "remediation": _install_remediation() if missing else [],
        }

    @property
    def version(self) -> str:
        if self._version is None:
            preflight = self.preflight()
            self._version = str(preflight["version"] or "unavailable")
        return self._version

    def require(self) -> None:
        check = self.preflight()
        if not check["available"]:
            raise EditorError(
                "DEPENDENCY_UNAVAILABLE",
                "ImageMagick 7 with PNG, JPEG, and LCMS support is required.",
                False,
                tuple(check["remediation"]),
            )

    def inspect(self, path: Path) -> ImageInfo:
        self._validate_input(path)
        template = (
            '{"format":"%m","width":%w,"height":%h,"channels":"%[channels]",'
            '"colorspace":"%[colorspace]","profiles":"%[profiles]","depth":%z}'
        )
        result = self.run(["identify", "-quiet", "-format", template, str(path)])
        try:
            raw = json.loads(result.stdout)
            info = ImageInfo(**raw)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise EditorError("DECODE_FAILED", "Image metadata could not be decoded.") from exc
        if info.width > MAX_DIMENSION or info.height > MAX_DIMENSION:
            raise invalid(f"Image dimensions cannot exceed {MAX_DIMENSION} pixels.")
        if info.width * info.height > MAX_DECODED_PIXELS:
            raise invalid("Image exceeds the 100 million decoded-pixel limit.")
        if info.format.upper() not in {"PNG", "JPEG", "JPG"}:
            raise invalid("Only PNG and JPEG images are supported.")
        return info

    def crop(self, source: Path, output: Path, x: int, y: int, width: int, height: int) -> None:
        geometry = f"{width}x{height}+{x}+{y}"
        self.run(
            [
                str(source),
                "-crop",
                geometry,
                "+repage",
                "-colorspace",
                "sRGB",
                "-depth",
                "8",
                str(output),
            ]
        )

    def resize(
        self,
        source: Path,
        output: Path,
        width: int,
        height: int,
        resize_filter: ResizeFilter,
        modifier: str = "!",
    ) -> None:
        args = [
            str(source),
            "-filter",
            resize_filter.value,
            "-resize",
            f"{width}x{height}{modifier}",
        ]
        if modifier == "^":
            args.extend(["-gravity", "center", "-extent", f"{width}x{height}"])
        args.extend(["-colorspace", "sRGB", "-depth", "8", str(output)])
        self.run(args)

    def normalize(self, source: Path, output: Path) -> None:
        self.run([str(source), "-auto-orient", "-colorspace", "sRGB", "-depth", "8", str(output)])

    def render(
        self,
        canvas_width: int,
        canvas_height: int,
        background: str,
        layers: list[tuple[Path, int, int, float]],
        output: Path,
        *,
        preview_max: int | None = None,
        jpeg_quality: int | None = None,
        jpeg_background: str | None = None,
        metadata_strip: bool = True,
    ) -> None:
        color = "none" if background == "transparent" else background
        args = ["-size", f"{canvas_width}x{canvas_height}", f"canvas:{color}"]
        for source, x, y, opacity in layers:
            args.extend(
                [
                    "(",
                    str(source),
                    "-alpha",
                    "on",
                    "-channel",
                    "A",
                    "-evaluate",
                    "multiply",
                    _decimal(opacity),
                    "+channel",
                    ")",
                    "-geometry",
                    f"{x:+d}{y:+d}",
                    "-compose",
                    "over",
                    "-composite",
                ]
            )
        if preview_max is not None:
            args.extend(["-filter", "lanczos", "-resize", f"{preview_max}x{preview_max}>"])
        if jpeg_quality is not None:
            if not jpeg_background:
                raise invalid("JPEG export requires an explicit flattening background.")
            args.extend(
                [
                    "-background",
                    jpeg_background,
                    "-alpha",
                    "remove",
                    "-alpha",
                    "off",
                    "-sampling-factor",
                    "4:2:0",
                    "-quality",
                    str(jpeg_quality),
                ]
            )
        args.extend(["-colorspace", "sRGB", "-depth", "8"])
        if metadata_strip:
            args.append("-strip")
        args.append(str(output))
        self.run(args)

    def run(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        self.require()
        command = [str(self.executable)]
        if arguments and arguments[0] == "identify":
            command.append("identify")
            arguments = arguments[1:]
        command.extend(
            [
            "-limit",
            "memory",
            "1GiB",
            "-limit",
            "map",
            "2GiB",
            "-limit",
            "disk",
            "4GiB",
            "-limit",
            "thread",
            "2",
            *arguments,
            ]
        )
        try:
            result = subprocess.run(
                command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=OPERATION_TIMEOUT_SECONDS,
                check=False,
                env=_safe_environment(),
            )
        except subprocess.TimeoutExpired as exc:
            raise EditorError(
                "OPERATION_TIMEOUT",
                "ImageMagick exceeded the 120-second operation limit.",
                True,
            ) from exc
        if result.returncode != 0:
            raise EditorError(
                "ENGINE_FAILED",
                "ImageMagick could not complete the requested operation.",
                False,
                _engine_remediation(result.stderr),
            )
        return result

    def _raw(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        assert self.executable is not None
        return subprocess.run(
            [self.executable, *arguments],
            shell=False,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            env=_safe_environment(),
        )

    @staticmethod
    def _validate_input(path: Path) -> None:
        if not path.is_file():
            raise EditorError("NOT_FOUND", "The input image does not exist.")
        if path.stat().st_size > MAX_COMPRESSED_INPUT_BYTES:
            raise invalid("Input exceeds the 100 MiB compressed-size limit.")


def _safe_environment() -> dict[str, str]:
    allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "LANG", "LC_ALL"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


def _decimal(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _engine_remediation(stderr: str) -> tuple[str, ...]:
    lowered = stderr.casefold()
    if "no decode delegate" in lowered:
        return (
            "Verify that the input is a valid PNG or JPEG and that its decoder is available.",
            "Run system_preflight to confirm the required ImageMagick delegates.",
        )
    if any(
        marker in lowered
        for marker in ("cache resources exhausted", "memory allocation failed", "disk limit")
    ):
        return (
            "Reduce the image dimensions or compressed input size and retry.",
            "Check the free temporary-disk value returned by system_preflight.",
        )
    if any(
        marker in lowered
        for marker in ("improper image header", "corrupt image", "insufficient image data")
    ):
        return ("Verify that the source file is a complete, valid PNG or JPEG.",)
    return ("Run system_preflight and verify that the input image is valid.",)


def _install_remediation() -> list[str]:
    if os.name == "nt":
        return [
            "Install ImageMagick 7 for Windows with the legacy utilities option disabled.",
            "Ensure magick.exe is on PATH and the build lists png, jpeg, and lcms delegates.",
        ]
    if platform.system() == "Darwin":
        return [
            "Install ImageMagick 7 with Homebrew: brew install imagemagick.",
            "Verify `magick -version` lists png, jpeg, and lcms delegates.",
        ]
    return [
        "Install ImageMagick 7 using your distribution package manager.",
        "Verify `magick -version` lists png, jpeg, and lcms delegates.",
    ]
