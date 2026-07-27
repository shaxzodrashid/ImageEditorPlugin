from __future__ import annotations

from typing import Any

import pytest

from image_editor_plugin.ai_service import AIService
from image_editor_plugin.errors import EditorError
from image_editor_plugin.models import (
    AIImageOptions,
    AIModelId,
    AIProviderId,
    AssetKind,
    LayerDecompositionOptions,
)
from image_editor_plugin.project import ProjectService
from image_editor_plugin.providers.base import ProviderImage, ProviderResult
from image_editor_plugin.providers.registry import ProviderRegistry


class FakeAdapter:
    provider_id = AIProviderId.GOOGLE

    def __init__(self) -> None:
        self.edits: list[dict[str, Any]] = []

    def generate(self, model: AIModelId, prompt: str, options: AIImageOptions) -> ProviderResult:
        return ProviderResult(
            (ProviderImage(b"20x10;icc", "image/png", "generated.png"),),
            request_id="interaction_1",
        )

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
        self.edits.append(
            {
                "model": model,
                "prompt": prompt,
                "images": images,
                "mask": mask,
                "previous_request_id": previous_request_id,
            }
        )
        return ProviderResult(
            (ProviderImage(b"20x10;icc", "image/png", "edited.png"),),
            request_id="interaction_2",
        )

    def decompose(
        self, model: AIModelId, image: ProviderImage, options: dict[str, Any]
    ) -> ProviderResult:
        return ProviderResult(
            (
                ProviderImage(b"20x10;icc", "image/png", "layer-1.png"),
                ProviderImage(b"20x10;icc", "image/png", "layer-2.png"),
            ),
            request_id="fal_1",
            metadata={"seed": 7},
        )


def test_generation_and_native_conversation_are_persisted(
    service: tuple[ProjectService, str],
) -> None:
    projects, workspace_id = service
    projects.create(workspace_id, "ai.image-work", "AI", 100, 50)
    google = FakeAdapter()
    ai = AIService(projects, ProviderRegistry({AIProviderId.GOOGLE: google}))

    generated = ai.generate(
        workspace_id,
        "ai.image-work",
        AIProviderId.GOOGLE,
        AIModelId.NANO_BANANA_2,
        "Create a campaign image",
        0,
        AIImageOptions(),
        add_as_layers=False,
    )
    assert generated.manifest.revision == 1
    assert generated.assets[0].kind is AssetKind.GENERATED
    assert generated.assets[0].ai_provenance is not None
    assert generated.assets[0].ai_provenance.provider is AIProviderId.GOOGLE
    assert generated.operation.deterministic is False
    assert generated.conversation is not None
    assert generated.conversation.provider_session_id == "interaction_1"

    continued = ai.continue_edit(
        workspace_id,
        "ai.image-work",
        generated.conversation.id,
        "Translate only the headline",
        1,
        AIImageOptions(),
        add_as_layers=True,
    )
    assert continued.manifest.revision == 2
    assert len(continued.conversation.turns) == 2 if continued.conversation else False
    assert continued.layers[0].asset_id == continued.assets[0].id
    assert google.edits[0]["images"] == []
    assert google.edits[0]["previous_request_id"] == "interaction_1"


def test_unsupported_model_operation_fails_before_provider_call(
    service: tuple[ProjectService, str],
) -> None:
    projects, workspace_id = service
    projects.create(workspace_id, "ai.image-work", "AI", 100, 50)
    ai = AIService(projects, ProviderRegistry({}))
    with pytest.raises(EditorError) as caught:
        ai.edit(
            workspace_id,
            "ai.image-work",
            AIProviderId.FAL,
            AIModelId.GROK_IMAGINE,
            "Change it",
            ["ast_missing"],
            0,
            AIImageOptions(),
            mask_asset_id=None,
            add_as_layers=False,
        )
    assert caught.value.code == "UNSUPPORTED_FEATURE"
    assert projects.inspect(workspace_id, "ai.image-work").revision == 0


def test_qwen_decomposition_commits_semantic_layers(
    tmp_path: Any,
    service: tuple[ProjectService, str],
) -> None:
    projects, workspace_id = service
    projects.create(workspace_id, "layers.image-work", "Layers", 100, 50)
    source = tmp_path / "source.png"
    source.write_text("20x10;icc", encoding="ascii")
    manifest, asset, _, _ = projects.import_asset(
        workspace_id, "layers.image-work", "source.png", 0
    )
    fal = FakeAdapter()
    ai = AIService(projects, ProviderRegistry({AIProviderId.FAL: fal}))

    result = ai.decompose_layers(
        workspace_id,
        "layers.image-work",
        asset.id,
        manifest.revision,
        LayerDecompositionOptions(num_layers=2, seed=7),
    )
    assert result.manifest.revision == 2
    assert len(result.assets) == 2
    assert len(result.layers) == 2
    assert result.conversation is None
    assert result.operation.parameters["seed"] == 7
