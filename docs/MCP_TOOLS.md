# MCP tool reference

All tools return one envelope with `ok`, `job_id: null`, identifiers, `outputs`,
`warnings`, `duration_ms`, and a stable `error` on failure.

| Tool | Effect |
|---|---|
| `system_preflight` | Checks ImageMagick and reports provider credential presence only |
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
| `layer_add` | Adds a topmost pixel layer |
| `transform_crop` | Crops one layer or document bounds |
| `transform_resize` | Resizes one layer or a document |
| `transform_position` | Sets integer top-left layer coordinates |
| `composite_overlay` | Adds a positioned normal-blend overlay |
| `image_render_preview` | Writes a bounded PNG without changing revision |
| `export_png` / `export_jpeg` | Writes and records an atomic delivery export |

Every project tool requires `workspace_id` and workspace-relative `project_path`.
Mutations require `expected_revision`; stale callers receive `CONFLICT`. Document resize
requires `content_policy: scale_all | canvas_only`. JPEG requires an explicit background.

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
