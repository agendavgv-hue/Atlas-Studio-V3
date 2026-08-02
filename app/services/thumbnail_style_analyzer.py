"""AI style analysis of reference thumbnails (style only — never content)."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Protocol

from app.models.thumbnail_dna import ThumbnailDNA
from app.providers.errors import ProviderError
from app.thumbnail.text_utils import parse_json_object

_SYSTEM = (
    "You are Atlas Studio's Thumbnail Style Analyst. "
    "Analyze ONLY visual STYLE across reference YouTube thumbnails. "
    "Do NOT describe story content, objects as plot, or what the video is about. "
    "Average style signals across ALL images. Return JSON only."
)

_USER = """Analyze these {count} reference thumbnails for channel "{channel}".

Focus exclusively on style averages:
- layout (title position, subject position, logo, negative space)
- text (size, typical word count, alignment)
- composition (subject count/scale, focus, gaze)
- colors (hex primary/secondary/accent, contrast, brightness, saturation)
- lighting (dark/light/cinematic/studio/mist/sunset)
- style genre (modern/documentary/horror/cinematic/fantasy/sci-fi/cartoon)
- emotion (mystery/excitement/fear/curiosity/wonder)
- logo (position, size)

Return ONLY JSON:
{{
  "layout": {{
    "title_position": "left|right|top|center",
    "subject_position": "left|right|center",
    "logo_position": "bottom_left|bottom_right|top_left|top_right|none",
    "negative_space": "left|right|top|bottom"
  }},
  "text": {{
    "title_size": "huge|large|medium",
    "average_words": 4,
    "title_alignment": "left|center|right"
  }},
  "colors": {{
    "primary": "#rrggbb",
    "secondary": "#rrggbb",
    "accent": "#rrggbb",
    "contrast": "very_high|high|medium",
    "brightness": "dark|medium|bright",
    "saturation": "low|medium|high"
  }},
  "style": {{
    "contrast": "very_high|high|medium",
    "lighting": "dark_cinematic|studio|mist|sunset|bright",
    "emotion": "mystery|excitement|fear|curiosity|wonder",
    "genre": "cinematic|documentary|horror|fantasy|sci-fi|modern|cartoon",
    "atmosphere": "short phrase"
  }},
  "composition": {{
    "subject_count": "one|two|group",
    "subject_scale": "large|medium|small",
    "focus": "hero|face|object",
    "gaze_direction": "into_frame|out|camera"
  }},
  "logo": {{
    "position": "bottom_left|bottom_right|top_left|top_right|none",
    "size": "small|medium|large"
  }}
}}
"""


class VisionCapable(Protocol):
    def generate_with_images(
        self,
        prompt: str,
        images: list[Path],
        *,
        system: str | None = None,
    ) -> str: ...


class ThumbnailStyleAnalyzer:
    """Turn reference images into averaged Thumbnail DNA via vision LLM."""

    def __init__(self, text_provider: Any | None = None) -> None:
        self._text = text_provider

    def analyze(
        self,
        channel: str,
        references: list[Path],
        *,
        channel_id: str = "",
    ) -> ThumbnailDNA:
        paths = [p for p in references if p.is_file()]
        if not paths:
            raise ValueError("No reference thumbnails to analyze.")

        if self._text is not None and hasattr(self._text, "generate_with_images"):
            try:
                raw = self._text.generate_with_images(
                    _USER.format(count=len(paths), channel=channel.strip()),
                    paths,
                    system=_SYSTEM,
                )
                data = parse_json_object(raw, label="Thumbnail Style Analysis")
                dna = ThumbnailDNA.from_dict(data)
                dna.channel_name = channel.strip()
                dna.channel_id = channel_id or dna.channel_id
                dna.reference_count = len(paths)
                return dna
            except (ProviderError, ValueError, OSError, TypeError):
                pass

        # Deterministic fallback keeps the pipeline usable without vision.
        return _fallback_dna(channel, channel_id=channel_id, count=len(paths))


def encode_image_part(path: Path) -> dict[str, Any]:
    """Gemini inlineData part for one image file."""
    mime, _ = mimetypes.guess_type(str(path))
    if not mime or not mime.startswith("image/"):
        suffix = path.suffix.casefold()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(suffix, "image/png")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"inlineData": {"mimeType": mime, "data": data}}


def _fallback_dna(channel: str, *, channel_id: str, count: int) -> ThumbnailDNA:
    dna = ThumbnailDNA(
        channel_id=channel_id,
        channel_name=channel.strip(),
        reference_count=count,
    )
    dna.extras["analysis_mode"] = "fallback"
    return dna
