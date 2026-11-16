from __future__ import annotations

import math
from dataclasses import dataclass

from .engine.types import ModelBoundaryMode
from .qt_compat import QSettings


def _stored_int(settings, key: str, default: int, minimum: int) -> int:
    """Read a persisted integer, falling back to ``default`` when corrupt."""

    try:
        value = int(settings.value(key, default))
    except (TypeError, ValueError, OverflowError):
        return default
    return value if value >= minimum else default


def _stored_positive_float(settings, key: str, default: float) -> float:
    """Read a persisted finite positive float, falling back when corrupt."""

    try:
        value = float(settings.value(key, default))
    except (TypeError, ValueError, OverflowError):
        return default
    return value if math.isfinite(value) and value > 0.0 else default


@dataclass
class GapFillSettings:
    threshold: int = 500
    marker_radius: float = 14.0
    sweep_radius: float = 18.0
    highlight_color: str = "#00D9FF"
    allow_per_gap_greedy_fallback: bool = True
    model_boundary_mode: ModelBoundaryMode = ModelBoundaryMode.LINE_ONLY

    @classmethod
    def load(cls) -> "GapFillSettings":
        settings = QSettings("GapFill", "KritaPlugin")
        stored_mode = str(settings.value("modelBoundaryMode", ModelBoundaryMode.LINE_ONLY.value))
        try:
            model_boundary_mode = ModelBoundaryMode(stored_mode)
        except ValueError:
            model_boundary_mode = ModelBoundaryMode.LINE_ONLY
        return cls(
            threshold=_stored_int(settings, "threshold", 500, minimum=1),
            marker_radius=_stored_positive_float(settings, "markerRadius", 14.0),
            sweep_radius=_stored_positive_float(settings, "sweepRadius", 18.0),
            highlight_color=str(settings.value("highlightColor", "#00D9FF")),
            allow_per_gap_greedy_fallback=str(settings.value("allowGreedyFallback", "true")).lower()
            in ("1", "true", "yes"),
            model_boundary_mode=model_boundary_mode,
        )

    def save(self) -> None:
        settings = QSettings("GapFill", "KritaPlugin")
        settings.setValue("threshold", self.threshold)
        settings.setValue("markerRadius", self.marker_radius)
        settings.setValue("sweepRadius", self.sweep_radius)
        settings.setValue("highlightColor", self.highlight_color)
        settings.setValue("allowGreedyFallback", self.allow_per_gap_greedy_fallback)
        settings.setValue("modelBoundaryMode", self.model_boundary_mode.value)
