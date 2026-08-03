# MCP tool reference

All tools return one envelope with `ok`, `job_id: null`, identifiers, `outputs`,
`warnings`, `duration_ms`, and a stable `error` on failure.

| Tool | Effect |
|---|---|
| `system_preflight` | Checks ImageMagick, local selection runtime/resources, and credentials |
| `system_capabilities` | Lists implemented features, deferred work, and limits |
| `ai_model_catalog` | Lists model IDs, operations, formats, limits, and credential names |
| `image_search` | Finds current source-attributed images through OpenAI hosted web search |
| `workspace_register` | Authorizes one session-local filesystem root |
| `ai_generate_image` | Generates candidates and starts a provenance-linked conversation |
| `ai_edit_image` | Edits one or more immutable assets, optionally with a supported mask |
| `ai_continue_edit` | Continues from provider state or the latest generated asset |
| `ai_decompose_layers` | Uses Qwen Image Layered to create semantic RGBA assets/layers |
| `project_create` | Creates a revision-zero `.image-work` directory |
| `project_inspect` | Returns the validated manifest |
| `project_validate` | Checks manifest, asset paths, and checksums |
| `asset_import` | Copies a PNG/JPEG into immutable content-addressed storage |
| `image_inspect` | Returns recorded image metadata and provenance |
| `object_select` | Creates a local immutable foreground selection and mask |
| `background_remove` | Applies a new/existing selection and creates a transparent cutout |
| `layer_add` | Adds a topmost pixel layer |
| `text_layer_create` | Renders rich text to a transparent PNG and adds it as a topmost pixel layer |
| `transform_crop` | Crops one layer or document bounds |
| `transform_resize` | Resizes one layer or a document |
| `transform_position` | Sets integer top-left layer coordinates |
| `composite_overlay` | Adds a positioned normal-blend overlay |
| `image_render_preview` | Writes a bounded PNG without changing revision |
| `poster_safe_zone_check` | Renders a safe-zone overlay and checks critical layer bounds |
| `export_png` / `export_jpeg` / `export_psd` | Writes and records an atomic delivery export |

Every project tool requires `workspace_id` and workspace-relative `project_path`.
Mutations require `expected_revision`; stale callers receive `CONFLICT`. Document resize
requires `content_policy: scale_all | canvas_only`. JPEG requires an explicit background.

`text_layer_create` accepts ordered `runs`, each with a portable `font_family` (`sans`, `serif`,
or `mono`), `font_size`, exactly one solid `color` or linear `gradient`, and `bold`, `italic`,
`underline`, and `strikethrough` controls. A gradient uses 2-8 ordered stops with positions from
0 to 1; angle 0 is left-to-right and increases clockwise. The renderer writes one transparent
PNG asset, then immediately adds it as a normal-blend layer at `x` and `y`, with optional opacity.
It supports a solid sentence plus a gradient word by making them separate runs:

```json
{
  "name": "Campaign title",
  "expected_revision": 4,
  "x": 72,
  "y": 128,
  "text": {
    "runs": [
      {"text": "Summer ", "style": {"font_size": 72, "color": "#111827"}},
      {
        "text": "Sale",
        "style": {
          "font_size": 72,
          "bold": true,
          "gradient": {
            "angle_degrees": 0,
            "stops": [
              {"position": 0, "color": "#EC4899"},
              {"position": 1, "color": "#8B5CF6"}
            ]
          }
        }
      }
    ]
  }
}
```

Text remains a transparent raster layer: it can be repositioned, resized, cropped, previewed,
and delivered in PNG/JPEG/PSD, but it is not a native editable Photoshop Type layer.

`export_psd` writes the current ordered normal-blend pixel-layer stack as an 8-bit RGB PSD. It
preserves layer names, bottom-to-top order, positions (including negative offsets), opacity,
visibility, alpha, and a solid canvas background as a bottom `Canvas Background` layer. The staged
file is created and reopened with the portable `psd-tools` backend before atomic commit. PSD export
accepts only `metadata_policy: strip`; its record reports the actual `backend`, `validation`, and
optional `native_fallback_from`. PhotoshopAPI is optional, never imported by MCP, and can only run
in a bounded child; a native failure falls back to portable export. It does not claim native Adobe
Photoshop or third-party-reader compatibility. PSB, groups, editable masks, text layers, smart
objects, blend modes other than normal, and native adjustments remain deferred.

The `psd-tools-roundtrip` record is not a native Photoshop claim. A rare optional
`photoshopapi-roundtrip` record is also not a native Photoshop claim. The release-only
`tests/test_photoshop_27_compatibility.py` gate must pass on an idle licensed Photoshop 27.8
Windows host before an export is labelled `photoshop-opened`.

`poster_safe_zone_check` is read-only with respect to the manifest and writes only a replaceable
preview under `previews/`. By default it scales the supplied 1080×1350 reference's measured
top/right/bottom/left margins of 64/65/70/65 px to the canvas dimensions. Set `margin_pixels` for
an exact uniform platform or campaign rule. Pass only semantically critical foreground layer IDs
in `critical_layer_ids`; intentional
background/full-bleed layers should not be included. The result contains resolved bounds, layer
bounds, per-edge overflow, an overlay path/checksum, and `visual_review_required: true`.

`status: fail` means at least one designated critical layer crosses the inset. Otherwise the tool
returns `status: review_required`, never an automatic semantic pass: the caller must open the
overlay and verify text, logos, faces, prices, and calls to action in flattened raster content.

`object_select` and `background_remove` accept `method: auto | border | local_model` and
`execution_policy: auto | cpu | accelerator`. Auto selection tries connected border removal first
and dispatches to the installed local model only when the border is unsuitable. Results record
requested/resolved method, runtime profile, actual provider, CPU fallback and reason, model hash,
elapsed time, bounds, coverage, and `local_inference: true`. A supplied `selection_id` must belong
to the same source. Selection, mask/cutout, optional layer, operation, and revision commit atomically.

`image_search` does not require a workspace or mutate projects. Its optional `model` defaults to
`gpt-5.6`, and the calling agent may choose another Responses model that supports `web_search`
image results. Options control 1-20 results, captions, supporting text, search context, hostname
allow/block lists, approximate location, and live versus cached/index-only access. Results retain
canonical image, source-page, and thumbnail URLs. The tool never downloads them automatically.

AI tools never accept raw keys or arbitrary provider URLs. `provider` plus optional `model`
is validated against the catalog before a network request. `AIImageOptions` provides common
format, quality, aspect, resolution, and candidate-count controls; unsupported combinations
return `UNSUPPORTED_FEATURE` or `INVALID_ARGUMENT` rather than silently dropping options.

By default, generated candidates remain assets until the caller selects one. Set
`add_as_layers: true` only when every returned image should be inserted immediately.
Qwen decomposition defaults to adding its ordered RGBA outputs as project layers.
