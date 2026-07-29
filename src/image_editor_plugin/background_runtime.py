from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .constants import (
    BACKGROUND_MIN_FREE_DISK_BYTES,
    BACKGROUND_MIN_FREE_MEMORY_BYTES,
    BACKGROUND_MODEL_FILENAME,
    BACKGROUND_MODEL_ID,
    BACKGROUND_MODEL_SHA256,
    BACKGROUND_OPERATION_TIMEOUT_SECONDS,
)
from .errors import EditorError, dependency, resource_limit, selection_failed
from .files import sha256_file
from .models import ExecutionPolicy


@dataclass(frozen=True, slots=True)
class RuntimeSelectionResult:
    runtime_profile: str
    execution_provider: str
    cpu_fallback: bool
    fallback_reason: str | None
    model_id: str
    model_sha256: str
    elapsed_ms: int
    warnings: list[str]


class BackgroundRuntime:
    def __init__(self, cache_root: Path | None = None, worker_path: Path | None = None) -> None:
        self.cache_root = (cache_root or background_cache_root()).resolve()
        self.worker_path = worker_path or Path(__file__).with_name("background_worker.py")

    def preflight(self) -> dict[str, Any]:
        resources = local_resources()
        descriptor = self._descriptor(required=False)
        if descriptor is None:
            return {
                "local_only": True,
                "installed": False,
                "runtime_profile": None,
                "runtime_versions": {"rembg": None, "onnxruntime": None},
                "configured_execution_provider": None,
                "actual_execution_provider": None,
                "registered_providers": [],
                "smoke_tested_execution_providers": [],
                "accelerator_healthy": False,
                "cpu_fallback_healthy": False,
                "model": {
                    "id": BACKGROUND_MODEL_ID,
                    "present": False,
                    "checksum_valid": False,
                },
                "resources": resources,
                "remediation": [background_install_command()],
            }
        runtime_python = self._runtime_python(descriptor)
        model_path = self._model_path(descriptor)
        model_valid = model_path.is_file() and sha256_file(model_path) == BACKGROUND_MODEL_SHA256
        runtime_healthy = runtime_python.is_file()
        configured_provider = str(descriptor["execution_provider"])
        accelerator_probe: dict[str, Any] = {}
        cpu_probe: dict[str, Any] = {}
        resources_sufficient = bool(
            resources["available_memory_bytes"] >= BACKGROUND_MIN_FREE_MEMORY_BYTES
            and resources["temporary_disk_free_bytes"] >= BACKGROUND_MIN_FREE_DISK_BYTES
        )
        if runtime_healthy and model_valid and resources_sufficient:
            policy = "cpu" if configured_provider == "CPUExecutionProvider" else "auto"
            accelerator_probe = self._smoke_probe(descriptor, policy)
            if accelerator_probe.get("execution_provider") == "CPUExecutionProvider":
                cpu_probe = accelerator_probe
            elif accelerator_probe.get("ok"):
                cpu_probe = self._smoke_probe(descriptor, "cpu")
        registered = accelerator_probe.get(
            "registered_providers", descriptor.get("registered_providers", [])
        )
        actual_provider = accelerator_probe.get("execution_provider")
        accelerator_healthy = bool(
            accelerator_probe.get("ok")
            and actual_provider not in {None, "CPUExecutionProvider"}
            and not accelerator_probe.get("cpu_fallback", False)
        )
        cpu_healthy = bool(cpu_probe.get("ok"))
        remediation: list[str] = []
        if not runtime_healthy or not model_valid:
            remediation.append(background_install_command())
        if resources["available_memory_bytes"] < BACKGROUND_MIN_FREE_MEMORY_BYTES:
            remediation.append("Close applications until at least 1.5 GiB of RAM is available.")
        if resources["temporary_disk_free_bytes"] < BACKGROUND_MIN_FREE_DISK_BYTES:
            remediation.append("Free at least 2 GiB in the temporary directory.")
        if resources_sufficient and (not accelerator_probe.get("ok") or not cpu_healthy):
            remediation.append(background_install_command())
        return {
            "local_only": True,
            "installed": runtime_healthy and model_valid,
            "runtime_profile": descriptor["profile"],
            "runtime_versions": {
                "rembg": descriptor.get("rembg_version"),
                "onnxruntime": descriptor.get("onnxruntime_version"),
            },
            "configured_execution_provider": configured_provider,
            "actual_execution_provider": actual_provider,
            "registered_providers": registered,
            "smoke_tested_execution_providers": list(
                dict.fromkeys(
                    str(probe["execution_provider"])
                    for probe in (accelerator_probe, cpu_probe)
                    if probe.get("ok") and probe.get("execution_provider")
                )
            ),
            "accelerator_healthy": accelerator_healthy,
            "cpu_fallback_healthy": cpu_healthy,
            "current_smoke_test": {
                "completed": bool(accelerator_probe.get("ok")),
                "cpu_fallback": bool(accelerator_probe.get("cpu_fallback", False)),
                "fallback_reason": accelerator_probe.get("fallback_reason"),
            },
            "model": {
                "id": BACKGROUND_MODEL_ID,
                "present": model_path.is_file(),
                "checksum_valid": model_valid,
                "sha256": BACKGROUND_MODEL_SHA256,
            },
            "resources": resources,
            "remediation": list(dict.fromkeys(remediation)),
        }

    def select_mask(
        self,
        source: Path,
        output: Path,
        execution_policy: ExecutionPolicy,
    ) -> RuntimeSelectionResult:
        resources = local_resources()
        if resources["available_memory_bytes"] < BACKGROUND_MIN_FREE_MEMORY_BYTES:
            raise resource_limit(
                "Local segmentation requires at least 1.5 GiB of available memory.",
                "Close memory-intensive applications or use border selection.",
            )
        if resources["temporary_disk_free_bytes"] < BACKGROUND_MIN_FREE_DISK_BYTES:
            raise resource_limit(
                "Local segmentation requires at least 2 GiB of free temporary disk.",
                "Free temporary disk space or use border selection.",
            )
        descriptor = self._descriptor(required=True)
        if descriptor is None:
            raise dependency("The local background-removal runtime is not installed.")
        runtime_python = self._runtime_python(descriptor)
        model_path = self._model_path(descriptor)
        if not runtime_python.is_file() or not model_path.is_file():
            raise dependency(
                "The local background-removal runtime is incomplete.", background_install_command()
            )
        if sha256_file(model_path) != BACKGROUND_MODEL_SHA256:
            raise dependency(
                "The local background-removal model failed checksum validation.",
                background_install_command(),
            )
        command = [
            str(runtime_python),
            str(self.worker_path),
            "select",
            "--source",
            str(source),
            "--output",
            str(output),
            "--model-path",
            str(model_path),
            "--model-sha256",
            BACKGROUND_MODEL_SHA256,
            "--profile",
            str(descriptor["profile"]),
            "--policy",
            execution_policy.value,
            "--threads",
            str(resources["worker_threads"]),
        ]
        try:
            completed = subprocess.run(
                command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=BACKGROUND_OPERATION_TIMEOUT_SECONDS,
                check=False,
                env=_worker_environment(),
            )
        except subprocess.TimeoutExpired as exc:
            output.unlink(missing_ok=True)
            raise EditorError(
                "OPERATION_TIMEOUT",
                "Local segmentation exceeded the 115-second operation limit.",
                True,
                ("Retry with CPU policy or use border selection for a clean background.",),
            ) from exc
        except OSError as exc:
            output.unlink(missing_ok=True)
            raise dependency(
                "The local segmentation worker could not be started.",
                background_install_command(),
            ) from exc
        payload = _worker_payload(completed.stdout)
        if completed.returncode != 0 or not payload.get("ok"):
            output.unlink(missing_ok=True)
            code = str(payload.get("code", "DEPENDENCY_UNAVAILABLE"))
            message = str(payload.get("message", "The local segmentation worker failed safely."))
            if code == "RESOURCE_LIMIT":
                raise resource_limit(message, "Retry with CPU policy or a smaller image.")
            if code == "SELECTION_FAILED":
                raise selection_failed(message)
            raise dependency(message, background_install_command())
        if not output.is_file():
            raise dependency("The local segmentation worker produced no mask.")
        return RuntimeSelectionResult(
            runtime_profile=str(payload["runtime_profile"]),
            execution_provider=str(payload["execution_provider"]),
            cpu_fallback=bool(payload.get("cpu_fallback", False)),
            fallback_reason=payload.get("fallback_reason"),
            model_id=BACKGROUND_MODEL_ID,
            model_sha256=BACKGROUND_MODEL_SHA256,
            elapsed_ms=int(payload.get("elapsed_ms", 0)),
            warnings=[str(item) for item in payload.get("warnings", [])],
        )

    def _descriptor(self, *, required: bool) -> dict[str, Any] | None:
        path = self.cache_root / "active.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            if required:
                raise dependency(
                    "The local background-removal runtime is not installed.",
                    background_install_command(),
                ) from exc
            return None
        if not isinstance(value, dict):
            if required:
                raise dependency("The local background-removal runtime descriptor is invalid.")
            return None
        runtime_dir = value.get("runtime_dir")
        if not isinstance(runtime_dir, str) or not re.fullmatch(
            r"runtime-[0-9a-f-]{36}", runtime_dir
        ):
            if required:
                raise dependency("The local background-removal runtime descriptor is invalid.")
            return None
        profile = value.get("profile")
        provider = value.get("execution_provider")
        if profile not in {"cpu", "cuda", "directml", "openvino"} or not isinstance(provider, str):
            if required:
                raise dependency("The local background-removal runtime descriptor is invalid.")
            return None
        return {str(key): item for key, item in value.items()}

    def _runtime_python(self, descriptor: dict[str, Any]) -> Path:
        runtime = _child(self.cache_root, str(descriptor["runtime_dir"]))
        relative = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        return _child(runtime, relative)

    def _model_path(self, descriptor: dict[str, Any]) -> Path:
        runtime = _child(self.cache_root, str(descriptor["runtime_dir"]))
        return _child(runtime, f"models/{BACKGROUND_MODEL_FILENAME}")

    def _smoke_probe(self, descriptor: dict[str, Any], policy: str) -> dict[str, Any]:
        runtime = _child(self.cache_root, str(descriptor["runtime_dir"]))
        source = _child(runtime, "smoke.png")
        if not source.is_file():
            return {"ok": False, "fallback_reason": "smoke_input_missing"}
        with tempfile.NamedTemporaryFile(
            dir=self.cache_root,
            prefix=".preflight-mask-",
            suffix=".png",
            delete=False,
        ) as handle:
            output = Path(handle.name)
        command = [
            str(self._runtime_python(descriptor)),
            str(self.worker_path),
            "select",
            "--source",
            str(source),
            "--output",
            str(output),
            "--model-path",
            str(self._model_path(descriptor)),
            "--model-sha256",
            BACKGROUND_MODEL_SHA256,
            "--profile",
            str(descriptor["profile"]),
            "--policy",
            policy,
            "--threads",
            str(local_resources()["worker_threads"]),
        ]
        try:
            completed = subprocess.run(
                command,
                shell=False,
                capture_output=True,
                text=True,
                timeout=BACKGROUND_OPERATION_TIMEOUT_SECONDS,
                check=False,
                env=_worker_environment(),
            )
            payload = _worker_payload(completed.stdout)
            payload["ok"] = completed.returncode == 0 and bool(payload.get("ok"))
            return payload
        except (OSError, subprocess.TimeoutExpired):
            return {"ok": False, "fallback_reason": "smoke_probe_failed"}
        finally:
            output.unlink(missing_ok=True)


def background_cache_root() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "image-editor-plugin" / "background-removal"
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "image-editor-plugin" / "background-removal"


def background_install_command() -> str:
    return "image-editor-background-model install isnet-general-use --profile auto"


def local_resources() -> dict[str, int]:
    logical = max(1, os.cpu_count() or 1)
    return {
        "logical_cpu_count": logical,
        "worker_threads": max(1, min(4, logical // 2)),
        "available_memory_bytes": _available_memory(),
        "temporary_disk_free_bytes": shutil.disk_usage(tempfile.gettempdir()).free,
    }


def _available_memory() -> int:
    if os.name == "nt":

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(MemoryStatus)
        windll = cast(Any, ctypes).windll
        if windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.available_physical)
    if hasattr(os, "sysconf"):
        try:
            return int(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
        except (ValueError, OSError):
            pass
    return BACKGROUND_MIN_FREE_MEMORY_BYTES


def _child(root: Path, relative: str) -> Path:
    candidate = root.joinpath(*Path(relative).parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise dependency("The local background-removal runtime path is unsafe.") from exc
    return candidate


def _worker_environment() -> dict[str, str]:
    allowed = {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "HOME",
        "LANG",
        "LC_ALL",
        "LD_LIBRARY_PATH",
    }
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment.pop("MODEL_CHECKSUM_DISABLED", None)
    environment["PYTHONNOUSERSITE"] = "1"
    return environment


def _worker_payload(stdout: str) -> dict[str, Any]:
    try:
        value = json.loads(stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}
