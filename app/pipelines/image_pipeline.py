"""Image pipeline — Generate Images from production sheet prompts via ImageProvider."""

from __future__ import annotations

from collections.abc import Callable

from app.artifacts import ArtifactKind, ArtifactResolver
from app.pipelines.base import Pipeline
from app.pipelines.context import PipelineContext
from app.pipelines.image_naming import image_basename, resolve_images_dir
from app.pipelines.results import PipelineResult
from app.pipelines.sheet_prompts import SheetImagePrompt, extract_image_prompts
from app.prompts.assembler import PromptAssembler
from app.providers.errors import ProviderError
from app.providers.image_base import ImageGenerationRequest, ImageProvider

# current, total, message, prompt
ProgressCallback = Callable[[int, int, str, str], None]


class ImagePipeline(Pipeline):
    """Professional image production. Prefer ``generate_all`` / ``generate_image``."""

    def __init__(
        self,
        provider: ImageProvider,
        prompts: PromptAssembler | None = None,
        *,
        global_negative: str = "",
        indexes: list[int] | None = None,
        on_queue_progress: ProgressCallback | None = None,
    ) -> None:
        super().__init__()
        self._provider = provider
        self._prompts = prompts or PromptAssembler()
        self._global_negative = global_negative
        # None = all; otherwise 1-based indexes for generate_image / future retry.
        self._indexes = indexes
        self._on_queue_progress = on_queue_progress

    @property
    def pipeline_id(self) -> str:
        return "images"

    @property
    def name(self) -> str:
        return "Images"

    def validate(self, context: PipelineContext) -> list[str]:
        """Validate project, sheet, Forge, model, and output folder before any generation."""
        errors = super().validate(context)
        if errors:
            return errors

        # Production sheet
        sheet = ArtifactResolver(context.project_dir).find(ArtifactKind.PRODUCTION_SHEET)
        if sheet is None:
            errors.append("No production sheet found. Generate Production first.")
            return errors
        try:
            text = sheet.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"Cannot read production sheet: {exc}")
            return errors
        prompts = extract_image_prompts(text)
        if not prompts:
            errors.append("No image prompts found in the production sheet.")
            return errors
        if self._indexes:
            valid = {item.index for item in prompts}
            for index in self._indexes:
                if index not in valid:
                    errors.append(f"Image index {index} is out of range (1–{len(prompts)}).")
            if errors:
                return errors

        # Forge connection + selected model (no generation attempts if this fails)
        try:
            self._provider.validate_ready()
        except ProviderError as exc:
            errors.append(str(exc))
            return errors
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Image provider validation failed: {exc}")
            return errors

        # Output folder (images/ preferred; legacy image/ accepted; else create images/)
        try:
            images_dir = resolve_images_dir(context.project_dir)
            if not images_dir.is_dir():
                errors.append(f"Images output folder is not available: {images_dir}")
            else:
                probe = images_dir / ".atlas_write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"Images output folder is not writable: {exc}")

        return errors

    def run(self, context: PipelineContext) -> PipelineResult:
        return self.generate_all(context)

    def generate_all(self, context: PipelineContext) -> PipelineResult:
        prompts = self._load_prompts(context)
        targets = [item.index for item in prompts]
        if self._indexes is not None:
            wanted = set(self._indexes)
            targets = [index for index in targets if index in wanted]
        return self._generate_indexes(context, prompts, targets)

    def generate_image(self, context: PipelineContext, index: int) -> PipelineResult:
        """Regenerate a single 1-based image without redesigning the pipeline."""
        prompts = self._load_prompts(context)
        return self._generate_indexes(context, prompts, [index])

    def _load_prompts(self, context: PipelineContext) -> list[SheetImagePrompt]:
        sheet = ArtifactResolver(context.project_dir).find(ArtifactKind.PRODUCTION_SHEET)
        if sheet is None:
            return []
        return extract_image_prompts(sheet.read_text(encoding="utf-8"))

    def _generate_indexes(
        self,
        context: PipelineContext,
        prompts: list[SheetImagePrompt],
        indexes: list[int],
    ) -> PipelineResult:
        by_index = {item.index: item for item in prompts}
        total = len(indexes)
        if total == 0:
            return PipelineResult.failed("No images selected for generation.")

        artifacts: list[str] = []
        errors: list[str] = []
        failed: list[int] = []
        succeeded: list[int] = []
        images_dir = resolve_images_dir(context.project_dir)

        for position, index in enumerate(indexes, start=1):
            if self.is_cancel_requested():
                return PipelineResult.cancelled(
                    queue_current=position,
                    queue_total=total,
                    failed_indexes=failed,
                    succeeded_indexes=succeeded,
                    artifacts=artifacts,
                )

            message = f"Image {position} / {total}"
            fraction = position / total
            self._set_progress(fraction, message)

            item = by_index.get(index)
            if item is None:
                self._emit_queue(position, total, message, "")
                failed.append(index)
                errors.append(f"Image {index}: prompt not found.")
                continue

            # Status before Forge call — cancel only stops before the next image.
            self._emit_queue(position, total, message, item.prompt)

            assembled = self._prompts.image_prompt(
                context,
                item.prompt,
                global_negative=self._global_negative,
            )
            request = ImageGenerationRequest(
                prompt=assembled.prompt,
                negative_prompt=assembled.negative_prompt,
            )
            try:
                response = self._provider.generate_image(request)
            except ProviderError as exc:
                failed.append(index)
                errors.append(f"Image {index}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001
                failed.append(index)
                errors.append(f"Image {index}: {exc}")
                continue

            image_path = images_dir / image_basename(index)
            image_path.write_bytes(response.image_png)
            artifacts.append(f"{images_dir.name}/{image_path.name}")
            succeeded.append(index)

        if not succeeded and failed:
            return PipelineResult.failed(
                f"All {total} image(s) failed",
                errors=errors,
                queue_current=total,
                queue_total=total,
                failed_indexes=failed,
                succeeded_indexes=succeeded,
            )
        if failed:
            return PipelineResult.warning(
                f"Generated {len(succeeded)}/{total} images; {len(failed)} failed",
                errors=errors,
                artifacts=artifacts,
                queue_current=total,
                queue_total=total,
                failed_indexes=failed,
                succeeded_indexes=succeeded,
            )
        return PipelineResult.success(
            f"Generated {len(succeeded)} image(s)",
            artifacts=artifacts,
            queue_current=total,
            queue_total=total,
            failed_indexes=failed,
            succeeded_indexes=succeeded,
        )

    def _emit_queue(self, current: int, total: int, message: str, prompt: str = "") -> None:
        if self._on_queue_progress is not None:
            self._on_queue_progress(current, total, message, prompt)
