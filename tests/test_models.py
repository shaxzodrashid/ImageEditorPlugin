from __future__ import annotations

import pytest
from pydantic import ValidationError

from image_editor_plugin.models import Canvas, ErrorDetail, RichTextLayerOptions, ToolEnvelope


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


def test_rich_text_rejects_ambiguous_or_unordered_gradient_fills() -> None:
    with pytest.raises(ValidationError, match="choose either"):
        RichTextLayerOptions.model_validate(
            {
                "runs": [
                    {
                        "text": "Sale",
                        "style": {
                            "color": "#FFFFFF",
                            "gradient": {
                                "stops": [
                                    {"position": 0, "color": "#FF0000"},
                                    {"position": 1, "color": "#0000FF"},
                                ]
                            },
                        },
                    }
                ]
            }
        )
    with pytest.raises(ValidationError, match="strictly increasing"):
        RichTextLayerOptions.model_validate(
            {
                "runs": [
                    {
                        "text": "Sale",
                        "style": {
                            "gradient": {
                                "stops": [
                                    {"position": 0.8, "color": "#FF0000"},
                                    {"position": 0.2, "color": "#0000FF"},
                                ]
                            }
                        },
                    }
                ]
            }
        )
