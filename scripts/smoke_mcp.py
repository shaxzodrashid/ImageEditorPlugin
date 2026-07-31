from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED = {
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


async def smoke() -> None:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    parameters = StdioServerParameters(
        command="uv",
        args=["run", "--project", ".", "image-editor-mcp"],
        cwd=str(root),
    )
    async with (
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        catalog = await session.list_tools()
        names = {tool.name for tool in catalog.tools}
        if names != EXPECTED:
            raise RuntimeError(f"Unexpected MCP catalog: {sorted(names)}")
        result = await session.call_tool("system_preflight", {})
        if result.isError:
            raise RuntimeError("system_preflight returned an MCP protocol error")
        print(f"MCP stdio smoke passed with {len(names)} tools.")


def main() -> None:
    asyncio.run(smoke())


if __name__ == "__main__":
    main()
