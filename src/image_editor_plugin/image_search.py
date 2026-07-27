from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .constants import MAX_IMAGE_SEARCH_QUERY_CHARACTERS
from .errors import EditorError, invalid
from .models import (
    ImageSearchCitation,
    ImageSearchOptions,
    ImageSearchResult,
)
from .providers.base import ProviderHttp
from .providers.utils import require_credential, safe_request_id

_RESPONSES_URL = "https://api.openai.com/v1/responses"


@dataclass(frozen=True, slots=True)
class ImageSearchResponse:
    model: str
    request_id: str | None
    results: tuple[ImageSearchResult, ...]
    summary: str | None
    citations: tuple[ImageSearchCitation, ...]
    warnings: tuple[str, ...]


class OpenAIImageSearchService:
    def __init__(self, http: ProviderHttp) -> None:
        self._http = http

    def search(self, query: str, options: ImageSearchOptions) -> ImageSearchResponse:
        normalized_query = query.strip()
        if not normalized_query:
            raise invalid("Image search query must not be empty.")
        if len(normalized_query) > MAX_IMAGE_SEARCH_QUERY_CHARACTERS:
            raise invalid(
                "Image search query must not exceed "
                f"{MAX_IMAGE_SEARCH_QUERY_CHARACTERS:,} characters."
            )

        key = require_credential(("OPENAI_API_KEY",), "OpenAI")
        tool: dict[str, Any] = {
            "type": "web_search",
            "search_content_types": (
                ["image", "text"] if options.include_supporting_text else ["image"]
            ),
            "image_settings": {
                "max_results": options.max_results,
                "caption": options.caption,
            },
            "search_context_size": options.search_context_size.value,
            "external_web_access": options.live_web_access,
        }
        if options.allowed_domains or options.blocked_domains:
            tool["filters"] = {
                **(
                    {"allowed_domains": options.allowed_domains}
                    if options.allowed_domains
                    else {}
                ),
                **(
                    {"blocked_domains": options.blocked_domains}
                    if options.blocked_domains
                    else {}
                ),
            }
        if options.location is not None:
            tool["user_location"] = {
                "type": "approximate",
                **options.location.model_dump(mode="json", exclude_none=True),
            }

        response = self._http.post_json(
            _RESPONSES_URL,
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            {
                "model": options.model,
                "tools": [tool],
                "tool_choice": "required",
                "include": ["web_search_call.results"],
                "input": normalized_query,
            },
        )
        return _parse_response(response.body, response.headers, options)


def _parse_response(
    body: dict[str, Any], headers: dict[str, str], options: ImageSearchOptions
) -> ImageSearchResponse:
    output = body.get("output")
    if not isinstance(output, list):
        raise EditorError("PROVIDER_REJECTED", "OpenAI returned an invalid search response.")

    saw_search_call = False
    results: list[ImageSearchResult] = []
    summary_parts: list[str] = []
    citations: list[ImageSearchCitation] = []
    warnings: list[str] = []
    seen_images: set[str] = set()
    seen_citations: set[str] = set()

    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "web_search_call":
            saw_search_call = True
            raw_results = item.get("results")
            if not isinstance(raw_results, list):
                continue
            for raw in raw_results:
                if not isinstance(raw, dict) or raw.get("type") != "image_result":
                    continue
                parsed = _parse_image_result(raw)
                if parsed is None:
                    warnings.append(
                        "OpenAI returned an image result with invalid or incomplete URLs."
                    )
                    continue
                if parsed.image_url in seen_images:
                    continue
                seen_images.add(parsed.image_url)
                results.append(parsed)
                if len(results) >= options.max_results:
                    break
        elif options.include_supporting_text and item.get("type") == "message":
            _parse_message(item, summary_parts, citations, seen_citations)

    if not saw_search_call:
        raise EditorError("PROVIDER_REJECTED", "OpenAI did not execute the requested image search.")
    if not results:
        warnings.append("The search completed but returned no usable image results.")

    model = body.get("model")
    return ImageSearchResponse(
        model=model if isinstance(model, str) and model else options.model,
        request_id=safe_request_id(headers.get("request-id")),
        results=tuple(results),
        summary="\n".join(summary_parts) or None,
        citations=tuple(citations),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _parse_image_result(value: dict[str, Any]) -> ImageSearchResult | None:
    image_url = _safe_https_url(value.get("image_url"))
    source_url = _safe_https_url(value.get("source_website_url"))
    if image_url is None or source_url is None:
        return None
    thumbnail_url = _safe_https_url(value.get("thumbnail_url"))
    caption = value.get("caption")
    safe_caption = caption.strip()[:2_000] if isinstance(caption, str) and caption.strip() else None
    return ImageSearchResult(
        image_url=image_url,
        source_website_url=source_url,
        thumbnail_url=thumbnail_url,
        caption=safe_caption,
    )


def _parse_message(
    item: dict[str, Any],
    summary_parts: list[str],
    citations: list[ImageSearchCitation],
    seen_citations: set[str],
) -> None:
    content = item.get("content")
    if not isinstance(content, list):
        return
    for part in content:
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            summary_parts.append(text.strip())
        annotations = part.get("annotations")
        if not isinstance(annotations, list):
            continue
        for annotation in annotations:
            if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                continue
            url = _safe_https_url(annotation.get("url"))
            if url is None or url in seen_citations:
                continue
            title = annotation.get("title")
            citations.append(
                ImageSearchCitation(
                    url=url,
                    title=title.strip()[:1_000]
                    if isinstance(title, str) and title.strip()
                    else None,
                )
            )
            seen_citations.add(url)


def _safe_https_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 8_192:
        return None
    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    return candidate
