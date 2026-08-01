"""AI Channel Creator — generate Channel DNA for NEW channels only.

Never mutates Hollow Atlas or Mirror Drift configurations.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.channels.generated_profile import GeneratedChannelProfile
from app.channels.reference_channels import assert_not_reference_channel
from app.providers.base import TextProvider
from app.thumbnail.text_utils import parse_json_object

_SYSTEM = (
    "You are Atlas Studio's Channel DNA architect. Design a complete YouTube "
    "channel visual identity for a NEW channel. Return JSON only. "
    "Do not mention Hollow Atlas or Mirror Drift as the channel name. "
    "The new channel must feel premium and instantly recognizable."
)

_USER = """Design Channel DNA for a new YouTube channel.

Name: {name}
Concept / niche: {concept}
Tone hints: {tone}

Return ONLY JSON with this shape:
{{
  "description": "one sentence channel description",
  "image_prompt": "rich house-style image prompt for Stable Diffusion (grading, light, materials, composition)",
  "negative_prompt": "artifacts and looks to avoid",
  "thumbnail_prompt": "thumbnail framing guidance",
  "outro_line": "spoken main-video closing line (NOT a Shorts CTA, NOT 'watch the full episode')",
  "voice": {{
    "provider": "kokoro",
    "gender": "Male or Female",
    "style_tags": ["tag1", "tag2", "tag3"],
    "language": "en-US",
    "speed": 1.0
  }},
  "dna": {{
    "display_name": "{name}",
    "signature": "one sentence: how a frame is recognizable without a logo",
    "emotion": ["emotion1", "emotion2", "emotion3"],
    "visual_language": {{
      "simplicity": "high",
      "hero_subjects": 1,
      "composition": "clean",
      "background": "supporting only",
      "contrast": "high",
      "headline_side": "left",
      "headline_size": "very_large",
      "empty_space": "required"
    }},
    "color_language": {{
      "primary": "...",
      "secondary": "...",
      "accent": "..."
    }},
    "identity_rules": ["rule1", "rule2", "rule3", "rule4"]
  }},
  "style": {{
    "display_name": "{name}",
    "colors": "color grading phrase",
    "lighting": "lighting phrase",
    "style": "overall style phrase",
    "atmosphere": "atmosphere phrase",
    "composition": "composition phrase with left headline space",
    "camera": "camera phrase",
    "contrast": "contrast phrase",
    "texture": "texture phrase",
    "background_style": "supporting background only, ...",
    "headline_position": "left",
    "headline_color": "readable color",
    "headline_shadow": "strong shadow for readability",
    "hero_scale": "hero subject fills about 40 percent of the frame",
    "depth": "strong depth phrase",
    "negative_prompt": "thumbnail negatives",
    "thumbnail_rules": "one hero, left free for headline, readable at small size, no baked-in text"
  }}
}}
"""


class AIChannelCreator:
    """Builds a GeneratedChannelProfile from a brief (AI or deterministic fallback)."""

    def __init__(self, text_provider: TextProvider | None = None) -> None:
        self._text = text_provider

    def generate(
        self,
        *,
        name: str,
        concept: str,
        tone: str = "",
    ) -> GeneratedChannelProfile:
        assert_not_reference_channel(name, action="create")
        cleaned = name.strip()
        concept_text = (concept or "").strip() or f"Premium YouTube channel: {cleaned}"
        tone_text = (tone or "").strip() or "cinematic, premium, distinctive"

        if self._text is not None:
            try:
                raw = self._text.generate_text(
                    _USER.format(name=cleaned, concept=concept_text, tone=tone_text),
                    system=_SYSTEM,
                )
                data = parse_json_object(raw, label="Channel DNA")
                profile = _profile_from_mapping(cleaned, data)
                if profile.image_prompt.strip():
                    return profile
            except Exception:  # noqa: BLE001
                pass

        return _fallback_profile(cleaned, concept_text, tone_text)


def _profile_from_mapping(name: str, data: dict[str, Any]) -> GeneratedChannelProfile:
    dna = data.get("dna") if isinstance(data.get("dna"), dict) else {}
    style = data.get("style") if isinstance(data.get("style"), dict) else {}
    voice = data.get("voice") if isinstance(data.get("voice"), dict) else {}
    dna = dict(dna)
    dna.setdefault("display_name", name)
    style = dict(style)
    style.setdefault("display_name", name)
    outro = str(data.get("outro_line") or "").strip()
    if "full episode" in outro.casefold():
        outro = f"Stay curious. More stories await on {name}."
    return GeneratedChannelProfile(
        name=name,
        description=str(data.get("description") or "").strip(),
        image_prompt=str(data.get("image_prompt") or "").strip(),
        negative_prompt=str(data.get("negative_prompt") or "").strip(),
        thumbnail_prompt=str(data.get("thumbnail_prompt") or "").strip(),
        outro_line=outro,
        voice={
            "provider": str(voice.get("provider") or "kokoro"),
            "gender": str(voice.get("gender") or "Male"),
            "style_tags": [
                str(t).strip()
                for t in (voice.get("style_tags") or [])
                if str(t).strip()
            ]
            or ["Clear", "Confident", "Cinematic"],
            "language": str(voice.get("language") or "en-US"),
            "speed": float(voice.get("speed") or 1.0),
        },
        dna=dna,
        style=style,
    )


def _fallback_profile(name: str, concept: str, tone: str) -> GeneratedChannelProfile:
    """Deterministic DNA when no text provider is available."""
    slug = re.sub(r"\s+", " ", name).strip()
    concept_clean = concept.strip()
    tone_clean = tone.strip()
    image_prompt = (
        f"{slug} house style: {concept_clean}, {tone_clean}, cinematic framing, "
        "strong subject hierarchy, coherent color grading, premium production still, "
        "photoreal materials, distinctive brand atmosphere, consistent film look"
    )
    negative = (
        "blurry, lowres, watermark, text, logo, cartoon, anime, collage, "
        "generic stock photo, flat lighting, cluttered composition"
    )
    return GeneratedChannelProfile(
        name=slug,
        description=concept_clean[:180],
        image_prompt=image_prompt,
        negative_prompt=negative,
        thumbnail_prompt=(
            f"one iconic {slug} subject, high contrast, open left third for headline, "
            "clean focus, readable at YouTube small size"
        ),
        outro_line=f"The story continues. Stay with {slug}.",
        voice={
            "provider": "kokoro",
            "gender": "Male",
            "style_tags": ["Clear", "Confident", "Cinematic"],
            "language": "en-US",
            "speed": 1.0,
        },
        dna={
            "display_name": slug,
            "signature": (
                f"A {slug} frame is unmistakable without a logo: one clear hero, "
                f"{tone_clean or 'premium'} grading, high contrast, open headline space."
            ),
            "emotion": ["curiosity", "awe", "discovery"],
            "visual_language": {
                "simplicity": "high",
                "hero_subjects": 1,
                "composition": "clean",
                "background": "supporting only",
                "contrast": "high",
                "headline_side": "left",
                "headline_size": "very_large",
                "empty_space": "required",
            },
            "color_language": {
                "primary": "brand key light",
                "secondary": "deep supporting dark",
                "accent": "subtle highlight",
            },
            "identity_rules": [
                "one hero only",
                "background supporting only",
                "left third empty for headline",
                "readable at YouTube small size",
                f"reflects: {concept_clean[:80]}",
            ],
        },
        style={
            "display_name": slug,
            "colors": f"{tone_clean or 'premium'} color grading, high contrast, muted supporting tones",
            "lighting": "cinematic key light, soft rim, controlled falloff, left side darker for headline",
            "style": f"{slug} Style Engine: {concept_clean}, photoreal, premium, distinctive brand look",
            "atmosphere": f"{tone_clean or 'cinematic'}, focused, premium",
            "composition": "hero on the right third, open darkened left third for headline, clean single focus",
            "camera": "medium-close cinematic framing, shallow depth of field",
            "contrast": "high contrast, filmic grade, maximum clickability",
            "texture": "realistic materials, tactile surfaces",
            "background_style": "supporting background only, no clutter, soft bokeh",
            "headline_position": "left",
            "headline_color": "high-contrast light",
            "headline_shadow": "strong dark drop shadow plus outline",
            "hero_scale": "hero subject fills about 40 percent of the frame",
            "depth": "strong foreground-to-background depth",
            "negative_prompt": negative,
            "thumbnail_rules": (
                "one hero subject, left side free for headline, clear background, "
                "strong focus, high contrast, readable at small YouTube size, "
                "no baked-in text from the image model"
            ),
        },
    )
