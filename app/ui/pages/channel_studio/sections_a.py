"""Channel Studio sections — Basics, Brand Kit, Thumbnail Studio."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.channels.studio.models import ChannelStudioPack
from app.channels.studio.paths import BRANDING_DIR
from app.ui.pages.channel_studio.form_kit import (
    combo_value,
    make_combo,
    make_slider,
    section_intro,
    set_combo,
    slider_row,
)
from app.ui.pages.channel_studio.reference_panel import ReferencePanel
from app.ui.pages.channel_studio.style_dna_card import StyleDNACard
from app.ui.widgets.asset_picker import IMAGE_FILTER, MEDIA_FILTER, AssetPickerWidget


class GeneralSection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.name = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setFixedHeight(80)
        self.niche = QLineEdit()
        self.audience = QLineEdit()
        self.language = make_combo(
            [("English (US)", "en-US"), ("English (UK)", "en-GB"), ("Dutch", "nl-NL")]
        )
        self.tone = make_combo(
            [
                ("Calm documentary", "calm documentary"),
                ("Curious explorer", "curious"),
                ("Epic storyteller", "epic"),
                ("Warm mentor", "warm"),
            ]
        )
        self.upload_frequency = make_combo(
            [
                ("1× per week", "1x/week"),
                ("2× per week", "2x/week"),
                ("3× per week", "3x/week"),
                ("Daily", "daily"),
            ]
        )
        self.channel_type = make_combo(
            [
                ("Documentary", "documentary"),
                ("Story", "story"),
                ("Education", "education"),
                ("Entertainment", "entertainment"),
                ("Tech", "tech"),
            ]
        )
        form = QFormLayout()
        form.addRow("Channel name", self.name)
        form.addRow("Description", self.description)
        form.addRow("Niche", self.niche)
        form.addRow("Audience", self.audience)
        form.addRow("Language", self.language)
        form.addRow("Tone of voice", self.tone)
        form.addRow("Upload rhythm", self.upload_frequency)
        form.addRow("Channel type", self.channel_type)
        layout = QVBoxLayout(self)
        layout.addWidget(
            section_intro(
                "Channel Basics",
                "Teach Atlas who this channel is — name, audience, and voice.",
            )
        )
        layout.addLayout(form)
        layout.addStretch()

    def load_pack(self, pack: ChannelStudioPack) -> None:
        g = pack.general
        self.name.setText(g.name)
        self.description.setPlainText(g.description)
        self.niche.setText(g.niche)
        self.audience.setText(g.audience)
        set_combo(self.language, g.language or "en-US")
        set_combo(self.tone, g.tone_of_voice or "calm documentary")
        set_combo(self.upload_frequency, g.upload_frequency or "1x/week")
        set_combo(self.channel_type, g.channel_type or "documentary")

    def apply_pack(self, pack: ChannelStudioPack) -> None:
        pack.general.name = self.name.text().strip()
        pack.general.description = self.description.toPlainText().strip()
        pack.general.niche = self.niche.text().strip()
        pack.general.audience = self.audience.text().strip()
        pack.general.language = combo_value(self.language, "en-US")
        pack.general.tone_of_voice = combo_value(self.tone, "calm documentary")
        pack.general.upload_frequency = combo_value(self.upload_frequency, "1x/week")
        pack.general.channel_type = combo_value(self.channel_type, "documentary")


class BrandSection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.logo = AssetPickerWidget(
            title="Logo",
            asset_key="logo",
            file_filter=IMAGE_FILTER,
            subdir=BRANDING_DIR,
            help_text="Main channel mark. Used on thumbnails, intros, and watermarks.",
        )
        self.thumb_logo = AssetPickerWidget(
            title="Thumbnail Logo",
            asset_key="thumbnail_logo",
            file_filter=IMAGE_FILTER,
            subdir=BRANDING_DIR,
            help_text="Compact logo variant optimized for busy thumbnails.",
        )
        self.thumb_frame = AssetPickerWidget(
            title="Thumbnail Frame",
            asset_key="thumbnail_frame",
            file_filter=IMAGE_FILTER,
            subdir=BRANDING_DIR,
            help_text="Optional overlay frame composited after AI generation (never AI-painted).",
        )
        self.banner = AssetPickerWidget(
            title="Banner",
            asset_key="banner",
            file_filter=IMAGE_FILTER,
            subdir=BRANDING_DIR,
            help_text="Channel banner / cover art for consistent brand presence.",
        )
        self.watermark = AssetPickerWidget(
            title="Watermark",
            asset_key="watermark",
            file_filter=IMAGE_FILTER,
            subdir=BRANDING_DIR,
            help_text="Subtle mark for images and movie frames.",
        )
        self.intro = AssetPickerWidget(
            title="Intro",
            asset_key="intro",
            file_filter=MEDIA_FILTER,
            subdir=BRANDING_DIR,
            help_text="Opening stinger that trains recognition in the first seconds.",
        )
        self.outro = AssetPickerWidget(
            title="Outro",
            asset_key="outro",
            file_filter=MEDIA_FILTER,
            subdir=BRANDING_DIR,
            help_text="Closing identity beat and call-to-action moment.",
        )
        self._asset_pickers = (
            self.logo,
            self.thumb_logo,
            self.thumb_frame,
            self.banner,
            self.watermark,
            self.intro,
            self.outro,
        )
        self.primary = QLineEdit()
        self.primary.setPlaceholderText("#1a1a2e")
        self.secondary = QLineEdit()
        self.accent = QLineEdit()
        self.fonts = QLineEdit()
        self.cta = QLineEdit()
        self.social = QPlainTextEdit()
        self.social.setPlaceholderText("youtube=...\ninstagram=...")
        self.social.setFixedHeight(56)
        self.refs = ReferencePanel(
            kind="branding", title="Extra brand references", max_count=20
        )
        colors = QFormLayout()
        colors.addRow("Primary color", self.primary)
        colors.addRow("Secondary color", self.secondary)
        colors.addRow("Accent color", self.accent)
        colors.addRow("Fonts", self.fonts)
        colors.addRow("CTA line", self.cta)
        colors.addRow("Social branding", self.social)
        layout = QVBoxLayout(self)
        layout.addWidget(
            section_intro(
                "Brand Kit",
                "Train visual identity with asset cards — no file paths, only previews.",
            )
        )
        for picker in self._asset_pickers:
            layout.addWidget(picker)
        layout.addLayout(colors)
        layout.addWidget(self.refs)
        layout.addStretch()

    def bind_assets(self, folder_name: str, service) -> None:
        for picker in self._asset_pickers:
            picker.bind(folder_name, service)

    def load_pack(self, pack: ChannelStudioPack) -> None:
        b = pack.brand
        self.logo.set_stored_path(b.logo)
        self.thumb_logo.set_stored_path(b.thumbnail_logo)
        self.thumb_frame.set_stored_path(b.thumbnail_frame)
        self.banner.set_stored_path(b.banner)
        self.watermark.set_stored_path(b.watermark)
        self.intro.set_stored_path(b.intro)
        self.outro.set_stored_path(b.outro)
        self.primary.setText(b.primary_color)
        self.secondary.setText(b.secondary_color)
        self.accent.setText(b.accent_color)
        self.fonts.setText(", ".join(b.fonts))
        self.cta.setText(b.cta)
        self.social.setPlainText(
            "\n".join(f"{k}={v}" for k, v in (b.social_branding or {}).items())
        )

    def apply_pack(self, pack: ChannelStudioPack) -> None:
        b = pack.brand
        b.logo = self.logo.stored_path()
        b.thumbnail_logo = self.thumb_logo.stored_path()
        b.thumbnail_frame = self.thumb_frame.stored_path()
        b.banner = self.banner.stored_path()
        b.watermark = self.watermark.stored_path()
        b.intro = self.intro.stored_path()
        b.outro = self.outro.stored_path()
        b.primary_color = self.primary.text().strip()
        b.secondary_color = self.secondary.text().strip()
        b.accent_color = self.accent.text().strip()
        b.fonts = [p.strip() for p in self.fonts.text().split(",") if p.strip()]
        b.cta = self.cta.text().strip()
        social = {}
        for line in self.social.toPlainText().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                social[k.strip()] = v.strip()
        b.social_branding = social


class ThumbnailSection(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.dominant = make_combo(
            [("One", "one"), ("Two", "two"), ("Three", "three")], current="one"
        )
        self.emotion = make_combo(
            [
                ("Mystery", "mystery"),
                ("Wonder", "wonder"),
                ("Danger", "danger"),
                ("Discovery", "discovery"),
                ("Fear", "fear"),
                ("Curiosity", "curiosity"),
            ],
            current="curiosity",
        )
        self.composition = make_combo(
            [
                ("Close Up", "close_up"),
                ("Medium", "medium"),
                ("Wide", "wide"),
            ],
            current="medium",
        )
        self.negative_space = make_combo(
            [
                ("Auto", "auto"),
                ("Left", "left"),
                ("Right", "right"),
                ("Balanced", "balanced"),
            ],
            current="auto",
        )
        self.logo_position = make_combo(
            [
                ("Auto", "auto"),
                ("Top Left", "top_left"),
                ("Top Right", "top_right"),
                ("Bottom Left", "bottom_left"),
                ("Bottom Right", "bottom_right"),
                ("Center", "center"),
            ],
            current="auto",
        )
        self.logo_visible = QCheckBox("Keep logo visible")
        self.max_words = QSpinBox()
        self.max_words.setRange(1, 8)
        self.cinematic, self.cinematic_r = make_slider(80)
        self.realism, self.realism_r = make_slider(85)
        self.documentary, self.documentary_r = make_slider(70)
        self.creativity, self.creativity_r = make_slider(60)
        self.style_strength, self.style_r = make_slider(80)
        self.brand_strength, self.brand_r = make_slider(85)
        self.refs = ReferencePanel(
            kind="thumbnails", title="Reference thumbnails", max_count=10
        )
        self.style_dna = StyleDNACard()

        form = QFormLayout()
        form.addRow("Dominant subject", self.dominant)
        form.addRow("Emotion", self.emotion)
        form.addRow("Composition", self.composition)
        form.addRow("Negative space", self.negative_space)
        form.addRow("Logo position", self.logo_position)
        form.addRow("Logo", self.logo_visible)
        form.addRow("Max words", self.max_words)

        layout = QVBoxLayout(self)
        layout.addWidget(
            section_intro(
                "Thumbnail Studio",
                "Train click-stopping thumbnail instincts — emotion, subject, and space.",
            )
        )
        layout.addLayout(form)
        layout.addWidget(
            slider_row(
                "Cinematic level",
                self.cinematic,
                self.cinematic_r,
                "How film-like the thumbnail should feel.",
            )
        )
        layout.addWidget(
            slider_row(
                "Realism",
                self.realism,
                self.realism_r,
                "Photoreal look versus stylized.",
            )
        )
        layout.addWidget(
            slider_row(
                "Documentary",
                self.documentary,
                self.documentary_r,
                "How grounded and documentary the frame feels.",
            )
        )
        layout.addWidget(slider_row("Creativity", self.creativity, self.creativity_r))
        layout.addWidget(slider_row("Style strength", self.style_strength, self.style_r))
        layout.addWidget(slider_row("Brand strength", self.brand_strength, self.brand_r))
        layout.addWidget(self.refs)
        layout.addWidget(self.style_dna)
        layout.addStretch()

        self.dominant.setToolTip("How many heroes fight for attention.")
        self.emotion.setToolTip("The feeling the viewer should get before clicking.")
        self.composition.setToolTip("Framing distance of the main subject.")
        self.negative_space.setToolTip("Where text and breathing room live.")
        self.logo_position.setToolTip("Where the channel mark sits.")

    def load_pack(self, pack: ChannelStudioPack) -> None:
        t = pack.thumbnail
        set_combo(self.dominant, t.dominant_subject or "one")
        set_combo(self.emotion, t.emotion or "curiosity")
        set_combo(self.composition, t.composition_style or "medium")
        set_combo(self.negative_space, t.negative_space or "auto")
        set_combo(self.logo_position, t.logo_position or "auto")
        self.logo_visible.setChecked(t.logo_visible)
        self.max_words.setValue(t.max_words)
        self.cinematic.setValue(int(t.cinematic_level))
        self.realism.setValue(int(t.realism))
        self.documentary.setValue(int(t.documentary))
        self.creativity.setValue(int(t.creativity))
        self.style_strength.setValue(int(t.style_strength))
        self.brand_strength.setValue(int(t.brand_strength))

    def apply_pack(self, pack: ChannelStudioPack) -> None:
        t = pack.thumbnail
        t.dominant_subject = combo_value(self.dominant, "one")
        t.emotion = combo_value(self.emotion, "curiosity")
        t.composition_style = combo_value(self.composition, "medium")
        t.negative_space = combo_value(self.negative_space, "auto")
        t.logo_position = combo_value(self.logo_position, "auto")
        t.logo_visible = self.logo_visible.isChecked()
        t.max_words = int(self.max_words.value())
        t.cinematic_level = float(self.cinematic.value())
        t.realism = float(self.realism.value())
        t.documentary = float(self.documentary.value())
        t.creativity = float(self.creativity.value())
        t.style_strength = float(self.style_strength.value())
        t.brand_strength = float(self.brand_strength.value())
