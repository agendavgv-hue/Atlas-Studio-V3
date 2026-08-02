"""Seed Creative Director / Brand / Style from channel + brain when present."""

from __future__ import annotations

from typing import Any

from app.channels.models import Channel
from app.creative.models.brand_kit import BrandKit
from app.creative.models.director import CreativeDirector
from app.creative.models.sections import (
    BrandStyle,
    MovieStyleRules,
    MusicStyleRules,
    StoryStyleRules,
    ThumbnailStyleRules,
    VisualStyle,
    VoiceStyleRules,
)
from app.creative.models.style_library import StyleLibrary


def seed_director(
    director: CreativeDirector,
    *,
    channel: Channel | None = None,
    brain: Any | None = None,
) -> CreativeDirector:
    if channel is not None:
        director.channel_name = channel.name or director.channel_name
        voice = dict(channel.voice or {})
        director.voice = VoiceStyleRules(
            provider=str(voice.get("provider") or "kokoro"),
            voice=str(voice.get("voice_name") or voice.get("voice") or ""),
            speed=_float(voice.get("speed"), 1.0),
            emotion=str(voice.get("emotion") or "calm"),
        )
        movie = dict(channel.movie or {})
        director.movie = MovieStyleRules(
            camera_style=str(movie.get("camera_style") or "cinematic"),
            zoom_style=str(movie.get("zoom_style") or movie.get("motion") or "slow_in"),
            pans=str(movie.get("pan_style") or "subtle"),
            transitions=str(
                movie.get("transitions") or movie.get("transition") or "crossfade"
            ),
            pacing=str(movie.get("pacing") or "documentary"),
            shot_length=_float(movie.get("average_shot_length") or movie.get("duration"), 4.0),
        )
        if channel.image_prompt:
            director.visual.color_palette = channel.image_prompt[:120]
        if channel.outro_line:
            director.story.endings = channel.outro_line[:80]

    if brain is not None:
        _apply_brain(director, brain)
    return director


def seed_brand_kit(channel: Channel | None = None, brain: Any | None = None) -> BrandKit:
    kit = BrandKit()
    if channel is not None:
        kit.logo = str(channel.logo or "")
        kit.banner = str(channel.banner or "")
        kit.outro = channel.outro_line or ""
        kit.cta = channel.outro_line or ""
    if brain is not None:
        thumb = getattr(brain, "thumbnail_dna", None)
        colors = getattr(thumb, "colors", None) if thumb is not None else None
        if isinstance(colors, dict):
            kit.primary_color = str(colors.get("primary") or kit.primary_color)
            kit.secondary_color = str(colors.get("secondary") or kit.secondary_color)
            kit.accent_color = str(colors.get("accent") or kit.accent_color)
        identity = getattr(brain, "channel_dna", None)
        if identity is not None and not kit.cta:
            kit.cta = str(getattr(identity, "mission", "") or "")[:120]
    return kit


def seed_style_library(channel: Channel | None = None, brain: Any | None = None) -> StyleLibrary:
    style = StyleLibrary()
    if brain is not None:
        image = getattr(brain, "image_dna", None)
        if image is not None:
            style.color_palette = str(getattr(image, "color_palette", "") or "")
            style.lighting = str(getattr(image, "lighting", "") or "")
            style.depth = str(getattr(image, "depth", "") or "")
            style.camera_style = str(getattr(image, "camera_style", "") or "")
            style.contrast = _weight_from_label(getattr(image, "contrast", None), 85.0)
        thumb = getattr(brain, "thumbnail_dna", None)
        if thumb is not None:
            style.thumbnail_style = str(getattr(thumb, "style", "") or "")
            style.darkness = _weight_from_label(getattr(thumb, "lighting", None), 60.0)
            style.mystery = 80.0 if "myster" in str(getattr(thumb, "emotion", "")).casefold() else style.mystery
        story = getattr(brain, "story_dna", None)
        if story is not None:
            style.story_style = str(getattr(story, "storytelling", "") or "")
            style.movie_pacing = str(getattr(story, "pacing", "") or "")
        voice = getattr(brain, "voice_dna", None)
        if voice is not None:
            tags = getattr(voice, "style_tags", None) or []
            style.voice_style = ", ".join(str(t) for t in tags) if tags else str(
                getattr(voice, "emotion", "") or ""
            )
        music = getattr(brain, "music_dna", None)
        if music is not None:
            style.music_style = str(getattr(music, "mood", "") or getattr(music, "genre", "") or "")
    if channel is not None and not style.color_palette and channel.image_prompt:
        style.color_palette = channel.image_prompt[:80]
    return style


def _apply_brain(director: CreativeDirector, brain: Any) -> None:
    image = getattr(brain, "image_dna", None)
    if image is not None:
        director.visual = VisualStyle(
            realism=str(getattr(image, "realism", None) or "photorealistic"),
            cinematic=str(getattr(image, "cinematic", None) or "high"),
            color_palette=str(getattr(image, "color_palette", "") or ""),
            contrast=str(getattr(image, "contrast", None) or "high"),
            lighting=str(getattr(image, "lighting", None) or "cinematic"),
            depth=str(getattr(image, "depth", None) or "strong"),
            image_quality=str(getattr(image, "detail", None) or "ultra"),
        )
    thumb = getattr(brain, "thumbnail_dna", None)
    if thumb is not None:
        colors = getattr(thumb, "colors", {}) or {}
        color_list = [
            str(colors.get(k))
            for k in ("primary", "secondary", "accent")
            if colors.get(k)
        ]
        director.brand = BrandStyle(
            colors=color_list,
            logo=str(getattr(thumb, "logo_position", "") or ""),
        )
        director.thumbnail = ThumbnailStyleRules(
            layout=str(getattr(thumb, "layout", None) or "subject_right_title_left"),
            logo_position=str(getattr(thumb, "logo_position", None) or "bottom_left"),
            text_position=str(getattr(thumb, "title_position", None) or "left"),
            subject_scale="large",
            negative_space=str(getattr(thumb, "negative_space", None) or "left"),
            max_words=4,
            ctr_style=str(getattr(thumb, "emotion", None) or "curiosity"),
        )
    movie = getattr(brain, "movie_dna", None)
    if movie is not None:
        director.movie = MovieStyleRules(
            camera_style=str(getattr(movie, "camera_style", None) or "cinematic"),
            zoom_style=str(getattr(movie, "zoom_style", None) or "slow_in"),
            pans=str(getattr(movie, "pan_style", None) or "subtle"),
            transitions=str(getattr(movie, "transitions", None) or "crossfade"),
            particles=str(getattr(movie, "particles", None) or "none"),
            fog=str(getattr(movie, "fog", None) or "none"),
            pacing=str(getattr(movie, "pacing", None) or "documentary"),
            shot_length=_float(getattr(movie, "average_shot_length", None), 4.0),
        )
    story = getattr(brain, "story_dna", None)
    if story is not None:
        director.story = StoryStyleRules(
            hook_style=str(getattr(story, "hook_style", None) or "curiosity-first"),
            suspense=str(getattr(story, "suspense", None) or "medium"),
            cliffhangers=str(getattr(story, "cliffhangers", None) or "occasional"),
            endings=str(getattr(story, "ending_style", None) or "reflective"),
            pace=str(getattr(story, "pacing", None) or "steady"),
        )
    voice = getattr(brain, "voice_dna", None)
    if voice is not None:
        director.voice = VoiceStyleRules(
            provider=str(getattr(voice, "provider", None) or "kokoro"),
            voice=str(getattr(voice, "voice", None) or getattr(voice, "voice_id", "") or ""),
            speed=_float(getattr(voice, "speed", None), 1.0),
            emotion=str(getattr(voice, "emotion", None) or "calm"),
        )
    music = getattr(brain, "music_dna", None)
    if music is not None:
        director.music = MusicStyleRules(
            genre=str(getattr(music, "genre", "") or ""),
            ducking=str(getattr(music, "ducking", None) or "voice_priority"),
            volume=_float(getattr(music, "volume", None), 0.35),
            mood=str(getattr(music, "mood", "") or ""),
        )


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _weight_from_label(value: Any, default: float) -> float:
    text = str(value or "").casefold()
    if not text:
        return default
    if "very_high" in text or "ultra" in text:
        return 95.0
    if "high" in text or "dark" in text:
        return 85.0
    if "medium" in text:
        return 55.0
    if "low" in text or "bright" in text:
        return 25.0
    return default
