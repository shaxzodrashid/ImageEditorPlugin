---
name: image-create
description: Generate new professional images with OpenAI, Google, or Fal models inside immutable Image Editor projects. Use for text-to-image creation, candidate generation, provider/model selection, conversational refinement, or semantic layer decomposition with provenance.
---

# Image Create

1. If current visual references are needed, call `image_search` first and retain source links. Then
   call `system_preflight`, `ai_model_catalog`, and `workspace_register`.
2. Create or inspect the `.image-work` project. Carry the current revision through every
   mutation.
3. Choose only a model whose catalog operations match the request:
   - Prefer the provider's default when the user has no quality, latency, or model preference.
   - Use Grok Imagine only for generation.
   - Use Qwen Image Layered only through `ai_decompose_layers`.
4. Resolve aspect ratio, resolution, candidate count, format, and quality before calling
   `ai_generate_image`. Keep the provider safety filter enabled.
5. Generate candidates with `add_as_layers: false` unless every result should enter the
   composition. Inspect candidates and add only the selected assets.
6. Refine with `ai_continue_edit` and the returned conversation ID. Do not switch provider
   or model within an existing conversation.
7. Use deterministic tools for exact crop, resize, placement, compositing, and export.
8. Preview and validate the project before delivery.

Report provider, resolved model, output asset IDs, conversation ID, revision, dimensions,
provider warnings, and whether any candidate was added as a layer. Never request, echo, or
persist an API key.
