---
name: image-edit
description: Edit PNG/JPEG assets deterministically or with conversational AI in immutable Image Editor projects. Use for exact geometry, semantic replacement, prompt-guided refinement, supported masked edits, or provider-aware multi-turn image editing with source preservation and provenance.
---

# Image Edit

1. Call `system_preflight` and `ai_model_catalog`; relay missing dependencies or credentials
   only when the requested path needs them.
2. Call `workspace_register` once for the narrowest root containing inputs and outputs.
3. Create or inspect the `.image-work` project before modifying it.
4. Import each source with `asset_import`, then use `image_inspect` to verify dimensions, alpha, and warnings.
5. Use deterministic tools for exact work:
   - `transform_crop` with explicit integer bounds.
   - `transform_resize` with an explicit filter and aspect policy.
   - `transform_position` for top-left integer coordinates.
   - For document resize, always choose `scale_all` or `canvas_only` deliberately.
   - For object isolation, call `object_select` or `background_remove`. Prefer `method=auto` so a
     uniform connected border uses ImageMagick and a complex scene uses only the local model. Use
     `execution_policy=auto` unless CPU-only or accelerator-required behavior matters.
   - Selection/removal is local-only; never route its source, mask, prompt, or diagnostics through
     an AI provider. If model setup is missing, relay the exact preflight remediation command.
6. Use `ai_edit_image` only for semantic changes. Name what must change and what must remain
   unchanged. Select a model that declares `edit`; never use Grok Imagine for editing.
7. Supply `mask_asset_id` to hosted AI only when the user requests that hosted semantic edit and
   the model declares `inpaint`. Local `selection_mask` assets are otherwise applied by
   `background_remove` and remain local.
8. Continue refinement with `ai_continue_edit` and the returned conversation ID. Preserve
   every intermediate generated asset; never overwrite the source or a previous turn.
9. Pass the current revision as `expected_revision` for every mutation. On `CONFLICT`,
   inspect and reconsider the operation before retrying.
10. Render a preview and validate the project after the edit.

Report deterministic geometry or AI provider/model, revision, operation ID, output asset IDs,
conversation ID, and warnings. Never request, echo, or persist provider credentials.
