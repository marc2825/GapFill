"""Krita-independent GapFill detection and color-prediction engine."""

from .detection import detect_gap_regions
from .inference import GapFillPredictor
from .types import (
    DetectionGeometry,
    GapKind,
    GapRegion,
    LayerImages,
    PredictionProvenance,
)

__all__ = [
    "GapFillPredictor",
    "DetectionGeometry",
    "GapKind",
    "GapRegion",
    "LayerImages",
    "PredictionProvenance",
    "detect_gap_regions",
]
