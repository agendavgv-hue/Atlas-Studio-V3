"""Creative Director Engine — central brain before every generator."""

from __future__ import annotations

from pathlib import Path

from app.creative.engine.brief import CreativeBrief, ProjectBrief
from app.creative.engine.loader import CreativeBriefLoader
from app.creative.engine.prompts import (
    create_image_prompt,
    create_movie_prompt,
    create_script_prompt,
    create_seo_prompt,
    create_shorts_prompt,
    create_thumbnail_prompt,
    director_system_block,
    master_prompt,
)
from app.creative.engine.report import CreativeDirectorReport, write_report
from app.creative.engine import layers
from app.projects.models import Project
from app.prompts.assembler import ImagePromptRequest


class CreativeDirectorEngine:
    """Load Channel Studio → Creative Brief → Master Prompt for all generators.

    Generators must not invent channel identity. They ask this engine.
    Fully generic — works for any trained channel, never hardcodes names.
    """

    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)
        self._loader = CreativeBriefLoader(self._data_root)

    @property
    def data_root(self) -> Path:
        return self._data_root

    def build_brief(
        self,
        channel_folder: str,
        *,
        project: Project | None = None,
        script_text: str = "",
        sheet_text: str = "",
    ) -> CreativeBrief:
        return self._loader.load_brief(
            channel_folder,
            project=project,
            script_text=script_text,
            sheet_text=sheet_text,
        )

    def enrich_project(
        self,
        brief: CreativeBrief,
        *,
        script_text: str = "",
        sheet_text: str = "",
        primary_subject: str = "",
        primary_location: str = "",
        primary_emotion: str = "",
    ) -> CreativeBrief:
        brief.project.script_excerpt = (script_text or brief.project.script_excerpt)[:1200]
        brief.project.sheet_excerpt = (sheet_text or brief.project.sheet_excerpt)[:1200]
        if primary_subject:
            brief.project.primary_subject = primary_subject
        if primary_location:
            brief.project.primary_location = primary_location
        if primary_emotion:
            brief.project.primary_emotion = primary_emotion
        return brief

    def create_thumbnail_prompt(self, brief: CreativeBrief, *, subject: str = "") -> str:
        return create_thumbnail_prompt(brief, subject=subject)

    def create_image_prompt(self, brief: CreativeBrief, *, subject: str = "") -> str:
        return create_image_prompt(brief, subject=subject)

    def create_script_prompt(self, brief: CreativeBrief, *, subject: str = "") -> str:
        return create_script_prompt(brief, subject=subject)

    def create_shorts_prompt(self, brief: CreativeBrief, *, subject: str = "") -> str:
        return create_shorts_prompt(brief, subject=subject)

    def create_seo_prompt(self, brief: CreativeBrief, *, subject: str = "") -> str:
        return create_seo_prompt(brief, subject=subject)

    def create_movie_prompt(self, brief: CreativeBrief, *, subject: str = "") -> str:
        return create_movie_prompt(brief, subject=subject)

    def director_system_block(self, brief: CreativeBrief) -> str:
        return director_system_block(brief)

    def assemble_image_request(
        self,
        brief: CreativeBrief,
        *,
        scene: str,
        previous_scene: str = "",
        for_thumbnail: bool = False,
        extra_negative: str = "",
    ) -> ImagePromptRequest:
        """Subject Director scene + Channel Studio look (never hardcoded profiles)."""
        from app.prompts.subject_director import (
            build_subject_director_block,
            subject_protection_negatives,
            subject_word_emphasis,
        )
        from app.prompts.style_engine import GLOBAL_NEGATIVE_LAYER, GLOBAL_QUALITY_LAYER

        scene_text = subject_word_emphasis(scene)
        subject_block = build_subject_director_block(scene_text)
        look = layers.compact_image_look(brief)
        if for_thumbnail:
            t = brief.thumbnail
            look = (
                f"{look}, thumbnail composition {t.composition_style}, "
                f"emotion {t.emotion}, negative space {t.negative_space}, "
                f"max {t.max_words} words space, high contrast, clickable"
            )

        layers_out = [
            f"SUBJECT DIRECTOR: {subject_block}",
            "CHANNEL DIRECTOR (look only — do not change location/era/climate): " + look,
            GLOBAL_QUALITY_LAYER,
        ]
        if previous_scene.strip():
            clip = " ".join(previous_scene.split())[:160]
            layers_out.append(
                "FILM CONTINUITY: same documentary as prior shot — match grade, "
                f"contrast, light, atmosphere from: {clip}"
            )
        # Keep master identity as a trailing guidance block (token-budget aware).
        master = master_prompt(brief, domain="thumbnail" if for_thumbnail else "image", subject="")
        if len(master) > 1200:
            master = master[:1200].rstrip() + "…"
        layers_out.append("CREATIVE DIRECTOR IDENTITY:\n" + master)

        positive = "\n".join(part for part in layers_out if part.strip())

        negatives = [
            GLOBAL_NEGATIVE_LAYER,
            layers.rule_negative_hints(brief),
            extra_negative,
            subject_protection_negatives(scene_text) if scene_text else "",
        ]
        negative = ", ".join(dict.fromkeys(n for n in negatives if n.strip()))
        return ImagePromptRequest(prompt=positive, negative_prompt=negative)

    def write_report(
        self,
        project_dir: Path,
        brief: CreativeBrief,
        *,
        domain: str,
        master_prompt_text: str = "",
        notes: list[str] | None = None,
        thumbnail_profile_loaded: bool = False,
        image_profile_loaded: bool = False,
    ) -> Path:
        report = CreativeDirectorReport.from_brief(
            brief,
            domain=domain,
            master_prompt=master_prompt_text,
            thumbnail_profile_loaded=thumbnail_profile_loaded,
            image_profile_loaded=image_profile_loaded,
        )
        if notes:
            report.notes.extend(notes)
        report.extras["folder_name"] = brief.folder_name
        report.extras["goals"] = brief.goals.to_dict()
        return write_report(project_dir, report)
