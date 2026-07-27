from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from .constants import (
    ALLOWED_INPUT_EXTENSIONS,
    MAX_ASSETS,
    MAX_LAYERS,
)
from .engine import ImageInfo, ImageMagickEngine
from .errors import EditorError, conflict, invalid, not_found
from .files import atomic_write_json, sha256_file, sha256_json
from .ids import IdProvider, TimeProvider, new_id, utc_now
from .models import (
    AIConversationRecord,
    AIConversationTurn,
    AIModelId,
    AIProvenance,
    AIProviderId,
    AspectPolicy,
    AssetKind,
    AssetRecord,
    Canvas,
    ContentPolicy,
    ExportRecord,
    ImageFormat,
    LayerRecord,
    MetadataPolicy,
    OperationRecord,
    ProjectManifest,
    ResizeFilter,
    TransformTarget,
)
from .security import WorkspaceRegistry, relative_to_root

MANIFEST_NAME = "manifest.json"


class ProjectService:
    def __init__(
        self,
        registry: WorkspaceRegistry,
        engine: ImageMagickEngine,
        id_provider: IdProvider = new_id,
        time_provider: TimeProvider = utc_now,
    ) -> None:
        self.registry = registry
        self.engine = engine
        self.id_provider = id_provider
        self.time_provider = time_provider

    def create(
        self,
        workspace_id: str,
        project_path: str,
        name: str,
        width: int,
        height: int,
        background: str = "transparent",
    ) -> ProjectManifest:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=False)
        if project_dir.exists():
            raise conflict("The project path already exists.")
        canvas = Canvas(width=width, height=height, background=_validate_color(background, True))
        now = self.time_provider()
        manifest = ProjectManifest(
            project_id=self.id_provider("prj"),
            name=name,
            created_at=now,
            updated_at=now,
            canvas=canvas,
        )
        project_dir.mkdir(parents=True)
        try:
            for directory in (
                "assets/imported",
                "assets/derived",
                "assets/generated",
                "previews",
                "exports",
                ".staging",
                "logs",
            ):
                project_dir.joinpath(directory).mkdir(parents=True)
            atomic_write_json(project_dir / MANIFEST_NAME, manifest.model_dump(mode="json"))
        except Exception:
            shutil.rmtree(project_dir, ignore_errors=True)
            raise
        return manifest

    def inspect(self, workspace_id: str, project_path: str) -> ProjectManifest:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        return self._load(project_dir)

    def validate(self, workspace_id: str, project_path: str) -> dict[str, Any]:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        manifest = self._load(project_dir)
        issues: list[str] = []
        checked = 0
        for asset in manifest.assets:
            try:
                path = self._asset_path(project_dir, asset.path)
                checked += 1
                if sha256_file(path) != asset.sha256:
                    issues.append(f"Checksum mismatch for asset {asset.id}.")
            except EditorError:
                issues.append(f"Missing or unsafe asset path for {asset.id}.")
        return {
            "manifest": manifest,
            "valid": not issues,
            "issues": issues,
            "assets_checked": checked,
        }

    def import_asset(
        self,
        workspace_id: str,
        project_path: str,
        source_path: str,
        expected_revision: int,
    ) -> tuple[ProjectManifest, AssetRecord, OperationRecord | None, list[str]]:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        source = self.registry.resolve(workspace_id, source_path, must_exist=True)
        if source.suffix.casefold() not in ALLOWED_INPUT_EXTENSIONS:
            raise invalid("Only .png, .jpg, and .jpeg inputs are allowed.")
        info = self.engine.inspect(source)
        checksum = sha256_file(source)
        warning = (
            [] if info.has_icc_profile else ["RGB input has no ICC profile; sRGB was assumed."]
        )

        with self._lock(project_dir):
            manifest = self._load(project_dir)
            self._expect_revision(manifest, expected_revision)
            existing = next((item for item in manifest.assets if item.sha256 == checksum), None)
            if existing is not None:
                return manifest, existing, None, ["Identical content was already imported."]
            if len(manifest.assets) >= MAX_ASSETS:
                raise invalid("The project has reached its 1,024-asset limit.")
            extension = ".png" if info.format.upper() == "PNG" else ".jpg"
            relative = f"assets/imported/{checksum}{extension}"
            destination = project_dir / relative
            if not destination.exists():
                stage = self._stage_path(project_dir, extension)
                shutil.copyfile(source, stage)
                os.replace(stage, destination)
            asset = self._asset_record(
                AssetKind.IMPORTED,
                relative,
                destination,
                info,
                source.name,
                warnings=warning,
            )
            output_assets = [asset]
            working_asset = asset
            if info.depth != 8 or info.colorspace.casefold() != "srgb":
                if len(manifest.assets) >= MAX_ASSETS - 1:
                    raise invalid("Normalization would exceed the 1,024-asset limit.")
                normalization_parameters = {
                    "input_sha256": checksum,
                    "color_space": "sRGB",
                    "bit_depth": 8,
                }
                working_asset = self._derive(
                    project_dir,
                    manifest,
                    asset,
                    "normalize",
                    normalization_parameters,
                    self.engine.normalize,
                )
                output_assets.append(working_asset)
                warning.append("A normalized 8-bit sRGB working derivative was created.")
            operation = self._operation(
                "asset_import",
                [],
                [],
                [item.id for item in output_assets],
                {"source_sha256": checksum, "source_name": source.name},
                warning,
            )
            manifest.assets.extend(output_assets)
            manifest.operations.append(operation)
            self._commit(project_dir, manifest)
            return manifest, working_asset, operation, warning

    def image_inspect(
        self, workspace_id: str, project_path: str, asset_id: str
    ) -> tuple[ProjectManifest, AssetRecord]:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        manifest = self._load(project_dir)
        return manifest, self._find_asset(manifest, asset_id)

    def read_ai_assets(
        self,
        workspace_id: str,
        project_path: str,
        asset_ids: list[str],
        expected_revision: int,
    ) -> tuple[ProjectManifest, list[tuple[AssetRecord, bytes]]]:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        manifest = self._load(project_dir)
        self._expect_revision(manifest, expected_revision)
        assets: list[tuple[AssetRecord, bytes]] = []
        for asset_id in asset_ids:
            asset = self._find_asset(manifest, asset_id)
            assets.append((asset, self._asset_path(project_dir, asset.path).read_bytes()))
        return manifest, assets

    def commit_ai_result(
        self,
        workspace_id: str,
        project_path: str,
        expected_revision: int,
        *,
        provider: AIProviderId,
        model: AIModelId,
        operation_type: str,
        prompt: str,
        input_asset_ids: list[str],
        mask_asset_id: str | None,
        output_images: list[tuple[bytes, str]],
        provider_request_id: str | None,
        provider_session_id: str | None,
        parameters: dict[str, Any],
        conversation_id: str | None,
        record_conversation: bool,
        add_as_layers: bool,
    ) -> tuple[
        ProjectManifest,
        list[AssetRecord],
        AIConversationRecord | None,
        OperationRecord,
        list[LayerRecord],
    ]:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        with self._lock(project_dir):
            manifest = self._load(project_dir)
            self._expect_revision(manifest, expected_revision)
            for asset_id in [*input_asset_ids, *([mask_asset_id] if mask_asset_id else [])]:
                self._find_asset(manifest, asset_id)
            if len(manifest.assets) + len(output_images) > MAX_ASSETS:
                raise invalid("The AI result would exceed the 1,024-asset project limit.")
            if add_as_layers and len(manifest.layers) + len(output_images) > MAX_LAYERS:
                raise invalid("The AI result would exceed the 256-layer project limit.")
            if not output_images:
                raise EditorError("PROVIDER_REJECTED", "The provider produced no usable image.")
            if any(
                mime_type.casefold() not in {"image/png", "image/jpeg"}
                for _, mime_type in output_images
            ):
                raise invalid("AI working assets must be PNG or JPEG.")

            conversation: AIConversationRecord | None = None
            if record_conversation:
                if conversation_id is None:
                    now = self.time_provider()
                    conversation = AIConversationRecord(
                        id=self.id_provider("cnv"),
                        provider=provider,
                        model=model,
                        provider_session_id=provider_session_id,
                        created_at=now,
                        updated_at=now,
                    )
                    manifest.ai_conversations.append(conversation)
                else:
                    conversation = self._find_conversation(manifest, conversation_id)
                    if conversation.provider is not provider or conversation.model is not model:
                        raise conflict("The conversation provider or model no longer matches.")
                    if provider_session_id:
                        conversation.provider_session_id = provider_session_id

            created_assets: list[AssetRecord] = []
            created_layers: list[LayerRecord] = []
            new_destinations: list[Path] = []
            provenance_parameters = _safe_provider_parameters(parameters)
            for index, (data, mime_type) in enumerate(output_images):
                suffix = ".png" if mime_type.casefold() == "image/png" else ".jpg"
                stage = self._stage_path(project_dir, suffix)
                try:
                    stage.write_bytes(data)
                    info = self.engine.inspect(stage)
                    actual = "image/png" if info.format.upper() == "PNG" else "image/jpeg"
                    if actual != mime_type.casefold():
                        raise EditorError(
                            "PROVIDER_REJECTED",
                            "The provider image content did not match its declared media type.",
                        )
                    checksum = sha256_file(stage)
                    relative = f"assets/generated/{checksum}{suffix}"
                    destination = project_dir / relative
                    if not destination.exists():
                        os.replace(stage, destination)
                        new_destinations.append(destination)
                    warnings = (
                        []
                        if info.has_icc_profile
                        else ["Generated RGB asset has no ICC profile; sRGB was assumed."]
                    )
                    provenance = AIProvenance(
                        provider=provider,
                        model=model,
                        operation=operation_type,
                        prompt=prompt,
                        input_asset_ids=input_asset_ids,
                        mask_asset_id=mask_asset_id,
                        provider_request_id=provider_request_id,
                        conversation_id=conversation.id if conversation else None,
                        parent_asset_ids=input_asset_ids,
                        parameters=provenance_parameters,
                        created_at=self.time_provider(),
                    )
                    asset = self._asset_record(
                        AssetKind.GENERATED,
                        relative,
                        destination,
                        info,
                        f"{model.value}-{index + 1}{suffix}",
                        warnings=warnings,
                        ai_provenance=provenance,
                    )
                except Exception:
                    _remove_files(new_destinations)
                    raise
                finally:
                    stage.unlink(missing_ok=True)
                manifest.assets.append(asset)
                created_assets.append(asset)
                if add_as_layers:
                    layer = LayerRecord(
                        id=self.id_provider("lyr"),
                        name=f"{model.value} {index + 1}",
                        asset_id=asset.id,
                    )
                    manifest.layers.append(layer)
                    created_layers.append(layer)

            now = self.time_provider()
            if conversation is not None:
                conversation.turns.append(
                    AIConversationTurn(
                        id=self.id_provider("trn"),
                        prompt=prompt,
                        input_asset_ids=input_asset_ids,
                        output_asset_ids=[asset.id for asset in created_assets],
                        mask_asset_id=mask_asset_id,
                        provider_request_id=provider_request_id,
                        created_at=now,
                    )
                )
                conversation.updated_at = now
            operation = OperationRecord(
                id=self.id_provider("op"),
                type=operation_type,
                target_ids=[
                    *([conversation.id] if conversation else []),
                    *[layer.id for layer in created_layers],
                ],
                input_asset_ids=[
                    *input_asset_ids,
                    *([mask_asset_id] if mask_asset_id else []),
                ],
                output_asset_ids=[asset.id for asset in created_assets],
                parameters=provenance_parameters,
                engine=provider.value,
                engine_version=model.value,
                deterministic=False,
                created_at=now,
                warnings=[warning for asset in created_assets for warning in asset.warnings],
            )
            manifest.operations.append(operation)
            try:
                self._commit(project_dir, manifest)
            except Exception:
                _remove_files(new_destinations)
                raise
            return manifest, created_assets, conversation, operation, created_layers

    def find_ai_conversation(
        self,
        workspace_id: str,
        project_path: str,
        conversation_id: str,
        expected_revision: int,
    ) -> tuple[ProjectManifest, AIConversationRecord]:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        manifest = self._load(project_dir)
        self._expect_revision(manifest, expected_revision)
        return manifest, self._find_conversation(manifest, conversation_id)

    def add_layer(
        self,
        workspace_id: str,
        project_path: str,
        asset_id: str,
        name: str,
        x: int,
        y: int,
        opacity: float,
        expected_revision: int,
        *,
        operation_type: str = "layer_add",
    ) -> tuple[ProjectManifest, LayerRecord, OperationRecord]:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        with self._lock(project_dir):
            manifest = self._load(project_dir)
            self._expect_revision(manifest, expected_revision)
            self._find_asset(manifest, asset_id)
            if len(manifest.layers) >= MAX_LAYERS:
                raise invalid("The project has reached its 256-layer limit.")
            layer = LayerRecord(
                id=self.id_provider("lyr"),
                name=name,
                asset_id=asset_id,
                x=x,
                y=y,
                opacity=opacity,
            )
            operation = self._operation(
                operation_type,
                [layer.id],
                [asset_id],
                [],
                {"name": name, "x": x, "y": y, "opacity": opacity, "blend_mode": "normal"},
            )
            manifest.layers.append(layer)
            manifest.operations.append(operation)
            self._commit(project_dir, manifest)
            return manifest, layer, operation

    def position_layer(
        self,
        workspace_id: str,
        project_path: str,
        layer_id: str,
        x: int,
        y: int,
        expected_revision: int,
    ) -> tuple[ProjectManifest, LayerRecord, OperationRecord]:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        with self._lock(project_dir):
            manifest = self._load(project_dir)
            self._expect_revision(manifest, expected_revision)
            layer = self._find_layer(manifest, layer_id)
            previous = {"x": layer.x, "y": layer.y}
            layer.x, layer.y = x, y
            operation = self._operation(
                "transform_position",
                [layer.id],
                [layer.asset_id],
                [],
                {"x": x, "y": y, "previous": previous},
            )
            manifest.operations.append(operation)
            self._commit(project_dir, manifest)
            return manifest, layer, operation

    def crop(
        self,
        workspace_id: str,
        project_path: str,
        target: TransformTarget,
        target_id: str | None,
        x: int,
        y: int,
        width: int,
        height: int,
        expected_revision: int,
    ) -> tuple[ProjectManifest, OperationRecord, AssetRecord | None]:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        with self._lock(project_dir):
            manifest = self._load(project_dir)
            self._expect_revision(manifest, expected_revision)
            parameters = {"target": target.value, "x": x, "y": y, "width": width, "height": height}
            if target is TransformTarget.DOCUMENT:
                if target_id is not None:
                    raise invalid("target_id must be omitted for a document crop.")
                if (
                    x < 0
                    or y < 0
                    or x + width > manifest.canvas.width
                    or y + height > manifest.canvas.height
                ):
                    raise invalid("Document crop bounds must stay within the canvas.")
                manifest.canvas.width, manifest.canvas.height = width, height
                for layer in manifest.layers:
                    layer.x -= x
                    layer.y -= y
                operation = self._operation(
                    "transform_crop", [manifest.project_id], [], [], parameters
                )
                derived = None
            else:
                layer = self._require_layer_target(manifest, target_id)
                source_asset = self._find_asset(manifest, layer.asset_id)
                if (
                    x < 0
                    or y < 0
                    or x + width > source_asset.width
                    or y + height > source_asset.height
                ):
                    raise invalid("Layer crop bounds must stay within the source asset.")
                derived = self._derive(
                    project_dir,
                    manifest,
                    source_asset,
                    "crop",
                    parameters,
                    lambda source, output: self.engine.crop(source, output, x, y, width, height),
                )
                layer.asset_id = derived.id
                operation = self._operation(
                    "transform_crop", [layer.id], [source_asset.id], [derived.id], parameters
                )
                manifest.assets.append(derived)
            manifest.operations.append(operation)
            self._commit(project_dir, manifest)
            return manifest, operation, derived

    def resize(
        self,
        workspace_id: str,
        project_path: str,
        target: TransformTarget,
        target_id: str | None,
        width: int,
        height: int,
        resize_filter: ResizeFilter,
        aspect_policy: AspectPolicy,
        content_policy: ContentPolicy | None,
        expected_revision: int,
    ) -> tuple[ProjectManifest, OperationRecord, list[AssetRecord]]:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        with self._lock(project_dir):
            manifest = self._load(project_dir)
            self._expect_revision(manifest, expected_revision)
            parameters = {
                "target": target.value,
                "width": width,
                "height": height,
                "filter": resize_filter.value,
                "aspect_policy": aspect_policy.value,
                "content_policy": content_policy.value if content_policy else None,
            }
            modifier = {
                AspectPolicy.EXACT: "!",
                AspectPolicy.FIT: "",
                AspectPolicy.FILL: "^",
            }[aspect_policy]
            derived_assets: list[AssetRecord] = []
            input_ids: list[str] = []
            output_ids: list[str] = []
            if target is TransformTarget.LAYER:
                if content_policy is not None:
                    raise invalid("content_policy is only valid for document resize.")
                layer = self._require_layer_target(manifest, target_id)
                source_asset = self._find_asset(manifest, layer.asset_id)
                derived = self._derive(
                    project_dir,
                    manifest,
                    source_asset,
                    "resize",
                    parameters,
                    lambda source, output: self.engine.resize(
                        source, output, width, height, resize_filter, modifier
                    ),
                )
                manifest.assets.append(derived)
                derived_assets.append(derived)
                input_ids.append(source_asset.id)
                output_ids.append(derived.id)
                layer.asset_id = derived.id
                targets = [layer.id]
            else:
                if target_id is not None:
                    raise invalid("target_id must be omitted for document resize.")
                if content_policy is None:
                    raise invalid("Document resize requires content_policy.")
                old_width, old_height = manifest.canvas.width, manifest.canvas.height
                if content_policy is ContentPolicy.SCALE_ALL:
                    factor_x, factor_y = width / old_width, height / old_height
                    for layer in manifest.layers:
                        source_asset = self._find_asset(manifest, layer.asset_id)
                        layer_width = max(1, round(source_asset.width * factor_x))
                        layer_height = max(1, round(source_asset.height * factor_y))
                        layer_params = {
                            **parameters,
                            "layer_width": layer_width,
                            "layer_height": layer_height,
                        }
                        derived = self._derive(
                            project_dir,
                            manifest,
                            source_asset,
                            "resize",
                            layer_params,
                            partial(
                                self.engine.resize,
                                width=layer_width,
                                height=layer_height,
                                resize_filter=resize_filter,
                                modifier="!",
                            ),
                        )
                        manifest.assets.append(derived)
                        derived_assets.append(derived)
                        input_ids.append(source_asset.id)
                        output_ids.append(derived.id)
                        layer.asset_id = derived.id
                        layer.x = round(layer.x * factor_x)
                        layer.y = round(layer.y * factor_y)
                manifest.canvas.width, manifest.canvas.height = width, height
                targets = [manifest.project_id]
            operation = self._operation(
                "transform_resize", targets, input_ids, output_ids, parameters
            )
            manifest.operations.append(operation)
            self._commit(project_dir, manifest)
            return manifest, operation, derived_assets

    def render_preview(
        self,
        workspace_id: str,
        project_path: str,
        max_dimension: int,
    ) -> tuple[ProjectManifest, Path, str]:
        if not 64 <= max_dimension <= 4096:
            raise invalid("Preview max_dimension must be between 64 and 4,096.")
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        manifest = self._load(project_dir)
        output = project_dir / "previews" / f"preview-r{manifest.revision}.png"
        stage = self._stage_path(project_dir, ".png")
        try:
            self.engine.render(
                manifest.canvas.width,
                manifest.canvas.height,
                manifest.canvas.background,
                self._render_layers(project_dir, manifest),
                stage,
                preview_max=max_dimension,
            )
            os.replace(stage, output)
        finally:
            stage.unlink(missing_ok=True)
        return manifest, output, sha256_file(output)

    def export(
        self,
        workspace_id: str,
        project_path: str,
        output_path: str,
        image_format: ImageFormat,
        expected_revision: int,
        overwrite: bool,
        *,
        quality: int | None = None,
        background: str | None = None,
        metadata_policy: MetadataPolicy = MetadataPolicy.STRIP,
    ) -> tuple[ProjectManifest, ExportRecord]:
        project_dir = self._project_dir(workspace_id, project_path, must_exist=True)
        output = self.registry.resolve(workspace_id, output_path, must_exist=False)
        expected_suffixes = {".png"} if image_format is ImageFormat.PNG else {".jpg", ".jpeg"}
        if output.suffix.casefold() not in expected_suffixes:
            raise invalid(f"{image_format.value} export path has the wrong extension.")
        if output.exists() and not overwrite:
            raise conflict("The export already exists; set overwrite to true to replace it.")
        if image_format is ImageFormat.JPEG:
            if quality is None or not 1 <= quality <= 100:
                raise invalid("JPEG quality must be between 1 and 100.")
            background = _validate_color(background or "", False)
        output.parent.mkdir(parents=True, exist_ok=True)
        with self._lock(project_dir):
            manifest = self._load(project_dir)
            self._expect_revision(manifest, expected_revision)
            stage = self._stage_path(project_dir, output.suffix.casefold())
            try:
                self.engine.render(
                    manifest.canvas.width,
                    manifest.canvas.height,
                    manifest.canvas.background,
                    self._render_layers(project_dir, manifest),
                    stage,
                    jpeg_quality=quality if image_format is ImageFormat.JPEG else None,
                    jpeg_background=background,
                    metadata_strip=metadata_policy is MetadataPolicy.STRIP,
                )
                self._commit_export_file(stage, output, overwrite)
            finally:
                stage.unlink(missing_ok=True)
            root = self.registry.root(workspace_id)
            record = ExportRecord(
                id=self.id_provider("exp"),
                format=image_format,
                path=relative_to_root(output, root),
                sha256=sha256_file(output),
                width=manifest.canvas.width,
                height=manifest.canvas.height,
                parameters={
                    "quality": quality,
                    "chroma_subsampling": "4:2:0" if image_format is ImageFormat.JPEG else None,
                    "background": background,
                    "metadata_policy": metadata_policy.value,
                },
                created_at=self.time_provider(),
            )
            operation = self._operation(
                f"export_{image_format.value.casefold()}",
                [manifest.project_id],
                [layer.asset_id for layer in manifest.layers],
                [],
                record.parameters,
            )
            manifest.exports.append(record)
            manifest.operations.append(operation)
            self._commit(project_dir, manifest)
            return manifest, record

    def _derive(
        self,
        project_dir: Path,
        manifest: ProjectManifest,
        source_asset: AssetRecord,
        operation_type: str,
        parameters: dict[str, Any],
        generate: Callable[[Path, Path], None],
    ) -> AssetRecord:
        if len(manifest.assets) >= MAX_ASSETS:
            raise invalid("The project has reached its 1,024-asset limit.")
        operation_hash = sha256_json(
            {
                "input_sha256": source_asset.sha256,
                "operation": operation_type,
                "parameters": parameters,
                "engine": "ImageMagick",
                "engine_version": self.engine.version,
            }
        )
        extension = ".png"
        relative = f"assets/derived/{operation_hash}{extension}"
        output = project_dir / relative
        if not output.exists():
            stage = self._stage_path(project_dir, extension)
            try:
                generate(self._asset_path(project_dir, source_asset.path), stage)
                os.replace(stage, output)
            finally:
                stage.unlink(missing_ok=True)
        info = self.engine.inspect(output)
        return self._asset_record(
            AssetKind.DERIVED,
            relative,
            output,
            info,
            None,
            operation_hash,
        )

    def _asset_record(
        self,
        kind: AssetKind,
        relative: str,
        path: Path,
        info: ImageInfo,
        source_name: str | None,
        operation_hash: str | None = None,
        warnings: list[str] | None = None,
        ai_provenance: AIProvenance | None = None,
    ) -> AssetRecord:
        normalized_format = ImageFormat.PNG if info.format.upper() == "PNG" else ImageFormat.JPEG
        return AssetRecord(
            id=self.id_provider("ast"),
            kind=kind,
            path=relative,
            sha256=sha256_file(path),
            format=normalized_format,
            mime_type="image/png" if normalized_format is ImageFormat.PNG else "image/jpeg",
            width=info.width,
            height=info.height,
            bit_depth=info.depth,
            has_alpha=info.has_alpha,
            color_space=info.colorspace,
            has_icc_profile=info.has_icc_profile,
            source_name=source_name,
            operation_hash=operation_hash,
            created_at=self.time_provider(),
            warnings=warnings or [],
            ai_provenance=ai_provenance,
        )

    def _operation(
        self,
        operation_type: str,
        targets: list[str],
        inputs: list[str],
        outputs: list[str],
        parameters: dict[str, Any],
        warnings: list[str] | None = None,
    ) -> OperationRecord:
        return OperationRecord(
            id=self.id_provider("op"),
            type=operation_type,
            target_ids=targets,
            input_asset_ids=inputs,
            output_asset_ids=outputs,
            parameters=parameters,
            engine="ImageMagick"
            if operation_type not in {"layer_add", "composite_overlay", "transform_position"}
            else "project",
            engine_version=self.engine.version
            if operation_type not in {"layer_add", "composite_overlay", "transform_position"}
            else "1",
            created_at=self.time_provider(),
            warnings=warnings or [],
        )

    def _commit(self, project_dir: Path, manifest: ProjectManifest) -> None:
        manifest.revision += 1
        manifest.updated_at = self.time_provider()
        validated = ProjectManifest.model_validate(manifest.model_dump(mode="python"))
        atomic_write_json(project_dir / MANIFEST_NAME, validated.model_dump(mode="json"))

    def _project_dir(self, workspace_id: str, project_path: str, *, must_exist: bool) -> Path:
        if not project_path.endswith(".image-work"):
            raise invalid("project_path must end with .image-work.")
        path = self.registry.resolve(workspace_id, project_path, must_exist=must_exist)
        if must_exist and not path.is_dir():
            raise not_found("The project directory does not exist.")
        return path

    @staticmethod
    def _load(project_dir: Path) -> ProjectManifest:
        manifest_path = project_dir / MANIFEST_NAME
        try:
            return ProjectManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise not_found("The project manifest does not exist.") from exc
        except ValueError as exc:
            raise EditorError(
                "PROJECT_INVALID",
                "The project manifest is invalid.",
                False,
                ("Run project_validate or restore a known-good manifest.",),
            ) from exc

    @staticmethod
    def _expect_revision(manifest: ProjectManifest, expected: int) -> None:
        if manifest.revision != expected:
            raise conflict(
                f"Expected revision {expected}, but the project is at revision {manifest.revision}."
            )

    @staticmethod
    def _find_asset(manifest: ProjectManifest, asset_id: str) -> AssetRecord:
        asset = next((item for item in manifest.assets if item.id == asset_id), None)
        if asset is None:
            raise not_found("The requested asset does not exist.")
        return asset

    @staticmethod
    def _find_layer(manifest: ProjectManifest, layer_id: str) -> LayerRecord:
        layer = next((item for item in manifest.layers if item.id == layer_id), None)
        if layer is None:
            raise not_found("The requested layer does not exist.")
        return layer

    @staticmethod
    def _find_conversation(manifest: ProjectManifest, conversation_id: str) -> AIConversationRecord:
        conversation = next(
            (item for item in manifest.ai_conversations if item.id == conversation_id),
            None,
        )
        if conversation is None:
            raise not_found("The requested AI conversation does not exist.")
        return conversation

    def _require_layer_target(
        self, manifest: ProjectManifest, target_id: str | None
    ) -> LayerRecord:
        if target_id is None:
            raise invalid("A layer target requires target_id.")
        return self._find_layer(manifest, target_id)

    @staticmethod
    def _asset_path(project_dir: Path, relative: str) -> Path:
        candidate = project_dir.joinpath(*Path(relative).parts).resolve(strict=True)
        assets_root = (project_dir / "assets").resolve(strict=True)
        try:
            candidate.relative_to(assets_root)
        except ValueError as exc:
            raise EditorError("PATH_OUTSIDE_PROJECT", "An asset path escapes the project.") from exc
        if not candidate.is_file():
            raise not_found("The asset file does not exist.")
        return candidate

    def _render_layers(
        self, project_dir: Path, manifest: ProjectManifest
    ) -> list[tuple[Path, int, int, float]]:
        return [
            (
                self._asset_path(
                    project_dir, layer.asset_id and self._find_asset(manifest, layer.asset_id).path
                ),
                layer.x,
                layer.y,
                layer.opacity,
            )
            for layer in manifest.layers
            if layer.visible
        ]

    @contextmanager
    def _lock(self, project_dir: Path) -> Iterator[None]:
        lock = FileLock(project_dir / ".project.lock", timeout=10)
        try:
            lock.acquire()
        except Timeout as exc:
            raise EditorError(
                "PROJECT_BUSY", "The project is locked by another operation.", True
            ) from exc
        try:
            yield
        finally:
            lock.release()

    def _stage_path(self, project_dir: Path, suffix: str) -> Path:
        return project_dir / ".staging" / f"{self.id_provider('tmp')}{suffix}"

    @staticmethod
    def _commit_export_file(stage: Path, output: Path, overwrite: bool) -> None:
        if overwrite:
            os.replace(stage, output)
            return
        try:
            os.link(stage, output)
        except FileExistsError as exc:
            raise conflict("The export already exists; explicit overwrite is required.") from exc
        stage.unlink()


def _validate_color(value: str, allow_transparent: bool) -> str:
    if allow_transparent and value == "transparent":
        return value
    lowered = value.casefold()
    named = {"black", "white", "red", "green", "blue", "gray", "grey"}
    if lowered in named:
        return lowered
    if len(value) in {4, 7} and value.startswith("#"):
        try:
            int(value[1:], 16)
        except ValueError:
            pass
        else:
            return value
    raise invalid("Background must be a supported color name or #RGB/#RRGGBB.")


def _safe_provider_parameters(value: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, item in value.items():
        if key.casefold() in {"api_key", "authorization", "credentials", "token"}:
            continue
        is_scalar = item is None or isinstance(item, (str, int, float, bool))
        is_safe_list = isinstance(item, list) and all(
            nested is None or isinstance(nested, (str, int, float, bool)) for nested in item
        )
        is_safe_dict = isinstance(item, dict) and all(
            isinstance(nested_key, str)
            and (nested_value is None or isinstance(nested_value, (str, int, float, bool)))
            for nested_key, nested_value in item.items()
        )
        if is_scalar or is_safe_list or is_safe_dict:
            safe[key] = item
    return safe


def _remove_files(paths: list[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)
