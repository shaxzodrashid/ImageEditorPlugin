---
name: image-deliver
description: Preview, validate, and export deterministic Image Editor projects as PNG or JPEG. Use when delivering final image artifacts, checking provenance and checksums, preserving PNG alpha, or flattening transparency into an explicit JPEG background.
---

# Image Deliver

1. Inspect the project and render a preview without mutating its revision.
2. Call `project_validate`. Do not export a project with manifest, path, or checksum issues.
3. Choose the format deliberately:
   - PNG for lossless output and alpha.
   - JPEG for compact photographic delivery.
4. For JPEG, specify a flattening background, resolved quality, and metadata policy. Never imply JPEG preserves transparency.
5. Use workspace-relative output paths. Do not set `overwrite: true` unless the user explicitly authorizes replacement.
6. Pass the current revision to the export. A successful export increments the revision and records checksum and provenance.
7. Re-run project inspection or validation after all exports when multiple formats are delivered.

Return paths, formats, dimensions, checksums, JPEG background/quality/subsampling, metadata policy, warnings, and validation status.
