"""Production Sheet pipeline — generates a production sheet from the resolved script."""

from __future__ import annotations

from app.artifacts import ArtifactKind, ArtifactResolver
from app.pipelines.artifacts import PRODUCTION_SHEET_FILENAME, SCRIPT_FOLDER
from app.pipelines.base import Pipeline
from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.prompts.assembler import PromptAssembler
from app.providers.base import TextProvider
from app.providers.errors import ProviderError


class ProductionSheetPipeline(Pipeline):
    def __init__(
        self,
        provider: TextProvider,
        prompts: PromptAssembler | None = None,
    ) -> None:
        super().__init__()
        self._provider = provider
        self._prompts = prompts or PromptAssembler()

    @property
    def pipeline_id(self) -> str:
        return "production_sheet"

    @property
    def name(self) -> str:
        return "Production Sheet"

    def validate(self, context: PipelineContext) -> list[str]:
        errors = super().validate(context)
        script_path = ArtifactResolver(context.project_dir).find(ArtifactKind.SCRIPT)
        if script_path is None:
            errors.append("No script artifact found. Generate a script first.")
            return errors
        try:
            if not script_path.read_text(encoding="utf-8").strip():
                errors.append(f"Script artifact is empty: {script_path.name}")
        except OSError as exc:
            errors.append(f"Cannot read script artifact: {exc}")
        return errors

    def run(self, context: PipelineContext) -> PipelineResult:
        resolver = ArtifactResolver(context.project_dir)
        script_path = resolver.find(ArtifactKind.SCRIPT)
        if script_path is None:
            return PipelineResult.failed("No script artifact found.")

        script_text = script_path.read_text(encoding="utf-8")
        self._set_progress(0.1, "Building prompt")
        request = self._prompts.production_sheet_prompt(context, script_text)
        self._set_progress(0.35, "Generating production sheet")
        try:
            text = self._provider.generate_text(request.user, system=request.system)
        except ProviderError as exc:
            return PipelineResult.failed(str(exc), errors=[str(exc)])

        if self.is_cancel_requested():
            return PipelineResult.cancelled()

        existing = resolver.find(ArtifactKind.PRODUCTION_SHEET)
        path = existing if existing is not None else context.folder(SCRIPT_FOLDER) / PRODUCTION_SHEET_FILENAME
        path.write_text(text.strip() + "\n", encoding="utf-8")
        self._set_progress(1.0, "Production sheet saved")
        rel = f"{path.parent.name}/{path.name}"
        return PipelineResult.success(
            "Production sheet generated",
            artifacts=[rel],
        )
