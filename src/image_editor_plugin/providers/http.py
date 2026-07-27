from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from image_editor_plugin.constants import (
    AI_OPERATION_TIMEOUT_SECONDS,
    MAX_COMPRESSED_INPUT_BYTES,
)
from image_editor_plugin.errors import EditorError

from .base import ProviderResponse


class HttpProviderClient:
    def __init__(self, timeout_seconds: float = AI_OPERATION_TIMEOUT_SECONDS) -> None:
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
        )

    def post_json(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> ProviderResponse:
        try:
            response = self._client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise EditorError(
                "PROVIDER_UNAVAILABLE",
                "The image provider timed out.",
                True,
                ("Retry the operation; provider requests are not retried automatically.",),
            ) from exc
        except httpx.HTTPError as exc:
            raise EditorError(
                "PROVIDER_UNAVAILABLE",
                "The image provider could not be reached.",
                True,
            ) from exc
        return _decode_response(response)

    def post_multipart(
        self,
        url: str,
        headers: dict[str, str],
        fields: dict[str, str],
        files: list[tuple[str, tuple[str, bytes, str]]],
    ) -> ProviderResponse:
        try:
            response = self._client.post(url, headers=headers, data=fields, files=files)
        except httpx.TimeoutException as exc:
            raise EditorError(
                "PROVIDER_UNAVAILABLE",
                "The image provider timed out.",
                True,
                ("Retry the operation; provider requests are not retried automatically.",),
            ) from exc
        except httpx.HTTPError as exc:
            raise EditorError(
                "PROVIDER_UNAVAILABLE",
                "The image provider could not be reached.",
                True,
            ) from exc
        return _decode_response(response)

    def get_bytes(self, url: str, allowed_hosts: frozenset[str]) -> tuple[bytes, str]:
        parsed = urlparse(url)
        host = (parsed.hostname or "").casefold()
        if (
            parsed.scheme != "https"
            or not host
            or not any(host == item or host.endswith(f".{item}") for item in allowed_hosts)
        ):
            raise EditorError(
                "PROVIDER_REJECTED",
                "The provider returned an image URL outside its approved media hosts.",
            )
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EditorError(
                "PROVIDER_UNAVAILABLE",
                "A generated image could not be downloaded from the provider.",
                True,
            ) from exc
        if len(response.content) > MAX_COMPRESSED_INPUT_BYTES:
            raise EditorError(
                "RESOURCE_LIMIT",
                "A generated image exceeded the 100 MiB compressed-size limit.",
            )
        return response.content, response.headers.get("content-type", "application/octet-stream")


def _decode_response(response: httpx.Response) -> ProviderResponse:
    request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
    if response.status_code >= 400:
        retryable = response.status_code in {408, 409, 429} or response.status_code >= 500
        code = "PROVIDER_UNAVAILABLE" if retryable else "PROVIDER_REJECTED"
        message = (
            "The image provider is temporarily unavailable or rate limited."
            if retryable
            else "The image provider rejected the request."
        )
        remediation = (
            ("Retry later or choose a different provider.",)
            if retryable
            else ("Review the prompt, model capabilities, and provider account access.",)
        )
        raise EditorError(code, message, retryable, remediation)
    try:
        body = response.json()
    except ValueError as exc:
        raise EditorError(
            "PROVIDER_REJECTED",
            "The image provider returned an invalid response.",
            False,
        ) from exc
    if not isinstance(body, dict):
        raise EditorError("PROVIDER_REJECTED", "The image provider response was not an object.")
    headers = {"request-id": request_id} if request_id else {}
    return ProviderResponse(body=body, headers=headers)
