from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from conftest import FakeEngine

from image_editor_plugin.errors import EditorError
from image_editor_plugin.models import (
    AspectPolicy,
    ContentPolicy,
    ImageFormat,
    MetadataPolicy,
    ResizeFilter,
    RichTextLayerOptions,
    TransformTarget,
)
from image_editor_plugin.project import ProjectService


def write_image(path: Path, dimensions: str = "20x10;icc") -> str:
    path.write_text(dimensions, encoding="ascii")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_project_survives_restart_and_conflicts_preserve_revision(
    tmp_path: Path, service: tuple[ProjectService, str]
) -> None:
    projects, workspace_id = service
    created = projects.create(workspace_id, "demo.image-work", "Demo", 100, 50)
    assert created.revision == 0

    restarted = ProjectService(projects.registry, projects.engine)
    loaded = restarted.inspect(workspace_id, "demo.image-work")
    assert loaded.project_id == created.project_id

    with pytest.raises(EditorError) as caught:
        restarted.add_layer(workspace_id, "demo.image-work", "ast_missing", "Nope", 0, 0, 1, 9)
    assert caught.value.code == "CONFLICT"
    assert restarted.inspect(workspace_id, "demo.image-work").revision == 0


def test_import_is_immutable_and_deduplicated(
    tmp_path: Path, service: tuple[ProjectService, str]
) -> None:
    projects, workspace_id = service
    projects.create(workspace_id, "demo.image-work", "Demo", 100, 50)
    source = tmp_path / "source.png"
    source_hash = write_image(source)

    manifest, asset, operation, warnings = projects.import_asset(
        workspace_id, "demo.image-work", "source.png", 0
    )
    assert operation is not None
    assert manifest.revision == 1
    assert asset.sha256 == source_hash
    assert not warnings
    assert source.read_text(encoding="ascii") == "20x10;icc"

    same_manifest, same_asset, same_operation, same_warnings = projects.import_asset(
        workspace_id, "demo.image-work", "source.png", 1
    )
    assert same_manifest.revision == 1
    assert same_asset.id == asset.id
    assert same_operation is None
    assert same_warnings


def test_layer_order_crop_resize_and_document_positioning(
    tmp_path: Path, service: tuple[ProjectService, str]
) -> None:
    projects, workspace_id = service
    projects.create(workspace_id, "layout.image-work", "Layout", 100, 50)
    write_image(tmp_path / "one.png", "20x10;icc")
    write_image(tmp_path / "two.png", "10x10")
    manifest, one, _, _ = projects.import_asset(workspace_id, "layout.image-work", "one.png", 0)
    manifest, two, _, warnings = projects.import_asset(
        workspace_id, "layout.image-work", "two.png", manifest.revision
    )
    assert warnings == ["RGB input has no ICC profile; sRGB was assumed."]
    manifest, bottom, _ = projects.add_layer(
        workspace_id, "layout.image-work", one.id, "Bottom", 4, 6, 1, manifest.revision
    )
    manifest, top, _ = projects.add_layer(
        workspace_id, "layout.image-work", two.id, "Top", 8, 9, 0.5, manifest.revision
    )
    assert [layer.name for layer in manifest.layers] == ["Bottom", "Top"]

    manifest, _, cropped = projects.crop(
        workspace_id,
        "layout.image-work",
        TransformTarget.LAYER,
        top.id,
        1,
        1,
        5,
        5,
        manifest.revision,
    )
    assert cropped is not None and cropped.width == 5
    manifest, _, resized = projects.resize(
        workspace_id,
        "layout.image-work",
        TransformTarget.LAYER,
        bottom.id,
        40,
        20,
        ResizeFilter.LANCZOS,
        AspectPolicy.EXACT,
        None,
        manifest.revision,
    )
    assert resized[0].width == 40
    manifest, _, _ = projects.crop(
        workspace_id,
        "layout.image-work",
        TransformTarget.DOCUMENT,
        None,
        2,
        3,
        80,
        40,
        manifest.revision,
    )
    assert manifest.canvas.width == 80
    assert manifest.layers[0].x == 2
    assert manifest.layers[0].y == 3

    manifest, _, scaled = projects.resize(
        workspace_id,
        "layout.image-work",
        TransformTarget.DOCUMENT,
        None,
        160,
        80,
        ResizeFilter.MITCHELL,
        AspectPolicy.EXACT,
        ContentPolicy.SCALE_ALL,
        manifest.revision,
    )
    assert len(scaled) == 2
    assert manifest.layers[0].x == 4
    assert manifest.canvas.width == 160


def test_failed_derived_operation_keeps_prior_manifest(
    tmp_path: Path,
    service: tuple[ProjectService, str],
    engine: FakeEngine,
) -> None:
    projects, workspace_id = service
    projects.create(workspace_id, "safe.image-work", "Safe", 100, 50)
    write_image(tmp_path / "source.png")
    manifest, asset, _, _ = projects.import_asset(workspace_id, "safe.image-work", "source.png", 0)
    manifest, layer, _ = projects.add_layer(
        workspace_id, "safe.image-work", asset.id, "Layer", 0, 0, 1, manifest.revision
    )
    before = manifest.revision
    engine.fail_next = True
    with pytest.raises(RuntimeError, match="forced"):
        projects.crop(
            workspace_id,
            "safe.image-work",
            TransformTarget.LAYER,
            layer.id,
            0,
            0,
            5,
            5,
            before,
        )
    assert projects.inspect(workspace_id, "safe.image-work").revision == before


def test_rich_text_creates_a_transparent_positionable_pixel_layer(
    service: tuple[ProjectService, str],
) -> None:
    projects, workspace_id = service
    projects.create(workspace_id, "text.image-work", "Text", 1080, 1350)
    text = RichTextLayerOptions.model_validate(
        {
            "runs": [
                {"text": "Summer ", "style": {"font_size": 72, "color": "#111827"}},
                {
                    "text": "Sale",
                    "style": {
                        "font_size": 72,
                        "bold": True,
                        "underline": True,
                        "gradient": {
                            "angle_degrees": 0,
                            "stops": [
                                {"position": 0, "color": "#EC4899"},
                                {"position": 1, "color": "#8B5CF6"},
                            ],
                        },
                    },
                },
            ],
            "padding": 4,
        }
    )

    manifest, asset, layer, operation = projects.create_text_layer(
        workspace_id,
        "text.image-work",
        "Summer sale title",
        text,
        80,
        120,
        0.75,
        0,
    )

    assert manifest.revision == 1
    assert asset.kind.value == "derived"
    assert asset.format.value == "PNG"
    assert asset.has_alpha is True
    assert asset.width > 100 and asset.height > 60
    assert layer.asset_id == asset.id
    assert (layer.x, layer.y, layer.opacity) == (80, 120, 0.75)
    assert operation.type == "text_layer_create"
    assert projects.validate(workspace_id, "text.image-work")["valid"] is True


def test_preview_and_exports_record_checksums(
    tmp_path: Path, service: tuple[ProjectService, str]
) -> None:
    projects, workspace_id = service
    projects.create(workspace_id, "deliver.image-work", "Deliver", 100, 50)
    manifest, preview, checksum = projects.render_preview(workspace_id, "deliver.image-work", 800)
    assert manifest.revision == 0
    assert preview.is_file() and len(checksum) == 64

    manifest, png = projects.export(
        workspace_id,
        "deliver.image-work",
        "out/final.png",
        image_format=ImageFormat.PNG,
        expected_revision=0,
        overwrite=False,
        metadata_policy=MetadataPolicy.STRIP,
    )
    assert manifest.revision == 1
    assert png.path == "out/final.png"
    with pytest.raises(EditorError) as output_conflict:
        projects.export(
            workspace_id,
            "deliver.image-work",
            "out/final.png",
            image_format=ImageFormat.PNG,
            expected_revision=1,
            overwrite=False,
        )
    assert output_conflict.value.code == "CONFLICT"
    assert projects.inspect(workspace_id, "deliver.image-work").revision == 1

    with pytest.raises(EditorError, match="Background"):
        projects.export(
            workspace_id,
            "deliver.image-work",
            "out/final.jpg",
            image_format=ImageFormat.JPEG,
            expected_revision=1,
            overwrite=False,
            quality=90,
            background="transparent",
        )
    assert projects.inspect(workspace_id, "deliver.image-work").revision == 1

    manifest, jpeg = projects.export(
        workspace_id,
        "deliver.image-work",
        "out/final.jpg",
        image_format=ImageFormat.JPEG,
        expected_revision=1,
        overwrite=False,
        quality=90,
        background="#ffffff",
    )
    assert manifest.revision == 2
    assert jpeg.parameters["chroma_subsampling"] == "4:2:0"


def test_safe_zone_check_renders_overlay_and_reports_critical_layer_overflow(
    tmp_path: Path,
    service: tuple[ProjectService, str],
    engine: FakeEngine,
) -> None:
    projects, workspace_id = service
    projects.create(workspace_id, "poster.image-work", "Poster", 100, 100)
    write_image(tmp_path / "critical.png", "20x10;icc")
    manifest, asset, _, _ = projects.import_asset(
        workspace_id, "poster.image-work", "critical.png", 0
    )
    manifest, inside, _ = projects.add_layer(
        workspace_id,
        "poster.image-work",
        asset.id,
        "Inside title",
        20,
        20,
        1,
        manifest.revision,
    )
    manifest, outside, _ = projects.add_layer(
        workspace_id,
        "poster.image-work",
        asset.id,
        "Unsafe CTA",
        75,
        85,
        1,
        manifest.revision,
    )

    checked, preview, checksum, result = projects.check_safe_zone(
        workspace_id,
        "poster.image-work",
        800,
        margin_pixels=10,
        critical_layer_ids=[inside.id, outside.id],
    )

    assert checked.revision == manifest.revision
    assert projects.inspect(workspace_id, "poster.image-work").revision == manifest.revision
    assert preview.name == f"safe-zone-r{manifest.revision}-t10-r10-b10-l10.png"
    assert preview.is_file() and len(checksum) == 64
    assert engine.last_render_kwargs == {
        "preview_max": 800,
        "safe_zone_margins": (10, 10, 10, 10),
    }
    assert result["status"] == "fail"
    assert result["geometry_passed"] is False
    assert result["safe_zone"]["bounds"] == {"x": 10, "y": 10, "width": 80, "height": 80}
    assert result["critical_layers_checked"][0]["inside_safe_zone"] is True
    assert result["violations"] == [
        {
            "layer_id": outside.id,
            "name": "Unsafe CTA",
            "asset_id": asset.id,
            "bounds": {"x": 75, "y": 85, "width": 20, "height": 10},
            "inside_safe_zone": False,
            "overflow_pixels": {"left": 0, "top": 0, "right": 5, "bottom": 5},
        }
    ]
    assert result["visual_review_required"] is True


def test_safe_zone_check_scales_template_inset_and_requires_a_valid_inner_area(
    service: tuple[ProjectService, str],
) -> None:
    projects, workspace_id = service
    projects.create(workspace_id, "portrait.image-work", "Portrait", 1080, 1350)

    _, _, _, result = projects.check_safe_zone(workspace_id, "portrait.image-work", 1600)

    assert result["status"] == "review_required"
    assert result["safe_zone"]["margins"] == {
        "top": 64,
        "right": 65,
        "bottom": 70,
        "left": 65,
    }
    assert result["safe_zone"]["bounds"] == {
        "x": 65,
        "y": 64,
        "width": 950,
        "height": 1216,
    }
    assert result["safe_zone"]["margin_source"] == "scaled_reference_template"

    with pytest.raises(EditorError, match="non-empty inner area"):
        projects.check_safe_zone(
            workspace_id,
            "portrait.image-work",
            1600,
            margin_pixels=540,
        )
