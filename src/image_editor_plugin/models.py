from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .constants import (
    DEFAULT_IMAGE_SEARCH_MODEL,
    MAX_ASSETS,
    MAX_DIMENSION,
    MAX_IMAGE_SEARCH_DOMAINS,
    MAX_IMAGE_SEARCH_RESULTS,
    MAX_LAYERS,
    PLUGIN_VERSION,
    SCHEMA_VERSION,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AssetKind(StrEnum):
    IMPORTED = "imported"
    DERIVED = "derived"
    GENERATED = "generated"


class AssetRole(StrEnum):
    IMAGE = "image"
    SELECTION_MASK = "selection_mask"


class ImageFormat(StrEnum):
    PNG = "PNG"
    JPEG = "JPEG"
    PSD = "PSD"


class ResizeFilter(StrEnum):
    POINT = "point"
    BOX = "box"
    TRIANGLE = "triangle"
    MITCHELL = "mitchell"
    LANCZOS = "lanczos"


class AspectPolicy(StrEnum):
    EXACT = "exact"
    FIT = "fit"
    FILL = "fill"


class TransformTarget(StrEnum):
    LAYER = "layer"
    DOCUMENT = "document"


class ContentPolicy(StrEnum):
    SCALE_ALL = "scale_all"
    CANVAS_ONLY = "canvas_only"


class MetadataPolicy(StrEnum):
    STRIP = "strip"
    PRESERVE_SAFE = "preserve_safe"


class BlendMode(StrEnum):
    NORMAL = "normal"


class SelectionMethod(StrEnum):
    AUTO = "auto"
    BORDER = "border"
    LOCAL_MODEL = "local_model"


class ExecutionPolicy(StrEnum):
    AUTO = "auto"
    CPU = "cpu"
    ACCELERATOR = "accelerator"


class RuntimeProfile(StrEnum):
    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"
    DIRECTML = "directml"
    OPENVINO = "openvino"


class AIProviderId(StrEnum):
    OPENAI = "openai"
    GOOGLE = "google"
    FAL = "fal"


class AIModelId(StrEnum):
    GPT_IMAGE_2 = "gpt-image-2"
    NANO_BANANA_2 = "gemini-3.1-flash-image"
    NANO_BANANA_PRO = "gemini-3-pro-image"
    SEEDREAM_5_PRO = "bytedance/seedream/v5/pro"
    GROK_IMAGINE = "xai/grok-imagine-image"
    QWEN_IMAGE_LAYERED = "fal-ai/qwen-image-layered"


class AIOutputFormat(StrEnum):
    PNG = "png"
    JPEG = "jpeg"


class AIQuality(StrEnum):
    AUTO = "auto"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AIResolution(StrEnum):
    HALF_K = "0.5K"
    ONE_K = "1K"
    TWO_K = "2K"
    FOUR_K = "4K"


class AIBackground(StrEnum):
    AUTO = "auto"
    OPAQUE = "opaque"


class SearchContextSize(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ImageSearchLocation(StrictModel):
    country: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    city: str | None = Field(default=None, min_length=1, max_length=128)
    region: str | None = Field(default=None, min_length=1, max_length=128)
    timezone: str | None = Field(
        default=None,
        min_length=3,
        max_length=128,
        pattern=r"^[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)+$",
    )

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None

    @model_validator(mode="after")
    def at_least_one_field(self) -> ImageSearchLocation:
        if not any((self.country, self.city, self.region, self.timezone)):
            raise ValueError("location must contain at least one field")
        return self


class ImageSearchOptions(StrictModel):
    model: str = Field(
        default=DEFAULT_IMAGE_SEARCH_MODEL,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
        description=(
            "Responses model used to drive OpenAI web_search. The calling agent may override "
            "the default with another model that supports image search results."
        ),
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=MAX_IMAGE_SEARCH_RESULTS,
        description="Maximum source-attributed image results requested from OpenAI.",
    )
    caption: bool = Field(default=True, description="Request a short caption for each image.")
    include_supporting_text: bool = Field(
        default=True,
        description="Also search text sources for a grounded summary and citations.",
    )
    search_context_size: SearchContextSize = Field(
        default=SearchContextSize.LOW,
        description="Amount of web context available to the model: low, medium, or high.",
    )
    allowed_domains: list[str] = Field(default_factory=list, max_length=MAX_IMAGE_SEARCH_DOMAINS)
    blocked_domains: list[str] = Field(default_factory=list, max_length=MAX_IMAGE_SEARCH_DOMAINS)
    location: ImageSearchLocation | None = None
    live_web_access: bool = Field(
        default=True,
        description="Use the live web; false restricts search to cached/indexed results.",
    )

    @field_validator("allowed_domains", "blocked_domains")
    @classmethod
    def normalize_domains(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            domain = value.strip().casefold().rstrip(".")
            if (
                not domain
                or "://" in domain
                or "/" in domain
                or "@" in domain
                or ":" in domain
                or "*" in domain
                or len(domain) > 253
            ):
                raise ValueError(
                    "domains must be hostnames without schemes, paths, ports, or wildcards"
                )
            labels = domain.split(".")
            if len(labels) < 2 or any(
                not label
                or len(label) > 63
                or label.startswith("-")
                or label.endswith("-")
                or not all(
                    character.isascii() and (character.isalnum() or character == "-")
                    for character in label
                )
                for label in labels
            ):
                raise ValueError("domains must be valid DNS hostnames")
            if domain not in normalized:
                normalized.append(domain)
        return normalized

    @model_validator(mode="after")
    def disjoint_domain_filters(self) -> ImageSearchOptions:
        overlap = set(self.allowed_domains) & set(self.blocked_domains)
        if overlap:
            raise ValueError("the same domain cannot be both allowed and blocked")
        return self


class ImageSearchResult(StrictModel):
    image_url: str
    source_website_url: str
    thumbnail_url: str | None = None
    caption: str | None = Field(default=None, max_length=2_000)


class ImageSearchCitation(StrictModel):
    url: str
    title: str | None = Field(default=None, max_length=1_000)


class AIImageOptions(StrictModel):
    width: int | None = Field(default=None, ge=256, le=4096)
    height: int | None = Field(default=None, ge=256, le=4096)
    aspect_ratio: str | None = Field(default=None, pattern=r"^\d+(?:\.\d+)?:\d+(?:\.\d+)?$")
    resolution: AIResolution | None = None
    quality: AIQuality = AIQuality.AUTO
    output_format: AIOutputFormat = AIOutputFormat.PNG
    background: AIBackground = AIBackground.AUTO
    num_images: int = Field(default=1, ge=1, le=4)
    safety_filter: bool = True

    @model_validator(mode="after")
    def paired_dimensions(self) -> AIImageOptions:
        if (self.width is None) != (self.height is None):
            raise ValueError("width and height must be supplied together")
        return self


class LayerDecompositionOptions(StrictModel):
    prompt: str | None = Field(default=None, max_length=4_000)
    negative_prompt: str = Field(default="", max_length=4_000)
    num_layers: int = Field(default=4, ge=1, le=10)
    num_inference_steps: int = Field(default=28, ge=1, le=100)
    guidance_scale: float = Field(default=5.0, ge=0.0, le=20.0)
    seed: int | None = Field(default=None, ge=0)
    safety_filter: bool = True
    add_as_layers: bool = True


class AIProvenance(StrictModel):
    provider: AIProviderId
    model: AIModelId
    operation: str
    prompt: str
    input_asset_ids: list[str] = Field(default_factory=list)
    mask_asset_id: str | None = None
    provider_request_id: str | None = Field(default=None, max_length=256)
    conversation_id: str | None = None
    parent_asset_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AIConversationTurn(StrictModel):
    id: str = Field(pattern=r"^trn_[0-9a-f-]{36}$")
    prompt: str = Field(min_length=1, max_length=32_000)
    input_asset_ids: list[str]
    output_asset_ids: list[str]
    mask_asset_id: str | None = None
    provider_request_id: str | None = Field(default=None, max_length=256)
    created_at: datetime


class AIConversationRecord(StrictModel):
    id: str = Field(pattern=r"^cnv_[0-9a-f-]{36}$")
    provider: AIProviderId
    model: AIModelId
    provider_session_id: str | None = Field(default=None, max_length=256)
    turns: list[AIConversationTurn] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class Canvas(StrictModel):
    width: int = Field(ge=1, le=MAX_DIMENSION)
    height: int = Field(ge=1, le=MAX_DIMENSION)
    color_space: Literal["sRGB"] = "sRGB"
    bit_depth: Literal[8] = 8
    mode: Literal["RGB"] = "RGB"
    background: str = "transparent"

    @model_validator(mode="after")
    def validate_pixels(self) -> Canvas:
        if self.width * self.height > 100_000_000:
            raise ValueError("canvas exceeds 100 million pixels")
        return self


class AssetRecord(StrictModel):
    id: str = Field(pattern=r"^ast_[0-9a-f-]{36}$")
    kind: AssetKind
    role: AssetRole = AssetRole.IMAGE
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    format: ImageFormat
    mime_type: Literal["image/png", "image/jpeg"]
    width: int = Field(ge=1, le=MAX_DIMENSION)
    height: int = Field(ge=1, le=MAX_DIMENSION)
    bit_depth: int = Field(ge=1, le=32)
    has_alpha: bool
    color_space: str
    has_icc_profile: bool
    source_name: str | None = None
    operation_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    warnings: list[str] = Field(default_factory=list)
    ai_provenance: AIProvenance | None = None

    @model_validator(mode="after")
    def validate_pixels(self) -> AssetRecord:
        if self.width * self.height > 100_000_000:
            raise ValueError("asset exceeds 100 million decoded pixels")
        return self


class SelectionBounds(StrictModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class SelectionRecord(StrictModel):
    id: str = Field(pattern=r"^sel_[0-9a-f-]{36}$")
    source_asset_id: str
    mask_asset_id: str
    requested_method: SelectionMethod
    resolved_method: SelectionMethod
    execution_policy: ExecutionPolicy
    runtime_profile: str | None = None
    execution_provider: str | None = None
    cpu_fallback: bool = False
    fallback_reason: str | None = Field(default=None, max_length=128)
    local_inference: bool = True
    model_id: str | None = None
    model_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    elapsed_ms: int = Field(ge=0)
    bounds: SelectionBounds
    coverage_ratio: float = Field(ge=0.0, le=1.0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class LayerRecord(StrictModel):
    id: str = Field(pattern=r"^lyr_[0-9a-f-]{36}$")
    name: str = Field(min_length=1, max_length=128)
    asset_id: str
    x: int = 0
    y: int = 0
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    visible: bool = True
    blend_mode: BlendMode = BlendMode.NORMAL


class OperationRecord(StrictModel):
    id: str = Field(pattern=r"^op_[0-9a-f-]{36}$")
    type: str
    target_ids: list[str]
    input_asset_ids: list[str]
    output_asset_ids: list[str]
    parameters: dict[str, Any]
    engine: str
    engine_version: str
    deterministic: bool = True
    created_at: datetime
    warnings: list[str] = Field(default_factory=list)


class ExportRecord(StrictModel):
    id: str = Field(pattern=r"^exp_[0-9a-f-]{36}$")
    format: ImageFormat
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    width: int
    height: int
    parameters: dict[str, Any]
    created_at: datetime


class ProjectManifest(StrictModel):
    schema_version: str = SCHEMA_VERSION
    plugin_version: str = PLUGIN_VERSION
    project_id: str = Field(pattern=r"^prj_[0-9a-f-]{36}$")
    name: str = Field(min_length=1, max_length=128)
    revision: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    canvas: Canvas
    assets: list[AssetRecord] = Field(default_factory=list, max_length=MAX_ASSETS)
    layers: list[LayerRecord] = Field(default_factory=list, max_length=MAX_LAYERS)
    selections: list[SelectionRecord] = Field(default_factory=list, max_length=MAX_ASSETS)
    operations: list[OperationRecord] = Field(default_factory=list)
    exports: list[ExportRecord] = Field(default_factory=list)
    ai_conversations: list[AIConversationRecord] = Field(default_factory=list)

    @field_validator("assets")
    @classmethod
    def unique_assets(cls, value: list[AssetRecord]) -> list[AssetRecord]:
        if len({item.id for item in value}) != len(value):
            raise ValueError("asset IDs must be unique")
        return value

    @model_validator(mode="after")
    def validate_references(self) -> ProjectManifest:
        asset_ids = {asset.id for asset in self.assets}
        if any(layer.asset_id not in asset_ids for layer in self.layers):
            raise ValueError("layer references an unknown asset")
        asset_roles = {asset.id: asset.role for asset in self.assets}
        if any(asset_roles[layer.asset_id] is not AssetRole.IMAGE for layer in self.layers):
            raise ValueError("pixel layer references a non-image asset")
        if len({layer.id for layer in self.layers}) != len(self.layers):
            raise ValueError("layer IDs must be unique")
        if len({selection.id for selection in self.selections}) != len(self.selections):
            raise ValueError("selection IDs must be unique")
        for selection in self.selections:
            if (
                selection.source_asset_id not in asset_ids
                or selection.mask_asset_id not in asset_ids
            ):
                raise ValueError("selection references an unknown asset")
            mask = next(asset for asset in self.assets if asset.id == selection.mask_asset_id)
            source = next(asset for asset in self.assets if asset.id == selection.source_asset_id)
            if mask.role is not AssetRole.SELECTION_MASK:
                raise ValueError("selection mask asset has the wrong role")
            if (mask.width, mask.height) != (source.width, source.height):
                raise ValueError("selection mask dimensions must match its source")
        conversation_ids = {conversation.id for conversation in self.ai_conversations}
        if len(conversation_ids) != len(self.ai_conversations):
            raise ValueError("AI conversation IDs must be unique")
        for conversation in self.ai_conversations:
            for turn in conversation.turns:
                references = {
                    *turn.input_asset_ids,
                    *turn.output_asset_ids,
                    *([turn.mask_asset_id] if turn.mask_asset_id else []),
                }
                if not references <= asset_ids:
                    raise ValueError("AI conversation turn references an unknown asset")
        for asset in self.assets:
            provenance = asset.ai_provenance
            if provenance is None:
                continue
            references = {
                *provenance.input_asset_ids,
                *provenance.parent_asset_ids,
                *([provenance.mask_asset_id] if provenance.mask_asset_id else []),
            }
            if not references <= asset_ids:
                raise ValueError("AI provenance references an unknown asset")
            if (
                provenance.conversation_id is not None
                and provenance.conversation_id not in conversation_ids
            ):
                raise ValueError("AI provenance references an unknown conversation")
        return self


class ErrorDetail(StrictModel):
    code: str
    message: str
    retryable: bool = False
    remediation: list[str] = Field(default_factory=list)


class ToolEnvelope(StrictModel):
    ok: bool
    job_id: None = None
    project_id: str | None = None
    revision: int | None = None
    operation_id: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    duration_ms: int = Field(ge=0)
    error: ErrorDetail | None = None

    @model_validator(mode="after")
    def error_matches_status(self) -> ToolEnvelope:
        if self.ok == (self.error is not None):
            raise ValueError("successful envelopes cannot have errors and failures must have one")
        return self
