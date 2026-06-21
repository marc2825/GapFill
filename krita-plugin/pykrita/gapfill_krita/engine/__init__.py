"""Krita-independent GapFill detection and color-prediction engine."""

from .detection import detect_gap_regions
from .inference import GapFillPredictor
from .types import GapKind, GapRegion, LayerImages

__all__ = [
    "GapFillPredictor",
    "GapKind",
    "GapRegion",
    "LayerImages",
    "detect_gap_regions",
]
