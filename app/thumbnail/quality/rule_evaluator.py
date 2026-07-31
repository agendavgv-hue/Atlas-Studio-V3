"""Rule-based QualityEvaluator — metadata/prompt heuristics until Vision AI ships.

Does not invent new thumbnails. Scores the creative package that was already
planned/generated so Atlas can reject weak work before accepting it.
"""

from __future__ import annotations

from app.thumbnail.quality.evaluator import QualityEvaluator
from app.thumbnail.quality.models import QualityEvaluationContext, ThumbnailQualityScore


class RuleBasedQualityEvaluator(QualityEvaluator):
    """Simple CTR / DNA rules. Replace with a Vision evaluator later."""

    @property
    def evaluator_id(self) -> str:
        return "rules_v1"

    def evaluate(self, context: QualityEvaluationContext) -> ThumbnailQualityScore:
        prompt = (context.prompt or "").casefold()
        negative = (context.negative_prompt or "").casefold()
        hook = (context.hook or "").strip()
        hero = (context.hero_subject or "").strip()
        dna = context.channel_dna or {}
        critique = context.critique or {}
        checks = critique.get("checks") if isinstance(critique.get("checks"), list) else []
        check_map = {
            str(item.get("name") or ""): bool(item.get("passed"))
            for item in checks
            if isinstance(item, dict)
        }

        has_image = bool(context.image_png)
        hero_in_prompt = bool(hero) and hero.casefold() in prompt
        single_hero = (
            "single hero" in prompt
            or "exactly one" in prompt
            or "one hero" in prompt
            or check_map.get("single_hero", False)
        )
        simple = (
            "never busy" in prompt
            or "clean" in prompt
            or "simple" in prompt
            or check_map.get("simple_composition", False)
        )
        headline_space = (
            "negative space" in prompt
            or "empty" in prompt and "left" in prompt
            or "headline" in prompt
            or check_map.get("empty_headline_side", False)
        )
        dna_block = "channel dna" in prompt or bool(dna.get("signature"))
        dna_colors = dna.get("color_language") if isinstance(dna.get("color_language"), dict) else {}
        color_hit = any(
            str(value).casefold() in prompt
            for value in dna_colors.values()
            if str(value).strip()
        )
        emotion_ok = bool(context.emotion) and context.emotion.casefold() in prompt
        curiosity_hook = 2 <= len(hook.split()) <= 5 and hook == hook.upper()
        anti_ai = "busy composition" in negative or "watermark" in negative
        supporting_bg = (
            "supporting" in prompt
            or check_map.get("supporting_background", False)
        )
        readable = check_map.get("readable_small", False) or "readable" in prompt or "high contrast" in prompt
        recognizable = check_map.get("channel_recognizable", False) or dna_block
        impact = "ctr" in prompt or "maximum ctr" in prompt or bool(context.click_reason)
        professional = "photorealistic" in prompt or "professional" in prompt

        score = ThumbnailQualityScore(
            hero_subject=_axis(
                10 if hero_in_prompt and single_hero and has_image else 0,
                8 if hero_in_prompt and has_image else 0,
                5 if hero else 0,
            ),
            curiosity=_axis(
                10 if curiosity_hook and emotion_ok else 0,
                8 if curiosity_hook or emotion_ok else 0,
                4 if context.click_reason else 0,
            ),
            composition=_axis(
                10 if simple and supporting_bg else 0,
                8 if simple or supporting_bg else 0,
                5 if "composition" in prompt else 0,
            ),
            headline_space=_axis(
                10 if headline_space else 0,
                7 if "left" in prompt else 0,
                3,
            ),
            impact=_axis(
                10 if impact and emotion_ok else 0,
                8 if impact else 0,
                5 if context.emotion else 0,
            ),
            readability=_axis(
                10 if readable and has_image else 0,
                8 if readable or "high contrast" in prompt else 0,
                4 if has_image else 0,
            ),
            dna=_axis(
                10 if dna_block and (color_hit or recognizable) else 0,
                8 if dna_block or recognizable else 0,
                4 if dna else 0,
            ),
            ctr=_axis(
                10 if impact and curiosity_hook and single_hero else 0,
                8 if impact and (curiosity_hook or single_hero) else 0,
                5 if impact else 0,
            ),
            simplicity=_axis(
                10 if simple and anti_ai else 0,
                8 if simple or anti_ai else 0,
                4,
            ),
            professional=_axis(
                10 if professional and anti_ai and has_image else 0,
                8 if professional or anti_ai else 0,
                4 if has_image else 0,
            ),
            notes="Rule-based QA (Vision AI not enabled).",
            evaluator_id=self.evaluator_id,
        )
        return score.with_clamped_axes()


def _axis(high: int, mid: int, low: int) -> int:
    if high:
        return high
    if mid:
        return mid
    return low
