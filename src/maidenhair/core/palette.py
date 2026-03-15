"""Named colour palette for L-system presets.

Human-readable colour names that can be used in preset TOML files
instead of raw RGB triples.
"""

from __future__ import annotations

# Greens
PALETTE: dict[str, tuple[int, int, int]] = {
    "green": (55, 140, 45),
    "light-green": (75, 175, 55),
    "bright-green": (100, 200, 60),
    "dark-green": (30, 80, 25),
    "olive": (90, 110, 40),
    "fern-green": (65, 155, 50),
    "moss": (50, 100, 35),
    "spring-green": (80, 190, 55),
    # Browns / bark
    "brown": (90, 55, 25),
    "dark-brown": (50, 28, 12),
    "light-brown": (140, 95, 50),
    "bark": (65, 40, 18),
    "dark-bark": (30, 15, 8),
    "walnut": (55, 35, 15),
    "oak": (110, 70, 35),
    "ebony": (20, 10, 5),
    # Blacks / greys
    "black": (5, 5, 5),
    "charcoal": (25, 25, 25),
    "slate": (60, 65, 70),
    "grey": (120, 120, 120),
    "light-grey": (180, 180, 180),
    "white": (240, 240, 240),
    # Backgrounds
    "forest-night": (12, 22, 16),
    "midnight": (8, 12, 18),
    "deep-green": (7, 18, 10),
    "parchment": (230, 220, 195),
    "cream": (245, 240, 225),
    # Flowers / accents
    "pink": (200, 100, 120),
    "red": (180, 40, 30),
    "yellow": (210, 190, 50),
    "orange": (200, 120, 30),
    "lavender": (150, 120, 180),
}


def resolve_color(value: str | list[int]) -> list[int]:
    """Resolve a colour value — either a name from the palette or an RGB list.

    Accepts:
        "light-green"       -> lookup in PALETTE
        [75, 175, 55]       -> pass through as-is
    """
    if isinstance(value, list):
        return value
    name = value.strip().lower()
    if name not in PALETTE:
        raise ValueError(f"Unknown colour name '{value}'. Available: {', '.join(sorted(PALETTE))}")
    return list(PALETTE[name])
