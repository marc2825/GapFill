from __future__ import annotations

from dataclasses import dataclass

from .qt_compat import QSettings


@dataclass
class GapFillSettings:
    threshold: int = 500
    marker_radius: float = 14.0
    sweep_radius: float = 18.0
    highlight_color: str = "#00D9FF"
    allow_per_gap_greedy_fallback: bool = True

    @classmethod
    def load(cls) -> "GapFillSettings":
        settings = QSettings("GapFill", "KritaPlugin")
        return cls(
            threshold=int(settings.value("threshold", 500)),
            marker_radius=float(settings.value("markerRadius", 14.0)),
            sweep_radius=float(settings.value("sweepRadius", 18.0)),
            highlight_color=str(settings.value("highlightColor", "#00D9FF")),
            allow_per_gap_greedy_fallback=str(settings.value("allowGreedyFallback", "true")).lower()
            in ("1", "true", "yes"),
        )

    def save(self) -> None:
        settings = QSettings("GapFill", "KritaPlugin")
        settings.setValue("threshold", self.threshold)
        settings.setValue("markerRadius", self.marker_radius)
        settings.setValue("sweepRadius", self.sweep_radius)
        settings.setValue("highlightColor", self.highlight_color)
        settings.setValue("allowGreedyFallback", self.allow_per_gap_greedy_fallback)
