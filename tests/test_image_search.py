from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from image_editor_plugin.errors import EditorError
from image_editor_plugin.image_search import OpenAIImageSearchService
from image_editor_plugin.models import ImageSearchLocation, ImageSearchOptions
from image_editor_plugin.providers.base import ProviderResponse


class FakeHttp:
    def __init__(self, response: ProviderResponse | None = None) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    def post_json(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> ProviderResponse:
        self.calls.append((url, headers, payload))
        if self.response is None:
            raise AssertionError("Unexpected network call")
        return self.response

    def post_multipart(
        self,
        url: str,
        headers: dict[str, str],
        fields: dict[str, str],
        files: list[tuple[str, tuple[str, bytes, str]]],
    ) -> ProviderResponse:
        raise AssertionError("Image search must not use multipart requests")

    def get_bytes(self, url: str, allowed_hosts: frozenset[str]) -> tuple[bytes, str]:
        raise AssertionError("Image search must not download third-party images")


def test_image_search_maps_openai_contract_and_parses_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-value")
    http = FakeHttp(
        ProviderResponse(
            {
                "model": "gpt-5.6-2026-07-01",
                "output": [
                    {
                        "type": "web_search_call",
                        "status": "completed",
                        "results": [
                            {
                                "type": "image_result",
                                "image_url": "https://images.example/photo.jpg",
                                "thumbnail_url": "https://images.example/thumb.jpg",
                                "source_website_url": "https://example.com/photo",
                                "caption": "  Example photo  ",
                            },
                            {
                                "type": "image_result",
                                "image_url": "https://images.example/photo.jpg",
                                "source_website_url": "https://example.com/duplicate",
                            },
                        ],
                    },
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Supporting context.",
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "url": "https://example.com/photo",
                                        "title": "Example source",
                                    }
                                ],
                            }
                        ],
                    },
                ],
            },
            {"request-id": "req_search_123"},
        )
    )
    service = OpenAIImageSearchService(http)

    result = service.search(
        "  Golden Gate Bridge at sunset  ",
        ImageSearchOptions(
            max_results=3,
            allowed_domains=["Example.COM."],
            blocked_domains=["ads.example"],
            location=ImageSearchLocation(country="uz", city="Tashkent"),
        ),
    )

    url, headers, payload = http.calls[0]
    assert url == "https://api.openai.com/v1/responses"
    assert headers["Authorization"].startswith("Bearer ")
    assert "test-openai-key-value" not in repr(payload)
    assert payload["input"] == "Golden Gate Bridge at sunset"
    assert payload["tool_choice"] == "required"
    assert payload["include"] == ["web_search_call.results"]
    tool = payload["tools"][0]
    assert tool["type"] == "web_search"
    assert tool["search_content_types"] == ["image", "text"]
    assert tool["image_settings"] == {"max_results": 3, "caption": True}
    assert tool["filters"] == {
        "allowed_domains": ["example.com"],
        "blocked_domains": ["ads.example"],
    }
    assert tool["user_location"] == {
        "type": "approximate",
        "country": "UZ",
        "city": "Tashkent",
    }
    assert result.model == "gpt-5.6-2026-07-01"
    assert result.request_id == "req_search_123"
    assert len(result.results) == 1
    assert result.results[0].caption == "Example photo"
    assert result.summary == "Supporting context."
    assert result.citations[0].url == "https://example.com/photo"


def test_image_search_can_request_images_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-value")
    http = FakeHttp(
        ProviderResponse(
            {"output": [{"type": "web_search_call", "status": "completed", "results": []}]},
            {},
        )
    )
    result = OpenAIImageSearchService(http).search(
        "brand reference",
        ImageSearchOptions(
            include_supporting_text=False,
            caption=False,
            live_web_access=False,
        ),
    )
    tool = http.calls[0][2]["tools"][0]
    assert tool["search_content_types"] == ["image"]
    assert tool["external_web_access"] is False
    assert result.results == ()
    assert result.warnings == ("The search completed but returned no usable image results.",)


def test_image_search_skips_unsafe_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-value")
    http = FakeHttp(
        ProviderResponse(
            {
                "output": [
                    {
                        "type": "web_search_call",
                        "results": [
                            {
                                "type": "image_result",
                                "image_url": "http://insecure.example/image.png",
                                "source_website_url": "https://example.com/source",
                            },
                            {
                                "type": "image_result",
                                "image_url": "https://user:pass@example.com/image.png",
                                "source_website_url": "https://example.com/source",
                            },
                        ],
                    }
                ]
            },
            {},
        )
    )
    result = OpenAIImageSearchService(http).search("test", ImageSearchOptions())
    assert result.results == ()
    assert len(result.warnings) == 2


def test_missing_search_credential_fails_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    http = FakeHttp()
    with pytest.raises(EditorError) as caught:
        OpenAIImageSearchService(http).search("test", ImageSearchOptions())
    assert caught.value.code == "CONFIGURATION_ERROR"
    assert http.calls == []


def test_missing_web_search_call_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key-value")
    http = FakeHttp(ProviderResponse({"output": [{"type": "message", "content": []}]}, {}))
    with pytest.raises(EditorError) as caught:
        OpenAIImageSearchService(http).search("test", ImageSearchOptions())
    assert caught.value.code == "PROVIDER_REJECTED"


@pytest.mark.parametrize(
    "domain",
    ["https://example.com", "example.com/path", "*.example.com", "localhost", "example.com:443"],
)
def test_domain_filters_reject_non_hostnames(domain: str) -> None:
    with pytest.raises(ValidationError):
        ImageSearchOptions(allowed_domains=[domain])


def test_domain_filters_reject_overlap() -> None:
    with pytest.raises(ValidationError):
        ImageSearchOptions(allowed_domains=["example.com"], blocked_domains=["EXAMPLE.COM"])
