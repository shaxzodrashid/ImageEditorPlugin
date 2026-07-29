---
name: image-deliver
description: Preview, validate, and export deterministic Image Editor projects as PNG or JPEG. Use when delivering final image artifacts, checking provenance and checksums, preserving PNG alpha, or flattening transparency into an explicit JPEG background.
---

# Image Deliver

1. Inspect the project and render a preview without mutating its revision.
2. For posters, carousels, ads, thumbnails, and social graphics, call
   `poster_safe_zone_check` before export. Use the supplied 1080×1350 template's default scaled
   top/right/bottom/left margins (64/65/70/65 px) unless the platform or brief specifies a uniform
   exact `margin_pixels` value.
3. Supply only critical foreground layer IDs (text, logos, prices, faces, and calls to action) to
   `critical_layer_ids`; do not treat background or intentional full-bleed decoration as a
   violation. For a flattened poster, omit the list and rely on visual review.
4. Open and visually inspect the returned overlay. `geometry_passed: true` is not final approval;
   do not approve while critical content intersects the red perimeter.
5. Call `project_validate`. Do not export a project with manifest, path, or checksum issues.
6. Choose the format deliberately:
   - PNG for lossless output and alpha.
   - JPEG for compact photographic delivery.
7. For JPEG, specify a flattening background, resolved quality, and metadata policy. Never imply JPEG preserves transparency.
8. Use workspace-relative output paths. Do not set `overwrite: true` unless the user explicitly authorizes replacement.
9. Pass the current revision to the export. A successful export increments the revision and records checksum and provenance.
10. Re-run project inspection or validation after all exports when multiple formats are delivered.

Return preview and export paths, safe-zone bounds/status, reviewed critical content, formats,
dimensions, checksums, JPEG background/quality/subsampling, metadata policy, warnings, and
validation status.
