# Project format

Each project is a `<name>.image-work/` directory:

```text
manifest.json
assets/imported/<sha256>.<extension>
assets/derived/<operation-hash>.png
assets/generated/<sha256>.<extension>
previews/
exports/
.staging/
logs/
```

`manifest.json` is generated from the authoritative Pydantic model and records schema/plugin
versions, project revision, 8-bit sRGB canvas settings, immutable assets, bottom-to-top
pixel layers, append-only operations, AI conversations, and exports with checksums and
provenance.

Generated assets include provider, resolved model, operation, prompt, input/mask IDs,
sanitized provider request ID, conversation ID, parent assets, non-secret parameters, and
timestamp. Conversations contain ordered turns and the provider session identifier needed
for native continuity. API keys and authorization headers are never project data.

The checked-in schema is [project-manifest.schema.json](../schemas/project-manifest.schema.json).
Derived identity hashes the input checksum, resolved parameters, engine name, and engine version.
