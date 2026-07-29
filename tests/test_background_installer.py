from __future__ import annotations

import json
import struct
import subprocess
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from image_editor_plugin import background_model_cli as installer


def test_smoke_png_is_structurally_valid() -> None:
    data = installer.SMOKE_PNG
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    compressed = bytearray()
    width = height = color_type = None
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        checksum = struct.unpack(">I", data[offset + 8 + length : offset + 12 + length])[0]
        assert zlib.crc32(chunk_type + payload) & 0xFFFFFFFF == checksum
        if chunk_type == b"IHDR":
            width, height, _, color_type = struct.unpack(">IIBB", payload[:10])
        elif chunk_type == b"IDAT":
            compressed.extend(payload)
        offset += 12 + length
    assert (width, height, color_type) == (8, 8, 2)
    assert len(zlib.decompress(compressed)) == 8 * (1 + 8 * 3)


def test_profile_install_uses_fixed_index_versions_and_one_onnx_distribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if "find" in command:
            return subprocess.CompletedProcess(command, 0, str(tmp_path / "python.exe"), "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(installer.subprocess, "run", run)
    installer._install_profile("uv", tmp_path / "runtime", "directml")
    assert calls[0][-1] == "3.12"
    assert calls[1][1:4] == ["-m", "venv", "--copies"]
    install_command = calls[2]
    assert "https://pypi.org/simple" in install_command
    assert "rembg==2.0.77" in install_command
    assert "onnxruntime-directml==1.24.4" in install_command
    assert "numpy==2.3.5" in install_command
    assert "pymatting==1.1.15" in install_command
    assert "numba==0.66.0" in install_command
    assert "llvmlite==0.48.0" in install_command
    assert sum(item.startswith("onnxruntime") for item in install_command) == 1


def test_profile_install_reports_sanitized_dependency_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(
                command, 0, str(tmp_path / "python.exe"), ""
            )
        if calls == 2:
            return subprocess.CompletedProcess(command, 0, "", "")
        raise subprocess.CalledProcessError(
            1,
            command,
            output="",
            stderr="No matching distribution found for the requested package",
        )

    monkeypatch.setattr(installer.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="package_install_dependency_incompatible"):
        installer._install_profile("uv", tmp_path / "runtime", "cpu")


def test_hash_rejection_removes_staged_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self) -> list[bytes]:
            return [b"wrong-model"]

    class Stream:
        def __enter__(self) -> Response:
            return Response()

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(installer.httpx, "stream", lambda *args, **kwargs: Stream())
    with pytest.raises(RuntimeError, match="SHA-256"):
        installer._download_model(tmp_path)
    assert not list((tmp_path / "downloads").glob("*.tmp"))


def test_failed_smoke_preserves_previous_runtime_and_cleans_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    previous = {"runtime_dir": "runtime-00000000-0000-0000-0000-000000000001"}
    (tmp_path / "active.json").write_text(json.dumps(previous), encoding="utf-8")
    model = tmp_path / "download.onnx"
    model.write_bytes(b"model")
    monkeypatch.setattr(
        installer,
        "local_resources",
        lambda: {"temporary_disk_free_bytes": installer.BACKGROUND_MIN_FREE_DISK_BYTES + 1},
    )
    monkeypatch.setattr(installer.shutil, "disk_usage", lambda path: SimpleNamespace(free=10**12))
    monkeypatch.setattr(installer.shutil, "which", lambda name: "uv")
    monkeypatch.setattr(installer, "_download_model", lambda cache: model)

    def staged_install(uv: str, runtime: Path, profile: str) -> None:
        runtime.mkdir(parents=True)

    monkeypatch.setattr(installer, "_install_profile", staged_install)
    monkeypatch.setattr(
        installer,
        "_smoke",
        lambda runtime, profile: (_ for _ in ()).throw(RuntimeError("smoke failed")),
    )

    with pytest.raises(RuntimeError, match="smoke failed"):
        installer.install_runtime("cpu", tmp_path)
    assert json.loads((tmp_path / "active.json").read_text(encoding="utf-8")) == previous
    assert not [path for path in tmp_path.glob("runtime-*") if path.is_dir()]


def test_insufficient_disk_stops_before_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        installer,
        "local_resources",
        lambda: {"temporary_disk_free_bytes": installer.BACKGROUND_MIN_FREE_DISK_BYTES - 1},
    )
    with pytest.raises(RuntimeError, match="2 GiB"):
        installer.install_runtime("cpu", tmp_path)
