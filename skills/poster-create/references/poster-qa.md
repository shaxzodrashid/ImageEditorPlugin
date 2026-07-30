# Poster QA gates

Apply every gate to the rendered export, not only the editable project.

## Authority, brand, copy, and reality

- Confirm the relevant brand-book example/template pages were visually inspected, not only text-extracted.
- Confirm hard mandates, permitted choices, examples, locked templates, conflicts, and missing production assets were distinguished correctly.
- Confirm copy, spelling, offer, product, dates, CTA, and legal text against the approved brief.
- Confirm logo variant/clear space, typography, colors, spacing, grid, tone, dimensions, background, and safe zone against the authoritative design system.
- Confirm every real product is the exact model/variant represented by the copy and source.
- Confirm every external asset has a canonical source, rights basis, and identity check.

## Visual thesis and anti-generic quality

- State the selected concept in one plain sentence. Fail a layer list or a string of style adjectives.
- Confirm the visual communicates a specific part of this message before the supporting copy is read.
- Confirm the hero is evidence, mechanism, result, or meaningful context—not an interchangeable beauty shot.
- Explain the copy-subject relationship through scale, crop, overlap, direction, contrast, transformation, or sequence.
- Apply the swap test: fail when another brand or unrelated product can replace the logo/hero without changing the concept.
- Apply the one-second and thumbnail tests: subject, emotion, and primary question/benefit must survive at feed size.
- Confirm one decisive focal point, intentional negative space, and a clear first/second/third reading beat.
- Compare the export to the selected thumbnail and visual thesis. Fail concept drift caused by convenient assets or safe layout decisions.
- Fail “generic image + detached headline” unless a deliberate type-led concept makes that separation the idea.

## Campaign coherence and controlled variation

- Confirm every poster has a distinct communication purpose and advances the ordered story.
- Confirm two to four planned campaign invariants are visible across the set.
- Compare neighboring layout fingerprints. Fail repeated static crops/placements and copy blocks; also fail unrelated visual worlds introduced only for difference.
- Allow a repeated exact product or hero only when recorded as campaign continuity or product-truth necessity and its narrative/spatial role changes.
- Compare source lineages, not filenames. Fail lazy derivative reuse and accidental repetition; do not fail deliberate continuity.
- Inspect the contact sheet for pacing, density changes, hook-to-payoff progression, and a coherent material/lighting/illustration world.

## Safe-zone containment

Call `poster_safe_zone_check` with all critical foreground layer IDs. Do not include intentional full-bleed background/decoration.

From returned safe-zone bounds `(sx, sy, sw, sh)`, derive:

```text
safe_left   = sx
safe_top    = sy
safe_right  = sx + sw
safe_bottom = sy + sh
```

For each checked layer `(x, y, width, height)`, require:

```text
x >= safe_left
y >= safe_top
x + width <= safe_right
y + height <= safe_bottom
```

The tool uses full asset bounds. Tightly crop transparent padding, strokes, and unintended shadow spread before using bounds as visible-edge evidence. Open the overlay and inspect flattened text, logos, faces, prices, CTAs, and product-critical details; `geometry_passed: true` alone is insufficient.

## Exact edge anchors

Containment does not prove zero gap. For each planned edge anchor require integer equality:

```text
left:   x == safe_left
top:    y == safe_top
right:  x + width == safe_right
bottom: y + height == safe_bottom
```

Fail a `1 px` gap or overflow. When a brand mandates logo clear space, apply equality to the clear-space box and verify the visible logo remains inside it.

## Pixel alignment

- Name every intended shared axis and record its integer coordinate.
- Require side-aligned logo and label edges/centers to use the exact same x-coordinate.
- Require intentional horizontal alignment to use the exact same y-coordinate or baseline as applicable.
- Inspect optical balance only after mathematical alignment. Document deliberate optical corrections.

## Navigation

- Remove page counts, fractions, progress labels, “swipe” copy, and redundant continuation text.
- Keep arrows optional and purposeful.
- Use a continuation arrow alone, without numbers or labels.
- Validate the arrow as critical content and prove any planned edge equality.

## Visual and export review

Inspect each rendered poster at 100%, mobile view, and one-second thumbnail for legibility, contrast, hierarchy, crop quality, clean masks, believable lighting/perspective/materials, and absence of clipping, stretching, low-resolution artifacts, accidental tangencies, or unsafe features.

Inspect the ordered carousel contact sheet for narrative order, coherent variation, visual rhythm, generic slides, repeated static treatments, random discontinuities, and monotony. Run `project_validate`, export deliberately, then reopen the final files and confirm dimensions, format, color behavior, order, filenames, and checksums.

Record each gate as **Pass**, **Fail**, or **Unverified** with evidence. Do not call the poster fully validated while a required gate is failed or unverified.
