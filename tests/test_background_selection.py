from __future__ import annotations

from pathlib import Path

import pytest
from conftest import FakeEngine

from image_editor_plugin.background_runtime import RuntimeSelectionResult
from image_editor_plugin.errors import EditorError, dependency
from image_editor_plugin.models import AssetRole, ExecutionPolicy, SelectionMethod
from image_editor_plugin.project import ProjectService


class FakeRuntime:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def select_mask(
        self, source: Path, output: Path, execution_policy: ExecutionPolicy
    ) -> RuntimeSelectionResult:
        self.calls += 1
        if self.fail:
            raise dependency("worker failed")
        dimensions = source.read_text(encoding="ascii").split(";", 1)[0]
        output.write_text(dimensions, encoding="ascii")
        return RuntimeSelectionResult(
            runtime_profile="cuda",
            execution_provider="CPUExecutionProvider",
            cpu_fallback=True,
            fallback_reason="provider_failure",
            model_id="isnet-general-use",
            model_sha256="a" * 64,
            elapsed_ms=12,
            warnings=["Local accelerator was unavailable; segmentation completed on CPU."],
        )


def _import_source(
    tmp_path: Path, projects: ProjectService, workspace_id: str
) -> tuple[object, object, str]:
    projects.create(workspace_id, "select.image-work", "Select", 20, 20)
    source_path = tmp_path / "phone.png"
    source_path.write_text("20x20;icc", encoding="ascii")
    source_checksum = source_path.read_bytes()
    manifest, source, _, _ = projects.import_asset(
        workspace_id, "select.image-work", "phone.png", 0
    )
    return manifest, source, source_checksum.hex()


def test_border_selection_and_background_removal_are_atomic_and_immutable(
    tmp_path: Path,
    service: tuple[ProjectService, str],
) -> None:
    projects, workspace_id = service
    manifest, source, original_hex = _import_source(tmp_path, projects, workspace_id)
    result = projects.object_select(
        workspace_id,
        "select.image-work",
        source.id,
        manifest.revision,
        SelectionMethod.AUTO,
        ExecutionPolicy.AUTO,
        None,
        6,
        1,
    )

    assert result.manifest.revision == 2
    assert result.selection.resolved_method is SelectionMethod.BORDER
    assert result.selection.local_inference is True
    assert result.mask_asset.role is AssetRole.SELECTION_MASK
    assert result.selection.execution_provider is None

    removed = projects.background_remove(
        workspace_id,
        "select.image-work",
        source.id,
        result.manifest.revision,
        result.selection.id,
        SelectionMethod.AUTO,
        ExecutionPolicy.AUTO,
        None,
        6,
        1,
        True,
    )
    assert removed.manifest.revision == 3
    assert removed.cutout_asset.has_alpha
    assert removed.layer is not None
    assert (tmp_path / "phone.png").read_bytes().hex() == original_hex
    assert len(removed.manifest.selections) == 1


def test_auto_dispatches_to_local_model_and_records_cpu_fallback(
    tmp_path: Path,
    service: tuple[ProjectService, str],
    engine: FakeEngine,
) -> None:
    projects, workspace_id = service
    manifest, source, _ = _import_source(tmp_path, projects, workspace_id)
    engine.edge_colors = [
        (255, 255, 255),
        (0, 0, 0),
        (255, 0, 0),
        (0, 0, 255),
    ]
    runtime = FakeRuntime()
    projects.background_runtime = runtime  # type: ignore[assignment]

    result = projects.object_select(
        workspace_id,
        "select.image-work",
        source.id,
        manifest.revision,
        SelectionMethod.AUTO,
        ExecutionPolicy.AUTO,
        None,
        6,
        1,
    )

    assert runtime.calls == 1
    assert result.selection.resolved_method is SelectionMethod.LOCAL_MODEL
    assert result.selection.execution_provider == "CPUExecutionProvider"
    assert result.selection.cpu_fallback is True
    assert result.selection.fallback_reason == "provider_failure"
    assert result.operation.deterministic is False


def test_worker_failure_and_revision_conflict_leave_project_unchanged(
    tmp_path: Path,
    service: tuple[ProjectService, str],
    engine: FakeEngine,
) -> None:
    projects, workspace_id = service
    manifest, source, _ = _import_source(tmp_path, projects, workspace_id)
    engine.edge_colors = [
        (255, 255, 255),
        (0, 0, 0),
        (255, 0, 0),
        (0, 0, 255),
    ]
    projects.background_runtime = FakeRuntime(fail=True)  # type: ignore[assignment]

    with pytest.raises(EditorError) as worker_error:
        projects.background_remove(
            workspace_id,
            "select.image-work",
            source.id,
            manifest.revision,
            None,
            SelectionMethod.AUTO,
            ExecutionPolicy.CPU,
            None,
            6,
            1,
            False,
        )
    assert worker_error.value.code == "DEPENDENCY_UNAVAILABLE"
    assert projects.inspect(workspace_id, "select.image-work").revision == manifest.revision

    with pytest.raises(EditorError) as conflict_error:
        projects.object_select(
            workspace_id,
            "select.image-work",
            source.id,
            99,
            SelectionMethod.BORDER,
            ExecutionPolicy.AUTO,
            None,
            6,
            1,
        )
    assert conflict_error.value.code == "CONFLICT"


def test_cutout_failure_cleans_new_mask_and_preserves_manifest(
    tmp_path: Path,
    service: tuple[ProjectService, str],
    engine: FakeEngine,
) -> None:
    projects, workspace_id = service
    manifest, source, _ = _import_source(tmp_path, projects, workspace_id)
    engine.fail_apply = True
    with pytest.raises(RuntimeError, match="mask application"):
        projects.background_remove(
            workspace_id,
            "select.image-work",
            source.id,
            manifest.revision,
            None,
            SelectionMethod.BORDER,
            ExecutionPolicy.AUTO,
            None,
            6,
            1,
            False,
        )
    current = projects.inspect(workspace_id, "select.image-work")
    assert current.revision == manifest.revision
    assert current.selections == []
    project = tmp_path / "select.image-work"
    assert not list((project / "assets" / "derived").iterdir())
