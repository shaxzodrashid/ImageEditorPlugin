from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from image_editor_plugin.models import AIImageOptions, AIModelId, AIProviderId


@dataclass(frozen=True, slots=True)
class ProviderImage:
    data: bytes
    mime_type: str
    filename: str


@dataclass(frozen=True, slots=True)
class ProviderResult:
    images: tuple[ProviderImage, ...]
    request_id: str | None = None
    revised_prompt: str | None = None
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    body: dict[str, Any]
    headers: dict[str, str]


class ProviderHttp(Protocol):
    def post_json(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> ProviderResponse: ...

    def post_multipart(
        self,
        url: str,
        headers: dict[str, str],
        fields: dict[str, str],
        files: list[tuple[str, tuple[str, bytes, str]]],
    ) -> ProviderResponse: ...

    def get_bytes(self, url: str, allowed_hosts: frozenset[str]) -> tuple[bytes, str]: ...


class ImageProviderAdapter(Protocol):
    provider_id: AIProviderId

    def generate(
        self, model: AIModelId, prompt: str, options: AIImageOptions
    ) -> ProviderResult: ...

    def edit(
        self,
        model: AIModelId,
        prompt: str,
        images: list[ProviderImage],
        options: AIImageOptions,
        *,
        mask: ProviderImage | None = None,
        previous_request_id: str | None = None,
    ) -> ProviderResult: ...

    def decompose(
        self,
        model: AIModelId,
        image: ProviderImage,
        options: dict[str, Any],
    ) -> ProviderResult: ...
