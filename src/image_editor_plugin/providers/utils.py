from __future__ import annotations

import base64
import binascii
import os
from urllib.parse import unquote_to_bytes

from image_editor_plugin.constants import MAX_COMPRESSED_INPUT_BYTES
from image_editor_plugin.errors import EditorError, configuration


def require_credential(names: tuple[str, ...], provider_name: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if len(value) >= 16:
            return value
    joined = " or ".join(names)
    raise configuration(
        f"{provider_name} is not configured.",
        f"Set {joined} in the environment that launches Codex, then start a new session.",
    )


def decode_base64_image(value: str, context: str) -> bytes:
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise EditorError(
            "PROVIDER_REJECTED",
            f"{context} returned invalid base64 image data.",
        ) from exc
    if not data:
        raise EditorError("PROVIDER_REJECTED", f"{context} returned an empty image.")
    if len(data) > MAX_COMPRESSED_INPUT_BYTES:
        raise EditorError(
            "RESOURCE_LIMIT",
            f"{context} returned an image over the 100 MiB compressed-size limit.",
        )
    return data


def decode_data_uri(value: str, context: str) -> tuple[bytes, str] | None:
    if not value.startswith("data:"):
        return None
    header, separator, encoded = value.partition(",")
    if not separator:
        raise EditorError("PROVIDER_REJECTED", f"{context} returned an invalid data URI.")
    metadata = header[5:].split(";")
    mime_type = metadata[0] or "application/octet-stream"
    try:
        if "base64" in metadata[1:]:
            data = base64.b64decode(encoded, validate=True)
        else:
            data = unquote_to_bytes(encoded)
    except (binascii.Error, ValueError) as exc:
        raise EditorError("PROVIDER_REJECTED", f"{context} returned an invalid data URI.") from exc
    if not data or len(data) > MAX_COMPRESSED_INPUT_BYTES:
        raise EditorError(
            "RESOURCE_LIMIT",
            f"{context} returned an empty or oversized image.",
        )
    return data, mime_type


def safe_request_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped[:256] if stripped else None


def filename_for(index: int, mime_type: str) -> str:
    extension = ".jpg" if mime_type.casefold() == "image/jpeg" else ".png"
    return f"provider-output-{index + 1}{extension}"
