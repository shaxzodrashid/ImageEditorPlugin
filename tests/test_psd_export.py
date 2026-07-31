from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from PIL import Image
from psd_tools import PSDImage

from image_editor_plugin.errors import EditorError
from image_editor_plugin.models import ImageFormat, MetadataPolicy
from image_editor_plugin.project import ProjectService
from image_editor_plugin.psd_export import (
    PSD_NATIVE_BACKEND,
    PSD_PORTABLE_BACKEND,
    PsdExporter,
    PsdExportResult,
    PsdLayerSource,
)


class StubPsdExporter:
    def __init__(self) -> None:
        self.layers: list[PsdLayerSource] | None = None

    def export(
        self,
        output: Path,
        width: int,
        height: int,
        canvas_background: str,
        layers: list[PsdLayerSource],
    ) -> PsdExportResult:
        self.layers = layers
        output.write_bytes(b"PSD test export")
        return PsdExportResult(PSD_PORTABLE_BACKEND, "psd-tools-roundtrip")


class FailingPsdExporter:
    def export(
        self,
        output: Path,
        width: int,
        height: int,
        canvas_background: str,
        layers: list[PsdLayerSource],
    ) -> PsdExportResult:
        output.write_bytes(b"partial PSD")
        raise EditorError("EXPORT_FAILED", "portable test failure", False)


def test_forced_portable_export_round_trips_pixel_layer_structure_and_alpha(tmp_path: Path) -> None:
    back = tmp_path / "back.png"
    hidden = tmp_path / "hidden.png"
    Image.new("RGBA", (3, 4), (255, 0, 0, 160)).save(back)
    Image.new("RGBA", (5, 2), (0, 0, 255, 255)).save(hidden)

    output = tmp_path / "layered.psd"
    result = PsdExporter(preference="portable").export(
        output,
        width=20,
        height=10,
        canvas_background="#102030",
        layers=[
            PsdLayerSource(back, "Base artwork", 2, 3, 0.5, True),
            PsdLayerSource(hidden, "Hidden guide", -1, 6, 1.0, False),
        ],
    )

    document = PSDImage.open(output)
    assert result == PsdExportResult(PSD_PORTABLE_BACKEND, "psd-tools-roundtrip")
    assert (document.size, document.depth, document.color_mode, document.channels) == (
        (20, 10),
        8,
        3,
        4,
    )
    assert [layer.name for layer in document] == [
        "Canvas Background",
        "Base artwork",
        "Hidden guide",
    ]
    assert [(layer.left, layer.top) for layer in document] == [(0, 0), (2, 3), (-1, 6)]
    assert [layer.opacity for layer in document] == [255, 127, 255]
    assert [layer.visible for layer in document] == [True, True, False]
    assert document[1].topil().convert("RGBA").getpixel((0, 0)) == (255, 0, 0, 160)


def test_native_probe_or_worker_crash_falls_back_to_portable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.png"
    Image.new("RGBA", (2, 2), (1, 2, 3, 4)).save(source)
    exporter = PsdExporter(preference="native")
    calls: list[str] = []
    original = exporter._run_export_worker

    monkeypatch.setattr(exporter, "_native_probe_succeeds", lambda: True)

    def crash_native(module: str, payload: dict[str, object]) -> bool:
        calls.append(module)
        if module == "image_editor_plugin.native_psd_worker":
            return False  # Models a SIGILL/non-zero isolated child exit.
        return original(module, payload)

    monkeypatch.setattr(exporter, "_run_export_worker", crash_native)
    result = exporter.export(
        tmp_path / "fallback.psd",
        10,
        10,
        "transparent",
        [PsdLayerSource(source, "source", 0, 0, 1.0, True)],
    )

    assert calls == ["image_editor_plugin.native_psd_worker", "image_editor_plugin.psd_worker"]
    assert result == PsdExportResult(
        PSD_PORTABLE_BACKEND, "psd-tools-roundtrip", PSD_NATIVE_BACKEND
    )


def test_native_probe_failure_uses_portable_without_starting_native_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.png"
    Image.new("RGBA", (2, 2), (1, 2, 3, 4)).save(source)
    exporter = PsdExporter(preference="native")
    monkeypatch.setattr(exporter, "_native_probe_succeeds", lambda: False)
    result = exporter.export(
        tmp_path / "probe-fallback.psd",
        10,
        10,
        "transparent",
        [PsdLayerSource(source, "source", 0, 0, 1.0, True)],
    )

    assert result == PsdExportResult(
        PSD_PORTABLE_BACKEND, "psd-tools-roundtrip", PSD_NATIVE_BACKEND
    )


def test_project_psd_export_records_portable_provenance_and_rejects_metadata_preservation(
    service: tuple[ProjectService, str],
) -> None:
    projects, workspace_id = service
    exporter = StubPsdExporter()
    projects.psd_exporter = cast(PsdExporter, exporter)
    projects.create(workspace_id, "deliver.image-work", "Deliver", 100, 50)

    manifest, record = projects.export(
        workspace_id,
        "deliver.image-work",
        "out/final.psd",
        ImageFormat.PSD,
        expected_revision=0,
        overwrite=False,
    )
    assert manifest.revision == 1
    assert record.path == "out/final.psd"
    assert record.parameters["layered"] is True
    assert record.parameters["backend"] == PSD_PORTABLE_BACKEND
    assert record.parameters["validation"] == "psd-tools-roundtrip"
    assert record.parameters["native_fallback_from"] is None
    assert exporter.layers == []

    with pytest.raises(EditorError, match="metadata_policy=strip"):
        projects.export(
            workspace_id,
            "deliver.image-work",
            "out/another.psd",
            ImageFormat.PSD,
            expected_revision=1,
            overwrite=False,
            metadata_policy=MetadataPolicy.PRESERVE_SAFE,
        )
    assert projects.inspect(workspace_id, "deliver.image-work").revision == 1


def test_psd_export_refuses_to_overwrite_existing_delivery(
    service: tuple[ProjectService, str], tmp_path: Path
) -> None:
    projects, workspace_id = service
    projects.create(workspace_id, "no-overwrite.image-work", "No overwrite", 20, 20)
    output = tmp_path / "existing.psd"
    output.write_bytes(b"known-good")

    with pytest.raises(EditorError, match="already exists"):
        projects.export(
            workspace_id,
            "no-overwrite.image-work",
            "existing.psd",
            ImageFormat.PSD,
            expected_revision=0,
            overwrite=False,
        )

    assert output.read_bytes() == b"known-good"
    assert projects.inspect(workspace_id, "no-overwrite.image-work").revision == 0


def test_psd_export_failure_is_atomic_and_does_not_overwrite_existing_delivery(
    service: tuple[ProjectService, str], tmp_path: Path
) -> None:
    projects, workspace_id = service
    projects.psd_exporter = cast(PsdExporter, FailingPsdExporter())
    projects.create(workspace_id, "atomic.image-work", "Atomic", 20, 20)
    output = tmp_path / "existing.psd"
    output.write_bytes(b"known-good")

    with pytest.raises(EditorError, match="portable test failure"):
        projects.export(
            workspace_id,
            "atomic.image-work",
            "existing.psd",
            ImageFormat.PSD,
            expected_revision=0,
            overwrite=True,
        )

    assert output.read_bytes() == b"known-good"
    assert projects.inspect(workspace_id, "atomic.image-work").revision == 0
