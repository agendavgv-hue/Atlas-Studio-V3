"""Sync Channel Studio pack into Creative/ so AI modules keep working."""

from __future__ import annotations

from pathlib import Path

from app.channels.studio.models import ChannelStudioPack
from app.creative.models.director import CreativeDirector
from app.creative.models.sections import (
    MovieStyleRules,
    MusicStyleRules,
    StoryStyleRules,
    ThumbnailStyleRules,
    VisualStyle,
    VoiceStyleRules,
)
from app.creative.services.director_service import CreativeDirectorService
from app.thumbnail.intelligence.settings import (
    ThumbnailStudioSettings,
    ThumbnailStudioSettingsStore,
)


def sync_studio_to_creative(data_root: Path, pack: ChannelStudioPack) -> None:
    """Write Brand Kit, rules, and section styles into Creative/<id>/."""
    try:
        creative = CreativeDirectorService(data_root)
        director = creative.ensure(pack.folder_name)
        director.channel_name = pack.general.name or pack.folder_name
        director.rules = list(pack.rules)
        director.thumbnail = ThumbnailStyleRules(
            layout=f"subject_right_title_{pack.thumbnail.negative_space}",
            logo_position=pack.thumbnail.logo_position
            if pack.thumbnail.logo_position != "auto"
            else "bottom_left",
            text_position=pack.thumbnail.negative_space,
            subject_scale="large",
            negative_space=pack.thumbnail.negative_space,
            max_words=pack.thumbnail.max_words,
            ctr_style="curiosity",
        )
        director.visual = VisualStyle(
            realism="photorealistic",
            cinematic="high",
            color_palette=pack.image.color_palette,
            contrast=pack.thumbnail.contrast,
            lighting=pack.image.lighting or "cinematic",
            depth="strong",
            image_quality=pack.image.image_quality,
        )
        director.movie = MovieStyleRules(
            camera_style=pack.movie.camera_style,
            zoom_style=pack.movie.zoom_style,
            pans=pack.movie.pan_style,
            transitions=pack.movie.transitions,
            particles=pack.movie.particles,
            fog=pack.movie.fog,
            pacing="documentary",
            shot_length=4.0,
        )
        director.story = StoryStyleRules(
            hook_style=pack.story.hook_style,
            suspense="medium",
            cliffhangers=pack.story.cliffhangers,
            endings=pack.story.ending_style,
            pace=pack.story.pacing,
        )
        director.voice = VoiceStyleRules(
            provider=pack.voice.provider,
            voice=pack.voice.voice,
            speed=pack.voice.speed,
            emotion=pack.voice.emotion,
        )
        director.music = MusicStyleRules(
            genre=pack.music.genre,
            ducking=pack.music.ducking,
            volume=pack.music.volume,
            mood=pack.music.mood,
        )
        creative.save(director)
        creative.save_brand(pack.folder_name, pack.brand)

        # Thumbnail Intelligence studio knobs
        ThumbnailStudioSettingsStore(data_root).save(
            pack.folder_name,
            ThumbnailStudioSettings(
                max_words=pack.thumbnail.max_words,
                logo_visible=pack.thumbnail.logo_visible,
                logo_position=pack.thumbnail.logo_position,
                logo_size=pack.thumbnail.logo_size,
                contrast=pack.thumbnail.contrast,
                negative_space=pack.thumbnail.negative_space,
                creativity=pack.thumbnail.creativity,
                style_strength=pack.thumbnail.style_strength,
                brand_strength=pack.thumbnail.brand_strength,
            ),
        )
    except Exception:  # noqa: BLE001
        return
