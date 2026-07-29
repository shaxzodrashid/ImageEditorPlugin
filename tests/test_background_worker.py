from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from image_editor_plugin import background_worker


class FakeSession:
    def __init__(self, providers: list[Any]) -> None:
        names = [item[0] if isinstance(item, tuple) else item for item in providers]
        self.inner_session = SimpleNamespace(get_providers=lambda: names)


def _install_fake_modules(
    monkeypatch: pytest.MonkeyPatch,
    available: list[str],
    fail_accelerator: str | None = None,
) -> list[list[Any]]:
    calls: list[list[Any]] = []
    ort = ModuleType("onnxruntime")
    ort.SessionOptions = type("SessionOptions", (), {})  # type: ignore[attr-defined]
    ort.ExecutionMode = SimpleNamespace(ORT_SEQUENTIAL="sequential")  # type: ignore[attr-defined]
    ort.get_available_providers = lambda: available  # type: ignore[attr-defined]

    rembg = ModuleType("rembg")

    def new_session(
        model: str, *, sess_opts: object, providers: list[Any]
    ) -> FakeSession:
        calls.append(providers)
        first = providers[0][0] if isinstance(providers[0], tuple) else providers[0]
        if first != "CPUExecutionProvider" and fail_accelerator:
            raise RuntimeError(fail_accelerator)
        return FakeSession(providers)

    rembg.new_session = new_session  # type: ignore[attr-defined]
    rembg.remove = lambda *args, **kwargs: b"\x89PNG\r\n\x1a\nmask"  # type: ignore[attr-defined]
    sessions = ModuleType("rembg.sessions")
    general = ModuleType("rembg.sessions.dis_general_use")
    general.DisSession = type("DisSession", (), {})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "onnxruntime", ort)
    monkeypatch.setitem(sys.modules, "rembg", rembg)
    monkeypatch.setitem(sys.modules, "rembg.sessions", sessions)
    monkeypatch.setitem(sys.modules, "rembg.sessions.dis_general_use", general)
    return calls


def _args(tmp_path: Path, policy: str, profile: str = "cuda") -> argparse.Namespace:
    source = tmp_path / "source.png"
    model = tmp_path / "model.onnx"
    source.write_bytes(b"source")
    model.write_bytes(b"model")
    return argparse.Namespace(
        source=str(source),
        output=str(tmp_path / "mask.png"),
        model_path=str(model),
        model_sha256="expected",
        profile=profile,
        policy=policy,
        threads=2,
    )


@pytest.mark.parametrize(
    ("failure", "reason"),
    [("CUDA driver failed", "driver_unavailable"), ("CUDA out of memory", "out_of_memory")],
)
def test_auto_accelerator_failure_retries_once_on_cpu(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    reason: str,
) -> None:
    calls = _install_fake_modules(
        monkeypatch,
        ["CUDAExecutionProvider", "CPUExecutionProvider"],
        failure,
    )
    monkeypatch.setattr(background_worker, "_sha256", lambda path: "expected")
    result = background_worker._select(_args(tmp_path, "auto"))
    assert calls == [
        ["CUDAExecutionProvider", "CPUExecutionProvider"],
        ["CPUExecutionProvider"],
    ]
    assert result["execution_provider"] == "CPUExecutionProvider"
    assert result["cpu_fallback"] is True
    assert result["fallback_reason"] == reason


def test_accelerator_policy_never_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_modules(
        monkeypatch,
        ["CUDAExecutionProvider", "CPUExecutionProvider"],
        "device lost",
    )
    monkeypatch.setattr(background_worker, "_sha256", lambda path: "expected")
    with pytest.raises(RuntimeError, match="device lost"):
        background_worker._select(_args(tmp_path, "accelerator"))
    assert calls == [["CUDAExecutionProvider"]]


def test_cpu_policy_uses_only_cpu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_modules(
        monkeypatch,
        ["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    monkeypatch.setattr(background_worker, "_sha256", lambda path: "expected")
    result: dict[str, Any] = background_worker._select(_args(tmp_path, "cpu"))
    assert calls == [["CPUExecutionProvider"]]
    assert result["cpu_fallback"] is False


def test_openvino_uses_fixed_automatic_intel_device_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_modules(
        monkeypatch,
        ["OpenVINOExecutionProvider", "CPUExecutionProvider"],
    )
    monkeypatch.setattr(background_worker, "_sha256", lambda path: "expected")
    result = background_worker._select(_args(tmp_path, "accelerator", "openvino"))
    assert calls == [
        [("OpenVINOExecutionProvider", {"device_type": "AUTO"})]
    ]
    assert result["execution_provider"] == "OpenVINOExecutionProvider"
