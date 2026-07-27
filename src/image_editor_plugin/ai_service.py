from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import MAX_AI_INPUTS, MAX_AI_PROMPT_CHARACTERS
from .errors import conflict, invalid
from .models import (
    AIConversationRecord,
    AIImageOptions,
    AIModelId,
    AIProviderId,
    AssetRecord,
    LayerDecompositionOptions,
    LayerRecord,
    OperationRecord,
    ProjectManifest,
)
from .project import ProjectService
from .providers.base import ProviderImage, ProviderResult
from .providers.catalog import require_operation, resolve_model
from .providers.registry import ProviderRegistry


@dataclass(frozen=True, slots=True)
class AICommit:
    manifest: ProjectManifest
    assets: list[AssetRecord]
    conversation: AIConversationRecord | None
    operation: OperationRecord
    layers: list[LayerRecord]
    revised_prompt: str | None


class AIService:
    def __init__(self, projects: ProjectService, providers: ProviderRegistry) -> None:
        self.projects = projects
        self.providers = providers

    def generate(
        self,
        workspace_id: str,
        project_path: str,
        provider: AIProviderId,
        model: AIModelId | None,
        prompt: str,
        expected_revision: int,
        options: AIImageOptions,
        *,
        add_as_layers: bool,
    ) -> AICommit:
        prompt = _validate_prompt(prompt)
        descriptor = resolve_model(provider, model)
        require_operation(descriptor, "generate")
        self.projects.read_ai_assets(workspace_id, project_path, [], expected_revision)
        result = self.providers.adapter(provider).generate(descriptor.model, prompt, options)
        return self._commit(
            workspace_id,
            project_path,
            expected_revision,
            provider,
            descriptor.model,
            "ai_generate_image",
            prompt,
            [],
            None,
            result,
            options.model_dump(mode="json"),
            None,
            True,
            add_as_layers,
            descriptor.stateful_conversation,
        )

    def edit(
        self,
        workspace_id: str,
        project_path: str,
        provider: AIProviderId,
        model: AIModelId | None,
        prompt: str,
        input_asset_ids: list[str],
        expected_revision: int,
        options: AIImageOptions,
        *,
        mask_asset_id: str | None,
        add_as_layers: bool,
    ) -> AICommit:
        prompt = _validate_prompt(prompt)
        descriptor = resolve_model(provider, model)
        require_operation(descriptor, "inpaint" if mask_asset_id else "edit")
        if not 1 <= len(input_asset_ids) <= min(MAX_AI_INPUTS, descriptor.maximum_inputs):
            raise invalid(
                f"{descriptor.display_name} requires 1-{descriptor.maximum_inputs} input images."
            )
        ids = [*input_asset_ids, *([mask_asset_id] if mask_asset_id else [])]
        _, records = self.projects.read_ai_assets(
            workspace_id, project_path, ids, expected_revision
        )
        source_records = records[: len(input_asset_ids)]
        sources = [_provider_image(asset, data) for asset, data in source_records]
        mask: ProviderImage | None = None
        if mask_asset_id:
            mask_record, mask_data = records[-1]
            first = source_records[0][0]
            if (
                mask_record.mime_type != "image/png"
                or not mask_record.has_alpha
                or mask_record.width != first.width
                or mask_record.height != first.height
            ):
                raise invalid(
                    "A mask must be an alpha PNG with the same dimensions as the first input image."
                )
            mask = _provider_image(mask_record, mask_data)
        result = self.providers.adapter(provider).edit(
            descriptor.model,
            prompt,
            sources,
            options,
            mask=mask,
        )
        return self._commit(
            workspace_id,
            project_path,
            expected_revision,
            provider,
            descriptor.model,
            "ai_inpaint" if mask else "ai_edit_image",
            prompt,
            input_asset_ids,
            mask_asset_id,
            result,
            options.model_dump(mode="json"),
            None,
            True,
            add_as_layers,
            descriptor.stateful_conversation,
        )

    def continue_edit(
        self,
        workspace_id: str,
        project_path: str,
        conversation_id: str,
        prompt: str,
        expected_revision: int,
        options: AIImageOptions,
        *,
        add_as_layers: bool,
    ) -> AICommit:
        prompt = _validate_prompt(prompt)
        _, conversation = self.projects.find_ai_conversation(
            workspace_id, project_path, conversation_id, expected_revision
        )
        descriptor = resolve_model(conversation.provider, conversation.model)
        require_operation(descriptor, "continue")
        if not conversation.turns:
            raise conflict("The AI conversation has no completed turn to continue.")
        previous = conversation.turns[-1]
        if descriptor.stateful_conversation and conversation.provider_session_id:
            sources: list[ProviderImage] = []
            input_ids = previous.output_asset_ids
            previous_request_id = conversation.provider_session_id
        else:
            input_ids = previous.output_asset_ids
            _, records = self.projects.read_ai_assets(
                workspace_id, project_path, input_ids, expected_revision
            )
            sources = [_provider_image(asset, data) for asset, data in records]
            previous_request_id = None
        result = self.providers.adapter(conversation.provider).edit(
            conversation.model,
            prompt,
            sources,
            options,
            previous_request_id=previous_request_id,
        )
        return self._commit(
            workspace_id,
            project_path,
            expected_revision,
            conversation.provider,
            conversation.model,
            "ai_continue_edit",
            prompt,
            input_ids,
            None,
            result,
            options.model_dump(mode="json"),
            conversation_id,
            True,
            add_as_layers,
            descriptor.stateful_conversation,
        )

    def decompose_layers(
        self,
        workspace_id: str,
        project_path: str,
        source_asset_id: str,
        expected_revision: int,
        options: LayerDecompositionOptions,
    ) -> AICommit:
        descriptor = resolve_model(AIProviderId.FAL, AIModelId.QWEN_IMAGE_LAYERED)
        require_operation(descriptor, "decompose")
        _, records = self.projects.read_ai_assets(
            workspace_id, project_path, [source_asset_id], expected_revision
        )
        source = _provider_image(*records[0])
        values = options.model_dump(mode="json")
        result = self.providers.adapter(AIProviderId.FAL).decompose(
            descriptor.model, source, values
        )
        prompt = options.prompt or "Decompose the source image into semantic RGBA layers."
        return self._commit(
            workspace_id,
            project_path,
            expected_revision,
            AIProviderId.FAL,
            descriptor.model,
            "ai_decompose_layers",
            prompt,
            [source_asset_id],
            None,
            result,
            values,
            None,
            False,
            options.add_as_layers,
            False,
        )

    def _commit(
        self,
        workspace_id: str,
        project_path: str,
        expected_revision: int,
        provider: AIProviderId,
        model: AIModelId,
        operation_type: str,
        prompt: str,
        input_asset_ids: list[str],
        mask_asset_id: str | None,
        result: ProviderResult,
        parameters: dict[str, Any],
        conversation_id: str | None,
        record_conversation: bool,
        add_as_layers: bool,
        stateful: bool,
    ) -> AICommit:
        safe_parameters = {
            **parameters,
            **result.metadata,
            "revised_prompt": result.revised_prompt,
        }
        manifest, assets, conversation, operation, layers = self.projects.commit_ai_result(
            workspace_id,
            project_path,
            expected_revision,
            provider=provider,
            model=model,
            operation_type=operation_type,
            prompt=prompt,
            input_asset_ids=input_asset_ids,
            mask_asset_id=mask_asset_id,
            output_images=[(image.data, image.mime_type) for image in result.images],
            provider_request_id=result.request_id,
            provider_session_id=result.request_id if stateful else None,
            parameters=safe_parameters,
            conversation_id=conversation_id,
            record_conversation=record_conversation,
            add_as_layers=add_as_layers,
        )
        return AICommit(manifest, assets, conversation, operation, layers, result.revised_prompt)


def _provider_image(asset: AssetRecord, data: bytes) -> ProviderImage:
    filename = asset.source_name or f"{asset.id}.png"
    return ProviderImage(data=data, mime_type=asset.mime_type, filename=filename)


def _validate_prompt(value: str) -> str:
    prompt = value.strip()
    if not prompt:
        raise invalid("An AI image prompt is required.")
    if len(prompt) > MAX_AI_PROMPT_CHARACTERS:
        raise invalid(f"AI prompts cannot exceed {MAX_AI_PROMPT_CHARACTERS:,} characters.")
    return prompt
