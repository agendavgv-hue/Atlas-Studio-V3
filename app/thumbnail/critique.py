"""Thumbnail Critique Planner — gate prompts against Channel DNA before generate.

If any CTR / DNA check fails, the prompt is rewritten. Images are never
generated from a failing prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.providers.base import TextProvider
from app.providers.errors import ProviderError
from app.thumbnail.anti_ai import AntiAiRules
from app.thumbnail.dna_loader import ChannelDNA
from app.thumbnail.prompt_builder import ThumbnailPromptPlan
from app.thumbnail.text_utils import parse_json_object
from app.thumbnail.thumbnail_director import ThumbnailStrategy

CRITIQUE_CHECKS = (
    "single_hero",
    "simple_composition",
    "supporting_background",
    "readable_small",
    "empty_headline_side",
    "channel_recognizable",
)


@dataclass(frozen=True)
class CritiqueCheckResult:
    name: str
    passed: bool
    note: str = ""


@dataclass(frozen=True)
class PromptCritique:
    """Outcome of critiquing one variant prompt."""

    variant_id: str
    passed: bool
    checks: tuple[CritiqueCheckResult, ...]
    original_prompt: str
    final_prompt: str
    rewritten: bool
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "passed": self.passed,
            "rewritten": self.rewritten,
            "notes": self.notes,
            "checks": [
                {"name": item.name, "passed": item.passed, "note": item.note}
                for item in self.checks
            ],
            "original_prompt": self.original_prompt,
            "final_prompt": self.final_prompt,
        }


_SYSTEM = (
    "You are a ruthless YouTube Thumbnail Critique Planner. "
    "You protect Channel DNA and CTR. "
    "A thumbnail must be instantly recognizable as this channel without a logo. "
    "If ANY check fails, you rewrite the prompt."
)

_USER_TEMPLATE = """Critique this thumbnail IMAGE PROMPT before generation.

Channel: {channel_name}
Channel DNA:
{dna_block}

Strategy emotion: {emotion}
Click reason: {click_reason}
Hero subject (must remain singular): {hero}

Anti-AI bans (must obey):
{anti_ai}

Prompt to critique:
---
{prompt}
---

Checks (answer true/false for each):
1. single_hero — exactly one hero subject
2. simple_composition — composition is simple enough (not busy)
3. supporting_background — background supports, never competes
4. readable_small — readable / clear at small YouTube grid size
5. empty_headline_side — headline side has enough empty space
6. channel_recognizable — would a viewer recognize this channel without a logo

Rules:
- If ANY check is false, set passed=false and rewrite the full prompt.
- Rewritten prompt must keep the same hero, emotion, and Channel DNA.
- Never add text/watermarks/logos into the image.
- Return ONLY JSON.

{{
  "passed": true/false,
  "checks": {{
    "single_hero": true/false,
    "simple_composition": true/false,
    "supporting_background": true/false,
    "readable_small": true/false,
    "empty_headline_side": true/false,
    "channel_recognizable": true/false
  }},
  "notes": "short critique",
  "rewritten_prompt": "full prompt if passed is false, else empty string"
}}
"""


class ThumbnailCritiquePlanner:
    """Pre-generation gate: DNA + CTR checks, rewrite on failure."""

    def __init__(self, text_provider: TextProvider) -> None:
        self._text = text_provider

    def critique_plans(
        self,
        plans: list[ThumbnailPromptPlan],
        *,
        strategy: ThumbnailStrategy,
        hero_subject: str,
        dna: ChannelDNA,
        anti_ai: AntiAiRules,
        channel_name: str = "",
    ) -> tuple[list[ThumbnailPromptPlan], list[PromptCritique]]:
        critiqued: list[ThumbnailPromptPlan] = []
        reports: list[PromptCritique] = []
        for plan in plans:
            report = self.critique_prompt(
                plan.prompt,
                variant_id=plan.variant_id,
                strategy=strategy,
                hero_subject=hero_subject,
                dna=dna,
                anti_ai=anti_ai,
                channel_name=channel_name,
            )
            reports.append(report)
            critiqued.append(
                ThumbnailPromptPlan(
                    variant_id=plan.variant_id,
                    variant_key=plan.variant_key,
                    variant_label=plan.variant_label,
                    prompt=report.final_prompt,
                    negative_prompt=plan.negative_prompt,
                )
            )
        return critiqued, reports

    def critique_prompt(
        self,
        prompt: str,
        *,
        variant_id: str,
        strategy: ThumbnailStrategy,
        hero_subject: str,
        dna: ChannelDNA,
        anti_ai: AntiAiRules,
        channel_name: str = "",
    ) -> PromptCritique:
        original = (prompt or "").strip()
        if not original:
            raise ProviderError("Cannot critique an empty thumbnail prompt.")

        user = _USER_TEMPLATE.format(
            channel_name=(channel_name or dna.display_name or "Unknown").strip()
            or "Unknown",
            dna_block=dna.dna_block(),
            emotion=strategy.emotion,
            click_reason=strategy.click_reason,
            hero=(hero_subject or strategy.hero_subject).strip(),
            anti_ai="; ".join(anti_ai.forbidden) if anti_ai.forbidden else anti_ai.negative_prompt,
            prompt=original,
        )
        try:
            raw = self._text.generate_text(user, system=_SYSTEM)
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Thumbnail critique failed: {exc}") from exc

        data = parse_json_object(raw, label="Thumbnail critique")
        checks_raw = data.get("checks") if isinstance(data.get("checks"), dict) else {}
        checks: list[CritiqueCheckResult] = []
        for name in CRITIQUE_CHECKS:
            value = checks_raw.get(name, True)
            passed = _as_bool(value, default=True)
            checks.append(CritiqueCheckResult(name=name, passed=passed))

        all_passed = all(item.passed for item in checks) and _as_bool(
            data.get("passed"), default=all(item.passed for item in checks)
        )
        notes = str(data.get("notes") or "").strip()
        rewritten_prompt = str(data.get("rewritten_prompt") or "").strip()

        if all_passed:
            final = original
            rewritten = False
            passed = True
        else:
            final = rewritten_prompt or _fallback_rewrite(
                original, hero=hero_subject or strategy.hero_subject, dna=dna
            )
            rewritten = final != original
            passed = False

        return PromptCritique(
            variant_id=variant_id,
            passed=passed,
            checks=tuple(checks),
            original_prompt=original,
            final_prompt=final,
            rewritten=rewritten,
            notes=notes,
        )


def _as_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().casefold()
    if text in {"true", "yes", "1", "pass", "passed"}:
        return True
    if text in {"false", "no", "0", "fail", "failed"}:
        return False
    return default


def _fallback_rewrite(original: str, *, hero: str, dna: ChannelDNA) -> str:
    """Deterministic safety rewrite if the model fails to supply one."""
    return (
        f"{original.rstrip().rstrip('.')} "
        f"STRICT DNA ENFORCEMENT: exactly one hero subject ({hero}), "
        f"clean simple composition, supporting background only, "
        f"empty {dna.visual_language.headline_side} side for headline, "
        f"high contrast, instantly recognizable as {dna.display_name}, "
        "no text, no watermark, no logo, no clutter."
    )
