from __future__ import annotations

PLUGIN_VERSION = "0.4.0"
SCHEMA_VERSION = "1.2.0"

MAX_COMPRESSED_INPUT_BYTES = 100 * 1024 * 1024
MAX_DECODED_PIXELS = 100_000_000
MAX_DIMENSION = 32_768
MAX_LAYERS = 256
MAX_ASSETS = 1_024
OPERATION_TIMEOUT_SECONDS = 120
AI_OPERATION_TIMEOUT_SECONDS = 115
BACKGROUND_OPERATION_TIMEOUT_SECONDS = 115
BACKGROUND_MIN_FREE_MEMORY_BYTES = 1536 * 1024 * 1024
BACKGROUND_MIN_FREE_DISK_BYTES = 2 * 1024 * 1024 * 1024
BACKGROUND_MODEL_ID = "isnet-general-use"
BACKGROUND_MODEL_FILENAME = "isnet-general-use.onnx"
BACKGROUND_MODEL_URL = (
    "https://github.com/danielgatis/rembg/releases/download/v0.0.0/"
    "isnet-general-use.onnx"
)
# Upstream rembg 2.0.77 pins this model with the equivalent MD5. The installer uses SHA-256.
BACKGROUND_MODEL_SHA256 = "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a"
BACKGROUND_MODEL_MAX_BYTES = 512 * 1024 * 1024
BACKGROUND_RUNTIME_VERSIONS = {
    "cpu": ("onnxruntime", "1.27.0"),
    "cuda": ("onnxruntime-gpu", "1.27.0"),
    "directml": ("onnxruntime-directml", "1.24.4"),
    "openvino": ("onnxruntime-openvino", "1.24.1"),
}
MAX_AI_INPUTS = 10
MAX_AI_PROMPT_CHARACTERS = 32_000
MAX_IMAGE_SEARCH_RESULTS = 20
MAX_IMAGE_SEARCH_DOMAINS = 100
MAX_IMAGE_SEARCH_QUERY_CHARACTERS = 4_000
DEFAULT_IMAGE_SEARCH_MODEL = "gpt-5.6"

ALLOWED_INPUT_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_OUTPUT_EXTENSIONS = {".png", ".jpg", ".jpeg"}
