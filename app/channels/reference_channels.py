"""Official Atlas Studio reference channels — never mutated by AI Channel Creator."""

from __future__ import annotations

REFERENCE_CHANNEL_NAMES: frozenset[str] = frozenset(
    {
        "Hollow Atlas",
        "Mirror Drift",
    }
)


def is_reference_channel(name: str) -> bool:
    """True when ``name`` is an official reference channel."""
    key = (name or "").strip()
    if key in REFERENCE_CHANNEL_NAMES:
        return True
    lowered = key.casefold()
    return any(ref.casefold() == lowered for ref in REFERENCE_CHANNEL_NAMES)


def assert_not_reference_channel(name: str, *, action: str = "modify") -> None:
    """Raise if the name targets a locked reference channel."""
    if is_reference_channel(name):
        raise ValueError(
            f"Cannot {action} official reference channel "
            f"'{name.strip()}'. Hollow Atlas and Mirror Drift are locked; "
            "use AI Channel Creator only for NEW channels."
        )
