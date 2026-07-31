from __future__ import annotations

import os
import platform
import shutil
import sys
import tempfile
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .ai_service import AICommit, AIService
from .constants import (
    BACKGROUND_MIN_FREE_DISK_BYTES,
    BACKGROUND_MIN_FREE_MEMORY_BYTES,
    BACKGROUND_MODEL_ID,
    BACKGROUND_MODEL_SHA256,
    BACKGROUND_OPERATION_TIMEOUT_SECONDS,
    DEFAULT_IMAGE_SEARCH_MODEL,
    MAX_ASSETS,
    MAX_COMPRESSED_INPUT_BYTES,
    MAX_DECODED_PIXELS,
    MAX_DIMENSION,
    MAX_IMAGE_SEARCH_DOMAINS,
    MAX_IMAGE_SEARCH_RESULTS,
    MAX_LAYERS,
    OPERATION_TIMEOUT_SECONDS,
    PLUGIN_VERSION,
    SCHEMA_VERSION,
)
from .engine import ImageMagickEngine
from .envelopes import run_enveloped
from .image_search import OpenAIImageSearchService
from .models import (
    AIImageOptions,
    AIModelId,
    AIProviderId,
    AspectPolicy,
    ContentPolicy,
    ExecutionPolicy,
    ImageFormat,
    ImageSearchOptions,
    LayerDecompositionOptions,
    MetadataPolicy,
    ResizeFilter,
    SelectionMethod,
    TransformTarget,
)
from .project import ProjectService
from .providers import ProviderRegistry
from .providers.http import HttpProviderClient
from .psd_export import PSD_COMPATIBILITY_WARNING
from .security import WorkspaceRegistry, relative_to_root

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
OPEN_WORLD_READ = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
EXPORT_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False)
AI_WRITE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=True,
)

mcp = FastMCP(
    "image-editor",
    instructions=(
        "Register one workspace, inspect assets and projects before editing, prefer deterministic "
        "tools for exact changes, select AI models through ai_model_catalog, use image_search for "
        "source-attributed web visuals, use expected_revision "
        "for every mutation, preview and validate before export, never expose provider "
        "credentials, and never infer overwrite consent."
    ),
)
registry = WorkspaceRegistry()
engine = ImageMagickEngine()
projects = ProjectService(registry, engine)
provider_http = HttpProviderClient()
providers = ProviderRegistry.default(provider_http)
ai = AIService(projects, providers)
image_search_service = OpenAIImageSearchService(provider_http)


@mcp.tool(annotations=READ_ONLY)
def system_preflight() -> dict[str, Any]:
    """Report current image engine, local selection runtime, and provider health."""

    def action() -> dict[str, Any]:
        temporary = tempfile.gettempdir()
        disk = shutil.disk_usage(temporary)
        return {
            "outputs": {
                "plugin_version": PLUGIN_VERSION,
                "schema_version": SCHEMA_VERSION,
                "python": {
                    "version": platform.python_version(),
                    "supported": sys.version_info >= (3, 12),
                },
                "platform": {
                    "operating_system": platform.system(),
                    "release": platform.release(),
                    "architecture": platform.machine(),
                },
                "temporary_directory": {
                    "path": temporary,
                    "writable": os.access(temporary, os.W_OK),
                    "free_bytes": disk.free,
                },
                "imagemagick": engine.preflight(),
                "background_removal": projects.background_runtime.preflight(),
                "ai_providers": {
                    "configured": providers.credential_status(),
                    "note": (
                        "Only credential presence is reported. Secret values are never read into "
                        "tool output, project data, or diagnostics."
                    ),
                },
            }
        }

    return run_enveloped(action)


@mcp.tool(annotations=READ_ONLY)
def system_capabilities() -> dict[str, Any]:
    """Return implemented deterministic/AI operations and hard resource limits."""
    return run_enveloped(
        lambda: {
            "outputs": {
                "inputs": ["PNG", "JPEG"],
                "outputs": ["PNG", "JPEG", "PSD"],
                "operations": [
                    "inspect",
                    "crop",
                    "resize",
                    "position",
                    "normal alpha composite",
                    "local object selection",
                    "local background removal",
                    "preview",
                    "validate",
                    "export",
                    "layered PSD export",
                    "poster safe-zone validation",
                    "AI image generation",
                    "conversational AI image editing",
                    "masked AI editing where supported",
                    "Qwen semantic layer decomposition",
                    "OpenAI web-grounded image search",
                ],
                "deferred": [
                    "PSB",
                    "editable per-layer masks",
                    "groups",
                    "filters",
                    "undo/redo",
                    "asynchronous jobs",
                ],
                "background_removal": {
                    "local_only": True,
                    "methods": [item.value for item in SelectionMethod],
                    "execution_policies": [item.value for item in ExecutionPolicy],
                    "model": {
                        "id": BACKGROUND_MODEL_ID,
                        "sha256": BACKGROUND_MODEL_SHA256,
                    },
                    "editable_per_layer_masks": False,
                },
                "limits": {
                    "compressed_input_bytes": MAX_COMPRESSED_INPUT_BYTES,
                    "decoded_pixels": MAX_DECODED_PIXELS,
                    "maximum_dimension": MAX_DIMENSION,
                    "layers": MAX_LAYERS,
                    "assets": MAX_ASSETS,
                    "memory_bytes": 1024**3,
                    "map_bytes": 2 * 1024**3,
                    "temporary_disk_bytes": 4 * 1024**3,
                    "threads": 2,
                    "timeout_seconds": OPERATION_TIMEOUT_SECONDS,
                    "background_attempt_timeout_seconds": (BACKGROUND_OPERATION_TIMEOUT_SECONDS),
                    "background_minimum_memory_bytes": BACKGROUND_MIN_FREE_MEMORY_BYTES,
                    "background_minimum_temporary_disk_bytes": (BACKGROUND_MIN_FREE_DISK_BYTES),
                    "image_search_results": MAX_IMAGE_SEARCH_RESULTS,
                    "image_search_domains": MAX_IMAGE_SEARCH_DOMAINS,
                },
            }
        }
    )


@mcp.tool(annotations=READ_ONLY)
def ai_model_catalog() -> dict[str, Any]:
    """List supported providers, model IDs, credentials, and hard capability gates."""
    return run_enveloped(
        lambda: {
            "outputs": {
                "models": providers.public_catalog(),
                "configured": providers.credential_status(),
                "image_search": {
                    "provider": "openai",
                    "default_model": DEFAULT_IMAGE_SEARCH_MODEL,
                    "agent_selectable_model": True,
                    "requirement": (
                        "Choose a Responses model that supports web_search image results."
                    ),
                    "credential": "OPENAI_API_KEY",
                },
            }
        }
    )


@mcp.tool(annotations=OPEN_WORLD_READ)
def image_search(
    query: str,
    options: ImageSearchOptions | None = None,
) -> dict[str, Any]:
    """Search the live web for source-attributed images with OpenAI Image Search."""

    def action() -> dict[str, Any]:
        result = image_search_service.search(query, options or ImageSearchOptions())
        return {
            "outputs": {
                "query": query.strip(),
                "model": result.model,
                "provider_request_id": result.request_id,
                "result_count": len(result.results),
                "results": result.results,
                "summary": result.summary,
                "citations": result.citations,
                "usage_note": (
                    "Review each source page and applicable license before downloading, "
                    "editing, or publishing a result."
                ),
            },
            "warnings": list(result.warnings),
        }

    return run_enveloped(action)


@mcp.tool(annotations=WRITE)
def workspace_register(root: str) -> dict[str, Any]:
    """Authorize one existing non-root filesystem directory for this MCP session."""

    def action() -> dict[str, Any]:
        workspace_id, path = registry.register(root)
        return {"outputs": {"workspace_id": workspace_id, "root": str(path)}}

    return run_enveloped(action)


@mcp.tool(annotations=AI_WRITE)
def ai_generate_image(
    workspace_id: str,
    project_path: str,
    provider: AIProviderId,
    prompt: str,
    expected_revision: int,
    model: AIModelId | None = None,
    options: AIImageOptions | None = None,
    add_as_layers: bool = False,
) -> dict[str, Any]:
    """Generate image candidates, preserve provenance, and start an edit conversation."""

    def action() -> dict[str, Any]:
        result = ai.generate(
            workspace_id,
            project_path,
            provider,
            model,
            prompt,
            expected_revision,
            options or AIImageOptions(),
            add_as_layers=add_as_layers,
        )
        return _ai_envelope(result)

    return run_enveloped(action)


@mcp.tool(annotations=AI_WRITE)
def ai_edit_image(
    workspace_id: str,
    project_path: str,
    provider: AIProviderId,
    prompt: str,
    input_asset_ids: list[str],
    expected_revision: int,
    model: AIModelId | None = None,
    options: AIImageOptions | None = None,
    mask_asset_id: str | None = None,
    add_as_layers: bool = False,
) -> dict[str, Any]:
    """Semantically edit project assets and start a provider-aware conversation."""

    def action() -> dict[str, Any]:
        result = ai.edit(
            workspace_id,
            project_path,
            provider,
            model,
            prompt,
            input_asset_ids,
            expected_revision,
            options or AIImageOptions(),
            mask_asset_id=mask_asset_id,
            add_as_layers=add_as_layers,
        )
        return _ai_envelope(result)

    return run_enveloped(action)


@mcp.tool(annotations=AI_WRITE)
def ai_continue_edit(
    workspace_id: str,
    project_path: str,
    conversation_id: str,
    prompt: str,
    expected_revision: int,
    options: AIImageOptions | None = None,
    add_as_layers: bool = False,
) -> dict[str, Any]:
    """Continue an AI edit using native provider state or the latest immutable result."""

    def action() -> dict[str, Any]:
        result = ai.continue_edit(
            workspace_id,
            project_path,
            conversation_id,
            prompt,
            expected_revision,
            options or AIImageOptions(),
            add_as_layers=add_as_layers,
        )
        return _ai_envelope(result)

    return run_enveloped(action)


@mcp.tool(annotations=AI_WRITE)
def ai_decompose_layers(
    workspace_id: str,
    project_path: str,
    source_asset_id: str,
    expected_revision: int,
    options: LayerDecompositionOptions | None = None,
) -> dict[str, Any]:
    """Decompose one image into semantically ordered RGBA layers with Qwen Image Layered."""

    def action() -> dict[str, Any]:
        result = ai.decompose_layers(
            workspace_id,
            project_path,
            source_asset_id,
            expected_revision,
            options or LayerDecompositionOptions(),
        )
        return _ai_envelope(result)

    return run_enveloped(action)


@mcp.tool(annotations=WRITE)
def project_create(
    workspace_id: str,
    project_path: str,
    name: str,
    width: int,
    height: int,
    background: str = "transparent",
) -> dict[str, Any]:
    """Create a new revision-zero project at a workspace-relative .image-work path."""

    def action() -> dict[str, Any]:
        manifest = projects.create(workspace_id, project_path, name, width, height, background)
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "outputs": {"project_path": project_path, "manifest": manifest},
        }

    return run_enveloped(action)


@mcp.tool(annotations=READ_ONLY)
def project_inspect(workspace_id: str, project_path: str) -> dict[str, Any]:
    """Read the complete validated project manifest without modifying it."""

    def action() -> dict[str, Any]:
        manifest = projects.inspect(workspace_id, project_path)
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "outputs": {"manifest": manifest},
        }

    return run_enveloped(action)


@mcp.tool(annotations=READ_ONLY)
def project_validate(workspace_id: str, project_path: str) -> dict[str, Any]:
    """Validate manifest structure, references, asset paths, and checksums."""

    def action() -> dict[str, Any]:
        result = projects.validate(workspace_id, project_path)
        manifest = result.pop("manifest")
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "outputs": result,
        }

    return run_enveloped(action)


@mcp.tool(annotations=WRITE)
def asset_import(
    workspace_id: str,
    project_path: str,
    source_path: str,
    expected_revision: int,
) -> dict[str, Any]:
    """Copy a PNG/JPEG into the immutable content-addressed project store."""

    def action() -> dict[str, Any]:
        manifest, asset, operation, warnings = projects.import_asset(
            workspace_id, project_path, source_path, expected_revision
        )
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "operation_id": operation.id if operation else None,
            "outputs": {"asset": asset},
            "warnings": warnings,
        }

    return run_enveloped(action)


@mcp.tool(annotations=READ_ONLY)
def image_inspect(workspace_id: str, project_path: str, asset_id: str) -> dict[str, Any]:
    """Read stored dimensions, alpha, color, checksum, and provenance for one asset."""

    def action() -> dict[str, Any]:
        manifest, asset = projects.image_inspect(workspace_id, project_path, asset_id)
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "outputs": {"asset": asset},
            "warnings": asset.warnings,
        }

    return run_enveloped(action)


@mcp.tool(annotations=WRITE)
def object_select(
    workspace_id: str,
    project_path: str,
    source_asset_id: str,
    expected_revision: int,
    method: SelectionMethod = SelectionMethod.AUTO,
    execution_policy: ExecutionPolicy = ExecutionPolicy.AUTO,
    background_color: str | None = None,
    tolerance_percent: float = 6,
    feather_radius: float = 1,
) -> dict[str, Any]:
    """Create an immutable local-only foreground selection and grayscale mask."""

    def action() -> dict[str, Any]:
        result = projects.object_select(
            workspace_id,
            project_path,
            source_asset_id,
            expected_revision,
            method,
            execution_policy,
            background_color,
            tolerance_percent,
            feather_radius,
        )
        return {
            "project_id": result.manifest.project_id,
            "revision": result.manifest.revision,
            "operation_id": result.operation.id,
            "outputs": {
                "selection": result.selection,
                "mask_asset": result.mask_asset,
                "operation": result.operation,
                "local_inference": True,
            },
            "warnings": result.warnings,
        }

    return run_enveloped(action)


@mcp.tool(annotations=WRITE)
def background_remove(
    workspace_id: str,
    project_path: str,
    source_asset_id: str,
    expected_revision: int,
    selection_id: str | None = None,
    method: SelectionMethod = SelectionMethod.AUTO,
    execution_policy: ExecutionPolicy = ExecutionPolicy.AUTO,
    background_color: str | None = None,
    tolerance_percent: float = 6,
    feather_radius: float = 1,
    add_as_layer: bool = False,
) -> dict[str, Any]:
    """Remove an image background locally using a new or existing selection."""

    def action() -> dict[str, Any]:
        result = projects.background_remove(
            workspace_id,
            project_path,
            source_asset_id,
            expected_revision,
            selection_id,
            method,
            execution_policy,
            background_color,
            tolerance_percent,
            feather_radius,
            add_as_layer,
        )
        return {
            "project_id": result.manifest.project_id,
            "revision": result.manifest.revision,
            "operation_id": result.operation.id,
            "outputs": {
                "selection": result.selection,
                "mask_asset": result.mask_asset,
                "cutout_asset": result.cutout_asset,
                "layer": result.layer,
                "operation": result.operation,
                "local_inference": True,
            },
            "warnings": result.warnings,
        }

    return run_enveloped(action)


@mcp.tool(annotations=WRITE)
def layer_add(
    workspace_id: str,
    project_path: str,
    asset_id: str,
    name: str,
    expected_revision: int,
    x: int = 0,
    y: int = 0,
    opacity: float = 1.0,
) -> dict[str, Any]:
    """Add an imported or derived asset as the new topmost normal-blend pixel layer."""

    def action() -> dict[str, Any]:
        manifest, layer, operation = projects.add_layer(
            workspace_id,
            project_path,
            asset_id,
            name,
            x,
            y,
            opacity,
            expected_revision,
        )
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "operation_id": operation.id,
            "outputs": {"layer": layer},
        }

    return run_enveloped(action)


@mcp.tool(annotations=WRITE)
def transform_crop(
    workspace_id: str,
    project_path: str,
    target: TransformTarget,
    x: int,
    y: int,
    width: int,
    height: int,
    expected_revision: int,
    target_id: str | None = None,
) -> dict[str, Any]:
    """Crop one layer immutably or crop document bounds and shift all layer positions."""

    def action() -> dict[str, Any]:
        manifest, operation, derived = projects.crop(
            workspace_id,
            project_path,
            target,
            target_id,
            x,
            y,
            width,
            height,
            expected_revision,
        )
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "operation_id": operation.id,
            "outputs": {"derived_asset": derived},
        }

    return run_enveloped(action)


@mcp.tool(annotations=WRITE)
def transform_resize(
    workspace_id: str,
    project_path: str,
    target: TransformTarget,
    width: int,
    height: int,
    expected_revision: int,
    target_id: str | None = None,
    resize_filter: ResizeFilter = ResizeFilter.LANCZOS,
    aspect_policy: AspectPolicy = AspectPolicy.EXACT,
    content_policy: ContentPolicy | None = None,
) -> dict[str, Any]:
    """Resize one layer or resize a document with explicit scale_all/canvas_only policy."""

    def action() -> dict[str, Any]:
        manifest, operation, derived = projects.resize(
            workspace_id,
            project_path,
            target,
            target_id,
            width,
            height,
            resize_filter,
            aspect_policy,
            content_policy,
            expected_revision,
        )
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "operation_id": operation.id,
            "outputs": {"derived_assets": derived},
        }

    return run_enveloped(action)


@mcp.tool(annotations=WRITE)
def transform_position(
    workspace_id: str,
    project_path: str,
    layer_id: str,
    x: int,
    y: int,
    expected_revision: int,
) -> dict[str, Any]:
    """Set a layer's integer top-left position."""

    def action() -> dict[str, Any]:
        manifest, layer, operation = projects.position_layer(
            workspace_id, project_path, layer_id, x, y, expected_revision
        )
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "operation_id": operation.id,
            "outputs": {"layer": layer},
        }

    return run_enveloped(action)


@mcp.tool(annotations=WRITE)
def composite_overlay(
    workspace_id: str,
    project_path: str,
    asset_id: str,
    name: str,
    x: int,
    y: int,
    expected_revision: int,
    opacity: float = 1.0,
) -> dict[str, Any]:
    """Add an asset as a positioned topmost overlay using normal alpha compositing."""

    def action() -> dict[str, Any]:
        manifest, layer, operation = projects.add_layer(
            workspace_id,
            project_path,
            asset_id,
            name,
            x,
            y,
            opacity,
            expected_revision,
            operation_type="composite_overlay",
        )
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "operation_id": operation.id,
            "outputs": {"layer": layer},
        }

    return run_enveloped(action)


@mcp.tool(annotations=WRITE)
def image_render_preview(
    workspace_id: str,
    project_path: str,
    max_dimension: int = 1600,
) -> dict[str, Any]:
    """Render a bounded PNG preview without incrementing the project revision."""

    def action() -> dict[str, Any]:
        manifest, output, checksum = projects.render_preview(
            workspace_id, project_path, max_dimension
        )
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "outputs": {
                "path": relative_to_root(output, registry.root(workspace_id)),
                "sha256": checksum,
            },
        }

    return run_enveloped(action)


@mcp.tool(annotations=READ_ONLY)
def poster_safe_zone_check(
    workspace_id: str,
    project_path: str,
    max_dimension: int = 1600,
    margin_pixels: int | None = None,
    critical_layer_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Render a safe-zone overlay and check designated critical layer bounds."""

    def action() -> dict[str, Any]:
        manifest, output, checksum, result = projects.check_safe_zone(
            workspace_id,
            project_path,
            max_dimension,
            margin_pixels,
            critical_layer_ids,
        )
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "outputs": {
                **result,
                "preview": {
                    "path": relative_to_root(output, registry.root(workspace_id)),
                    "sha256": checksum,
                },
            },
            "warnings": [
                "Safe-zone approval requires visual inspection of the returned overlay preview."
            ],
        }

    return run_enveloped(action)


@mcp.tool(annotations=EXPORT_WRITE)
def export_png(
    workspace_id: str,
    project_path: str,
    output_path: str,
    expected_revision: int,
    overwrite: bool = False,
    metadata_policy: MetadataPolicy = MetadataPolicy.STRIP,
) -> dict[str, Any]:
    """Atomically export a flattened 8-bit sRGB PNG with alpha."""

    def action() -> dict[str, Any]:
        manifest, record = projects.export(
            workspace_id,
            project_path,
            output_path,
            ImageFormat.PNG,
            expected_revision,
            overwrite,
            metadata_policy=metadata_policy,
        )
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "operation_id": manifest.operations[-1].id,
            "outputs": {"export": record},
        }

    return run_enveloped(action)


@mcp.tool(annotations=EXPORT_WRITE)
def export_jpeg(
    workspace_id: str,
    project_path: str,
    output_path: str,
    background: str,
    expected_revision: int,
    quality: int = 92,
    overwrite: bool = False,
    metadata_policy: MetadataPolicy = MetadataPolicy.STRIP,
) -> dict[str, Any]:
    """Atomically export flattened 8-bit sRGB JPEG with explicit background and 4:2:0 chroma."""

    def action() -> dict[str, Any]:
        manifest, record = projects.export(
            workspace_id,
            project_path,
            output_path,
            ImageFormat.JPEG,
            expected_revision,
            overwrite,
            quality=quality,
            background=background,
            metadata_policy=metadata_policy,
        )
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "operation_id": manifest.operations[-1].id,
            "outputs": {"export": record},
        }

    return run_enveloped(action)


@mcp.tool(annotations=EXPORT_WRITE)
def export_psd(
    workspace_id: str,
    project_path: str,
    output_path: str,
    expected_revision: int,
    overwrite: bool = False,
    metadata_policy: MetadataPolicy = MetadataPolicy.STRIP,
) -> dict[str, Any]:
    """Atomically export the current pixel-layer stack as an 8-bit RGB PSD."""

    def action() -> dict[str, Any]:
        manifest, record = projects.export(
            workspace_id,
            project_path,
            output_path,
            ImageFormat.PSD,
            expected_revision,
            overwrite,
            metadata_policy=metadata_policy,
        )
        return {
            "project_id": manifest.project_id,
            "revision": manifest.revision,
            "operation_id": manifest.operations[-1].id,
            "outputs": {"export": record},
            "warnings": [PSD_COMPATIBILITY_WARNING],
        }

    return run_enveloped(action)


def _ai_envelope(result: AICommit) -> dict[str, Any]:
    return {
        "project_id": result.manifest.project_id,
        "revision": result.manifest.revision,
        "operation_id": result.operation.id,
        "outputs": {
            "assets": result.assets,
            "layers": result.layers,
            "conversation_id": result.conversation.id if result.conversation else None,
            "provider_session_retained": bool(
                result.conversation and result.conversation.provider_session_id
            ),
            "revised_prompt": result.revised_prompt,
        },
        "warnings": [warning for asset in result.assets for warning in asset.warnings],
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
