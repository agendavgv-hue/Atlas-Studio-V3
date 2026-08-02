"""DesignEngineService — Atlas designs the thumbnail; AI only illustrates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.thumbnail.design_engine.critic import LayoutCritic
from app.thumbnail.design_engine.layouts import MIN_LAYOUTS, generate_layouts
from app.thumbnail.design_engine.models import DesignReviewBoard, LayoutCandidate
from app.thumbnail.design_engine.render import render_layout, save_layout_preview
from app.thumbnail.design_engine.store import write_design_review
from app.thumbnail.design_engine.typography import invent_line_breaks
from app.thumbnail.design_engine.vision import analyze_illustration
from app.thumbnail.naming import THUMBNAIL_FOLDER, resolve_thumbnail_dir
from app.thumbnail.pipeline.brand_composer import BrandComposerAssets
from app.thumbnail.style_dna.models import ThumbnailStyleDNA


@dataclass
class DesignEngineResult:
    image_png: bytes
    winner: LayoutCandidate
    board: DesignReviewBoard
    scene_map: dict


class DesignEngineService:
    """
    Illustration → Vision → Layouts (≥20) → Typography → Brand → Critic → Best.
    """

    def __init__(self) -> None:
        self._critic = LayoutCritic()

    def design(
        self,
        illustration_png: bytes,
        *,
        hook: str,
        assets: BrandComposerAssets,
        style_dna: ThumbnailStyleDNA | None = None,
        channel_name: str = "",
        project_name: str = "",
        project_dir: Path | None = None,
        max_preview: int = 8,
    ) -> DesignEngineResult:
        scene = analyze_illustration(illustration_png)
        max_words = int(assets.max_words or (style_dna.average_words if style_dna else 4) or 4)
        breaks = invent_line_breaks(hook, style_dna=style_dna, max_words=max_words)
        layouts = generate_layouts(
            scene=scene,
            style_dna=style_dna or assets.style_dna,
            line_breaks=breaks,
            hook_word_count=len((hook or "").split()),
        )
        if len(layouts) < MIN_LAYOUTS:
            # Should not happen — generator pads — but keep safe.
            while len(layouts) < MIN_LAYOUTS and layouts:
                layouts.append(layouts[0])

        # Score all layouts (geometry critic first)
        for layout in layouts:
            layout.scores = self._critic.score(
                layout, scene=scene, style_dna=style_dna or assets.style_dna
            )
            layout.why = "; ".join(layout.scores.notes) or layout.label

        ranked = sorted(layouts, key=lambda L: L.scores.overall, reverse=True)

        # Render winner + top previews for Design Review
        out_dir = resolve_thumbnail_dir(project_dir) if project_dir else None
        rendered: dict[str, bytes] = {}
        for layout in ranked[: max(1, max_preview)]:
            png = render_layout(
                illustration_png,
                layout,
                assets=assets,
                channel_name=channel_name,
            )
            rendered[layout.id] = png
            if out_dir is not None:
                rel = f"design_layout_{layout.id}.png"
                save_layout_preview(out_dir / rel, png)
                layout.image_relpath = f"{THUMBNAIL_FOLDER}/{rel}"

        winner = ranked[0]
        winner_png = rendered.get(winner.id) or render_layout(
            illustration_png, winner, assets=assets, channel_name=channel_name
        )
        if out_dir is not None and not winner.image_relpath:
            rel = f"design_layout_{winner.id}.png"
            save_layout_preview(out_dir / rel, winner_png)
            winner.image_relpath = f"{THUMBNAIL_FOLDER}/{rel}"

        winner_why = (
            f"Layout {winner.id} won with {winner.scores.overall:.0f}/100 — {winner.label}. "
            f"{winner.why}"
        )
        board = DesignReviewBoard(
            channel_name=channel_name,
            project_name=project_name,
            winner_id=winner.id,
            winner_score=winner.scores.overall,
            winner_why=winner_why,
            scene_map=scene.to_dict(),
            layouts=ranked,
            extras={
                "layout_count": len(layouts),
                "typography_top": (
                    {
                        "lines": breaks[0].lines,
                        "score": breaks[0].score,
                        "why": breaks[0].why,
                    }
                    if breaks
                    else {}
                ),
            },
        )
        if project_dir is not None:
            write_design_review(project_dir, board)

        return DesignEngineResult(
            image_png=winner_png,
            winner=winner,
            board=board,
            scene_map=scene.to_dict(),
        )
