from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from image_editor_plugin import background_model_cli as installer


def test_profile_install_uses_fixed_index_versions_and_one_onnx_distribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(installer.subprocess, "run", run)
    installer._install_profile("uv", tmp_path / "runtime", "directml")
    install_command = calls[1]
    assert "https://pypi.org/simple" in install_command
    assert "rembg==2.0.77" in install_command
    assert "onnxruntime-directml==1.24.4" in install_command
    assert sum(item.startswith("onnxruntime") for item in install_command) == 1


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
