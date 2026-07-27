from __future__ import annotations

from dataclasses import dataclass

from image_editor_plugin.errors import unsupported
from image_editor_plugin.models import AIModelId, AIProviderId


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    provider: AIProviderId
    model: AIModelId
    display_name: str
    operations: frozenset[str]
    credential_environment: tuple[str, ...]
    maximum_inputs: int
    output_formats: tuple[str, ...]
    resolutions: tuple[str, ...]
    stateful_conversation: bool
    transparency: bool
    notes: tuple[str, ...] = ()

    def public_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider.value,
            "model": self.model.value,
            "display_name": self.display_name,
            "operations": sorted(self.operations),
            "credential_environment": list(self.credential_environment),
            "maximum_inputs": self.maximum_inputs,
            "output_formats": list(self.output_formats),
            "resolutions": list(self.resolutions),
            "stateful_conversation": self.stateful_conversation,
            "transparency": self.transparency,
            "notes": list(self.notes),
        }


MODEL_CATALOG: dict[AIModelId, ModelDescriptor] = {
    AIModelId.GPT_IMAGE_2: ModelDescriptor(
        AIProviderId.OPENAI,
        AIModelId.GPT_IMAGE_2,
        "GPT Image 2",
        frozenset({"generate", "edit", "inpaint", "continue"}),
        ("OPENAI_API_KEY",),
        10,
        ("png", "jpeg"),
        ("custom up to 3840px",),
        False,
        False,
        ("Image inputs always use high fidelity.", "Transparent backgrounds are unsupported."),
    ),
    AIModelId.NANO_BANANA_2: ModelDescriptor(
        AIProviderId.GOOGLE,
        AIModelId.NANO_BANANA_2,
        "Nano Banana 2",
        frozenset({"generate", "edit", "continue"}),
        ("GEMINI_API_KEY",),
        10,
        ("png", "jpeg"),
        ("0.5K", "1K", "2K", "4K"),
        True,
        False,
        ("Recommended general-purpose Google image model.",),
    ),
    AIModelId.NANO_BANANA_PRO: ModelDescriptor(
        AIProviderId.GOOGLE,
        AIModelId.NANO_BANANA_PRO,
        "Nano Banana Pro",
        frozenset({"generate", "edit", "continue"}),
        ("GEMINI_API_KEY",),
        6,
        ("png", "jpeg"),
        ("1K", "2K", "4K"),
        True,
        False,
        ("Premium model for complex professional asset production.",),
    ),
    AIModelId.SEEDREAM_5_PRO: ModelDescriptor(
        AIProviderId.FAL,
        AIModelId.SEEDREAM_5_PRO,
        "Seedream 5.0 Pro",
        frozenset({"generate", "edit", "continue"}),
        ("FAL_KEY", "FAL_API_KEY"),
        10,
        ("png", "jpeg"),
        ("1K", "2K"),
        False,
        False,
        ("Conversational continuation resubmits the latest project asset.",),
    ),
    AIModelId.GROK_IMAGINE: ModelDescriptor(
        AIProviderId.FAL,
        AIModelId.GROK_IMAGINE,
        "Grok Imagine",
        frozenset({"generate"}),
        ("FAL_KEY", "FAL_API_KEY"),
        0,
        ("png", "jpeg"),
        ("1K", "2K"),
        False,
        False,
        ("Generation-only by plugin policy.",),
    ),
    AIModelId.QWEN_IMAGE_LAYERED: ModelDescriptor(
        AIProviderId.FAL,
        AIModelId.QWEN_IMAGE_LAYERED,
        "Qwen Image Layered",
        frozenset({"decompose"}),
        ("FAL_KEY", "FAL_API_KEY"),
        1,
        ("png",),
        ("source resolution",),
        False,
        True,
        ("Decomposes one image into 1-10 semantically ordered RGBA layers.",),
    ),
}

DEFAULT_MODELS = {
    AIProviderId.OPENAI: AIModelId.GPT_IMAGE_2,
    AIProviderId.GOOGLE: AIModelId.NANO_BANANA_2,
    AIProviderId.FAL: AIModelId.SEEDREAM_5_PRO,
}


def resolve_model(provider: AIProviderId, model: AIModelId | None) -> ModelDescriptor:
    resolved = model or DEFAULT_MODELS[provider]
    descriptor = MODEL_CATALOG[resolved]
    if descriptor.provider is not provider:
        raise unsupported(
            f"Model {resolved.value} does not belong to provider {provider.value}.",
            f"Choose provider {descriptor.provider.value} or another model.",
        )
    return descriptor


def require_operation(descriptor: ModelDescriptor, operation: str) -> None:
    if operation not in descriptor.operations:
        raise unsupported(
            f"{descriptor.display_name} does not support {operation} in this plugin.",
            f"Choose a model whose operations include {operation}.",
        )
