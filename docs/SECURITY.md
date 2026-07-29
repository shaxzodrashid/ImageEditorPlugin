# Security model

- Files are inaccessible until `workspace_register` authorizes an existing non-root directory.
- Project tools accept only workspace-relative paths.
- Traversal, absolute/UNC/device paths, alternate streams, symlink escapes, and protocols are
  rejected.
- Inputs are limited to 100 MiB compressed, 100 million decoded pixels, and 32,768 pixels
  per dimension.
- Projects are limited to 1,024 assets and 256 layers.
- ImageMagick receives an internal argument array with `shell=False`; callers cannot provide
  an executable, switches, protocols, or shell fragments.
- Engine limits are 1 GiB memory, 2 GiB map, 4 GiB temporary disk, two threads, and 120 seconds.
- Background inference runs in an isolated pinned worker with `shell=False`, a sanitized
  environment, 1-4 threads, RAM/disk checks, and a 115-second timeout per attempt.
- Selection inference is local-only. It has no provider API or image-upload path and resolves the
  verified local model without downloading at runtime. Only the explicit setup may use network.
- The installer accepts fixed profiles/model, versions, index, URL, and SHA-256; it stages,
  smoke-tests, and atomically activates a runtime while retaining the prior healthy runtime.
- Only one ONNX Runtime distribution exists per worker. Under `auto`, recoverable accelerator
  failures discard partial output and retry once on CPU; `accelerator` never silently falls back.
- Existing exports require explicit overwrite authorization.
- Mutations use a project lock, expected revision, staging, and atomic manifest replacement.
- Responses and logs do not expose subprocess command lines, environment variables, or raw
  engine stderr.
- Provider endpoints and Fal media-download hosts are hardcoded allowlists; tools cannot
  supply URLs, base URLs, headers, or executable paths.
- Provider credentials are read from allowlisted environment names at call time. Preflight
  returns booleans only; keys never enter prompts, responses, provenance, or logs.
- Provider-returned images are size-bounded, decoded, inspected, media-type checked, staged,
  and committed only if the expected project revision still matches.
- AI tools are non-idempotent and do not automatically retry POST requests, avoiding duplicate
  paid generations after an ambiguous network failure.
- `image_search` is read-only but open-world. It sends only the caller's query and declared search
  options to OpenAI, requires HTTPS result/source URLs, strips malformed records, and never returns
  authorization headers or the raw provider response.
- Search results are remote references, not trusted or licensed assets. The plugin does not fetch,
  decode, import, or execute content from result URLs; callers must review source pages and rights
  before a separately authorized download/import workflow.
