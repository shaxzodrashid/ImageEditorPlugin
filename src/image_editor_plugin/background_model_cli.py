from __future__ import annotations

import argparse
import base64
import json
import os
import platform
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

from .background_runtime import background_cache_root, local_resources
from .constants import (
    BACKGROUND_MIN_FREE_DISK_BYTES,
    BACKGROUND_MODEL_FILENAME,
    BACKGROUND_MODEL_ID,
    BACKGROUND_MODEL_MAX_BYTES,
    BACKGROUND_MODEL_SHA256,
    BACKGROUND_MODEL_URL,
    BACKGROUND_RUNTIME_VERSIONS,
)
from .files import atomic_write_json, sha256_file

REMBG_VERSION = "2.0.77"
WORKER_PYTHON_VERSION = "3.12"
# rembg's alpha-matting dependency leaves NumPy/Numba effectively unconstrained. Without these
# pins, uv can prefer a newer NumPy and backtrack to numba 0.53.1, whose metadata does not declare
# its real Python upper bound. That produces an attempted source build which fails on modern
# Python even though compatible wheels exist for the pinned stack below.
NUMERICAL_STACK = (
    "numpy==2.4.6",
    "pymatting==1.1.15",
    "numba==0.66.0",
    "llvmlite==0.48.0",
)
SMOKE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFElEQVR4nGP8z8DAwMDAxMDAwMAAAAwAAf4CB0kAAAAASUVORK5CYII="
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the local background-removal runtime.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    install = subparsers.add_parser("install")
    install.add_argument("model", choices=[BACKGROUND_MODEL_ID])
    install.add_argument(
        "--profile", choices=["auto", *BACKGROUND_RUNTIME_VERSIONS], default="auto"
    )
    args = parser.parse_args()
    if args.command == "install":
        descriptor = install_runtime(args.profile)
        print(json.dumps(descriptor, indent=2))


def install_runtime(profile: str, cache_root: Path | None = None) -> dict[str, object]:
    cache = (cache_root or background_cache_root()).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    if (
        local_resources()["temporary_disk_free_bytes"] < BACKGROUND_MIN_FREE_DISK_BYTES
        or shutil.disk_usage(cache).free < BACKGROUND_MIN_FREE_DISK_BYTES
    ):
        raise RuntimeError("At least 2 GiB of free temporary disk is required.")
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required to create the isolated local runtime.")
    model_download = _download_model(cache)
    failures: list[str] = []
    for candidate in _profiles(profile):
        runtime_name = f"runtime-{uuid4()}"
        runtime = cache / runtime_name
        try:
            _install_profile(uv, runtime, candidate)
            models = runtime / "models"
            models.mkdir()
            shutil.copyfile(model_download, models / BACKGROUND_MODEL_FILENAME)
            smoke = _smoke(runtime, candidate)
            descriptor: dict[str, object] = {
                "runtime_dir": runtime_name,
                "profile": candidate,
                "onnxruntime_package": BACKGROUND_RUNTIME_VERSIONS[candidate][0],
                "onnxruntime_version": BACKGROUND_RUNTIME_VERSIONS[candidate][1],
                "rembg_version": REMBG_VERSION,
                "execution_provider": smoke["execution_provider"],
                "registered_providers": smoke.get("registered_providers", []),
                "model_id": BACKGROUND_MODEL_ID,
                "model_sha256": BACKGROUND_MODEL_SHA256,
                "local_only": True,
                "installed_at": datetime.now(UTC).isoformat(),
            }
            atomic_write_json(cache / "active.json", descriptor)
            return descriptor
        except Exception as exc:
            failures.append(f"{candidate}: {_failure_code(exc)}")
            _remove_owned_runtime(cache, runtime)
            if profile != "auto":
                raise
    raise RuntimeError("No local runtime profile passed its smoke test: " + ", ".join(failures))


def _profiles(requested: str) -> list[str]:
    if requested != "auto":
        return [requested]
    candidates: list[str] = []
    if platform.system() in {"Windows", "Linux"} and shutil.which("nvidia-smi"):
        candidates.append("cuda")
    if _windows_10_or_newer():
        candidates.append("directml")
    if platform.system() in {"Windows", "Linux"} and _intel_hardware_present():
        candidates.append("openvino")
    candidates.append("cpu")
    return list(dict.fromkeys(candidates))


def _intel_hardware_present() -> bool:
    if platform.system() == "Linux" and shutil.which("lspci"):
        result = subprocess.run(
            ["lspci"], shell=False, capture_output=True, text=True, timeout=10, check=False
        )
        lowered = result.stdout.casefold()
        return "intel" in lowered and any(item in lowered for item in ("vga", "display", "3d"))
    if platform.system() == "Windows":
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-CimInstance Win32_PnPEntity | Select-Object -ExpandProperty Name",
            ],
            shell=False,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        lowered = result.stdout.casefold()
        return "intel" in lowered and any(
            item in lowered for item in ("graphics", "display", "npu", "ai boost")
        )
    return False


def _windows_10_or_newer() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        return int(platform.release().split(".", 1)[0]) >= 10
    except ValueError:
        return False


def _install_profile(uv: str, runtime: Path, profile: str) -> None:
    _run_install_step(
        [uv, "venv", "--python", WORKER_PYTHON_VERSION, str(runtime)],
        timeout=180,
        phase="environment_creation",
    )
    python = _runtime_python(runtime)
    package, version = BACKGROUND_RUNTIME_VERSIONS[profile]
    _run_install_step(
        [
            uv,
            "--no-config",
            "pip",
            "install",
            "--python",
            str(python),
            "--index-url",
            "https://pypi.org/simple",
            f"rembg=={REMBG_VERSION}",
            f"{package}=={version}",
            *NUMERICAL_STACK,
        ],
        timeout=600,
        phase="package_install",
    )


def _run_install_step(command: list[str], *, timeout: int, phase: str) -> None:
    try:
        subprocess.run(
            command,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = f"{exc.stdout or ''}\n{exc.stderr or ''}".casefold()
        reason = (
            "dependency_incompatible"
            if any(
                marker in detail
                for marker in (
                    "cannot install on python version",
                    "no solution found",
                    "no matching distribution",
                    "requirements are unsatisfiable",
                )
            )
            else "command_failed"
        )
        raise RuntimeError(f"{phase}_{reason}") from exc


def _failure_code(exc: Exception) -> str:
    message = str(exc)
    if re.fullmatch(
        r"(?:environment_creation|package_install)_(?:dependency_incompatible|command_failed)",
        message,
    ):
        return message
    if "smoke" in message.casefold():
        return "smoke_inference_failed"
    return type(exc).__name__


def _download_model(cache: Path) -> Path:
    downloads = cache / "downloads"
    downloads.mkdir(exist_ok=True)
    destination = downloads / BACKGROUND_MODEL_FILENAME
    if destination.is_file() and sha256_file(destination) == BACKGROUND_MODEL_SHA256:
        return destination
    stage = downloads / f".{BACKGROUND_MODEL_FILENAME}.{uuid4()}.tmp"
    try:
        total = 0
        with httpx.stream(
            "GET",
            BACKGROUND_MODEL_URL,
            follow_redirects=True,
            timeout=httpx.Timeout(15, read=120),
            headers={"User-Agent": "image-editor-plugin-model-installer/0.4.1"},
        ) as response:
            response.raise_for_status()
            with stage.open("wb") as output:
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > BACKGROUND_MODEL_MAX_BYTES:
                        raise RuntimeError("The model download exceeded the 512 MiB limit.")
                    output.write(chunk)
        if sha256_file(stage) != BACKGROUND_MODEL_SHA256:
            raise RuntimeError("The model download failed SHA-256 verification.")
        os.replace(stage, destination)
        return destination
    finally:
        stage.unlink(missing_ok=True)


def _smoke(runtime: Path, profile: str) -> dict[str, object]:
    source = runtime / "smoke.png"
    output = runtime / "smoke-mask.png"
    source.write_bytes(SMOKE_PNG)
    worker = Path(__file__).with_name("background_worker.py")
    policy = "cpu" if profile == "cpu" else "accelerator"
    command = [
        str(_runtime_python(runtime)),
        str(worker),
        "select",
        "--source",
        str(source),
        "--output",
        str(output),
        "--model-path",
        str(runtime / "models" / BACKGROUND_MODEL_FILENAME),
        "--model-sha256",
        BACKGROUND_MODEL_SHA256,
        "--profile",
        profile,
        "--policy",
        policy,
        "--threads",
        "1",
    ]
    result = subprocess.run(
        command,
        shell=False,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env=_installer_worker_environment(),
    )
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError("The local runtime smoke test returned invalid output.") from exc
    if result.returncode != 0 or not payload.get("ok") or not output.is_file():
        raise RuntimeError("The local runtime smoke inference failed.")
    if not isinstance(payload, dict):
        raise RuntimeError("The local runtime smoke test returned invalid output.")
    return {str(key): value for key, value in payload.items()}


def _runtime_python(runtime: Path) -> Path:
    return runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _installer_worker_environment() -> dict[str, str]:
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
    result = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    result["PYTHONNOUSERSITE"] = "1"
    return result


def _remove_owned_runtime(cache: Path, runtime: Path) -> None:
    resolved = runtime.resolve()
    resolved.relative_to(cache)
    if resolved.name.startswith("runtime-"):
        shutil.rmtree(resolved, ignore_errors=True)


if __name__ == "__main__":
    main()
