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

_GENERATIONS_URL = "https://api.openai.com/v1/images/generations"
_EDITS_URL = "https://api.openai.com/v1/images/edits"


class OpenAIImageAdapter:
    provider_id = AIProviderId.OPENAI

    def __init__(self, http: ProviderHttp) -> None:
        self._http = http

    def generate(self, model: AIModelId, prompt: str, options: AIImageOptions) -> ProviderResult:
        _require_model(model)
        key = require_credential(("OPENAI_API_KEY",), "OpenAI")
        payload: dict[str, Any] = {
            "model": model.value,
            "prompt": prompt,
            "n": options.num_images,
            "quality": options.quality.value,
            "output_format": options.output_format.value,
            "background": options.background.value,
        }
        size = _resolve_size(options)
        if size:
            payload["size"] = size
        response = self._http.post_json(
            _GENERATIONS_URL,
            {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            payload,
        )
        return _parse_result(response.body, response.headers, options)

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
        del previous_request_id
        _require_model(model)
        if not images:
            raise invalid("OpenAI image editing requires at least one input image.")
        key = require_credential(("OPENAI_API_KEY",), "OpenAI")
        fields = {
            "model": model.value,
            "prompt": prompt,
            "n": str(options.num_images),
            "quality": options.quality.value,
            "output_format": options.output_format.value,
            "background": options.background.value,
        }
        size = _resolve_size(options)
        if size:
            fields["size"] = size
        files = [("image[]", (image.filename, image.data, image.mime_type)) for image in images]
        if mask is not None:
            files.append(("mask", (mask.filename, mask.data, mask.mime_type)))
        response = self._http.post_multipart(
            _EDITS_URL,
            {"Authorization": f"Bearer {key}"},
            fields,
            files,
        )
        return _parse_result(response.body, response.headers, options)

    def decompose(
        self, model: AIModelId, image: ProviderImage, options: dict[str, Any]
    ) -> ProviderResult:
        del model, image, options
        raise unsupported("OpenAI does not provide Qwen Image Layered decomposition.")


def _require_model(model: AIModelId) -> None:
    if model is not AIModelId.GPT_IMAGE_2:
        raise unsupported("The OpenAI adapter only supports gpt-image-2.")


def _resolve_size(options: AIImageOptions) -> str | None:
    if options.width is not None and options.height is not None:
        width, height = options.width, options.height
    elif options.aspect_ratio:
        left, right = (float(value) for value in options.aspect_ratio.split(":"))
        long_edge = {
            None: 1024,
            AIResolution.HALF_K: 1024,
            AIResolution.ONE_K: 1024,
            AIResolution.TWO_K: 2048,
            AIResolution.FOUR_K: 3840,
        }[options.resolution]
        ratio = left / right
        if ratio >= 1:
            width, height = long_edge, round(long_edge / ratio)
        else:
            width, height = round(long_edge * ratio), long_edge
        width = max(256, round(width / 16) * 16)
        height = max(256, round(height / 16) * 16)
    elif options.resolution is not None:
        edge = {
            AIResolution.HALF_K: 1024,
            AIResolution.ONE_K: 1024,
            AIResolution.TWO_K: 2048,
            AIResolution.FOUR_K: 2880,
        }[options.resolution]
        width = height = edge
    else:
        return None

    pixels = width * height
    ratio = max(width, height) / min(width, height)
    if (
        max(width, height) > 3840
        or width % 16
        or height % 16
        or ratio > 3
        or not 655_360 <= pixels <= 8_294_400
    ):
        raise invalid(
            "GPT Image 2 size must use 16-pixel increments, stay within 3840px and a 3:1 "
            "ratio, and contain 655,360-8,294,400 pixels."
        )
    return f"{width}x{height}"


def _parse_result(
    body: dict[str, Any], headers: dict[str, str], options: AIImageOptions
) -> ProviderResult:
    raw_data = body.get("data")
    if not isinstance(raw_data, list) or not raw_data:
        raise EditorError("PROVIDER_REJECTED", "OpenAI returned no generated image.")
    mime_type = f"image/{options.output_format.value}"
    images: list[ProviderImage] = []
    revised_prompt: str | None = None
    for index, item in enumerate(raw_data):
        if not isinstance(item, dict) or not isinstance(item.get("b64_json"), str):
            raise EditorError("PROVIDER_REJECTED", "OpenAI returned an invalid image item.")
        data = decode_base64_image(item["b64_json"], "OpenAI")
        revised = item.get("revised_prompt")
        if revised_prompt is None and isinstance(revised, str):
            revised_prompt = revised
        images.append(ProviderImage(data, mime_type, filename_for(index, mime_type)))
    return ProviderResult(
        images=tuple(images),
        request_id=safe_request_id(headers.get("request-id")),
        revised_prompt=revised_prompt,
    )
