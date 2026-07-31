"""Assemble optimized PromptBlocks into a model-specific prompt string."""

from __future__ import annotations

from app.thumbnail.prompt_intelligence.blocks import PromptBlocks
from app.thumbnail.prompt_intelligence.model_profiles import ModelPromptProfile
from app.thumbnail.prompt_intelligence.optimizer import optimize_negative, optimize_text
from app.thumbnail.prompt_intelligence.semantics import resolve_contradictions


def assemble_prompt(
    blocks: PromptBlocks,
    profile: ModelPromptProfile,
) -> tuple[str, str, PromptBlocks, list[str]]:
    """Return (positive_prompt, negative_prompt, cleaned_blocks, semantic_fixes)."""
    semantic = resolve_contradictions(blocks)
    cleaned = semantic.blocks
    max_words = profile.max_block_words if profile.prefer_short_blocks else None

    positive_parts: list[str] = []
    for name, text in cleaned.ordered_positive_items():
        optimized = optimize_text(text, max_words=max_words)
        if not optimized:
            continue
        if profile.cinematography_bias and name in {"lighting", "camera", "mood"}:
            optimized = _cinematic_touch(optimized, name)
        if profile.label_blocks:
            optimized = f"{name.replace('_', ' ')}: {optimized}"
        positive_parts.append(optimized)

    # Intra-prompt dedupe of near-identical consecutive fragments
    positive_parts = _dedupe_parts(positive_parts)

    if profile.use_commas and profile.separator.strip() == ",":
        separator = ", "
    else:
        separator = profile.separator or ". "

    positive = separator.join(positive_parts)
    if profile.use_commas:
        # Normalize residual sentence periods into the model's preferred commas.
        if separator.strip().startswith(","):
            positive = positive.replace(". ", ", ")
    else:
        positive = positive.replace(",,", ",")

    negative = optimize_negative(cleaned.negative_prompt)
    cleaned.subject = optimize_text(cleaned.subject, max_words=max_words)
    cleaned.environment = optimize_text(cleaned.environment, max_words=max_words)
    cleaned.lighting = optimize_text(cleaned.lighting, max_words=max_words)
    cleaned.composition = optimize_text(cleaned.composition, max_words=max_words)
    cleaned.camera = optimize_text(cleaned.camera, max_words=max_words)
    cleaned.mood = optimize_text(cleaned.mood, max_words=max_words)
    cleaned.style = optimize_text(cleaned.style, max_words=max_words)
    cleaned.materials = optimize_text(cleaned.materials, max_words=max_words)
    cleaned.color_palette = optimize_text(cleaned.color_palette, max_words=max_words)
    cleaned.quality = optimize_text(cleaned.quality, max_words=max_words)
    cleaned.negative_prompt = negative

    return positive.strip(), negative, cleaned, list(semantic.fixed)


def _cinematic_touch(text: str, name: str) -> str:
    lowered = text.casefold()
    if name == "lighting" and "cinematic" not in lowered and "key light" not in lowered:
        return f"{text}, cinematic key light"
    if name == "camera" and "cinematic" not in lowered and "lens" not in lowered:
        return f"{text}, cinematic framing"
    return text


def _dedupe_parts(parts: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        key = part.casefold().strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(part)
    return out
