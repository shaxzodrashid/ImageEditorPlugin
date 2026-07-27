# AI provider configuration

The plugin uses one provider-neutral project contract and model-specific adapters. Call
`ai_model_catalog` at runtime instead of assuming a model supports an operation.

## OpenAI Image Search

`image_search` is a separate read-only discovery tool built on the Responses API hosted
`web_search` tool. It requests `search_content_types` containing `image`, always includes
`web_search_call.results`, and requires a search call so invocation cannot silently produce an
unsearched answer. The default model is `gpt-5.6`; the caller may choose another compatible
Responses model through `options.model` without changing plugin configuration.

Returned `image_result` records include the canonical image URL, source-page URL, optional
thumbnail, and optional caption. Supporting text and URL citations are returned when enabled.
The plugin filters malformed or non-HTTPS URLs, deduplicates images, and does not download or
assert usage rights over third-party content.

## Credentials

Set credentials in the environment that launches Codex:

| Provider | Environment variable |
|---|---|
| OpenAI | `OPENAI_API_KEY` |
| Google Gemini | `GEMINI_API_KEY` |
| Fal AI | `FAL_KEY` (preferred) or `FAL_API_KEY` |

Provider keys are optional until that provider is invoked. `system_preflight` and
`ai_model_catalog` report only whether a usable value is present. Codex/ChatGPT product
authentication is not an OpenAI Platform API key and is not exposed to plugins.

## Capability matrix

| Model ID | Generate | Edit | Continue | Mask | Special |
|---|---:|---:|---:|---:|---|
| `gpt-image-2` | Yes | Yes | Asset-based | Yes | Flexible dimensions; no transparent background |
| `gemini-3.1-flash-image` | Yes | Yes | Native interaction | No | Nano Banana 2; 0.5K/1K/2K/4K |
| `gemini-3-pro-image` | Yes | Yes | Native interaction | No | Nano Banana Pro; 1K/2K/4K |
| `bytedance/seedream/v5/pro` | Yes | Yes | Asset-based | No | Fal generation/edit endpoints; up to 10 references |
| `xai/grok-imagine-image` | Yes | No | No | No | Generation-only plugin policy |
| `fal-ai/qwen-image-layered` | No | No | No | No | Decomposes one image into 1-10 RGBA layers |

Google continuation stores the returned interaction ID and sends it as
`previous_interaction_id`. OpenAI and Seedream continuation resubmit the latest immutable
result, so the project itself remains the durable conversation record.

## Unified options

`AIImageOptions` includes:

- `width` and `height` for models that accept exact dimensions;
- `aspect_ratio` and `resolution` for models with resolution tiers;
- `quality` for GPT Image 2;
- `output_format: png | jpeg`;
- `background: auto | opaque`;
- `num_images` from 1 to 4;
- `safety_filter`, which remains enabled by default.

Adapters reject unsupported options rather than pretending they were applied. Use
deterministic resize after generation when a provider cannot guarantee exact pixel
dimensions.

## Model-specific behavior

- GPT Image 2 uses the OpenAI Image API generation and edit endpoints. Masked edits require
  an alpha PNG matching the first input image's dimensions. The model always uses high
  input fidelity, so the plugin does not send `input_fidelity`.
- Nano Banana models use Google's Interactions API. The plugin retains native interaction
  state for conversational edits and accepts provider-defined aspect/resolution output.
- Seedream uses Fal's Pro text-to-image and edit endpoints. Local inputs are sent as data
  URIs; up to ten reference images are accepted.
- Grok Imagine is restricted to text-to-image even if Fal later exposes other endpoints.
- Qwen Image Layered is a decomposition model, not a general generator. Its dedicated tool
  preserves every returned RGBA image and can insert them as ordered project layers.

## Primary API references

- [OpenAI GPT Image 2](https://developers.openai.com/api/docs/models/gpt-image-2)
- [OpenAI image generation and editing](https://developers.openai.com/api/docs/guides/image-generation)
- [OpenAI web and image search](https://developers.openai.com/api/docs/guides/tools-web-search#image-search-results)
- [Google Nano Banana image generation](https://ai.google.dev/gemini-api/docs/image-generation)
- [Fal Seedream 5.0 Pro](https://fal.ai/seedream-5.0)
- [Fal Grok Imagine image API](https://fal.ai/docs/model-api-reference/image-generation-api/xai-grok-imagine-image)
- [Fal Qwen Image Layered API](https://fal.ai/models/fal-ai/qwen-image-layered/api)
