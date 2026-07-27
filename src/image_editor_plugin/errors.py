from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EditorError(Exception):
    code: str
    safe_message: str
    retryable: bool = False
    remediation: tuple[str, ...] = ()

    def __str__(self) -> str:
        return self.safe_message


def invalid(message: str, *remediation: str) -> EditorError:
    return EditorError("INVALID_ARGUMENT", message, False, remediation)


def not_found(message: str) -> EditorError:
    return EditorError("NOT_FOUND", message)


def conflict(message: str) -> EditorError:
    return EditorError(
        "CONFLICT", message, True, ("Inspect the project and retry with its revision.",)
    )


def configuration(message: str, *remediation: str) -> EditorError:
    return EditorError("CONFIGURATION_ERROR", message, False, remediation)


def unsupported(message: str, *remediation: str) -> EditorError:
    return EditorError("UNSUPPORTED_FEATURE", message, False, remediation)
