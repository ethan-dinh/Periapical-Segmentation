"""Landmark utilities for DentAnX."""

from __future__ import annotations

LANDMARK_CLASSES = ["CEJ", "CREST", "APEX"]

LANDMARK_COLORS = {
    "CEJ": "#4DA3FF",
    "CREST": "#61D0B5",
    "APEX": "#FFC107",
}


def normalize_class(label: str) -> str:
    """
    Normalize a landmark class label to uppercase and validate against allowed classes.
    """
    label = str(label).upper()
    return label if label in LANDMARK_CLASSES else "CEJ"


BBOX_CLASSES = ["Unlabeled", "Tooth", "Crest", "PDL", "LD"]

BBOX_COLORS = {
    "Unlabeled": "#808080",   # Gray
    "Tooth": "#FF5733",       # Orange-ish
    "Crest": "#3357FF",       # Blue-ish
    "PDL": "#FF33F6",         # Pink-ish
    "LD": "#33FFF6",          # Cyan-ish
}
