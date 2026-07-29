"""Script pipeline — generates script/script.txt via TextProvider."""

from __future__ import annotations

from app.pipelines.artifacts import SCRIPT_FILENAME, SCRIPT_FOLDER
from app.pipelines.base import Pipeline
from app.pipelines.context import PipelineContext
from app.pipelines.results import PipelineResult
from app.prompts.assembler import PromptAssembler
from app.providers.base import TextProvider
from app.providers.errors import ProviderError


class ScriptPipeline(Pipeline):
    def __init__(
        self,
        provider: TextProvider,
        prompts: PromptAssembler | None = None,
        *,
        topic: str | None = None,
    ) -> None:
        super().__init__()
        self._provider = provider
        self._prompts = prompts or PromptAssembler()
        self._topic = (topic or "").strip()

    @property
    def pipeline_id(self) -> str:
        return "script"

    @property
    def name(self) -> str:
        return "Script"

    def validate(self, context: PipelineContext) -> list[str]:
        errors = super().validate(context)
        topic = self._topic or context.project.idea.strip() or context.project.name.strip()
        if not topic:
            errors.append("Enter a topic before generating a script.")
        return errors

    def run(self, context: PipelineContext) -> PipelineResult:
        topic = self._topic or context.project.idea.strip() or context.project.name
        self._set_progress(0.1, "Building prompt")
        request = self._prompts.script_prompt(context, topic)
        self._set_progress(0.35, "Generating script")
        try:
            text = self._provider.generate_text(request.user, system=request.system)
        except ProviderError as exc:
            return PipelineResult.failed(str(exc), errors=[str(exc)])

        if self.is_cancel_requested():
            return PipelineResult.cancelled()

        path = context.folder(SCRIPT_FOLDER) / SCRIPT_FILENAME
        path.write_text(text.strip() + "\n", encoding="utf-8")
        self._set_progress(1.0, "Script saved")
        return PipelineResult.success(
            "Script generated",
            artifacts=[f"{SCRIPT_FOLDER}/{SCRIPT_FILENAME}"],
        )
