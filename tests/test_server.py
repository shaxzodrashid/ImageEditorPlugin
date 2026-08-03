from __future__ import annotations

import asyncio

from image_editor_plugin.server import mcp

EXPECTED_TOOLS = {
    "system_preflight",
    "system_capabilities",
    "ai_model_catalog",
    "image_search",
    "workspace_register",
    "ai_generate_image",
    "ai_edit_image",
    "ai_continue_edit",
    "ai_decompose_layers",
    "project_create",
    "project_inspect",
    "project_validate",
    "asset_import",
    "image_inspect",
    "object_select",
    "background_remove",
    "layer_add",
    "text_layer_create",
    "transform_crop",
    "transform_resize",
    "transform_position",
    "composite_overlay",
    "image_render_preview",
    "poster_safe_zone_check",
    "export_png",
    "export_jpeg",
    "export_psd",
}


def test_public_tool_catalog_is_complete() -> None:
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == EXPECTED_TOOLS
