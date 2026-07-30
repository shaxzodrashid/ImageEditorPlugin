# Poster QA gates

Apply every gate to the rendered export, not only the editable project.

## Brand, copy, and reality

- Confirm copy, spelling, offer, product, dates, CTA, and legal text against the approved brief.
- Confirm logo variant/clear space, typography, colors, spacing, grid, tone, dimensions, and safe zone against the brand book.
- Confirm every real product is the exact model/variant represented by the copy and source.
- Confirm every external asset has a canonical source, rights basis, and identity check.
- Confirm the requested creative style is followed; otherwise confirm photorealistic execution.

## Creative uniqueness

- Compare every asset-ledger entry by source content, not filename. Fail any repeated creative asset or derivative reuse.
- Compare every layout fingerprint pair. Fail repeated spatial skeletons, not just pixel-identical layouts.
- Confirm every poster has a distinct communication purpose.

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

Inspect each rendered poster at 100% and mobile view for legibility, contrast, hierarchy, crop quality, clean masks, believable lighting/perspective/materials, and absence of clipping, stretching, low-resolution artifacts, accidental tangencies, or unsafe features.

Inspect the ordered carousel contact sheet for narrative order, visual rhythm, repeated assets, repeated layouts, and monotony. Run `project_validate`, export deliberately, then reopen the final files and confirm dimensions, format, color behavior, order, filenames, and checksums.

Record each gate as **Pass**, **Fail**, or **Unverified** with evidence. Do not call the poster fully validated while a required gate is failed or unverified.
