from __future__ import annotations

from pathlib import Path

import pytest

from image_editor_plugin.errors import EditorError
from image_editor_plugin.security import WorkspaceRegistry


def test_registration_rejects_filesystem_root() -> None:
    registry = WorkspaceRegistry()
    with pytest.raises(EditorError, match="roots"):
        registry.register(str(Path.cwd().anchor))


@pytest.mark.parametrize(
    "unsafe",
    [
        "../secret.png",
        "folder/../../secret.png",
        "C:\\Windows\\file.png",
        "\\\\server\\share\\file.png",
        "NUL.png",
        "image.png:stream",
        "https://example.test/image.png",
    ],
)
def test_path_resolution_rejects_unsafe_syntax(tmp_path: Path, unsafe: str) -> None:
    registry = WorkspaceRegistry()
    workspace_id, _ = registry.register(str(tmp_path))
    with pytest.raises(EditorError):
        registry.resolve(workspace_id, unsafe)


def test_unregistered_workspace_is_rejected(tmp_path: Path) -> None:
    registry = WorkspaceRegistry()
    with pytest.raises(EditorError) as caught:
        registry.resolve("wsp_unknown", "image.png")
    assert caught.value.code == "WORKSPACE_NOT_REGISTERED"


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    link = tmp_path / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks is not permitted on this host")
    registry = WorkspaceRegistry()
    workspace_id, _ = registry.register(str(tmp_path))
    with pytest.raises(EditorError) as caught:
        registry.resolve(workspace_id, "escape/file.png")
    assert caught.value.code == "PATH_OUTSIDE_WORKSPACE"
