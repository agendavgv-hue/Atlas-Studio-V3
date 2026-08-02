"""Layout Generator — invent ≥20 design layouts from scene + DNA + typography."""

from __future__ import annotations

from app.thumbnail.design_engine.models import LayoutCandidate, RectNorm, SceneMap
from app.thumbnail.design_engine.typography import LineBreakCandidate
from app.thumbnail.style_dna.models import ThumbnailStyleDNA

MIN_LAYOUTS = 20


def generate_layouts(
    *,
    scene: SceneMap,
    style_dna: ThumbnailStyleDNA | None,
    line_breaks: list[LineBreakCandidate],
    hook_word_count: int = 3,
) -> list[LayoutCandidate]:
    """Produce diverse layout candidates (generic — never channel-hardcoded)."""
    del hook_word_count
    dna_neg = (style_dna.negative_space if style_dna else "") or scene.negative_space
    dna_logo = (style_dna.logo_position if style_dna else "") or "bottom_left"
    dna_scale = float(style_dna.logo_scale) if style_dna else 0.11
    dna_top = float(style_dna.text_top) if style_dna else 0.12
    dna_width = float(style_dna.text_width) if style_dna else 0.40
    dna_margin = float(style_dna.margin_x) if style_dna else 0.05
    dna_lines = int(style_dna.text_max_lines) if style_dna else 3

    breaks = line_breaks[:5] or [
        LineBreakCandidate(lines=["TITLE"], score=50.0, why="fallback")
    ]

    recipes: list[dict] = []
    # DNA-first layouts
    for br in breaks[:2]:
        recipes.append(
            {
                "anchor": dna_neg if dna_neg in {"left", "right"} else "left",
                "logo": dna_logo,
                "scale": "large",
                "lines_n": dna_lines,
                "orient": "horizontal",
                "break": br,
            }
        )
        recipes.append(
            {
                "anchor": dna_neg if dna_neg in {"left", "right"} else "left",
                "logo": dna_logo,
                "scale": "medium",
                "lines_n": max(2, dna_lines - 1),
                "orient": "horizontal",
                "break": br,
            }
        )

    # Systematic variations
    for anchor in ("left", "right", "top", "bottom", "center"):
        for logo in (dna_logo, "bottom_left", "bottom_right", "top_left"):
            for scale in ("large", "medium", "small"):
                for lines_n in (2, 3, 4):
                    for orient in ("horizontal", "vertical"):
                        for br in breaks[:2]:
                            recipes.append(
                                {
                                    "anchor": anchor,
                                    "logo": logo,
                                    "scale": scale,
                                    "lines_n": lines_n,
                                    "orient": orient,
                                    "break": br,
                                }
                            )

    layouts: list[LayoutCandidate] = []
    seen: set[tuple] = set()
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for recipe in recipes:
        if len(layouts) >= 28:
            break
        br: LineBreakCandidate = recipe["break"]
        lines = _fit_lines(br.lines, int(recipe["lines_n"]))
        if not lines:
            continue
        orient = recipe["orient"]
        anchor = recipe["anchor"]
        if orient == "vertical":
            if anchor in {"top", "bottom"}:
                continue
            lines = [w for line in lines for w in line.split()][:4]
        key = (
            anchor,
            recipe["logo"],
            recipe["scale"],
            tuple(lines),
            orient,
        )
        if key in seen:
            continue
        seen.add(key)

        scale = recipe["scale"]
        top = dna_top
        width = dna_width
        if scale == "small":
            width *= 0.85
            top = min(0.28, top + 0.02)
        elif scale == "large":
            width = min(0.55, width * 1.08)
        if anchor == "top":
            top, width = 0.06, min(0.72, width * 1.15)
        elif anchor == "bottom":
            top = 0.58
        elif anchor == "center":
            top, width = 0.28, min(0.55, width)
        if orient == "vertical":
            width = min(0.28, width * 0.7)

        align = (
            "left"
            if anchor == "left"
            else "right"
            if anchor == "right"
            else "center"
        )
        idx = len(layouts)
        lid = alphabet[idx % len(alphabet)]
        if idx >= len(alphabet):
            lid = f"{alphabet[idx % len(alphabet)]}{1 + idx // len(alphabet)}"

        text_rect = _estimate_text_rect(
            anchor=anchor,
            top_ratio=top,
            width_ratio=width,
            margin=dna_margin,
            line_count=len(lines),
            scale=scale,
        )
        layouts.append(
            LayoutCandidate(
                id=lid,
                label=_label(anchor, len(lines), scale, recipe["logo"], orient),
                text_anchor=anchor,
                text_align=align,
                max_lines=len(lines),
                title_scale=scale,
                orientation=orient,
                logo_position=str(recipe["logo"]),
                logo_scale=dna_scale * (0.9 if scale == "large" else 1.0),
                top_ratio=top,
                max_width_ratio=width,
                margin_x_ratio=dna_margin,
                lines=lines,
                line_break_score=br.score,
                text_rect=text_rect,
            )
        )

    while len(layouts) < MIN_LAYOUTS and layouts:
        base = layouts[len(layouts) % len(layouts)]
        flip = "bottom_right" if "left" in base.logo_position else "bottom_left"
        layouts.append(
            LayoutCandidate(
                id=f"{base.id}x",
                label=f"{base.label} · logo flip",
                text_anchor=base.text_anchor,
                text_align=base.text_align,
                max_lines=base.max_lines,
                title_scale=base.title_scale,
                orientation=base.orientation,
                logo_position=flip,
                logo_scale=base.logo_scale,
                top_ratio=base.top_ratio,
                max_width_ratio=base.max_width_ratio,
                margin_x_ratio=base.margin_x_ratio,
                lines=list(base.lines),
                line_break_score=base.line_break_score,
                text_rect=base.text_rect,
            )
        )
    return layouts[: max(MIN_LAYOUTS, min(28, len(layouts)))]


def _fit_lines(lines: list[str], max_lines: int) -> list[str]:
    if not lines:
        return []
    if len(lines) <= max_lines:
        return list(lines)[:max_lines]
    head = lines[: max_lines - 1]
    tail = " ".join(lines[max_lines - 1 :])
    return [*head, tail]


def _estimate_text_rect(
    *,
    anchor: str,
    top_ratio: float,
    width_ratio: float,
    margin: float,
    line_count: int,
    scale: str,
) -> RectNorm:
    height = min(0.55, 0.10 * line_count * (1.35 if scale == "large" else 1.0))
    if anchor == "left":
        return RectNorm(x=margin, y=top_ratio, w=width_ratio, h=height)
    if anchor == "right":
        return RectNorm(
            x=1.0 - margin - width_ratio, y=top_ratio, w=width_ratio, h=height
        )
    if anchor == "top":
        return RectNorm(x=(1.0 - width_ratio) / 2, y=0.06, w=width_ratio, h=height)
    if anchor == "bottom":
        return RectNorm(x=(1.0 - width_ratio) / 2, y=0.62, w=width_ratio, h=height)
    return RectNorm(x=(1.0 - width_ratio) / 2, y=top_ratio, w=width_ratio, h=height)


def _label(anchor: str, lines: int, scale: str, logo: str, orient: str) -> str:
    return (
        f"text {anchor} · {lines} lines · {scale} · "
        f"logo {logo.replace('_', ' ')} · {orient}"
    )
