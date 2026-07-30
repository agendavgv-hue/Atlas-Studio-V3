"""Artifact Resolver — locate project files by purpose, never by exact filename."""

from __future__ import annotations

from pathlib import Path

from app.artifacts.kinds import ArtifactKind
from app.artifacts.rules import ARTIFACT_RULES, ArtifactRule, IGNORE_FILENAMES


class ArtifactResolver:
    """Standard file lookup service for Atlas Studio projects.

    Searches the correct project folder(s) and matches files by purpose
    (name hints + supported extensions). Compatible with V2, V3, and
    user-renamed files.
    """

    def __init__(self, project_dir: Path) -> None:
        self._root = project_dir.expanduser().resolve()

    @property
    def project_dir(self) -> Path:
        return self._root

    def find(self, kind: ArtifactKind) -> Path | None:
        """Return the preferred file for ``kind``, or ``None`` if missing."""
        matches = self.find_all(kind)
        return matches[0] if matches else None

    def find_all(self, kind: ArtifactKind) -> list[Path]:
        """Return all matching files, preferred match first."""
        rule = ARTIFACT_RULES[kind]
        candidates = self._candidates(rule)
        if kind == ArtifactKind.SCRIPT:
            sheet_paths = set(self._candidates(ARTIFACT_RULES[ArtifactKind.PRODUCTION_SHEET]))
            candidates = [path for path in candidates if path not in sheet_paths]
        ranked = sorted(candidates, key=lambda path: self._rank(path, rule))
        return ranked

    def exists(self, kind: ArtifactKind) -> bool:
        return self.find(kind) is not None

    def open_path(self, kind: ArtifactKind) -> Path | None:
        """Alias for :meth:`find` — used by Workspace Open actions."""
        return self.find(kind)

    def _candidates(self, rule: ArtifactRule) -> list[Path]:
        found: list[Path] = []
        for folder_name in rule.folders:
            folder = self._root / folder_name
            if not folder.is_dir():
                continue
            for path in self._iter_files(folder):
                if path.suffix.casefold() not in rule.extensions:
                    continue
                if self._matches_purpose(path, rule):
                    found.append(path)
        return found

    def _matches_purpose(self, path: Path, rule: ArtifactRule) -> bool:
        suffix = path.suffix.casefold()
        if suffix in rule.type_only_extensions:
            return True
        stem = path.stem.casefold()
        if rule.name_hints and any(hint in stem for hint in rule.name_hints):
            return True
        if rule.any_matching_file:
            return True
        return False

    def _rank(self, path: Path, rule: ArtifactRule) -> tuple[int, int, int, str]:
        """Lower tuple sorts earlier — prefer earlier rule folders, then name hints."""
        folder_rank = self._folder_rank(path, rule)
        stem = path.stem.casefold()
        if not rule.name_hints:
            hint_rank = 0
        elif any(hint in stem for hint in rule.name_hints):
            # Prefer longer / more specific hints (e.g. thumbnail over thumb).
            hint_rank = -max(
                (len(hint) for hint in rule.name_hints if hint in stem),
                default=0,
            )
        else:
            hint_rank = 100
        return (folder_rank, hint_rank, -path.stat().st_mtime_ns, path.name.casefold())

    @staticmethod
    def _folder_rank(path: Path, rule: ArtifactRule) -> int:
        """Prefer folders listed earlier in ``rule.folders`` (e.g. voice before mp3)."""
        parent = path.parent.name.casefold()
        for index, folder_name in enumerate(rule.folders):
            if parent == folder_name.casefold():
                return index
        return len(rule.folders) + 1

    @staticmethod
    def _iter_files(folder: Path) -> list[Path]:
        files: list[Path] = []
        for entry in folder.iterdir():
            if not entry.is_file():
                continue
            if entry.name.startswith("."):
                continue
            if entry.name.casefold() in IGNORE_FILENAMES:
                continue
            files.append(entry)
        return files
