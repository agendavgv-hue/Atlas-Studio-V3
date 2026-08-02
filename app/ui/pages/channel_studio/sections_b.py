"""Channel Studio sections — Image, Movie, Story, Voice, Music."""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QVBoxLayout, QWidget

from app.channels.studio.models import ChannelStudioPack
from app.ui.pages.channel_studio.form_kit import (
    combo_value,
    make_combo,
    make_slider,
    section_intro,
    set_combo,
    slider_row,
)
from app.ui.pages.channel_studio.reference_panel import ReferencePanel


class ImageSection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.lighting = make_combo(
            [
                ("Warm Cinematic", "warm_cinematic"),
                ("Cold", "cold"),
                ("Moonlight", "moonlight"),
                ("Golden Hour", "golden_hour"),
                ("Natural", "natural"),
                ("Dramatic", "dramatic"),
            ]
        )
        self.camera = make_combo(
            [
                ("Documentary", "documentary"),
                ("Cinema", "cinema"),
                ("Drone", "drone"),
                ("Macro", "macro"),
                ("Landscape", "landscape"),
                ("Portrait", "portrait"),
            ]
        )
        self.mood = make_combo(
            [
                ("Mystery", "mystery"),
                ("Ancient", "ancient"),
                ("Dark", "dark"),
                ("Epic", "epic"),
                ("Wonder", "wonder"),
                ("Scientific", "scientific"),
                ("Adventure", "adventure"),
                ("Fantasy", "fantasy"),
            ]
        )
        self.atmosphere = make_combo(
            [
                ("None", "none"),
                ("Fog", "fog"),
                ("Dust", "dust"),
                ("Smoke", "smoke"),
                ("Snow", "snow"),
                ("Rain", "rain"),
            ]
        )
        self.film_grain = make_combo(
            [("Off", "off"), ("Low", "low"), ("Medium", "medium"), ("High", "high")]
        )
        self.texture = make_combo(
            [
                ("Stone", "stone"),
                ("Ancient", "ancient"),
                ("Leather", "leather"),
                ("Wood", "wood"),
                ("Metal", "metal"),
            ]
        )
        self.resolution = make_combo(
            [
                ("1536×864 (standard)", "1536x864"),
                ("1280×720", "1280x720"),
                ("1920×1080", "1920x1080"),
            ],
            current="1536x864",
        )
        self.realism, self.realism_r = make_slider(90)
        self.refs = ReferencePanel(kind="images", title="Reference images", max_count=20)
        form = QFormLayout()
        form.addRow("Lighting", self.lighting)
        form.addRow("Camera style", self.camera)
        form.addRow("Mood", self.mood)
        form.addRow("Atmosphere", self.atmosphere)
        form.addRow("Film grain", self.film_grain)
        form.addRow("Texture", self.texture)
        form.addRow("Resolution", self.resolution)
        layout = QVBoxLayout(self)
        layout.addWidget(
            section_intro(
                "Image Studio",
                "Describe the look in plain language — lighting, mood, and atmosphere.",
            )
        )
        layout.addLayout(form)
        layout.addWidget(
            slider_row(
                "Realism",
                self.realism,
                self.realism_r,
                "How photographic versus stylized images should feel.",
            )
        )
        layout.addWidget(self.refs)
        layout.addStretch()
        self.lighting.setToolTip("The light recipe for every image.")
        self.camera.setToolTip("Lens language and camera attitude.")
        self.mood.setToolTip("Emotional color of the world.")

    def load_pack(self, pack: ChannelStudioPack) -> None:
        i = pack.image
        set_combo(self.lighting, i.lighting or "warm_cinematic")
        set_combo(self.camera, i.camera_style or "documentary")
        set_combo(self.mood, i.mood or "mystery")
        set_combo(self.atmosphere, i.atmosphere or "none")
        set_combo(self.film_grain, i.film_grain or "low")
        set_combo(self.texture, i.texture or "stone")
        set_combo(self.resolution, i.resolution or "1536x864")
        self.realism.setValue(int(i.realism))

    def apply_pack(self, pack: ChannelStudioPack) -> None:
        i = pack.image
        i.lighting = combo_value(self.lighting, "warm_cinematic")
        i.camera_style = combo_value(self.camera, "documentary")
        i.mood = combo_value(self.mood, "mystery")
        i.atmosphere = combo_value(self.atmosphere, "none")
        i.film_grain = combo_value(self.film_grain, "low")
        i.texture = combo_value(self.texture, "stone")
        i.resolution = combo_value(self.resolution, "1536x864")
        i.realism = float(self.realism.value())


class MovieSection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.preset = make_combo(
            [
                ("Documentary Cinematic", "documentary_cinematic"),
                ("Future Tech", "future_tech"),
                ("Storybook", "storybook"),
                ("Epic Adventure", "epic_adventure"),
                ("Mystery", "mystery"),
            ]
        )
        self.camera_motion = make_combo(
            [
                ("Very Slow", "very_slow"),
                ("Slow", "slow"),
                ("Medium", "medium"),
                ("Fast", "fast"),
            ]
        )
        self.particles = make_combo(
            [
                ("None", "none"),
                ("Fog", "fog"),
                ("Dust", "dust"),
                ("Rain", "rain"),
                ("Snow", "snow"),
            ]
        )
        self.lighting = make_combo(
            [
                ("Warm", "warm"),
                ("Cold", "cold"),
                ("Golden", "golden"),
                ("Moonlight", "moonlight"),
                ("Documentary", "documentary"),
            ]
        )
        self.shot_style = make_combo(
            [("Long", "long"), ("Medium", "medium"), ("Short", "short")]
        )
        self.refs = ReferencePanel(kind="movies", title="Movie references", max_count=20)
        form = QFormLayout()
        form.addRow("Preset", self.preset)
        form.addRow("Camera motion", self.camera_motion)
        form.addRow("Particles", self.particles)
        form.addRow("Lighting", self.lighting)
        form.addRow("Shot style", self.shot_style)
        layout = QVBoxLayout(self)
        layout.addWidget(
            section_intro(
                "Movie Studio",
                "Pick a motion personality. Presets teach pacing before fine details.",
            )
        )
        layout.addLayout(form)
        layout.addWidget(self.refs)
        layout.addStretch()
        self.preset.setToolTip("Starting cinematic recipe for this channel.")
        self.camera_motion.setToolTip("How quickly the camera breathes.")

    def load_pack(self, pack: ChannelStudioPack) -> None:
        m = pack.movie
        set_combo(self.preset, m.preset or "documentary_cinematic")
        set_combo(self.camera_motion, m.camera_motion or m.motion_amount or "slow")
        set_combo(self.particles, m.particles or "none")
        set_combo(self.lighting, m.lighting_preset or m.lighting or "documentary")
        set_combo(self.shot_style, m.shot_style or "medium")

    def apply_pack(self, pack: ChannelStudioPack) -> None:
        m = pack.movie
        m.preset = combo_value(self.preset, "documentary_cinematic")
        m.camera_motion = combo_value(self.camera_motion, "slow")
        m.motion_amount = m.camera_motion
        m.particles = combo_value(self.particles, "none")
        m.lighting_preset = combo_value(self.lighting, "documentary")
        m.lighting = m.lighting_preset
        m.shot_style = combo_value(self.shot_style, "medium")


class StorySection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.hook_type = make_combo(
            [
                ("Question", "question"),
                ("Impossible Fact", "impossible_fact"),
                ("Ancient Mystery", "ancient_mystery"),
                ("Lost Civilization", "lost_civilization"),
                ("Unknown Technology", "unknown_technology"),
            ]
        )
        self.emotion = make_combo(
            [
                ("Curiosity", "curiosity"),
                ("Suspense", "suspense"),
                ("Wonder", "wonder"),
                ("Fear", "fear"),
            ]
        )
        self.cliffhangers = make_combo(
            [
                ("Rare", "rare"),
                ("Occasional", "occasional"),
                ("Frequent", "frequent"),
            ]
        )
        self.sliders: dict[str, object] = {}
        traits = (
            ("mystery", "Mystery", "How much unknown drives the episode."),
            ("wonder", "Wonder", "Awe and discovery."),
            ("science", "Science", "Evidence and explanation weight."),
            ("history", "History", "Past-world grounding."),
            ("adventure", "Adventure", "Journey and stakes."),
            ("fantasy", "Fantasy", "Mythic or speculative flavor."),
            ("suspense", "Suspense", "Delayed answers."),
            ("speculation", "Speculation", "Room for theory."),
            ("historical_accuracy", "Historical accuracy", "Fidelity to known facts."),
            ("open_questions", "Open questions", "Leave viewers thinking."),
            ("tension", "Tension", "Pressure under the narrative."),
            ("documentary_level", "Documentary level", "Non-fiction gravity."),
        )
        layout = QVBoxLayout(self)
        layout.addWidget(
            section_intro(
                "Story Studio",
                "Train narrative DNA — hooks, tension, and the emotions that carry episodes.",
            )
        )
        form = QFormLayout()
        form.addRow("Hook type", self.hook_type)
        form.addRow("Core emotion", self.emotion)
        form.addRow("Cliffhangers", self.cliffhangers)
        layout.addLayout(form)
        for key, label, tip in traits:
            slider, readout = make_slider(60)
            self.sliders[key] = slider
            layout.addWidget(slider_row(label, slider, readout, tip))
        layout.addStretch()

    def load_pack(self, pack: ChannelStudioPack) -> None:
        s = pack.story
        set_combo(self.hook_type, s.hook_type or "question")
        set_combo(self.emotion, s.emotion or "curiosity")
        set_combo(self.cliffhangers, s.cliffhangers or "occasional")
        mapping = {
            "mystery": s.mystery,
            "wonder": s.wonder,
            "science": s.science,
            "history": s.history,
            "adventure": s.adventure,
            "fantasy": s.fantasy,
            "suspense": s.suspense,
            "speculation": s.speculation,
            "historical_accuracy": s.historical_accuracy,
            "open_questions": s.open_questions,
            "tension": s.tension,
            "documentary_level": s.documentary_level,
        }
        for key, value in mapping.items():
            slider = self.sliders[key]
            slider.setValue(int(value))

    def apply_pack(self, pack: ChannelStudioPack) -> None:
        s = pack.story
        s.hook_type = combo_value(self.hook_type, "question")
        s.hook_style = s.hook_type
        s.emotion = combo_value(self.emotion, "curiosity")
        s.cliffhangers = combo_value(self.cliffhangers, "occasional")
        for key, slider in self.sliders.items():
            setattr(s, key, float(slider.value()))


class VoiceSection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.voice_style = make_combo(
            [
                ("Narrator", "narrator"),
                ("Documentary", "documentary"),
                ("Storyteller", "storyteller"),
                ("Trailer", "trailer"),
                ("Podcast", "podcast"),
            ]
        )
        self.accent = make_combo(
            [
                ("American", "american"),
                ("British", "british"),
                ("Neutral", "neutral"),
            ]
        )
        self.age = make_combo(
            [("Young", "young"), ("Adult", "adult"), ("Older", "older")]
        )
        self.authority, self.authority_r = make_slider(70)
        self.warmth, self.warmth_r = make_slider(60)
        self.curiosity, self.curiosity_r = make_slider(65)
        self.mystery, self.mystery_r = make_slider(55)
        self.energy, self.energy_r = make_slider(45)
        self.refs = ReferencePanel(kind="voices", title="Voice references", max_count=20)
        form = QFormLayout()
        form.addRow("Voice style", self.voice_style)
        form.addRow("Accent", self.accent)
        form.addRow("Age feel", self.age)
        layout = QVBoxLayout(self)
        layout.addWidget(
            section_intro(
                "Voice Studio",
                "Shape narrator personality — style first, technical voice later.",
            )
        )
        layout.addLayout(form)
        layout.addWidget(slider_row("Authority", self.authority, self.authority_r))
        layout.addWidget(slider_row("Warmth", self.warmth, self.warmth_r))
        layout.addWidget(slider_row("Curiosity", self.curiosity, self.curiosity_r))
        layout.addWidget(slider_row("Mystery", self.mystery, self.mystery_r))
        layout.addWidget(slider_row("Energy", self.energy, self.energy_r))
        layout.addWidget(self.refs)
        layout.addStretch()

    def load_pack(self, pack: ChannelStudioPack) -> None:
        v = pack.voice
        set_combo(self.voice_style, v.voice_style or "documentary")
        set_combo(self.accent, v.accent or "neutral")
        set_combo(self.age, v.age or "adult")
        self.authority.setValue(int(v.authority))
        self.warmth.setValue(int(v.warmth))
        self.curiosity.setValue(int(v.curiosity))
        self.mystery.setValue(int(v.mystery))
        self.energy.setValue(int(v.energy))

    def apply_pack(self, pack: ChannelStudioPack) -> None:
        v = pack.voice
        v.voice_style = combo_value(self.voice_style, "documentary")
        v.accent = combo_value(self.accent, "neutral")
        v.age = combo_value(self.age, "adult")
        v.authority = float(self.authority.value())
        v.warmth = float(self.warmth.value())
        v.curiosity = float(self.curiosity.value())
        v.mystery = float(self.mystery.value())
        v.energy = float(self.energy.value())


class MusicSection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.personality = make_combo(
            [
                ("Dark", "dark"),
                ("Epic", "epic"),
                ("Mystery", "mystery"),
                ("Ancient", "ancient"),
                ("Hope", "hope"),
                ("Adventure", "adventure"),
                ("Sci-Fi", "sci_fi"),
                ("Calm", "calm"),
                ("Suspense", "suspense"),
            ]
        )
        self.volume, self.volume_r = make_slider(35)
        self.background, self.background_r = make_slider(25)
        self.fade = make_combo(
            [("Soft", "soft"), ("Medium", "medium"), ("Hard", "hard")]
        )
        self.refs = ReferencePanel(kind="music", title="Music references", max_count=20)
        form = QFormLayout()
        form.addRow("Music personality", self.personality)
        form.addRow("Fade style", self.fade)
        layout = QVBoxLayout(self)
        layout.addWidget(
            section_intro(
                "Music Studio",
                "Choose a musical personality — not a technical genre list.",
            )
        )
        layout.addLayout(form)
        layout.addWidget(slider_row("Volume", self.volume, self.volume_r))
        layout.addWidget(
            slider_row("Background level", self.background, self.background_r)
        )
        layout.addWidget(self.refs)
        layout.addStretch()

    def load_pack(self, pack: ChannelStudioPack) -> None:
        m = pack.music
        set_combo(self.personality, m.personality or m.mood or "mystery")
        self.volume.setValue(int(m.volume * 100))
        self.background.setValue(int(m.background_level * 100))
        set_combo(self.fade, m.fade_in or "soft")

    def apply_pack(self, pack: ChannelStudioPack) -> None:
        m = pack.music
        m.personality = combo_value(self.personality, "mystery")
        m.mood = m.personality
        m.volume = float(self.volume.value()) / 100.0
        m.background_level = float(self.background.value()) / 100.0
        m.fade_in = combo_value(self.fade, "soft")
        m.fade_out = m.fade_in
