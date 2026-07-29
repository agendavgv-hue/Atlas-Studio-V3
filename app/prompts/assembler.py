"""Assemble prompts: Global → Channel → Project → Pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from app.pipelines.context import PipelineContext
from app.prompts import defaults


@dataclass(frozen=True)
class PromptRequest:
    system: str
    user: str


@dataclass(frozen=True)
class ImagePromptRequest:
    """Final positive + negative prompts for an image provider."""

    prompt: str
    negative_prompt: str


class PromptAssembler:
    """Builds provider-ready prompts from layered sources."""

    def script_prompt(self, context: PipelineContext, topic: str) -> PromptRequest:
        system = self._system_layers(context)
        channel_hint = context.channel_defaults.image_prompt.strip()
        parts = [
            defaults.SCRIPT_PIPELINE_INSTRUCTION,
            f"Channel: {context.channel_name}",
            f"Topic: {topic.strip()}",
        ]
        if channel_hint:
            parts.append(f"Channel creative guidance: {channel_hint}")
        if context.project.idea.strip() and context.project.idea.strip() != topic.strip():
            parts.append(f"Project notes: {context.project.idea.strip()}")
        return PromptRequest(system=system, user="\n\n".join(parts))

    def production_sheet_prompt(self, context: PipelineContext, script_text: str) -> PromptRequest:
        system = self._system_layers(context)
        user = "\n\n".join(
            [
                defaults.PRODUCTION_SHEET_PIPELINE_INSTRUCTION,
                f"Channel: {context.channel_name}",
                f"Project: {context.project_name}",
                "Script:",
                script_text.strip(),
            ]
        )
        return PromptRequest(system=system, user=user)

    def image_prompt(
        self,
        context: PipelineContext,
        sheet_prompt: str,
        *,
        global_negative: str = "",
    ) -> ImagePromptRequest:
        """Global → Channel → Production Sheet prompt → Negative hierarchy."""
        layers: list[str] = []
        if defaults.GLOBAL_IMAGE_STYLE.strip():
            layers.append(defaults.GLOBAL_IMAGE_STYLE.strip())
        channel_style = context.channel_defaults.image_prompt.strip()
        if channel_style:
            layers.append(channel_style)
        layers.append(sheet_prompt.strip())
        positive = ", ".join(part for part in layers if part)

        negatives: list[str] = []
        if global_negative.strip():
            negatives.append(global_negative.strip())
        channel_neg = context.channel_defaults.negative_prompt.strip()
        if channel_neg:
            negatives.append(channel_neg)
        negative = ", ".join(dict.fromkeys(negatives))
        return ImagePromptRequest(prompt=positive, negative_prompt=negative)

    def _system_layers(self, context: PipelineContext) -> str:
        layers = [defaults.GLOBAL_SYSTEM]
        if context.channel_defaults.name:
            layers.append(
                f"You are producing content for the channel '{context.channel_defaults.name}'."
            )
        return "\n".join(layers)
