---
name: poster-create
description: Plan, source, create, validate, and export professional branded posters and multi-poster carousels with the Image Editor plugin. Use for social posts, promotional graphics, product posters, campaign carousels, poster redesigns, photorealistic asset sourcing, brand-book compliance, unique per-poster assets and layouts, exact safe-zone anchoring, or final poster QA.
---

# Poster Create

Create each poster as a reproducible Image Editor project. Treat brand compliance, source accuracy, asset and layout uniqueness, safe-zone geometry, and final render inspection as delivery gates.

## Establish authority

1. Inspect the brief, brand book, design system, supplied assets, platform requirements, and approved examples before designing.
2. Let explicit task direction control the creative style. Otherwise default to photorealistic assets and compositing.
3. Treat the brand book as authoritative for logo use, typography, color, spacing, grid, tone, safe zone, and dimensions unless the user explicitly overrides it.
4. Record missing rules and conflicts. Do not invent a brand rule silently.
5. Verify current platform dimensions when neither brief nor brand book specifies them. Use `1080 x 1350 px (4:5)` only as the Instagram portrait fallback.

## Plan the set

Plan before mutating a project. For every poster, record its purpose, takeaway, approved copy, CTA, unique primary/supporting assets, composition concept, reading path, brand anchors, and safe-zone anchors.

For carousels, give each poster one distinct communication job. Share the brand system across the set, but never reuse a layout. Before composition, complete both ledgers in [references/planning-ledgers.md](references/planning-ledgers.md).

## Source and prepare assets

1. Invoke `$image-search` when the task needs current visual references or real product imagery. Prefer supplied approved libraries, official manufacturer pages or press kits, authorized product media, reputable editorial sources, then properly licensed stock.
2. Open and verify the source page. Match the real product's exact model, generation, color, configuration, and relevant market details. Keep the image URL, source-page URL, caption, rights status, and supporting citations.
3. Treat search results as discovery references, not automatically licensed assets. Download and import only after the source and permitted-use basis have been reviewed and the chosen result is authorized for use.
4. Use actual product photography when an exact real product is required and approved photography is available. Never substitute a similar model or generated lookalike without explicit disclosure and approval.
5. Invoke `$image-create` only when generation is appropriate. Use the requested style strictly; otherwise request photorealistic lighting, material, scale, perspective, and texture.
6. Invoke `$image-edit` for isolation, background removal, cleanup, exact crop/resize, or semantic edits. Keep selections/background removal local unless the user requests a supported hosted semantic edit.
7. Render logos and exact final typography deterministically as tightly cropped transparent PNG assets when they are not already supplied. Do not rely on an image model to spell final poster copy.

Never reuse one creative source asset in two placements across the deliverable. A new crop, mirror, recolor, blur, mask, cutout, or filename is still the same asset. Brand-mandated identity marks and standardized arrow glyphs may repeat only as required system primitives; do not alter a logo to manufacture uniqueness.

## Build reproducibly

1. Call `system_preflight`, `workspace_register`, and then create or inspect one `.image-work` project per poster.
2. Import and inspect every approved PNG/JPEG. Keep an asset assigned to exactly one planned creative placement.
3. Use `$image-compose` to add layers bottom-to-top. Use deterministic crop, resize, and integer positioning for final geometry. Carry the returned revision through every mutation.
4. Define the canvas and safe-zone rectangle in integer pixels before placing functional content. Allow intentional full-bleed backgrounds; keep text, logos, prices, product-critical features, faces, CTAs, icons, and arrows within the safe zone.
5. For edge-anchored elements, crop transparent padding first and position the specified visible boundary exactly on the safe-zone boundary: `0 px` gap and `0 px` overflow. Respect logo clear-space rules by aligning the prescribed clear-space box when applicable.
6. Make shared alignment axes exact. Side-aligned logos and text labels must use the same intended vertical edge or center coordinate, pixel for pixel. Document any deliberate optical correction without changing the declared anchor.

Never reuse a layout across posters. Changing only copy, color, crop, or subject does not create a new layout. Require a materially different dominant subject position, copy-block position, alignment axis, reading path, major shape arrangement, or negative-space structure.

## Handle carousel navigation

Do not add page numbers, fractions such as `02/05`, progress labels, “swipe” copy, or any label whose only purpose is to announce more posters.

An arrow is optional. Use it only when it strengthens direction or CTA behavior. For continuation, use the arrow glyph alone with no number or explanatory label. Treat it as critical content and validate its intended safe-zone anchor.

## Validate and deliver

Read and apply [references/poster-qa.md](references/poster-qa.md). For every poster:

1. Render a preview and inspect it at final-size and mobile-size views.
2. Call `poster_safe_zone_check` with every critical foreground layer ID. Use the supplied template's scaled default margins unless the brief/platform specifies an exact uniform `margin_pixels` value.
3. Open the returned overlay. A true `geometry_passed` value is not final approval.
4. Prove edge tangency separately by comparing checked layer bounds with returned safe-zone bounds. The checker proves containment, not zero-gap equality.
5. Verify brand rules, copy, real-product identity, source provenance, asset uniqueness, layout uniqueness, alignment, legibility, and compositing quality.
6. Call `project_validate`, then invoke `$image-deliver` for deliberate PNG/JPEG export without overwriting unless explicitly authorized.
7. Reopen final exports. For a carousel, inspect an ordered contact sheet to catch repetition, pacing, and sequence problems.

Do not deliver with a failed or unverified required gate. Report project/export paths, dimensions, safe-zone bounds, edge-equality evidence, source ledger, checksums, warnings, and validation status.
