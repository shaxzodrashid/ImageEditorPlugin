# Image Editor Plugin

An installable Codex plugin for source-attributed visual discovery, provider-neutral AI
creation, and deterministic, reproducible image work:

```text
generate/edit → immutable asset → layer/finish → preview → safe-zone review → PNG/JPEG export
```

## Local object selection and background removal

`object_select` creates an immutable foreground selection and grayscale mask.
`background_remove` applies a new or compatible saved selection and returns a transparent RGBA
cutout, optionally added as a layer. Clean, uniform borders use ImageMagick without loading an ML
model. Complex scenes use pinned `isnet-general-use` inference in a separate local worker.

Selection and removal never send the image, mask, prompt, or telemetry to a provider. Install the
optional local model runtime once (the setup itself downloads pinned packages and model weights):

```powershell
image-editor-background-model install isnet-general-use --profile auto
```

After installation, inference works offline. `auto` prefers a smoke-tested CUDA, DirectML, or
OpenVINO provider and retries recoverable accelerator failures once on CPU. `cpu` forces CPU;
`accelerator` requires the installed non-CPU provider. See
[local background removal](docs/BACKGROUND_REMOVAL.md).

## Image discovery

`image_search` uses OpenAI's hosted Image Search capability through the Responses API. It returns
canonical image URLs with their source pages, thumbnails, captions, optional supporting text, and
clickable citation metadata. Search supports agent-selected compatible models, domain filters,
approximate location, result limits, and live or cached/index-only access.

Search is intentionally read-only and does not require a registered filesystem workspace. The
plugin never downloads or imports a result automatically; review the source page and applicable
rights before using a third-party image.

The canonical source is a versioned `.image-work` project. Imported files and derived
assets are immutable and content-addressed. Every mutation is locked, revision-checked,
recorded, and committed through an atomic manifest replacement.

## AI providers

| Provider | Models | Credential |
|---|---|---|
| OpenAI | GPT Image 2 | `OPENAI_API_KEY` |
| Google | Nano Banana 2, Nano Banana Pro | `GEMINI_API_KEY` |
| Fal AI | Seedream 5.0 Pro, Grok Imagine, Qwen Image Layered | `FAL_KEY` |

GPT Image 2, both Nano Banana models, and Seedream support generation and editing.
Grok Imagine is intentionally generation-only. Qwen Image Layered has a dedicated
semantic decomposition tool. `ai_continue_edit` preserves native Google interaction state;
stateless providers continue from the latest immutable result.

Keys are read only when a provider tool runs. They are never returned, logged, or written
to project manifests. Codex product authentication is separate from an
`OPENAI_API_KEY`; the plugin can use a key inherited by the process that launches Codex.

See [AI provider configuration](docs/AI_PROVIDERS.md) for the full model and option matrix.

## Current boundary

The plugin accepts PNG and JPEG, uses ordered normal-blend pixel layers and immutable selection
masks on an 8-bit sRGB canvas, and exports PNG or explicitly flattened JPEG. PSD/PSB, editable
per-layer masks, groups, filters, undo/redo, and background jobs remain deferred.

## Poster safe-zone validation

`poster_safe_zone_check` creates a non-mutating overlay preview and checks the rectangular bounds
of explicitly designated critical layers such as titles, logos, prices, faces, and calls to action.
The default inset scales the supplied 1080×1350 reference template's measured margins—64 px top,
65 px right, 70 px bottom, and 65 px left—to the canvas dimensions. Callers can provide a uniform
exact pixel margin when a channel has another rule.

The red perimeter may contain backgrounds and intentional full-bleed decoration. A geometry pass
never counts as final approval: the calling AI must open the returned preview and verify the
flattened content visually, because raster assets do not encode which pixels are semantically
important.

The bundled `$poster-create` skill orchestrates research, generation/editing, deterministic
composition, and delivery for branded posters and carousels. It requires brand-book-first planning,
source and identity review for real products, unique creative assets per placement, distinct layouts
per poster, and pixel-exact alignment. Containment from `poster_safe_zone_check` is only one gate:
planned edge-anchored logos/arrows must also be proven tangent to the returned safe-zone boundary
with zero gap and zero overflow.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)
- ImageMagick 7 available as `magick`, built with PNG, JPEG, and LCMS delegates

`system_preflight` reports missing dependencies and OS-specific remediation. It never
installs or modifies the host.

## Development

```powershell
cd D:\Shakhzod\Javascript\ImageEditorPlugin
uv sync --locked --dev
uv run image-editor-schema
uv run ruff check .
uv run mypy
uv run pytest
```

ImageMagick integration tests skip when preflight fails. Provider tests use fake HTTP and
fake image results, so development verification never spends provider credits.

## Local plugin installation

The repository-local marketplace is `.agents/plugins/marketplace.json`. Add that
marketplace, install the plugin, and start a fresh session:

```powershell
cd D:\Shakhzod\Javascript\ImageEditorPlugin
codex plugin marketplace add .
codex plugin add image-editor@image-editor-local
```

After changing plugin metadata, skills, or tools, reinstall the plugin and open a new Codex thread
so the cache and MCP tool catalog refresh.

Start with `system_preflight`, then register the narrowest filesystem root with
`workspace_register`. Every subsequent path is relative to that root.

## Safe workflow

1. Register a workspace.
2. Create or inspect a `.image-work` project.
3. For visual research, call `image_search`; for generation/editing, call `ai_model_catalog` and
   choose a model whose declared operations match the task.
4. Generate or edit; preserve returned candidates as generated assets.
5. Continue with the returned conversation ID or add the selected asset as a layer.
6. Apply exact crop, resize, and placement with deterministic tools.
7. Render a preview and run `poster_safe_zone_check` for poster/social deliverables.
8. Open the safe-zone preview, resolve every critical-content violation, then validate checksums.
9. Export only after both visual safe-zone review and `project_validate` pass.

Existing exports are never replaced unless `overwrite: true` is supplied.

See [MCP tools](docs/MCP_TOOLS.md), [project format](docs/PROJECT_FORMAT.md),
[security](docs/SECURITY.md), and [troubleshooting](docs/TROUBLESHOOTING.md).
