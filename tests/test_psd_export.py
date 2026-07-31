from __future__ import annotations

from pathlib import Path
from typing import cast

import photoshopapi as psapi
import pytest
from PIL import Image

from image_editor_plugin.errors import EditorError
from image_editor_plugin.models import ImageFormat, MetadataPolicy
from image_editor_plugin.project import ProjectService
from image_editor_plugin.psd_export import PsdExporter, PsdLayerSource


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
    ) -> None:
        self.layers = layers
        output.write_bytes(b"PSD test export")


def test_psd_exporter_round_trips_pixel_layer_structure(tmp_path: Path) -> None:
    back = tmp_path / "back.png"
    hidden = tmp_path / "hidden.png"
    Image.new("RGBA", (3, 4), (255, 0, 0, 160)).save(back)
    Image.new("RGBA", (5, 2), (0, 0, 255, 255)).save(hidden)

    output = tmp_path / "layered.psd"
    PsdExporter().export(
        output,
        width=20,
        height=10,
        canvas_background="#102030",
        layers=[
            PsdLayerSource(back, "Base artwork", 2, 3, 0.5, True),
            PsdLayerSource(hidden, "Hidden guide", -1, 6, 1.0, False),
        ],
    )

    document = psapi.LayeredFile.read(str(output))
    assert (document.width, document.height) == (20, 10)
    assert document.bit_depth == psapi.enum.BitDepth.bd_8
    assert [layer.name for layer in document.layers] == [
        "Canvas Background",
        "Base artwork",
        "Hidden guide",
    ]
    assert [(layer.center_x, layer.center_y) for layer in document.layers] == [
        (0.0, 0.0),
        (-6.5, 0.0),
        (-8.5, 2.0),
    ]
    assert [int(layer.opacity * 255) for layer in document.layers] == [255, 127, 255]
    assert [layer.is_visible for layer in document.layers] == [True, True, False]


def test_project_psd_export_records_validation_and_rejects_metadata_preservation(
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
    assert record.parameters["validation"] == "photoshopapi-roundtrip"
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
