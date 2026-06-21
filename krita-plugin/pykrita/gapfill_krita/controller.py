from __future__ import annotations

from typing import Optional

import numpy as np
from krita import Krita

from .engine.types import GapRegion
from .krita_adapter import apply_gap_colors, snapshot_layers
from .model import find_model_path
from .overlay import GapFillOverlay
from .qt_compat import QThread, QWidget, qimage_from_rgba
from .worker import GapFillWorker


class GapFillController:
    def __init__(self, docker):
        self.docker = docker
        self.document = None
        self.view = None
        self.coloring_node = None
        self.images = None
        self.gaps: list[GapRegion] = []
        self.overlay: Optional[GapFillOverlay] = None
        self.thread: Optional[QThread] = None
        self.worker: Optional[GapFillWorker] = None

    @property
    def busy(self) -> bool:
        return self.thread is not None

    def scan(
        self, coloring_node, line_node, guides_node, threshold: int, allow_greedy: bool
    ) -> None:
        if self.busy:
            return
        app = Krita.instance()
        self.document = app.activeDocument()
        window = app.activeWindow()
        self.view = window.activeView() if window else None
        if self.document is None or self.view is None:
            self.docker.show_error("Open a document before activating GapFill.")
            return
        if coloring_node is None or line_node is None:
            self.docker.show_error("Select both a Coloring layer and a Line Art layer.")
            return
        try:
            self.docker.set_busy(True, "Reading Krita layers…")
            self.images = snapshot_layers(self.document, coloring_node, line_node, guides_node)
        except Exception as error:
            self.docker.set_busy(False)
            self.docker.show_error(str(error))
            return

        self.coloring_node = coloring_node
        self.thread = QThread()
        self.worker = GapFillWorker(self.images, threshold, find_model_path(), allow_greedy)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.docker.update_progress)
        self.worker.completed.connect(self._scan_completed)
        self.worker.failed.connect(self._scan_failed)
        self.worker.cancelled.connect(lambda: self.docker.set_status("Cancelled."))
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self._thread_finished)
        self.thread.start()

    def cancel(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.docker.set_status("Cancelling…")

    def deactivate(self) -> None:
        self.cancel()
        if self.overlay is not None:
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None
        self.gaps = []
        self.docker.set_regions([])
        self.docker.set_status("GapFill is inactive.")

    def _thread_finished(self) -> None:
        if self.worker:
            self.worker.deleteLater()
        if self.thread:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None
        self.docker.set_busy(False)

    def _scan_failed(self, message: str) -> None:
        self.gaps = []
        self.docker.show_error(
            "GapFill could not load or run its color-prediction model.\n" + message
        )

    def _scan_completed(self, gaps: list[GapRegion]) -> None:
        if not self._context_is_current():
            self.gaps = []
            self.docker.set_regions([])
            self.docker.show_error(
                "The active document or view changed during scanning. Activate the intended canvas and scan again."
            )
            return
        self.gaps = gaps
        self.docker.set_regions(gaps)
        if not gaps:
            self.docker.set_status("No enclosed gaps were found.")
            self._remove_overlay()
            return
        try:
            self._install_overlay()
            self._refresh_overlay_images()
            self.docker.set_status(f"{len(gaps)} gaps detected.")
        except Exception as error:
            self._remove_overlay()
            self.docker.show_error(
                f"{len(gaps)} gaps were detected, but the canvas overlay could not be created: {error}"
            )

    def _remove_overlay(self) -> None:
        if self.overlay:
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None

    def _find_canvas_widget(self):
        window = Krita.instance().activeWindow()
        qwindow = window.qwindow() if window else None
        if qwindow is None:
            return None
        widgets = [widget for widget in qwindow.findChildren(QWidget) if widget.isVisible()]
        preferred = []
        for widget in widgets:
            class_name = widget.metaObject().className().lower()
            if "canvas" in class_name and "controller" not in class_name:
                preferred.append(widget)
        candidates = preferred or widgets
        return max(candidates, key=lambda widget: widget.width() * widget.height(), default=None)

    def _context_is_current(self) -> bool:
        app = Krita.instance()
        window = app.activeWindow()
        return (
            self.document is not None
            and app.activeDocument() == self.document
            and window is not None
            and window.activeView() == self.view
        )

    def _install_overlay(self) -> None:
        self._remove_overlay()
        canvas_widget = self._find_canvas_widget()
        if canvas_widget is None:
            raise RuntimeError("Krita's canvas widget was not found.")
        self.overlay = GapFillOverlay(canvas_widget, self.view)
        settings = self.docker.current_settings()
        self.overlay.set_style(
            settings.highlight_color, settings.marker_radius, settings.sweep_radius
        )
        self.overlay.applyRequested.connect(self.apply_ids)
        self.overlay.previewColorChanged.connect(self._preview_changed)
        self.overlay.interactionCancelled.connect(self._preview_cancelled)

    def _preview_changed(self, _gap_id: str, _color) -> None:
        # The overlay updates the affected gap in place for responsive dragging.
        pass

    def _preview_cancelled(self, _gap_id: str) -> None:
        self.docker.set_regions(self.gaps)

    def _render_preview_rgba(self) -> tuple[np.ndarray, np.ndarray]:
        if self.images is None:
            raise RuntimeError("No layer snapshot is available.")
        height, width = self.images.coloring.shape[:2]
        preview = np.zeros((height, width, 4), dtype=np.uint8)
        composite = self.images.composite.copy()
        for gap in self.gaps:
            color = gap.color
            if color is None:
                continue
            ys, xs = np.divmod(gap.indices, width)
            preview[ys, xs, :3] = color
            preview[ys, xs, 3] = 255
            composite[ys, xs, :3] = color
            composite[ys, xs, 3] = 255
        return preview, composite

    def _refresh_overlay_images(self) -> None:
        if self.overlay is None or self.images is None:
            return
        preview, composite = self._render_preview_rgba()
        self.overlay.set_content(
            self.gaps,
            qimage_from_rgba(preview),
            qimage_from_rgba(composite),
            composite,
        )

    def set_preview_color(self, gap_ids: list[str], color) -> None:
        selected = set(gap_ids)
        for gap in self.gaps:
            if gap.id in selected:
                gap.preview_rgb = color
        self._refresh_overlay_images()
        self.docker.set_regions(self.gaps)

    def apply_ids(self, gap_ids: list[str]) -> None:
        if not gap_ids or self.document is None or self.view is None:
            return
        if not self._context_is_current():
            self.docker.show_error(
                "The active document or view changed. Return to the scanned canvas or rescan before applying."
            )
            return
        selected_ids = set(gap_ids)
        selected = [gap for gap in self.gaps if gap.id in selected_ids]
        try:
            apply_gap_colors(self.document, self.view, self.coloring_node, selected)
        except Exception as error:
            self.docker.show_error(f"Failed to apply gap colors: {error}")
            return
        if self.images is not None:
            width = self.images.width
            for gap in selected:
                color = gap.color
                if color is None:
                    continue
                ys, xs = np.divmod(gap.indices, width)
                self.images.coloring[ys, xs, :3] = color
                self.images.coloring[ys, xs, 3] = 255
                if self.images.composite is not None:
                    self.images.composite[ys, xs, :3] = color
                    self.images.composite[ys, xs, 3] = 255
        self.gaps = [gap for gap in self.gaps if gap.id not in selected_ids]
        self.docker.set_regions(self.gaps)
        if self.gaps:
            self._refresh_overlay_images()
            self.docker.set_status(f"Applied {len(selected)} gaps; {len(self.gaps)} remain.")
        else:
            self._remove_overlay()
            self.docker.set_status(f"Applied all {len(selected)} remaining gaps.")

    def apply_all(self) -> None:
        self.apply_ids([gap.id for gap in self.gaps])
