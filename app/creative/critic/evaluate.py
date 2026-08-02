"""Rule-based Critic evaluators — judge only, never mutate content."""

from __future__ import annotations

from typing import Any

from app.creative.critic.domains import CriticDomain
from app.creative.critic.rules import CriticFinding, CriticRule
from app.creative.critic.score import CriticScore


def evaluate_payload(
    domain: CriticDomain,
    payload: dict[str, Any],
    policy: dict[str, Any],
    *,
    extra_rules: list[CriticRule] | None = None,
) -> tuple[CriticScore, list[CriticFinding]]:
    findings: list[CriticFinding] = []
    for rule in built_in_rules() + list(extra_rules or []):
        if not rule.applies_to(domain) or rule.check is None:
            continue
        try:
            findings.extend(rule.check(payload, policy) or [])
        except Exception:  # noqa: BLE001
            continue

    findings.extend(_director_rule_findings(domain, payload, policy))
    score = _score_from_findings(findings)
    return score, findings


def built_in_rules() -> list[CriticRule]:
    return [
        CriticRule(
            id="thumb_max_words",
            title="Thumbnail word limit",
            domain="thumbnail",
            dimension="readability",
            check=_thumb_max_words,
        ),
        CriticRule(
            id="one_subject",
            title="One dominant subject",
            domain="*",
            dimension="composition",
            check=_one_subject,
        ),
        CriticRule(
            id="no_cartoon",
            title="No cartoon",
            domain="*",
            dimension="style",
            check=_no_cartoon,
        ),
        CriticRule(
            id="brand_colors",
            title="Brand color presence",
            domain="*",
            dimension="brand",
            check=_brand_colors,
        ),
        CriticRule(
            id="contrast_hint",
            title="Contrast expectation",
            domain="*",
            dimension="quality",
            check=_contrast_hint,
        ),
        CriticRule(
            id="identity_tokens",
            title="Channel identity tokens",
            domain="*",
            dimension="identity",
            check=_identity_tokens,
        ),
        CriticRule(
            id="thumb_layout",
            title="Thumbnail layout",
            domain="thumbnail",
            dimension="composition",
            check=_thumb_layout,
        ),
        CriticRule(
            id="script_hook",
            title="Script hook presence",
            domain="script",
            dimension="creativity",
            check=_script_hook,
        ),
        CriticRule(
            id="voice_speed",
            title="Voice speed band",
            domain="voice",
            dimension="technical",
            check=_voice_speed,
        ),
    ]


def _blob(payload: dict[str, Any]) -> str:
    keys = (
        "text",
        "script",
        "prompt",
        "style",
        "hook",
        "title",
        "description",
        "composition",
        "lighting",
        "colors",
        "layout",
        "notes",
    )
    return " ".join(str(payload.get(k) or "") for k in keys).casefold()


def _thumb_max_words(payload: dict[str, Any], policy: dict[str, Any]) -> list[CriticFinding]:
    director = policy.get("director") or {}
    thumb = director.get("thumbnail") if isinstance(director, dict) else {}
    max_words = int((thumb or {}).get("max_words") or 4)
    hook = str(payload.get("hook") or payload.get("title") or payload.get("text") or "")
    words = [w for w in hook.replace("\n", " ").split() if w.strip()]
    if words and len(words) > max_words:
        return [
            CriticFinding(
                "too_much_text",
                f"teveel tekst ({len(words)} woorden, max {max_words})",
                dimension="readability",
                severity=1.4,
            )
        ]
    return []


def _one_subject(payload: dict[str, Any], _policy: dict[str, Any]) -> list[CriticFinding]:
    count = payload.get("subject_count") or payload.get("subjects")
    try:
        n = int(count) if count is not None else None
    except (TypeError, ValueError):
        n = None
    blob = _blob(payload)
    if n is not None and n > 1:
        return [
            CriticFinding(
                "subject_too_many",
                "meer dan één dominant onderwerp",
                dimension="composition",
                severity=1.3,
            )
        ]
    if "collage" in blob or "multiple subjects" in blob or "crowd of" in blob:
        return [
            CriticFinding(
                "composition_busy",
                "compositie te druk",
                dimension="composition",
                severity=1.2,
            )
        ]
    scale = str(payload.get("subject_scale") or payload.get("hero_scale") or "").casefold()
    if scale in {"small", "tiny"} or "too small" in blob:
        return [
            CriticFinding(
                "subject_too_small",
                "onderwerp te klein",
                dimension="composition",
                severity=1.3,
            )
        ]
    return []


def _no_cartoon(payload: dict[str, Any], policy: dict[str, Any]) -> list[CriticFinding]:
    blob = _blob(payload)
    forbidden = ("cartoon", "anime", "comic book", "cel shaded")
    if any(token in blob for token in forbidden):
        return [
            CriticFinding(
                "cartoon_style",
                "stijl wijkt af (cartoon/anime)",
                dimension="style",
                severity=1.6,
            )
        ]
    # Honor director rules by id when present
    for rule in policy.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        if rule.get("id") == "no_cartoon" and rule.get("enabled", True):
            if any(token in blob for token in forbidden):
                return [
                    CriticFinding(
                        "rule_no_cartoon",
                        "Creative Director: No Cartoon",
                        dimension="style",
                        severity=1.6,
                    )
                ]
    return []


def _brand_colors(payload: dict[str, Any], policy: dict[str, Any]) -> list[CriticFinding]:
    brand = policy.get("brand") or {}
    primary = str(brand.get("primary_color") or "").strip()
    if not primary:
        colors = ((policy.get("director") or {}).get("brand") or {}).get("colors") or []
        primary = str(colors[0]) if colors else ""
    if not primary:
        return []
    observed = str(
        payload.get("primary_color")
        or payload.get("colors")
        or payload.get("color_palette")
        or payload.get("prompt")
        or ""
    ).casefold()
    token = primary.casefold()
    if token and token not in observed and token.lstrip("#") not in observed:
        return [
            CriticFinding(
                "colors_off",
                "kleuren wijken af",
                dimension="brand",
                severity=1.1,
            )
        ]
    return []


def _contrast_hint(payload: dict[str, Any], policy: dict[str, Any]) -> list[CriticFinding]:
    expected = str(
        ((policy.get("director") or {}).get("visual") or {}).get("contrast") or "high"
    ).casefold()
    observed = str(payload.get("contrast") or _blob(payload)).casefold()
    if "high" in expected or "very" in expected:
        if "low" in observed or "flat" in observed or "weinig contrast" in observed:
            return [
                CriticFinding(
                    "low_contrast",
                    "weinig contrast",
                    dimension="quality",
                    severity=1.2,
                )
            ]
    return []


def _identity_tokens(payload: dict[str, Any], policy: dict[str, Any]) -> list[CriticFinding]:
    identity = str(policy.get("identity_blob") or "").casefold()
    blob = _blob(payload)
    if not identity.strip() or not blob.strip():
        return []
    tokens = [t for t in identity.replace(",", " ").split() if len(t) > 4][:12]
    if not tokens:
        return []
    hits = sum(1 for t in tokens if t in blob)
    if hits == 0:
        return [
            CriticFinding(
                "identity_weak",
                "mist kanaalidentiteit",
                dimension="identity",
                severity=1.5,
            )
        ]
    return []


def _thumb_layout(payload: dict[str, Any], policy: dict[str, Any]) -> list[CriticFinding]:
    thumb = ((policy.get("director") or {}).get("thumbnail") or {})
    expected_text = str(thumb.get("text_position") or "left").casefold()
    observed = str(
        payload.get("text_position")
        or payload.get("title_position")
        or payload.get("layout")
        or ""
    ).casefold()
    findings: list[CriticFinding] = []
    if observed and expected_text and expected_text not in observed:
        findings.append(
            CriticFinding(
                "text_position_off",
                f"tekstpositie wijkt af (verwacht {expected_text})",
                dimension="composition",
                severity=1.0,
            )
        )
    logo = str(payload.get("logo_scale") or payload.get("logo_size") or "").casefold()
    if logo in {"large", "huge", "dominant"}:
        findings.append(
            CriticFinding(
                "logo_too_large",
                "logo te groot",
                dimension="brand",
                severity=1.0,
            )
        )
    if "mist ontbreekt" in _blob(payload) or payload.get("fog_missing") is True:
        findings.append(
            CriticFinding(
                "fog_missing",
                "mist ontbreekt",
                dimension="style",
                severity=0.8,
            )
        )
    return findings


def _script_hook(payload: dict[str, Any], policy: dict[str, Any]) -> list[CriticFinding]:
    text = str(payload.get("text") or payload.get("script") or "")
    if len(text.strip()) < 40:
        return [
            CriticFinding(
                "script_too_short",
                "script te kort voor beoordeling",
                dimension="quality",
                severity=1.2,
            )
        ]
    hook_style = str(
        ((policy.get("director") or {}).get("story") or {}).get("hook_style") or ""
    ).casefold()
    head = text[:400].casefold()
    if hook_style and "curios" in hook_style and "?" not in head and "why" not in head:
        return [
            CriticFinding(
                "weak_hook",
                "hook mist spanning/nieuwsgierigheid",
                dimension="creativity",
                severity=1.0,
            )
        ]
    return []


def _voice_speed(payload: dict[str, Any], policy: dict[str, Any]) -> list[CriticFinding]:
    expected = float(((policy.get("director") or {}).get("voice") or {}).get("speed") or 1.0)
    try:
        speed = float(payload.get("speed") if payload.get("speed") is not None else expected)
    except (TypeError, ValueError):
        return []
    if abs(speed - expected) > 0.2:
        return [
            CriticFinding(
                "voice_speed_off",
                f"snelheid wijkt af ({speed} vs {expected})",
                dimension="technical",
                severity=1.1,
            )
        ]
    return []


def _director_rule_findings(
    domain: CriticDomain,
    payload: dict[str, Any],
    policy: dict[str, Any],
) -> list[CriticFinding]:
    """Generic pass: enabled director rules that mention hard constraints in title."""
    _ = domain
    blob = _blob(payload)
    findings: list[CriticFinding] = []
    for rule in policy.get("rules") or []:
        if not isinstance(rule, dict) or not rule.get("enabled", True):
            continue
        title = str(rule.get("title") or "").casefold()
        rid = str(rule.get("id") or "")
        if "bright color" in title and any(t in blob for t in ("neon", "bright pink", "fluorescent")):
            findings.append(
                CriticFinding(
                    rid or "bright_colors",
                    "te felle kleuren",
                    dimension="style",
                    severity=1.0,
                )
            )
    return findings


def _score_from_findings(findings: list[CriticFinding]) -> CriticScore:
    score = CriticScore()
    penalties: dict[str, float] = {
        "brand": 0.0,
        "style": 0.0,
        "quality": 0.0,
        "readability": 0.0,
        "creativity": 0.0,
        "technical": 0.0,
        "composition": 0.0,
        "identity": 0.0,
    }
    for finding in findings:
        dim = finding.dimension if finding.dimension in penalties else "quality"
        penalties[dim] += 10.0 * float(finding.severity)

    for dim, penalty in penalties.items():
        setattr(score, dim, max(0.0, 100.0 - penalty))
    score.recompute_overall()
    return score.clamp()
