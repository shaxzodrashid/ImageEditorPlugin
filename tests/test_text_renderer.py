from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image
from psd_tools import PSDImage

from image_editor_plugin.engine import ImageMagickEngine
from image_editor_plugin.models import ImageFormat, MetadataPolicy, RichTextLayerOptions
from image_editor_plugin.project import ProjectService
from image_editor_plugin.security import WorkspaceRegistry
from image_editor_plugin.text_renderer import RichTextRenderer


def test_renderer_preserves_transparency_and_applies_per_run_gradient(tmp_path: Path) -> None:
    output = tmp_path / "title.png"
    options = RichTextLayerOptions.model_validate(
        {
            "runs": [
                {"text": "New ", "style": {"font_size": 60, "color": "#000000"}},
                {
                    "text": "Now",
                    "style": {
                        "font_size": 60,
                        "bold": True,
                        "italic": True,
                        "underline": True,
                        "strikethrough": True,
                        "gradient": {
                            "stops": [
                                {"position": 0, "color": "#FF0000"},
                                {"position": 1, "color": "#0000FF"},
                            ]
                        },
                    },
                },
            ]
        }
    )

    result = RichTextRenderer().render(options, output)

    image = Image.open(output).convert("RGBA")
    assert image.size == (result.width, result.height)
    assert image.getpixel((0, 0))[3] == 0
    colors = [
        (red, green, blue)
        for red, green, blue, alpha in image.get_flattened_data()
        if alpha > 200 and max(red, blue) > 20 and red != blue
    ]
    red_values = [red for red, _, _ in colors]
    blue_values = [blue for _, _, blue in colors]
    assert max(red_values) - min(red_values) > 60
    assert max(blue_values) - min(blue_values) > 60


@pytest.mark.integration
def test_text_layer_positions_in_png_jpeg_and_psd_exports(tmp_path: Path) -> None:
    executable = shutil.which("magick")
    if executable is None:
        pytest.skip("ImageMagick 7 is not installed")
    registry = WorkspaceRegistry()
    workspace_id, _ = registry.register(str(tmp_path))
    projects = ProjectService(registry, ImageMagickEngine(executable))
    projects.create(workspace_id, "deliver.image-work", "Deliver", 400, 240, "#FFFFFF")
    text = RichTextLayerOptions.model_validate(
        {
            "runs": [
                {
                    "text": "Gradient",
                    "style": {
                        "font_size": 48,
                        "gradient": {
                            "stops": [
                                {"position": 0, "color": "#F43F5E"},
                                {"position": 1, "color": "#4F46E5"},
                            ]
                        },
                    },
                }
            ]
        }
    )
    manifest, _, layer, _ = projects.create_text_layer(
        workspace_id, "deliver.image-work", "Gradient title", text, 33, 44, 1.0, 0
    )
    manifest, png = projects.export(
        workspace_id,
        "deliver.image-work",
        "title.png",
        ImageFormat.PNG,
        expected_revision=manifest.revision,
        overwrite=False,
        metadata_policy=MetadataPolicy.STRIP,
    )
    manifest, jpeg = projects.export(
        workspace_id,
        "deliver.image-work",
        "title.jpg",
        ImageFormat.JPEG,
        expected_revision=manifest.revision,
        overwrite=False,
        quality=90,
        background="#FFFFFF",
    )
    _, psd = projects.export(
        workspace_id,
        "deliver.image-work",
        "title.psd",
        ImageFormat.PSD,
        expected_revision=manifest.revision,
        overwrite=False,
    )

    assert (tmp_path / png.path).is_file()
    assert (tmp_path / jpeg.path).is_file()
    document = PSDImage.open(tmp_path / psd.path)
    text_layer = next(item for item in document if item.name == layer.name)
    assert (text_layer.left, text_layer.top) == (33, 44)
