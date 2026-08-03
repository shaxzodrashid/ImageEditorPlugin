# Changelog

## Unreleased

## 0.8.0 - 2026-08-01

- Add `text_layer_create`: deterministic rich text rasterization into a transparent PNG asset and
  separate positionable pixel layer. Ordered runs support portable sans/serif/mono fonts, size,
  solid colors or linear gradients, bold, italic, underline, strikethrough, wrapping, alignment,
  and line spacing.
- Preserve the resulting text layer in project previews, safe-zone validation, PNG/JPEG delivery,
  and layered PSD export. PSD text remains a raster pixel layer, not a native Photoshop Type layer.

## 0.7.1 - 2026-07-31

- Make layered PSD export portable by default with `psd-tools`, including structural reopen
  validation for 8-bit RGB+alpha pixel layers, names/order, offsets (including negative offsets),
  opacity, visibility, canvas background, and source alpha.
- Pin the core NumPy dependency to `2.3.5`, the known-compatible release for legacy SSE2 Linux
  hosts, and add a lockfile regression guard against CPU-baseline dependency drift.
- Move PhotoshopAPI to the `photoshopapi` optional extra. Its probe and export remain bounded,
  isolated child processes: native import crashes (including SIGILL) safely fall back to the
  portable exporter without corrupting staged or existing deliveries.
- Record the actual PSD backend, structural validator, and any native fallback in export provenance.
  Linux remains portable-first unless the optional native backend is explicitly requested.

## 0.7.0 - 2026-07-31

- Add atomic layered PSD export for the canonical 8-bit sRGB pixel-layer model. It preserves layer
  names/order/positions/opacity/visibility/alpha, writes a nontransparent canvas background as a
  named pixel layer, reopens staged files for structural validation, records compatibility limits,
  and requires explicit overwrite authorization. Bump the plugin to 0.7.0 and the project schema
  to 1.3.0.
- Add an opt-in Adobe Photoshop 27.8 COM acceptance test. It opens a real layered export with
  repair/error dialogs enabled, verifies its canvas/layers, and closes it without saving; this is the only gate
  that can label an export `photoshop-opened`.
- Add a model-robust creative-direction stage to `poster-create`: rendered brand-example review,
  four-to-six concept territories, three rough thumbnails, visual-thesis selection, anti-generic
  tests, and concept-level iteration before production polish.
- Replace absolute asset/layout uniqueness with controlled campaign coherence and variation.
  Deliberate exact-product or continuity reuse is allowed; unrelated imagery, lazy derivatives,
  generic beauty shots, and repeated static placements fail. Bump the plugin patch version to
  0.6.1; the project schema remains 1.2.0.
- Add the `poster-create` workflow skill for brand-book-first planning, source-verified imagery,
  per-placement asset uniqueness, distinct carousel layouts, exact safe-zone anchoring, pixel-perfect
  alignment, navigation restraint, and final render QA.
- Bump the plugin minor version to 0.6.0; the project schema remains 1.2.0.

## 0.5.1 - 2026-07-29

- Create the Linux worker environment with a copied managed Python interpreter so strict runtime
  path containment accepts the standard venv layout. Bump the plugin patch version to 0.4.3.
- Replace the malformed embedded smoke-test PNG with a structurally validated image and pin NumPy
  2.3.5 for compatibility with legacy x86 VPS CPUs so runtime activation reaches real ONNX
  inference. Bump the plugin patch version to 0.4.2.
- Fix local runtime installation by using a Python 3.12 worker and pinning the compatible
  NumPy/PyMatting/Numba/llvmlite stack instead of allowing uv to backtrack to an obsolete
  llvmlite source release. Installer failures now report a sanitized failing phase and reason.
- Update the MCP smoke catalog for the two background-selection tools introduced in 0.4.0.
- Bump the plugin patch version to 0.4.1; project schema remains 1.2.0.

- Add local-only `object_select` and `background_remove` with connected-border selection, pinned
  isnet/rembg fallback, immutable masks/cutouts, reusable selections, and atomic revision commits.
- Add isolated CPU/CUDA/DirectML/OpenVINO installation, runtime resource checks, actual provider
  and fallback provenance, bounded subprocess execution, model hashing, and offline inference.
- Bump the plugin to 0.4.0 and project schema to 1.2.0; editable per-layer masks remain deferred.

- Add `image_search`, a read-only OpenAI Responses API Image Search integration with
  agent-selectable models, canonical image/source/thumbnail URLs, captions, supporting text,
  citations, domain filters, approximate location, live/cache-only control, and bounded output.
- Force the hosted `web_search` tool when image discovery is invoked, sanitize returned URLs and
  request IDs, deduplicate results, avoid third-party downloads, and preserve stable provider
  errors without exposing credentials or raw responses.
- Add provider-neutral AI generation and conversational editing for GPT Image 2,
  Nano Banana 2, Nano Banana Pro, and Seedream 5.0 Pro.
- Add generation-only Grok Imagine and Qwen Image Layered semantic decomposition.
- Add native Google interaction continuation and asset-based continuation for stateless
  providers.
- Persist generated assets, provider/model provenance, conversations, parent lineage,
  sanitized request IDs, and non-deterministic operations atomically.
- Add capability-gated model discovery, credential-presence preflight, fixed provider host
  allowlists, bounded provider media handling, and stable provider error mapping.
- Add fake-HTTP adapter tests and mock-provider project integration tests with no live calls.
- Fixed `asset_import` on ImageMagick 7 by placing the `identify` subcommand before
  resource-limit options.
- Added safe, failure-specific remediation for decoder, corrupt-input, and resource-limit
  engine errors.
- Added unit and real-ImageMagick regression coverage for metadata inspection.

## 0.1.0 - 2026-07-24

- Add the deterministic Image Editor MVP with 15 synchronous MCP tools.
- Add immutable project assets, revisions, locking, atomic manifests, previews, validation,
  and PNG/JPEG exports.
- Add Windows, Linux, and macOS CI plus edit, compose, and delivery skills.
