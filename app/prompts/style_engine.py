"""Channel Style Engine — modular visual identity for AI image prompts.

Architecture surface: prompts only. Pipelines call PromptAssembler unchanged.
Every channel image must be recognizable by grading, light, and composition —
not only by subject matter.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelStyleProfile:
    """Fixed visual director pack for one YouTube channel."""

    channel_key: str
    identity: str
    cinematic_director: str
    color_grading: str
    lighting: str
    composition: str
    storytelling: str
    emotion: str
    continuity: str
    avoid: str
    negative: str
    thumbnail_boost: str

    def house_style_brief(self) -> str:
        """Full director brief for script/sheet system layers."""
        return (
            f"{self.channel_key} Visual Director — ALWAYS apply, never optional. "
            f"{self.identity} "
            f"CINEMATOGRAPHY: {self.cinematic_director} "
            f"COLOR: {self.color_grading} "
            f"LIGHT: {self.lighting} "
            f"COMPOSITION: {self.composition} "
            f"STORY DETAILS: {self.storytelling} "
            f"EMOTION: {self.emotion} "
            f"CONTINUITY: {self.continuity} "
            f"NEVER: {self.avoid}"
        )

    def image_style_layer(self) -> str:
        """Compact modular style block for Stable Diffusion assembly."""
        return ", ".join(
            part
            for part in (
                f"{self.channel_key} house style",
                self.identity,
                self.cinematic_director,
                self.color_grading,
                self.lighting,
                self.composition,
                self.storytelling,
                self.emotion,
                self.continuity,
            )
            if part.strip()
        )

    def compact_look_layer(self, *, for_thumbnail: bool = False) -> str:
        """Identity-critical look pack (color/light first) for subject-first prompts."""
        parts = [
            f"{self.channel_key} house style",
            self.color_grading,
            self.lighting,
        ]
        if for_thumbnail:
            parts.append(self.thumbnail_boost)
        parts.extend(
            [
                self.composition,
                self.cinematic_director,
                self.emotion,
                self.continuity,
                self.storytelling,
            ]
        )
        return ", ".join(part for part in parts if part.strip())

    def thumbnail_style_layer(self) -> str:
        """Same Style Engine + thumbnail clickability boost."""
        return self.compact_look_layer(for_thumbnail=True)


# ---------------------------------------------------------------------------
# Hollow Atlas — forbidden history / archaeological mystery documentary
# NOT National Geographic. NOT generic AI. NOT scientific illustration.
# ---------------------------------------------------------------------------

HOLLOW_ATLAS = ChannelStyleProfile(
    channel_key="Hollow Atlas",
    identity=(
        "forbidden-history archaeological mystery cinema: lost civilizations, "
        "ancient secrets, forgotten worlds, gigantic scale, dark documentary "
        "atmosphere — looks like a sealed museum vault opened at night"
    ),
    cinematic_director=(
        "shot as if a cinematographer, art director, and documentary director "
        "collaborated: photoreal textures, museum-still reverence, epic scale, "
        "tactile weathered materials, no fantasy CGI sheen"
    ),
    color_grading=(
        "museum color grading: deep blacks, dark charcoal, warm gold, ancient "
        "bronze, amber, soft ivory, dust brown, muted low-saturation palette, "
        "dark shadows with golden highlights — never bright or cartoon colors, "
        "never modern clean whites"
    ),
    lighting=(
        "volumetric lighting, god rays, dust particles in the beam, fog, ancient "
        "atmosphere, heavy contrast, directional golden light, soft rim light, "
        "cinematic shadows"
    ),
    composition=(
        "strong foreground, interesting midground, epic background, leading lines, "
        "cinematic framing, intentional negative space, sense of scale, rule of "
        "thirds — subject never casually dead-center"
    ),
    storytelling=(
        "translate Hollow Atlas atmosphere INTO the given subject world only — "
        "keep the real place, era, climate, and geography of the subject "
        "(Antarctica stays ice, glaciers, polar mist, ice caves — never swap in "
        "Egyptian tombs, deserts, temples, or tropical ruins when they are not the subject); "
        "add mystery atmosphere with subject-true details: weathered materials, mist, "
        "dust or snow as appropriate, half-revealed structures, light revealing a path"
    ),
    emotion=(
        "evoke at least one: awe, wonder, mystery, fear, curiosity, discovery, "
        "ancient power, forbidden knowledge, lost civilization"
    ),
    continuity=(
        "all scenes feel like the same film: identical warm-gold/charcoal grade, "
        "same atmospheric language, same documentary cinematography, same subject world"
    ),
    avoid=(
        "flat compositions, empty blank backgrounds, too much blue, too much white, "
        "AI plastic look, plastic textures, overly clean surfaces, cartoon colors, "
        "unnatural lighting, National Geographic travel-brochure look, scientific "
        "diagram illustration, neon cyberpunk, modern skyscrapers, "
        "replacing the subject with an unrelated biome or civilization"
    ),
    negative=(
        "National Geographic brochure look, scientific illustration, fantasy creature "
        "mashup, cartoon relic, neon cyberpunk, modern skyscraper, tourist selfie, "
        "bright flat daylight, plastic CGI ruins, oversaturated colors, too much blue, "
        "blown-out whites, clean modern interiors, plastic textures, flat composition, "
        "empty blank background, collage, text, watermark, logo, lowres, blurry"
    ),
    thumbnail_boost=(
        "thumbnail intensity: higher contrast, stronger single focus point, more "
        "negative space for headline text, maximum clickability, one iconic ancient "
        "subject readable at YouTube small size, warm gold on charcoal"
    ),
)


# ---------------------------------------------------------------------------
# Mirror Drift — premium near-future tech (Apple / Tesla / NASA / OpenAI)
# Completely separate identity from Hollow Atlas.
# ---------------------------------------------------------------------------

MIRROR_DRIFT = ChannelStyleProfile(
    channel_key="Mirror Drift",
    identity=(
        "premium near-future technology cinema: Apple keynote, Tesla event, "
        "NASA presentation, OpenAI launch, Netflix sci-fi polish — high-end CGI, "
        "clean product storytelling, zero archaeological dust"
    ),
    cinematic_director=(
        "shot like a luxury tech brand film: precise industrial design, glossy "
        "materials, photoreal CGI-grade surfaces, confident negative space, "
        "no cyberpunk chaos, no cluttered gadget piles"
    ),
    color_grading=(
        "deep black, graphite, chrome, electric blue, crisp white, cyan, subtle "
        "purple accents, neon accents used sparingly, gloss finish, high contrast "
        "cool grade — never warm museum gold, never dusty brown"
    ),
    lighting=(
        "studio lighting, neon reflections, clean rim lighting, glossy material "
        "response, HDR lighting, soft reflections, premium presentation lighting"
    ),
    composition=(
        "precise product-cinema framing, strong perspective lines, generous clean "
        "negative space, hero off-center with purpose, uncluttered midground, "
        "minimal supporting environment — never overcrowded"
    ),
    storytelling=(
        "translate Mirror Drift atmosphere INTO the given subject world only — "
        "keep the real technology, location, and design language of the subject; "
        "never graft ancient ruins or dusty tombs onto a tech subject; "
        "use subject-true premium materials: brushed metal, glass, circuitry glow, "
        "clean labs or craft interiors when they belong to the topic"
    ),
    emotion=(
        "evoke at least one: awe, curiosity, technological revelation, precision, "
        "inevitability of the future, premium power, clean wonder"
    ),
    continuity=(
        "all scenes feel like the same film: identical cool graphite/blue grade, "
        "same glossy material language, same keynote-cinema lighting, same subject world"
    ),
    avoid=(
        "ancient ruins, dusty tombs, warm gold museum look, medieval fantasy, "
        "cyberpunk chaos, cluttered scenes, muddy brown grade, plastic toy robots, "
        "oversaturated neon junk, documentary archaeology mood, "
        "replacing the subject with an unrelated product or era"
    ),
    negative=(
        "ancient ruins, dusty tombs, warm gold museum look, archaeological dig, "
        "medieval fantasy, dragons, grunge chaos, cluttered gadget pile, cartoon "
        "robot, muddy brown grade, warm amber dust, god rays through ruins, "
        "cyberpunk overload, busy composition, collage, text, watermark, logo, "
        "lowres, blurry"
    ),
    thumbnail_boost=(
        "thumbnail intensity: higher contrast, stronger single focus point, more "
        "open space for headline text, maximum clickability, one precise tech "
        "subject, cool blue-white light, industrial clarity"
    ),
)


CHANNEL_PROFILES: dict[str, ChannelStyleProfile] = {
    HOLLOW_ATLAS.channel_key: HOLLOW_ATLAS,
    MIRROR_DRIFT.channel_key: MIRROR_DRIFT,
}


# Channel-neutral quality floor — identity comes from the Style Engine, not here.
GLOBAL_QUALITY_LAYER = (
    "photorealistic, ultra detailed, premium production still, sharp focus on "
    "subject, coherent materials, high dynamic range, filmic contrast, "
    "professional color science"
)

GLOBAL_NEGATIVE_LAYER = (
    "blurry, lowres, jpeg artifacts, watermark, text, logo, subtitle, "
    "cartoon, anime, illustration, painting, deformed, extra limbs, mutated hands, "
    "duplicate, collage, split screen, generic stock photo, flat lighting, "
    "busy clutter, AI artifacts, plastic skin"
)


def resolve_profile(channel_name: str) -> ChannelStyleProfile | None:
    key = (channel_name or "").strip()
    if key in CHANNEL_PROFILES:
        return CHANNEL_PROFILES[key]
    # Case-insensitive fallback
    lowered = key.casefold()
    for name, profile in CHANNEL_PROFILES.items():
        if name.casefold() == lowered:
            return profile
    return None


def channel_style_layer(
    channel_name: str,
    *,
    override: str = "",
    for_thumbnail: bool = False,
) -> str:
    """Style layer for image assembly.

    Known channels always use the Style Engine compact look pack so identity
    tokens (grade/light) survive subject-first budgeting. Unknown channels
    fall back to channel.json override text.
    """
    profile = resolve_profile(channel_name)
    if profile is not None:
        return profile.compact_look_layer(for_thumbnail=for_thumbnail)
    explicit = (override or "").strip()
    return explicit


def channel_negative_layer(channel_name: str, *, override: str = "") -> str:
    explicit = (override or "").strip()
    if explicit:
        return explicit
    profile = resolve_profile(channel_name)
    return profile.negative if profile is not None else ""


def channel_director_brief(channel_name: str, *, override: str = "") -> str:
    """Rich Channel Director brief for sheet/script system layers.

    Known channels always use the Style Engine profile so identity stays locked.
    Unknown channels fall back to channel.json override text.
    """
    profile = resolve_profile(channel_name)
    if profile is not None:
        return (
            f"CHANNEL DIRECTOR ({profile.channel_key}) — atmosphere and look only; "
            f"never replace the Subject Director's place/era/climate. "
            f"{profile.house_style_brief()}"
        )
    return (override or "").strip()


def continuity_fragment(previous_prompt: str) -> str:
    text = " ".join((previous_prompt or "").split())
    if len(text) < 24:
        return ""
    clip = text[:180].rstrip(" ,;")
    return (
        "FILM CONTINUITY: same documentary as prior shot — match grade, contrast, "
        f"light language, atmosphere, and subject world from: {clip}"
    )


def _trim_words(text: str, max_words: int) -> str:
    words = (text or "").split()
    if max_words < 1 or len(words) <= max_words:
        return (text or "").strip()
    return " ".join(words[:max_words]).rstrip(" ,;")


def build_modular_image_prompt(
    *,
    scene: str,
    channel_name: str,
    channel_style_override: str = "",
    channel_negative_override: str = "",
    previous_scene: str = "",
    extra_global_negative: str = "",
    for_thumbnail: bool = False,
) -> tuple[str, str]:
    """Assemble Visual Director prompt: Subject Director → Channel Director.

    Subject content always leads. Channel style follows as look/feel only.
    """
    from app.prompts.subject_director import (
        build_subject_director_block,
        subject_protection_negatives,
        subject_word_emphasis,
    )

    profile = resolve_profile(channel_name)
    style = channel_style_layer(
        channel_name,
        override=channel_style_override,
        for_thumbnail=for_thumbnail,
    )

    scene_text = subject_word_emphasis(scene)
    subject_block = build_subject_director_block(scene_text)
    subject_words = max(1, len(subject_block.split()))
    # Channel look budget ~1.2× subject director (subject stays dominant).
    style_word_budget = max(90, int(subject_words * 1.2))

    if style:
        style_block = _trim_words(style, style_word_budget)
    elif profile is not None:
        style_block = _trim_words(
            profile.compact_look_layer(for_thumbnail=for_thumbnail),
            style_word_budget,
        )
    else:
        style_block = ""

    layers: list[str] = []
    # 1) SUBJECT DIRECTOR — content world first.
    layers.append(f"SUBJECT DIRECTOR: {subject_block}")

    # 2) CHANNEL DIRECTOR — recognizable Hollow Atlas / Mirror Drift look.
    if style_block:
        layers.append(
            "CHANNEL DIRECTOR (look only — do not change location/era/climate): "
            + style_block
        )

    # Neutral quality floor (short).
    layers.append(_trim_words(GLOBAL_QUALITY_LAYER, 16))

    cont = continuity_fragment(previous_scene)
    if cont:
        layers.append(cont)

    positive = ", ".join(part for part in layers if part.strip())

    negatives: list[str] = [GLOBAL_NEGATIVE_LAYER]
    if (extra_global_negative or "").strip():
        negatives.append(extra_global_negative.strip())
    channel_neg = channel_negative_layer(
        channel_name, override=channel_negative_override
    )
    if channel_neg:
        negatives.append(channel_neg)
    if profile is not None and profile.avoid:
        negatives.append(profile.avoid)
    if scene_text:
        negatives.append(subject_protection_negatives(scene_text))
    negative = ", ".join(dict.fromkeys(n for n in negatives if n.strip()))
    return positive, negative
