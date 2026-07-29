from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any

MODEL_ID = "isnet-general-use"
PROFILE_PROVIDERS = {
    "cpu": "CPUExecutionProvider",
    "cuda": "CUDAExecutionProvider",
    "directml": "DmlExecutionProvider",
    "openvino": "OpenVINOExecutionProvider",
}


class WorkerValidationError(Exception):
    pass


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("action", choices=["select"])
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--profile", choices=tuple(PROFILE_PROVIDERS), required=True)
    parser.add_argument("--policy", choices=("auto", "cpu", "accelerator"), required=True)
    parser.add_argument("--threads", type=int, choices=range(1, 5), required=True)
    args = parser.parse_args()
    started = perf_counter()
    try:
        result = _select(args)
        result.update(ok=True, elapsed_ms=max(0, round((perf_counter() - started) * 1000)))
        _emit(result, 0)
    except MemoryError:
        _emit(
            {
                "ok": False,
                "code": "RESOURCE_LIMIT",
                "message": "The local segmentation worker exhausted available memory.",
            },
            2,
        )
    except WorkerValidationError:
        _emit(
            {
                "ok": False,
                "code": "SELECTION_FAILED",
                "message": "The local segmentation input or output failed validation.",
            },
            2,
        )
    except Exception as exc:
        code = (
            "RESOURCE_LIMIT"
            if _failure_reason(exc) == "out_of_memory"
            else "DEPENDENCY_UNAVAILABLE"
        )
        _emit(
            {
                "ok": False,
                "code": code,
                "message": "The local segmentation runtime could not complete inference.",
            },
            2,
        )


def _select(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.source)
    output = Path(args.output)
    model_path = Path(args.model_path)
    if not source.is_file() or not model_path.is_file():
        raise WorkerValidationError
    if _sha256(model_path) != args.model_sha256:
        raise WorkerValidationError

    os.environ.pop("MODEL_CHECKSUM_DISABLED", None)
    os.environ["OMP_NUM_THREADS"] = str(args.threads)
    os.environ["U2NET_HOME"] = str(model_path.parent)

    import onnxruntime as ort  # type: ignore[import-not-found]
    from rembg import new_session, remove  # type: ignore[import-not-found]
    from rembg.sessions.dis_general_use import (  # type: ignore[import-not-found]
        DisSession,
    )

    DisSession.download_models = classmethod(lambda cls, *unused, **ignored: str(model_path))

    available = ort.get_available_providers()
    configured = PROFILE_PROVIDERS[args.profile]
    accelerator = configured if configured != "CPUExecutionProvider" else None
    fallback = False
    fallback_reason: str | None = None

    if args.policy == "cpu":
        requested = ["CPUExecutionProvider"]
    elif accelerator is None or accelerator not in available:
        if args.policy == "accelerator":
            raise RuntimeError("accelerator unavailable")
        requested = ["CPUExecutionProvider"]
        fallback = accelerator is not None
        fallback_reason = "provider_unavailable" if fallback else None
    else:
        requested = [accelerator]
        if args.policy == "auto":
            requested.append("CPUExecutionProvider")

    try:
        data, used = _infer(source, new_session, remove, requested, ort, args.profile)
    except Exception as exc:
        if args.policy != "auto" or requested == ["CPUExecutionProvider"]:
            raise
        fallback = True
        fallback_reason = _failure_reason(exc)
        data, used = _infer(
            source, new_session, remove, ["CPUExecutionProvider"], ort, args.profile
        )

    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise WorkerValidationError
    output.write_bytes(data)
    warnings = []
    if fallback:
        warnings.append("Local accelerator was unavailable; segmentation completed on CPU.")
    return {
        "runtime_profile": args.profile,
        "execution_provider": used,
        "registered_providers": available,
        "cpu_fallback": fallback,
        "fallback_reason": fallback_reason,
        "model_id": MODEL_ID,
        "warnings": warnings,
    }


def _infer(
    source: Path,
    new_session: Any,
    remove: Any,
    providers: list[str],
    ort: Any,
    profile: str,
) -> tuple[bytes, str]:
    options = ort.SessionOptions()
    if profile == "directml" and "DmlExecutionProvider" in providers:
        options.enable_mem_pattern = False
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session_providers: list[Any] = list(providers)
    if profile == "openvino" and providers[0] == "OpenVINOExecutionProvider":
        session_providers[0] = (
            "OpenVINOExecutionProvider",
            {"device_type": "AUTO"},
        )
    session = new_session(MODEL_ID, sess_opts=options, providers=session_providers)
    result = remove(
        source.read_bytes(),
        session=session,
        only_mask=True,
        post_process_mask=False,
        force_return_bytes=True,
    )
    if not isinstance(result, bytes):
        raise WorkerValidationError
    registered = session.inner_session.get_providers()
    used = providers[0] if providers[0] in registered else "CPUExecutionProvider"
    return result, used


def _failure_reason(exc: Exception) -> str:
    lowered = str(exc).casefold()
    if any(marker in lowered for marker in ("out of memory", "cuda_error_out_of_memory", "oom")):
        return "out_of_memory"
    if any(marker in lowered for marker in ("dll", "shared object", "cudnn", "cuda")):
        return "driver_unavailable"
    return "provider_failure"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _emit(payload: dict[str, Any], status: int) -> None:
    print(json.dumps(payload, separators=(",", ":")))
    raise SystemExit(status)


if __name__ == "__main__":
    main()
