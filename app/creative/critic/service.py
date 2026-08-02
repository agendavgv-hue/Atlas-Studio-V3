"""CriticService — evaluate generator output; never create or mutate content."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.creative.critic.context import context_as_policy, load_critic_context
from app.creative.critic.domains import CriticDomain
from app.creative.critic.evaluate import evaluate_payload
from app.creative.critic.report import CriticReport
from app.creative.critic.rules import CriticRule
from app.creative.critic.score import CriticScore
from app.creative.critic.settings import CriticSettings
from app.creative.critic.store import (
    append_report,
    load_settings,
    read_reports,
    save_settings,
)


class CriticService:
    """Central AI Critic entry point for every Atlas generator."""

    def __init__(
        self,
        data_root: Path,
        *,
        extra_rules: list[CriticRule] | None = None,
    ) -> None:
        self._data_root = Path(data_root)
        self._extra_rules = list(extra_rules or [])

    @property
    def data_root(self) -> Path:
        return self._data_root

    def get_settings(self, channel: str) -> CriticSettings:
        return load_settings(self._data_root, channel)

    def set_minimum_score(self, channel: str, minimum: float) -> CriticSettings:
        settings = self.get_settings(channel)
        settings.minimum_score = max(0.0, min(100.0, float(minimum)))
        save_settings(self._data_root, channel, settings)
        return settings

    def evaluate(
        self,
        channel: str,
        domain: str | CriticDomain,
        payload: dict[str, Any] | None = None,
        *,
        project: str = "",
        generator: str = "",
        persist: bool | None = None,
        minimum_score: float | None = None,
    ) -> CriticReport:
        """Judge output against Creative Director, Brand, Style, Channel Brain."""
        domain_key = (
            domain if isinstance(domain, CriticDomain) else CriticDomain.parse(str(domain))
        )
        settings = self.get_settings(channel)
        minimum = float(
            minimum_score if minimum_score is not None else settings.minimum_score
        )
        ctx = load_critic_context(self._data_root, channel)
        policy = context_as_policy(ctx)
        score, findings = evaluate_payload(
            domain_key,
            dict(payload or {}),
            policy,
            extra_rules=self._extra_rules,
        )
        problems = [f.message for f in findings]
        report = CriticReport(
            channel=channel.strip(),
            domain=domain_key.value,
            generator=generator or domain_key.value,
            project=project,
            score=score,
            minimum_score=minimum,
            problems=problems,
            findings=list(findings),
            consistency={
                "brand": score.brand,
                "style": score.style,
                "identity": score.identity,
                "composition": score.composition,
            },
            notes=[
                "Critic judges only — it does not generate or modify content.",
                f"Sources: Creative Director, Brand Kit, Style Library"
                + (", Channel Brain" if ctx.brain is not None else ""),
            ],
        )
        report.refresh_status()

        should_persist = settings.persist_reports if persist is None else persist
        if should_persist:
            append_report(
                self._data_root,
                channel,
                report,
                max_reports=settings.max_reports,
            )
        return report

    def approve(
        self,
        channel: str,
        domain: str | CriticDomain,
        payload: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> bool:
        return self.evaluate(channel, domain, payload, **kwargs).approved

    def read_history(self, channel: str) -> list[CriticReport]:
        return read_reports(self._data_root, channel)

    def last_report(self, channel: str, *, domain: str | None = None) -> CriticReport | None:
        history = self.read_history(channel)
        if domain:
            key = CriticDomain.parse(domain).value
            history = [r for r in history if r.domain == key]
        return history[-1] if history else None
