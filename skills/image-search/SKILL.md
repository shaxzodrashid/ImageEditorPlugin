---
name: image-search
description: Find current, web-grounded image references with OpenAI Image Search. Use for product photos, landmarks, events, places, visual research, moodboards, or source-attributed image discovery before creation or editing.
---

# Image Search

1. Call `system_preflight` or `ai_model_catalog` and verify that OpenAI is configured.
2. Call `image_search` with a concrete visual query. The default model is `gpt-5.6`; the calling
   agent may choose another Responses model only when it supports `web_search` image results.
3. Keep `caption: true` and `include_supporting_text: true` when ranking or explaining results.
   Use images-only mode for fast visual lookup.
4. Use `allowed_domains` or `blocked_domains` as hostname-only filters. Supply approximate
   location only when geographic relevance matters. Keep live web access enabled for current
   results; disable it only when cache/index-only behavior is intentional.
5. Present the image URL together with its source-page URL and caption. Keep supporting citations
   visible and clickable when summarizing text-derived context.
6. Treat results as discovery references, not licensed project assets. Review the source page and
   applicable rights before downloading, editing, publishing, or importing an image.
7. Do not automatically fetch result URLs. If the user explicitly chooses a result and authorizes
   its use, download it through a separately reviewed workflow, then import the local PNG/JPEG with
   `asset_import` so normal immutable-asset validation applies.

Report the query, resolved model, result count, captions, canonical image URLs, source-page URLs,
supporting citations, provider warnings, and whether live web access was requested. Never request,
echo, persist, or place `OPENAI_API_KEY` in tool arguments.
