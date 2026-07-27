from __future__ import annotations

import base64
from typing import Any

import pytest

from image_editor_plugin.errors import EditorError
from image_editor_plugin.models import (
    AIImageOptions,
    AIModelId,
    AIOutputFormat,
    AIResolution,
)
from image_editor_plugin.providers.base import ProviderImage, ProviderResponse
from image_editor_plugin.providers.fal import FalImageAdapter
from image_editor_plugin.providers.google import GoogleImageAdapter
from image_editor_plugin.providers.openai import OpenAIImageAdapter


class FakeHttp:
    def __init__(self, responses: list[ProviderResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def post_json(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> ProviderResponse:
        self.calls.append(("json", url, {"headers": headers, "payload": payload}))
        return self.responses.pop(0)

    def post_multipart(
        self,
        url: str,
        headers: dict[str, str],
        fields: dict[str, str],
        files: list[tuple[str, tuple[str, bytes, str]]],
    ) -> ProviderResponse:
        self.calls.append(
            (
                "multipart",
                url,
                {"headers": headers, "fields": fields, "files": files},
            )
        )
        return self.responses.pop(0)

    def get_bytes(self, url: str, allowed_hosts: frozenset[str]) -> tuple[bytes, str]:
        self.calls.append(("get", url, {"allowed_hosts": sorted(allowed_hosts)}))
        return b"remote-image", "image/png"


def encoded(value: bytes = b"image") -> str:
    return base64.b64encode(value).decode("ascii")


def test_openai_generation_maps_unified_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-value")
    http = FakeHttp(
        [
            ProviderResponse(
                {"data": [{"b64_json": encoded(), "revised_prompt": "refined"}]},
                {"request-id": "req_123"},
            )
        ]
    )
    adapter = OpenAIImageAdapter(http)
    result = adapter.generate(
        AIModelId.GPT_IMAGE_2,
        "A studio product photo",
        AIImageOptions(
            width=1024,
            height=1024,
            quality="high",
            output_format=AIOutputFormat.PNG,
        ),
    )

    _, url, call = http.calls[0]
    assert url.endswith("/v1/images/generations")
    assert call["payload"]["model"] == "gpt-image-2"
    assert call["payload"]["size"] == "1024x1024"
    assert call["payload"]["quality"] == "high"
    assert result.request_id == "req_123"
    assert result.revised_prompt == "refined"
    assert result.images[0].data == b"image"


def test_missing_credential_fails_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    http = FakeHttp([])
    adapter = OpenAIImageAdapter(http)
    with pytest.raises(EditorError) as caught:
        adapter.generate(AIModelId.GPT_IMAGE_2, "A safe prompt", AIImageOptions())
    assert caught.value.code == "CONFIGURATION_ERROR"
    assert "OPENAI_API_KEY" not in caught.value.safe_message
    assert http.calls == []


def test_google_native_continuation_uses_interaction_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-value")
    http = FakeHttp(
        [
            ProviderResponse(
                {
                    "id": "interaction_2",
                    "steps": [
                        {
                            "type": "model_output",
                            "content": [
                                {
                                    "type": "image",
                                    "mime_type": "image/png",
                                    "data": encoded(),
                                }
                            ],
                        }
                    ],
                },
                {},
            )
        ]
    )
    adapter = GoogleImageAdapter(http)
    result = adapter.edit(
        AIModelId.NANO_BANANA_2,
        "Keep everything but translate the headline",
        [],
        AIImageOptions(resolution=AIResolution.TWO_K, aspect_ratio="16:9"),
        previous_request_id="interaction_1",
    )

    payload = http.calls[0][2]["payload"]
    assert payload["previous_interaction_id"] == "interaction_1"
    assert payload["input"].startswith("Keep everything")
    assert payload["response_format"]["image_size"] == "2K"
    assert result.request_id == "interaction_2"


def test_fal_seedream_and_qwen_use_sync_data_uris(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAL_KEY", "test-fal-key-value")
    data_uri = f"data:image/png;base64,{encoded()}"
    http = FakeHttp(
        [
            ProviderResponse({"images": [{"url": data_uri}]}, {}),
            ProviderResponse(
                {
                    "images": [{"url": data_uri}, {"url": data_uri}],
                    "seed": 42,
                },
                {},
            ),
        ]
    )
    adapter = FalImageAdapter(http)
    generated = adapter.generate(
        AIModelId.SEEDREAM_5_PRO,
        "Campaign visual",
        AIImageOptions(output_format="png"),
    )
    decomposed = adapter.decompose(
        AIModelId.QWEN_IMAGE_LAYERED,
        ProviderImage(b"source", "image/png", "source.png"),
        {
            "prompt": "Separate the subject",
            "negative_prompt": "",
            "num_inference_steps": 28,
            "guidance_scale": 5.0,
            "num_layers": 2,
            "safety_filter": True,
            "seed": 42,
        },
    )

    generation_payload = http.calls[0][2]["payload"]
    layered_payload = http.calls[1][2]["payload"]
    assert generation_payload["sync_mode"] is True
    assert generation_payload["image_size"] == "auto_2K"
    assert layered_payload["image_url"].startswith("data:image/png;base64,")
    assert layered_payload["num_layers"] == 2
    assert len(generated.images) == 1
    assert len(decomposed.images) == 2
    assert decomposed.metadata["seed"] == 42


def test_grok_is_generation_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAL_KEY", "test-fal-key-value")
    adapter = FalImageAdapter(FakeHttp([]))
    with pytest.raises(EditorError) as caught:
        adapter.edit(
            AIModelId.GROK_IMAGINE,
            "Change it",
            [ProviderImage(b"x", "image/png", "x.png")],
            AIImageOptions(),
        )
    assert caught.value.code == "UNSUPPORTED_FEATURE"
