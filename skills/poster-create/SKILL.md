---
name: poster-create
description: Plan, art-direct, source, create, validate, and export concept-led branded posters and multi-poster carousels with the Image Editor plugin. Use for creative social posts, promotional graphics, product posters, campaign carousels, poster redesigns, brand-book interpretation, visual concept development, photorealistic or illustrated asset sourcing, safe-zone anchoring, and final poster QA.
---

# Poster Create

Create each poster as a reproducible Image Editor project. Treat the visual idea, brand and source accuracy, composition, campaign coherence, safe-zone geometry, and final render inspection as delivery gates.

## Establish authority

1. Inspect the brief, brand book, design system, supplied assets, platform requirements, approved examples, and recent campaign outputs before designing.
2. Render and visually inspect the relevant brand-book example/template pages. Do not rely on extracted text alone to understand crop, scale, spacing, energy, or layout behavior.
3. Separate hard mandates, permitted choices, examples, and locked templates. Record conflicts and missing production assets; do not silently turn an example into a rule or claim template compliance without the template.
4. Let explicit task direction control the creative style. Otherwise choose photography, collage, illustration, 3D, typography, or a hybrid from the message and brand system; do not default mechanically to photorealism.
5. Treat the brand book as authoritative for logo use, typography, color, spacing, grid, tone, safe zone, and dimensions unless the user explicitly overrides it.
6. Verify current platform dimensions when neither brief nor brand book specifies them. Use `1080 x 1350 px (4:5)` only as the Instagram portrait fallback.

## Develop art direction

Read and apply [references/creative-direction.md](references/creative-direction.md) whenever the visual concept is not already prescribed or the user asks for creative work.

Before sourcing polished assets or mutating a project:

1. Translate the message into an audience tension, benefit, proof, desired emotion, and one visual job.
2. Generate four to six genuinely different concept directions. Differ by premise, subject-message relationship, visual device, and spatial skeleton—not merely by color, style adjectives, crop, or background.
3. Reject semantically interchangeable beauty shots, literal stock-photo matches, decorative style-word concepts, and any direction that cannot be explained in one sentence.
4. Make low-fidelity thumbnails for the strongest three directions at the actual aspect ratio. Compare them at mobile size before selecting one.
5. Select the direction with the strongest message specificity, stopping power, brand ownability, clarity, truth, and feasible execution. Record why the discarded directions lost.
6. Write a one-sentence visual thesis that links the copy, hero, composition, and brand behavior. If the thesis is only “image plus headline,” keep ideating.
7. Compare the selected premise and spatial fingerprint with recent work. Change the combination when it repeats a familiar solution without a campaign reason.

Brand compliance defines the creative field; it is not the creative idea.

## Plan the set

Complete the ledgers in [references/planning-ledgers.md](references/planning-ledgers.md) before composition. For every poster, record its purpose, takeaway, approved copy, CTA, visual thesis, hero and supporting assets, visual-copy relationship, composition, reading path, brand anchors, and safe-zone anchors.

For carousels, give each poster one distinct communication job and plan the ordered story. Lock a small set of campaign invariants, then vary selected visual beats so the set feels related without becoming a repeated template. Do not force every slide to use an unrelated subject merely to appear different.

## Source and prepare assets

1. Choose the hero medium and asset requirements from the selected concept, then invoke `$image-search` when the task needs current visual references or real product imagery. Prefer supplied approved libraries, official manufacturer pages or press kits, authorized product media, reputable editorial sources, then properly licensed stock.
2. Open and verify the source page. Match the real product's exact model, generation, color, configuration, and relevant market details. Keep the image URL, source-page URL, caption, rights status, and supporting citations.
3. Treat search results as discovery references, not automatically licensed assets. Download and import only after the source and permitted-use basis have been reviewed and the chosen result is authorized for use.
4. Use actual product photography when an exact real product is required and approved photography is available. Never substitute a similar model or generated lookalike without explicit disclosure and approval.
5. Invoke `$image-create` only when generation is appropriate. Prompt for the selected art direction, material, scale, perspective, texture, lighting, negative space, and intended crop rather than asking for a generic “professional” image.
6. Invoke `$image-edit` for isolation, background removal, cleanup, exact crop/resize, or semantic edits. Keep selections/background removal local unless the user requests a supported hosted semantic edit.
7. Render logos and exact final typography deterministically as tightly cropped transparent PNG assets when they are not already supplied. Do not rely on an image model to spell final poster copy.

Reject a visually attractive asset when it could be swapped into an unrelated campaign without changing the idea. Reuse a hero asset only when it is an intentional campaign continuity device or the exact product truth requires it; change its narrative role or spatial relationship, not only its filename. Avoid repeated supporting assets and repeated static placements. Never introduce unrelated imagery or generated product lookalikes solely to satisfy an asset-uniqueness rule.

## Build reproducibly

1. Call `system_preflight`, `workspace_register`, and then create or inspect one `.image-work` project per poster.
2. Import and inspect every approved PNG/JPEG. Keep the asset ledger aligned with actual placements and intentional continuity reuse.
3. Use `$image-compose` to add layers bottom-to-top. Use deterministic crop, resize, and integer positioning for final geometry. Carry the returned revision through every mutation.
4. Define the canvas and safe-zone rectangle in integer pixels before placing functional content. Allow intentional full-bleed backgrounds only when the authoritative design system permits them; keep text, logos, prices, product-critical features, faces, CTAs, icons, and arrows within the safe zone.
5. Compose to the selected visual thesis: control hero scale, crop, overlap, directional tension, negative space, and copy-to-subject relationship deliberately. If the result collapses into a detached headline over a generic image, return to concept development instead of polishing it.
6. For edge-anchored elements, crop transparent padding first and position the specified visible boundary exactly on the safe-zone boundary: `0 px` gap and `0 px` overflow. Respect logo clear-space rules by aligning the prescribed clear-space box when applicable.
7. Make shared alignment axes exact. Side-aligned logos and text labels must use the same intended vertical edge or center coordinate, pixel for pixel. Document any deliberate optical correction without changing the declared anchor.

Do not repeat a layout mechanically. In a carousel, preserve planned invariants while changing enough of the dominant subject scale/position, copy relationship, alignment axis, reading path, major shape arrangement, or negative-space structure to create purposeful rhythm. Controlled repetition is valid; accidental sameness and random incoherence are not.

## Handle carousel navigation

Do not add page numbers, fractions such as `02/05`, progress labels, “swipe” copy, or any label whose only purpose is to announce more posters.

An arrow is optional. Use it only when it strengthens direction or CTA behavior. For continuation, use the arrow glyph alone with no number or explanatory label. Treat it as critical content and validate its intended safe-zone anchor.

## Validate and deliver

Read and apply [references/poster-qa.md](references/poster-qa.md). For every poster:

1. Render a preview and inspect it at final size, mobile size, and as a one-second thumbnail.
2. Run the anti-generic, visual-thesis, brand-ownability, copy-visual relationship, campaign-coherence, and product-truth gates before geometric QA. A beautiful but generic image fails.
3. Call `poster_safe_zone_check` with every critical foreground layer ID. Use the supplied template's scaled default margins unless the brief/platform specifies an exact uniform `margin_pixels` value.
4. Open the returned overlay. A true `geometry_passed` value is not final approval.
5. Prove edge tangency separately by comparing checked layer bounds with returned safe-zone bounds. The checker proves containment, not zero-gap equality.
6. Verify brand rules, copy, real-product identity, source provenance, deliberate asset reuse, controlled layout variation, alignment, legibility, and compositing quality.
7. Call `project_validate`, then invoke `$image-deliver` for deliberate PNG/JPEG export without overwriting unless explicitly authorized.
8. Reopen final exports. For a carousel, inspect an ordered contact sheet to catch weak pacing, generic slides, unintended repetition, random visual changes, and sequence problems.

Do not deliver with a failed or unverified required gate. Report project/export paths, dimensions, safe-zone bounds, edge-equality evidence, source ledger, concept/QA result, checksums, warnings, and validation status.
