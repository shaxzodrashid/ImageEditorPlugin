---
name: image-compose
description: Assemble deterministic layered PNG/JPEG compositions in Image Editor projects. Use for banners, overlays, collages, or multi-image layouts requiring ordered pixel layers, normal alpha compositing, explicit positions, and reproducible previews.
---

# Image Compose

1. Run `system_preflight`, register the workspace, and inspect or create the project.
2. Inspect every source before layout. Import sources once and reuse their content-addressed assets.
3. Add layers bottom-to-top. `layer_add` and `composite_overlay` always place the new layer at the top.
4. Resolve every placement to integer `x` and `y` coordinates from the canvas top-left.
5. Use only normal blend mode and opacity from `0` to `1`; advanced blending is outside this MVP.
6. Use crop/resize tools for geometry rather than relying on clipping side effects.
7. Carry the returned revision into the next mutation. If a revision conflicts, re-inspect before continuing.
8. Render a bounded preview after meaningful layout changes. Inspect it before delivery.
9. Call `project_validate` before export.

Communicate the final layer order, canvas dimensions, clipped content risk, preview path, and warnings.
