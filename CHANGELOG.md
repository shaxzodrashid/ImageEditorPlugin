# Changelog

## Unreleased

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
