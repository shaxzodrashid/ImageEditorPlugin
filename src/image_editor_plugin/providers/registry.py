from __future__ import annotations

import os

from image_editor_plugin.models import AIProviderId

from .base import ImageProviderAdapter, ProviderHttp
from .catalog import MODEL_CATALOG
from .fal import FalImageAdapter
from .google import GoogleImageAdapter
from .http import HttpProviderClient
from .openai import OpenAIImageAdapter


class ProviderRegistry:
    def __init__(self, adapters: dict[AIProviderId, ImageProviderAdapter]) -> None:
        self._adapters = adapters

    @classmethod
    def default(cls, http: ProviderHttp | None = None) -> ProviderRegistry:
        client = http or HttpProviderClient()
        return cls(
            {
                AIProviderId.OPENAI: OpenAIImageAdapter(client),
                AIProviderId.GOOGLE: GoogleImageAdapter(client),
                AIProviderId.FAL: FalImageAdapter(client),
            }
        )

    def adapter(self, provider: AIProviderId) -> ImageProviderAdapter:
        return self._adapters[provider]

    def public_catalog(self) -> list[dict[str, object]]:
        return [descriptor.public_dict() for descriptor in MODEL_CATALOG.values()]

    @staticmethod
    def credential_status() -> dict[str, bool]:
        return {
            "openai": _present("OPENAI_API_KEY"),
            "google": _present("GEMINI_API_KEY"),
            "fal": _present("FAL_KEY") or _present("FAL_API_KEY"),
        }


def _present(name: str) -> bool:
    return len(os.environ.get(name, "").strip()) >= 16
