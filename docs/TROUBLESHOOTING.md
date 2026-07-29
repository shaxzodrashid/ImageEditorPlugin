# Troubleshooting

## `DEPENDENCY_UNAVAILABLE`

Run `system_preflight`. Install ImageMagick 7 externally and confirm `magick -version`
lists PNG, JPEG, and LCMS delegates. Restart the Codex session afterward.

For complex-scene background removal, run the exact remediation under
`outputs.background_removal`, normally:

```powershell
image-editor-background-model install isnet-general-use --profile auto
```

Installation may use the network. Selection/removal is offline afterward. Use `--profile cpu`,
`cuda`, `directml`, or `openvino` only when deliberately selecting a profile.

## `RESOURCE_LIMIT` or `OPERATION_TIMEOUT`

Close memory-intensive programs, free at least 2 GiB of temporary disk, or use `method: border`
for a clean background. Local model attempts are limited to 115 seconds and 1-4 worker threads.

## Accelerator fallback warning

The accelerator became unavailable, lost its driver/device, or exhausted memory. Under
`execution_policy: auto`, partial output was discarded and one CPU retry completed. Inspect the
actual provider and sanitized reason. Use `accelerator` when fallback must be forbidden.

## `ENGINE_FAILED`

Use the returned remediation to distinguish an unsupported decoder, damaged input, or
resource exhaustion. Raw ImageMagick stderr remains private, but common failure classes
are translated into safe, actionable hints.

## `WORKSPACE_NOT_REGISTERED`

Call `workspace_register` again. Registrations are intentionally session-local.

## `CONFLICT`

Call `project_inspect`, reconsider the pending operation against the current manifest,
then retry with the returned revision.

## Image search returns `CONFIGURATION_ERROR`

Confirm `OPENAI_API_KEY` exists in the environment that launches Codex, then fully restart Codex
and start a fresh task. Never pass the key as an `image_search` argument.

## Image search returns no usable results

Broaden the query, remove restrictive domain filters, enable live web access, or choose a compatible
Responses model. An empty result set is successful and includes a warning; a missing search call or
invalid provider response returns `PROVIDER_REJECTED`.

## `PROJECT_INVALID`

Do not edit `manifest.json` manually. Run `project_validate`, inspect missing or modified
assets, and restore the project from a known-good copy if necessary.

## Plugin changes are not visible

Reinstall `image-editor@image-editor-local` and start a fresh thread. Skills and MCP tool
catalogs are loaded at session start.
