# Local object selection and background removal

## Privacy boundary

`object_select` and `background_remove` are local-only. Runtime paths do not call provider APIs,
upload media, or emit telemetry. The explicit installer may download fixed packages and the pinned
model; installed inference can run with outbound networking disabled.

## Setup and profiles

```powershell
image-editor-background-model install isnet-general-use --profile auto
```

Accepted profiles are `auto`, `cpu`, `cuda`, `directml`, and `openvino`. Auto probes CUDA on
compatible NVIDIA Windows/Linux hosts, DirectML on Windows, OpenVINO on Intel Windows/Linux, then
CPU. Every candidate is staged in an isolated virtual environment and activated only after model
checksum verification and real smoke inference. One ONNX Runtime distribution is installed:

| Profile | Package | Version | Provider |
|---|---|---:|---|
| CPU | `onnxruntime` | 1.27.0 | `CPUExecutionProvider` |
| CUDA | `onnxruntime-gpu` | 1.27.0 | `CUDAExecutionProvider` |
| DirectML | `onnxruntime-directml` | 1.24.4 | `DmlExecutionProvider` |
| OpenVINO | `onnxruntime-openvino` | 1.24.1 | `OpenVINOExecutionProvider` |

The worker uses managed Python 3.12. Its numerical dependency stack is pinned to NumPy 2.3.5,
PyMatting 1.1.15, Numba 0.66.0, and llvmlite 0.48.0 so package resolution cannot select an
obsolete llvmlite source release on newer host Python versions. NumPy remains on the 2.3 line
because its Linux wheels retain the older x86 baseline needed by legacy CPUs and virtual machines.

The pinned `rembg==2.0.77` model is `isnet-general-use`; its SHA-256 is
`60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a`. AMD Linux ROCm is not a
promised profile because that ONNX Runtime provider is deprecated/removed. AMD Windows may use
DirectML; unsupported systems use CPU.

## Runtime policy

- `auto`: use the installed accelerator when available and retry recoverable initialization,
  driver, device-loss, or OOM failures once on CPU.
- `cpu`: use only `CPUExecutionProvider`.
- `accelerator`: require the non-CPU provider and return an error on failure.

Partial failed outputs are discarded. Model/input/output validation failures are not retried.
Each attempt is a `shell=False` subprocess bounded to 115 seconds and half the logical CPUs,
clamped to 1-4 threads. Preflight checks RAM, temporary disk, runtime/model files and checksum,
registered providers, and the installed smoke-tested profile.

## Selection semantics

`method=auto` samples the perimeter. Three corners must agree and at least 90% of perimeter samples
must match within `tolerance_percent`. ImageMagick flood-fills only background connected to the
border. Foreground coverage must be 5-95%; otherwise the local model produces a soft grayscale
mask. A fixed one-pixel close and requested feathering are applied without changing dimensions.

`object_select` commits a mask and immutable selection in one revision. `background_remove` either
uses a compatible selection or atomically creates the selection, mask, cutout, operation, and
optional layer. Cutout alpha is `original alpha × selection mask`; source RGB, alpha, file, and
checksum remain unchanged.

Stable failures are `INVALID_ARGUMENT`, `NOT_FOUND`, `CONFLICT`, `DEPENDENCY_UNAVAILABLE`,
`RESOURCE_LIMIT`, `OPERATION_TIMEOUT`, and `SELECTION_FAILED`.

References: [ONNX Runtime execution providers](https://onnxruntime.ai/docs/execution-providers/),
[Python runtime packages](https://onnxruntime.ai/docs/get-started/with-python.html), and
[ROCm provider status](https://onnxruntime.ai/docs/execution-providers/ROCm-ExecutionProvider.html).
