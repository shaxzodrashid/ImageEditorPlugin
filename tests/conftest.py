from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from image_editor_plugin.engine import ImageInfo, ImageMagickEngine
from image_editor_plugin.project import ProjectService
from image_editor_plugin.security import WorkspaceRegistry


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self, prefix: str) -> str:
        self.value += 1
        return f"{prefix}_{UUID(int=self.value)}"


class FakeEngine(ImageMagickEngine):
    def __init__(self) -> None:
        super().__init__("fake-magick")
        self._version = "7.1.1-test"
        self.fail_next = False
        self.fail_apply = False
        self.edge_colors = [(255, 255, 255)] * 256
        self.selection_coverage = 0.5

    def preflight(self) -> dict[str, object]:
        return {
            "available": True,
            "version": self.version,
            "delegates": ["png", "jpeg", "lcms"],
            "missing": [],
            "remediation": [],
        }

    def inspect(self, path: Path) -> ImageInfo:
        data = path.read_bytes().decode("ascii")
        dimensions, *flags = data.split(";")
        width, height = (int(value) for value in dimensions.split("x"))
        is_jpeg = path.suffix.casefold() in {".jpg", ".jpeg"}
        return ImageInfo(
            format="JPEG" if is_jpeg else "PNG",
            width=width,
            height=height,
            channels="srgb" if is_jpeg else "srgba",
            colorspace="sRGB",
            profiles="icc" if "icc" in flags else "",
            depth=8,
        )

    def crop(self, source: Path, output: Path, x: int, y: int, width: int, height: int) -> None:
        self._maybe_fail()
        output.write_text(f"{width}x{height};icc", encoding="ascii")

    def resize(
        self,
        source: Path,
        output: Path,
        width: int,
        height: int,
        resize_filter: object,
        modifier: str = "!",
    ) -> None:
        self._maybe_fail()
        output.write_text(f"{width}x{height};icc", encoding="ascii")

    def normalize(self, source: Path, output: Path) -> None:
        self._maybe_fail()
        info = self.inspect(source)
        output.write_text(f"{info.width}x{info.height};icc", encoding="ascii")

    def pixel_colors(
        self, source: Path, coordinates: list[tuple[int, int]]
    ) -> list[tuple[int, int, int]]:
        return self.edge_colors[: len(coordinates)]

    def selection_mask_border(
        self,
        source: Path,
        output: Path,
        background_rgb: tuple[int, int, int],
        tolerance_percent: float,
        feather_radius: float,
    ) -> None:
        self._maybe_fail()
        info = self.inspect(source)
        output.write_text(f"{info.width}x{info.height}", encoding="ascii")

    def refine_selection_mask(
        self, source: Path, output: Path, feather_radius: float
    ) -> None:
        self._maybe_fail()
        info = self.inspect(source)
        output.write_text(f"{info.width}x{info.height}", encoding="ascii")

    def selection_metrics(self, mask: Path) -> tuple[float, tuple[int, int, int, int]]:
        info = self.inspect(mask)
        return self.selection_coverage, (1, 1, info.width - 2, info.height - 2)

    def apply_selection_mask(self, source: Path, mask: Path, output: Path) -> None:
        if self.fail_apply:
            self.fail_apply = False
            raise RuntimeError("forced mask application failure")
        self._maybe_fail()
        info = self.inspect(source)
        output.write_text(f"{info.width}x{info.height};icc", encoding="ascii")

    def render(
        self,
        canvas_width: int,
        canvas_height: int,
        background: str,
        layers: list[tuple[Path, int, int, float]],
        output: Path,
        **kwargs: object,
    ) -> None:
        self._maybe_fail()
        output.write_text(f"{canvas_width}x{canvas_height};icc", encoding="ascii")

    def _maybe_fail(self) -> None:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("forced test failure")


@pytest.fixture
def ids() -> SequenceIds:
    return SequenceIds()


@pytest.fixture
def engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def service(tmp_path: Path, ids: SequenceIds, engine: FakeEngine) -> tuple[ProjectService, str]:
    registry = WorkspaceRegistry(ids)
    workspace_id, _ = registry.register(str(tmp_path))

    def fixed_time() -> datetime:
        return datetime(2026, 7, 24, tzinfo=UTC)

    return ProjectService(registry, engine, ids, fixed_time), workspace_id
