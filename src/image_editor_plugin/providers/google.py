from __future__ import annotations

from typing import Any

from image_editor_plugin.errors import EditorError, invalid, unsupported
from image_editor_plugin.models import (
    AIImageOptions,
    AIModelId,
    AIProviderId,
    AIResolution,
)

from .base import ProviderHttp, ProviderImage, ProviderResult
from .utils import decode_base64_image, filename_for, require_credential, safe_request_id

_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
_MODELS = {AIModelId.NANO_BANANA_2, AIModelId.NANO_BANANA_PRO}


class GoogleImageAdapter:
    provider_id = AIProviderId.GOOGLE

    def __init__(self, http: ProviderHttp) -> None:
        self._http = http

    def generate(self, model: AIModelId, prompt: str, options: AIImageOptions) -> ProviderResult:
        _validate_options(model, options)
        payload = {
            "model": model.value,
            "input": [{"type": "text", "text": prompt}],
            "response_format": _response_format(options),
        }
        return self._request(payload, options)

    def edit(
        self,
        model: AIModelId,
        prompt: str,
        images: list[ProviderImage],
        options: AIImageOptions,
        *,
        mask: ProviderImage | None = None,
        previous_request_id: str | None = None,
    ) -> ProviderResult:
        if mask is not None:
            raise unsupported(
                "The Google adapter does not expose a deterministic mask contract.",
                "Use GPT Image 2 for masked inpainting or provide the selection "
                "as a reference image.",
            )
        _validate_options(model, options)
        if previous_request_id:
            payload: dict[str, Any] = {
                "model": model.value,
                "input": prompt,
                "previous_interaction_id": previous_request_id,
                "response_format": _response_format(options),
            }
        else:
            if not images:
                raise invalid("Google image editing requires at least one input image.")
            payload = {
                "model": model.value,
                "input": [
                    {"type": "text", "text": prompt},
                    *[
                        {
                            "type": "image",
                            "mime_type": image.mime_type,
                            "data": _encode(image.data),
                        }
                        for image in images
                    ],
                ],
                "response_format": _response_format(options),
            }
        return self._request(payload, options)

    def decompose(
        self, model: AIModelId, image: ProviderImage, options: dict[str, Any]
    ) -> ProviderResult:
        del model, image, options
        raise unsupported("Google does not provide Qwen Image Layered decomposition.")

    def _request(self, payload: dict[str, Any], options: AIImageOptions) -> ProviderResult:
        key = require_credential(("GEMINI_API_KEY",), "Google Gemini")
        response = self._http.post_json(
            _INTERACTIONS_URL,
            {"x-goog-api-key": key, "Content-Type": "application/json"},
            payload,
        )
        images = _extract_images(response.body, options)
        request_id = safe_request_id(response.body.get("id")) or safe_request_id(
            response.headers.get("request-id")
        )
        return ProviderResult(images=tuple(images), request_id=request_id)


def _validate_options(model: AIModelId, options: AIImageOptions) -> None:
    if model not in _MODELS:
        raise unsupported("The Google adapter only supports Nano Banana 2 and Nano Banana Pro.")
    if options.num_images != 1:
        raise invalid("Google Interactions image requests return one image per turn.")
    if options.width is not None or options.height is not None:
        raise invalid(
            "Google image models accept aspect_ratio plus resolution, not exact dimensions. "
            "Resize the result deterministically when exact pixels are required."
        )
    if model is AIModelId.NANO_BANANA_PRO and options.resolution is AIResolution.HALF_K:
        raise invalid("Nano Banana Pro supports 1K, 2K, or 4K output.")


def _response_format(options: AIImageOptions) -> dict[str, str]:
    result = {
        "type": "image",
        "mime_type": f"image/{options.output_format.value}",
        "image_size": (options.resolution or AIResolution.ONE_K).value,
    }
    if options.aspect_ratio:
        result["aspect_ratio"] = options.aspect_ratio
    return result


def _extract_images(body: dict[str, Any], options: AIImageOptions) -> list[ProviderImage]:
    candidates: list[tuple[str, str]] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            if value.get("type") == "image" and isinstance(value.get("data"), str):
                mime = value.get("mime_type")
                candidates.append(
                    (
                        value["data"],
                        mime if isinstance(mime, str) else f"image/{options.output_format.value}",
                    )
                )
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(body.get("steps", body))
    if not candidates:
        output = body.get("output_image")
        if isinstance(output, dict) and isinstance(output.get("data"), str):
            mime = output.get("mime_type")
            candidates.append(
                (
                    output["data"],
                    mime if isinstance(mime, str) else f"image/{options.output_format.value}",
                )
            )
    if not candidates:
        raise EditorError("PROVIDER_REJECTED", "Google returned no generated image.")
    return [
        ProviderImage(
            decode_base64_image(encoded, "Google"),
            mime,
            filename_for(index, mime),
        )
        for index, (encoded, mime) in enumerate(candidates)
    ]


def _encode(value: bytes) -> str:
    import base64

    return base64.b64encode(value).decode("ascii")
