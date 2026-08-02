"""Training completeness helpers for Channel Studio 2.0."""

from __future__ import annotations

from dataclasses import dataclass

from app.channels.studio.models import ChannelStudioPack

# Sections that count toward Creative Director training progress.
TRAINING_SECTIONS: tuple[tuple[str, str], ...] = (
    ("general", "Channel Basics"),
    ("personality", "Channel Personality"),
    ("brand", "Brand Kit"),
    ("thumbnail", "Thumbnail Studio"),
    ("image", "Image Studio"),
    ("movie", "Movie Studio"),
    ("story", "Story Studio"),
    ("voice", "Voice Studio"),
    ("music", "Music Studio"),
    ("rules", "Creative Rules"),
    ("goals", "Goals"),
)


@dataclass(frozen=True)
class TrainingProgress:
    completed: dict[str, bool]
    percent: int
    fully_trained: bool

    @property
    def done_count(self) -> int:
        return sum(1 for ok in self.completed.values() if ok)

    @property
    def total(self) -> int:
        return len(self.completed)


def evaluate_training(pack: ChannelStudioPack, *, visited: set[str] | None = None) -> TrainingProgress:
    """Score how complete the Creative Director training pack is.

    A section counts as complete when its core identity fields are filled.
    Optional ``visited`` can mark lightly-configured tabs after the user opens them.
    """
    seen = visited or set()
    completed: dict[str, bool] = {}
    for key, _label in TRAINING_SECTIONS:
        completed[key] = _is_complete(pack, key) or (
            key in seen and key in {"rules", "goals", "movie", "music"}
        )
    # Stricter: visited alone is not enough for brand/personality/general.
    completed["general"] = _is_complete(pack, "general")
    completed["personality"] = _is_complete(pack, "personality")
    completed["brand"] = _is_complete(pack, "brand")
    completed["thumbnail"] = _is_complete(pack, "thumbnail")
    completed["image"] = _is_complete(pack, "image")
    completed["story"] = _is_complete(pack, "story")
    completed["voice"] = _is_complete(pack, "voice")
    completed["rules"] = _is_complete(pack, "rules")
    completed["goals"] = _is_complete(pack, "goals")
    completed["movie"] = _is_complete(pack, "movie") or "movie" in seen
    completed["music"] = _is_complete(pack, "music") or "music" in seen

    total = len(completed) or 1
    done = sum(1 for ok in completed.values() if ok)
    percent = int(round(100.0 * done / total))
    return TrainingProgress(
        completed=completed,
        percent=percent,
        fully_trained=done == total,
    )


def _is_complete(pack: ChannelStudioPack, key: str) -> bool:
    if key == "general":
        return bool(pack.general.name.strip() and pack.general.description.strip())
    if key == "personality":
        return bool(pack.personality.traits)
    if key == "brand":
        return bool(pack.brand.logo.strip())
    if key == "thumbnail":
        return bool(pack.thumbnail.emotion and pack.thumbnail.dominant_subject)
    if key == "image":
        return bool(pack.image.lighting and pack.image.mood)
    if key == "movie":
        return bool(pack.movie.preset and pack.movie.camera_motion)
    if key == "story":
        return bool(pack.story.hook_type and pack.story.emotion)
    if key == "voice":
        return bool(pack.voice.voice_style and (pack.voice.voice or pack.voice.voice_style))
    if key == "music":
        return bool(pack.music.personality or pack.music.mood)
    if key == "rules":
        return any(rule.enabled for rule in pack.rules)
    if key == "goals":
        return pack.goals.uploads_per_week > 0
    return False
