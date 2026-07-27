from __future__ import annotations

import base64
from typing import Any

from image_editor_plugin.errors import EditorError, invalid, unsupported
from image_editor_plugin.models import (
    AIBackground,
    AIImageOptions,
    AIModelId,
    AIProviderId,
    AIQuality,
    AIResolution,
)

from .base import ProviderHttp, ProviderImage, ProviderResult
from .utils import decode_data_uri, filename_for, require_credential, safe_request_id

_FAL_ROOT = "https://fal.run"
_FAL_MEDIA_HOSTS = frozenset({"fal.media"})


class FalImageAdapter:
    provider_id = AIProviderId.FAL

    def __init__(self, http: ProviderHttp) -> None:
        self._http = http

    def generate(self, model: AIModelId, prompt: str, options: AIImageOptions) -> ProviderResult:
        _validate_common_options(options)
        if model is AIModelId.SEEDREAM_5_PRO:
            endpoint = "bytedance/seedream/v5/pro/text-to-image"
            payload = {
                "prompt": prompt,
                "image_size": _seedream_size(options),
                "num_images": options.num_images,
                "output_format": options.output_format.value,
                "sync_mode": True,
                "enable_safety_checker": options.safety_filter,
            }
        elif model is AIModelId.GROK_IMAGINE:
            if options.width is not None:
                raise invalid("Grok Imagine accepts aspect_ratio and resolution, not exact pixels.")
            if options.resolution not in {None, AIResolution.ONE_K, AIResolution.TWO_K}:
                raise invalid("Grok Imagine supports 1K or 2K output.")
            endpoint = model.value
            payload = {
                "prompt": prompt,
                "num_images": options.num_images,
                "aspect_ratio": options.aspect_ratio or "1:1",
                "resolution": (options.resolution or AIResolution.ONE_K).value.casefold(),
                "output_format": options.output_format.value,
                "sync_mode": True,
            }
        else:
            raise unsupported(f"{model.value} is not a Fal text-to-image model.")
        return self._request(endpoint, payload)

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
        _validate_common_options(options)
        if model is AIModelId.GROK_IMAGINE:
            raise unsupported(
                "Grok Imagine is generation-only in this plugin.",
                "Choose Seedream 5.0 Pro, GPT Image 2, or a Nano Banana model for edits.",
            )
        if model is not AIModelId.SEEDREAM_5_PRO:
            raise unsupported(f"{model.value} does not support conversational Fal editing.")
        if mask is not None:
            raise unsupported(
                "Seedream 5.0 Pro editing does not expose a standalone mask parameter.",
                "Provide an annotated reference image or use GPT Image 2 for "
                "mask-based inpainting.",
            )
        if not 1 <= len(images) <= 10:
            raise invalid("Seedream 5.0 Pro editing requires 1-10 input images.")
        payload = {
            "prompt": prompt,
            "image_size": _seedream_size(options),
            "num_images": options.num_images,
            "output_format": options.output_format.value,
            "sync_mode": True,
            "enable_safety_checker": options.safety_filter,
            "image_urls": [_data_uri(image) for image in images],
        }
        return self._request("bytedance/seedream/v5/pro/edit", payload)

    def decompose(
        self, model: AIModelId, image: ProviderImage, options: dict[str, Any]
    ) -> ProviderResult:
        if model is not AIModelId.QWEN_IMAGE_LAYERED:
            raise unsupported("The Fal decomposition adapter only supports Qwen Image Layered.")
        payload = {
            "image_url": _data_uri(image),
            "negative_prompt": options["negative_prompt"],
            "num_inference_steps": options["num_inference_steps"],
            "guidance_scale": options["guidance_scale"],
            "num_layers": options["num_layers"],
            "enable_safety_checker": options["safety_filter"],
            "output_format": "png",
            "acceleration": "regular",
            "sync_mode": True,
        }
        if options.get("prompt"):
            payload["prompt"] = options["prompt"]
        if options.get("seed") is not None:
            payload["seed"] = options["seed"]
        result = self._request(model.value, payload)
        metadata = dict(result.metadata)
        if isinstance(options.get("seed"), int):
            metadata["requested_seed"] = options["seed"]
        return ProviderResult(
            images=result.images,
            request_id=result.request_id,
            revised_prompt=result.revised_prompt,
            metadata=metadata,
        )

    def _request(self, endpoint: str, payload: dict[str, Any]) -> ProviderResult:
        key = require_credential(("FAL_KEY", "FAL_API_KEY"), "Fal AI")
        response = self._http.post_json(
            f"{_FAL_ROOT}/{endpoint}",
            {"Authorization": f"Key {key}", "Content-Type": "application/json"},
            payload,
        )
        raw_images = response.body.get("images")
        if not isinstance(raw_images, list) or not raw_images:
            raise EditorError("PROVIDER_REJECTED", "Fal AI returned no generated image.")
        images: list[ProviderImage] = []
        for index, item in enumerate(raw_images):
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                raise EditorError("PROVIDER_REJECTED", "Fal AI returned an invalid image item.")
            url = item["url"]
            decoded = decode_data_uri(url, "Fal AI")
            if decoded is None:
                data, mime = self._http.get_bytes(url, _FAL_MEDIA_HOSTS)
            else:
                data, mime = decoded
            declared = item.get("content_type")
            if isinstance(declared, str) and declared.startswith("image/"):
                mime = declared
            images.append(ProviderImage(data, mime, filename_for(index, mime)))
        metadata: dict[str, str | int | float | bool | None] = {}
        if isinstance(response.body.get("seed"), int):
            metadata["seed"] = response.body["seed"]
        revised = response.body.get("revised_prompt")
        return ProviderResult(
            images=tuple(images),
            request_id=safe_request_id(response.body.get("request_id"))
            or safe_request_id(response.headers.get("request-id")),
            revised_prompt=revised if isinstance(revised, str) else None,
            metadata=metadata,
        )


def _validate_common_options(options: AIImageOptions) -> None:
    if options.quality is not AIQuality.AUTO:
        raise invalid("Fal models do not expose the unified quality setting.")
    if options.background is not AIBackground.AUTO:
        raise invalid("Fal models do not expose the unified background setting.")


def _seedream_size(options: AIImageOptions) -> str | dict[str, int]:
    if options.width is not None and options.height is not None:
        pixels = options.width * options.height
        if not 1_048_576 <= pixels <= 4_194_304:
            raise invalid("Seedream 5.0 Pro output must contain between 1K² and 2K² pixels.")
        return {"width": options.width, "height": options.height}
    if options.aspect_ratio:
        mapping = {
            "1:1": "square_hd",
            "3:4": "portrait_4_3",
            "4:3": "landscape_4_3",
            "9:16": "portrait_16_9",
            "16:9": "landscape_16_9",
        }
        try:
            return mapping[options.aspect_ratio]
        except KeyError as exc:
            raise invalid(
                "Seedream aspect_ratio must be 1:1, 3:4, 4:3, 9:16, or 16:9 "
                "unless exact width and height are supplied."
            ) from exc
    if options.resolution in {None, AIResolution.TWO_K}:
        return "auto_2K"
    if options.resolution in {AIResolution.HALF_K, AIResolution.ONE_K}:
        return "auto_1K"
    raise invalid("Seedream 5.0 Pro supports 1K or 2K output.")


def _data_uri(image: ProviderImage) -> str:
    encoded = base64.b64encode(image.data).decode("ascii")
    return f"data:{image.mime_type};base64,{encoded}"
