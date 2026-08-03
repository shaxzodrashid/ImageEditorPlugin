---
name: typography-create
description: Create and place polished rich-text headlines, labels, prices, CTAs, and other typography in Image Editor projects. Use when a design needs transparent text layers with chosen font family, size, solid color, per-word linear gradients, bold, italic, underline, strikethrough, wrapping, alignment, safe-zone placement, or PNG/JPEG/PSD delivery.
---

# Typography Create

Use `text_layer_create` for exact final copy. It renders the text into a separate transparent PNG
pixel layer and places it in the project; it does not create a native editable Photoshop Type layer.

1. Inspect the brief, approved copy, brand book, design system, canvas, and existing project before
   writing typography. Let the brand system decide type hierarchy, colors, casing, and spacing.
2. Run `system_preflight`, register the workspace, and create or inspect the `.image-work` project.
   Carry the current `expected_revision` through every mutation.
3. Represent each independently styled portion as an ordered `runs` item. Keep shared words in the
   same run; split only where a fill or format changes. Use `sans`, `serif`, or `mono`; do not claim
   a specific installed typeface beyond those portable families.
4. Give every run a `font_size` and exactly one fill: `color` or `gradient`. Colors are
   `#RRGGBB` or `#RRGGBBAA`. A linear gradient needs two to eight strictly increasing stops from
   `0` to `1`; `angle_degrees: 0` reads left-to-right and angles increase clockwise.
5. Use `bold`, `italic`, `underline`, and `strikethrough` only when they support hierarchy or
   meaning. Set `max_width`, `alignment`, `line_spacing`, and `padding` deliberately for multiline
   text. If a word is wider than `max_width`, reduce its font size or increase the width.
6. Supply integer `x` and `y` coordinates for the new layer. Reposition a created text layer with
   `transform_position`; resize/crop it only when the resulting raster text remains legible.
7. Render and visually inspect a preview. Check copy exactly, including numbers, punctuation, and
   Uzbek/Cyrillic characters when applicable; inspect contrast, line breaks, clipping, and optical
   alignment rather than relying only on the layer rectangle.
8. Mark text, prices, logos, and CTAs as critical in `poster_safe_zone_check`. Open the overlay,
   then call `project_validate` before export. Deliver PNG for alpha, JPEG with an explicit
   flattening background, and PSD when the pixel-layer stack is needed.

Use separate runs for a single gradient word:

```json
{
  "name": "Campaign headline",
  "expected_revision": 7,
  "x": 72,
  "y": 128,
  "text": {
    "runs": [
      {"text": "Summer ", "style": {"font_size": 72, "color": "#111827"}},
      {
        "text": "Sale",
        "style": {
          "font_size": 72,
          "bold": true,
          "gradient": {
            "angle_degrees": 0,
            "stops": [
              {"position": 0, "color": "#EC4899"},
              {"position": 1, "color": "#8B5CF6"}
            ]
          }
        }
      }
    ],
    "padding": 4
  }
}
```

Return the created layer ID, position, dimensions, preview/overlay path, exact copy reviewed,
safe-zone result, project revision, export paths, and warnings. State that PSD text is rasterized
when that distinction matters to the user.
