from __future__ import annotations

import os
import re
from pathlib import Path, PurePath

from .errors import EditorError, invalid
from .ids import IdProvider, new_id

_WINDOWS_DEVICE = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.IGNORECASE)


class WorkspaceRegistry:
    """Session-local allowlist of roots; registrations are intentionally not persisted."""

    def __init__(self, id_provider: IdProvider = new_id) -> None:
        self._roots: dict[str, Path] = {}
        self._id_provider = id_provider

    def register(self, root: str) -> tuple[str, Path]:
        candidate = Path(root).expanduser()
        if not candidate.is_absolute():
            raise invalid("Workspace root must be an absolute path.")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_dir():
            raise invalid("Workspace root must be an existing directory.")
        if resolved.parent == resolved:
            raise invalid("Filesystem roots cannot be registered.")
        workspace_id = self._id_provider("wsp")
        self._roots[workspace_id] = resolved
        return workspace_id, resolved

    def root(self, workspace_id: str) -> Path:
        try:
            return self._roots[workspace_id]
        except KeyError as exc:
            raise EditorError(
                "WORKSPACE_NOT_REGISTERED",
                "The workspace is not registered in this MCP session.",
                False,
                ("Call workspace_register with the intended root.",),
            ) from exc

    def resolve(
        self,
        workspace_id: str,
        relative_path: str,
        *,
        must_exist: bool = False,
        allow_project_suffix: bool = True,
    ) -> Path:
        root = self.root(workspace_id)
        self._validate_relative(relative_path)
        lexical = root.joinpath(*PurePath(relative_path).parts)
        if must_exist:
            try:
                resolved = lexical.resolve(strict=True)
            except FileNotFoundError as exc:
                raise EditorError("NOT_FOUND", "The requested path does not exist.") from exc
        else:
            existing = lexical
            remainder: list[str] = []
            while not existing.exists() and existing != root:
                remainder.insert(0, existing.name)
                existing = existing.parent
            resolved = existing.resolve(strict=True).joinpath(*remainder)
        if not _is_within(resolved, root):
            raise EditorError(
                "PATH_OUTSIDE_WORKSPACE", "The path escapes the registered workspace."
            )
        if not allow_project_suffix and resolved.name.endswith(".image-work"):
            raise invalid("This path type is not accepted here.")
        return resolved

    @staticmethod
    def _validate_relative(value: str) -> None:
        if not value or "\x00" in value:
            raise invalid("A non-empty workspace-relative path is required.")
        path = PurePath(value)
        if path.is_absolute() or Path(value).drive or value.startswith(("\\\\", "//")):
            raise invalid("Absolute, UNC, and device paths are not allowed.")
        for part in path.parts:
            if part in {"", ".", ".."}:
                raise invalid("Path traversal is not allowed.")
            trimmed = part.rstrip(" .")
            if not trimmed or _WINDOWS_DEVICE.match(trimmed):
                raise invalid("Reserved device path components are not allowed.")
        if ":" in value:
            raise invalid("Protocol and alternate-stream syntax is not allowed.")


def relative_to_root(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([path, root]) == str(root)
    except ValueError:
        return False
