from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ValidationError

from .errors import EditorError
from .models import ErrorDetail, ToolEnvelope


def run_enveloped(action: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = perf_counter()
    try:
        payload = action()
        envelope = ToolEnvelope(ok=True, duration_ms=_elapsed(started), **payload)
    except EditorError as exc:
        envelope = ToolEnvelope(
            ok=False,
            duration_ms=_elapsed(started),
            error=ErrorDetail(
                code=exc.code,
                message=exc.safe_message,
                retryable=exc.retryable,
                remediation=list(exc.remediation),
            ),
        )
    except ValidationError:
        envelope = ToolEnvelope(
            ok=False,
            duration_ms=_elapsed(started),
            error=ErrorDetail(
                code="INVALID_ARGUMENT",
                message="The request contains an invalid value.",
                retryable=False,
                remediation=["Review the tool schema and correct the rejected field."],
            ),
        )
    except Exception:
        envelope = ToolEnvelope(
            ok=False,
            duration_ms=_elapsed(started),
            error=ErrorDetail(
                code="INTERNAL_ERROR",
                message="The image operation failed safely.",
                retryable=False,
                remediation=["Check the server log and run project_validate before retrying."],
            ),
        )
    return envelope.model_dump(mode="json")


def dump(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    return value.model_dump(mode="json") if isinstance(value, BaseModel) else value


def _elapsed(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
