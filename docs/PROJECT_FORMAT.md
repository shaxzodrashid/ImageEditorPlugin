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
pixel layers, immutable selections, append-only operations, AI conversations, and exports with
checksums and provenance. Schema `1.3.0` adds PSD to the export-format enum while retaining the
prior `1.2.0` selection and asset-role fields.

Each selection links one immutable source asset to a same-dimension grayscale mask asset. It
records the requested/resolved method, execution policy, installed runtime profile, provider
actually used, fallback status/reason, local model ID/hash, elapsed time, foreground bounds and
coverage, and safe parameters. Applying a selection never modifies the source: output alpha is
the original alpha multiplied by the selection mask.

Generated assets include provider, resolved model, operation, prompt, input/mask IDs,
sanitized provider request ID, conversation ID, parent assets, non-secret parameters, and
timestamp. Conversations contain ordered turns and the provider session identifier needed
for native continuity. API keys and authorization headers are never project data.

The checked-in schema is [project-manifest.schema.json](../schemas/project-manifest.schema.json).
Derived identity hashes the input checksum, resolved parameters, engine name, and engine version.

PSD delivery exports retain the current canonical raster-layer stack: each layer name, order,
integer position (including negative offsets), opacity, visibility, and alpha are written as a PSD
pixel layer. A nontransparent canvas background is written as a bottom `Canvas Background` pixel
layer. The PSD record stores `layered: true`, the actual `backend`, `validation`, and an optional
`native_fallback_from` only after the staged file is structurally reopened. The required portable
backend is `psd-tools` with `validation: psd-tools-roundtrip`; optional PhotoshopAPI acceleration
is child-process-only and may fall back safely. It never represents native text, smart objects,
groups, layer masks, filters, non-normal blending, or PSB; those features are not silently
flattened into a PSD. PSD records also do not attest to native Adobe Photoshop or third-party-reader
compatibility.

Normal previews use `preview-r<revision>.png`. Safe-zone reviews use
`safe-zone-r<revision>-t<top>-r<right>-b<bottom>-l<left>.png`. Both are derived, replaceable views that do not increment
the manifest revision and are not delivery exports. Safe-zone reports are returned to the caller;
they are not persisted as manifest approval because final semantic approval requires AI visual
inspection of that exact preview.
