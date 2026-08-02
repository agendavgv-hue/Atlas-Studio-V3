"""Load Channel Studio + references into a Creative Brief."""

from __future__ import annotations

from pathlib import Path

from app.channels.studio.models import ChannelStudioPack
from app.channels.studio.service import ChannelStudioService
from app.creative.engine.brief import CreativeBrief, ProjectBrief, ReferenceSummary
from app.projects.models import Project


class CreativeBriefLoader:
    """Reads Channel Studio packs generically (no hardcoded channel names)."""

    def __init__(self, data_root: Path) -> None:
        self._data_root = Path(data_root)
        self._studio = ChannelStudioService(self._data_root)

    @property
    def data_root(self) -> Path:
        return self._data_root

    def load_pack(self, channel_folder: str) -> ChannelStudioPack:
        return self._studio.load(channel_folder)

    def load_brief(
        self,
        channel_folder: str,
        *,
        project: Project | None = None,
        script_text: str = "",
        sheet_text: str = "",
    ) -> CreativeBrief:
        pack = self._studio.load(channel_folder)
        refs = self._reference_summaries(channel_folder)
        project_brief = ProjectBrief(
            topic=(project.name if project else "") or "",
            idea=(project.idea if project else "") or "",
            folder_name=(project.folder_name if project else "") or "",
            script_excerpt=(script_text or "")[:1200],
            sheet_excerpt=(sheet_text or "")[:1200],
        )
        return CreativeBrief.from_pack(pack, references=refs, project=project_brief)

    def _reference_summaries(self, channel_folder: str) -> list[ReferenceSummary]:
        summaries: list[ReferenceSummary] = []
        for kind in ("thumbnails", "images", "movies", "branding", "voices", "music"):
            try:
                files = self._studio.list_references(channel_folder, kind)
            except (ValueError, OSError):
                files = []
            summaries.append(
                ReferenceSummary(
                    kind=kind,
                    count=len(files),
                    names=[p.name for p in files[:12]],
                )
            )
        return summaries
