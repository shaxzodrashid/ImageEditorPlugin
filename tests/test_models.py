from __future__ import annotations

import pytest
from pydantic import ValidationError

from image_editor_plugin.models import Canvas, ErrorDetail, ToolEnvelope


def test_canvas_enforces_pixel_limit() -> None:
    with pytest.raises(ValidationError, match="100 million"):
        Canvas(width=20_000, height=20_000)


def test_response_envelope_status_matches_error() -> None:
    success = ToolEnvelope(ok=True, duration_ms=0)
    failure = ToolEnvelope(
        ok=False,
        duration_ms=1,
        error=ErrorDetail(code="CONFLICT", message="stale", retryable=True),
    )
    assert success.job_id is None
    assert failure.error is not None
    with pytest.raises(ValidationError):
        ToolEnvelope(ok=True, duration_ms=0, error=failure.error)
