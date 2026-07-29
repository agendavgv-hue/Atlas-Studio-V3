"""Assemble prompts: Global → Channel → Project → Pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from app.pipelines.context import PipelineContext
from app.prompts import defaults


@dataclass(frozen=True)
class PromptRequest:
    system: str
    user: str


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

    def _system_layers(self, context: PipelineContext) -> str:
        layers = [defaults.GLOBAL_SYSTEM]
        if context.channel_defaults.name:
            layers.append(f"You are producing content for the channel '{context.channel_defaults.name}'.")
        return "\n".join(layers)
