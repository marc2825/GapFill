from __future__ import annotations

from dataclasses import replace
from typing import Optional

import numpy as np
from krita import Krita

from .canvas_boundary import (
    require_supported_canvas_state,
    require_supported_widget_state,
    resolve_canvas_widget,
)
from .engine.types import GapRegion
from .host_contract import GenerationGate, HostSnapshot, StaleScanError
from .krita_adapter import (
    apply_gap_colors,
    canvas_color_bridge,
    snapshot_host,
    validate_scan_context,
)
from .model import find_model_path
from .native_backend import NativeHostError
from .overlay import GapFillOverlay
from .qt_compat import QImage, QThread, QWidget, qimage_from_rgba
from .worker import GapFillWorker


class GapFillController:
    def __init__(self, docker):
        self.docker = docker
        self.document = None
        self.view = None
        self.snapshot: Optional[HostSnapshot] = None
        self.gaps: list[GapRegion] = []
        self.overlay: Optional[GapFillOverlay] = None
        self._gate = GenerationGate()
        self._runs: dict[int, tuple[QThread, GapFillWorker]] = {}
        self._shutting_down = False
        self._published_generation: Optional[int] = None
        self.resolved_ids: set[str] = set()
        self.invalidated_ids: set[str] = set()

    @property
    def busy(self) -> bool:
        return self._gate.active in self._runs

    def scan(
        self, coloring_node, line_node, guides_node, threshold: int, allow_greedy: bool
    ) -> None:
        if self._shutting_down:
            return
        self._retire_workers()
        generation = self._gate.start()
        self._published_generation = None
        self.resolved_ids.clear()
        self.invalidated_ids.clear()
        app = Krita.instance()
        document = app.activeDocument()
        window = app.activeWindow()
        view = window.activeView() if window else None
        if document is None or view is None:
            self._gate.retire(generation)
            self.docker.show_error("Open a document before activating GapFill.")
            return
        if coloring_node is None or line_node is None:
            self._gate.retire(generation)
            self.docker.show_error("Select both a Coloring layer and a Line Art layer.")
            return
        try:
            self.docker.set_busy(True, "Reading Krita layers…")
            snapshot = snapshot_host(
                document, view, coloring_node, line_node, guides_node, generation
            )
        except Exception as error:
            self._gate.retire(generation)
            self.docker.set_busy(False)
            self.docker.show_error(str(error))
            return

        self.document = document
        self.view = view
        self.snapshot = snapshot
        thread = QThread()
        worker = GapFillWorker(
            generation, snapshot, threshold, find_model_path(), allow_greedy
        )
        self._runs[generation] = (thread, worker)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._scan_progress)
        worker.completed.connect(self._scan_completed)
        worker.failed.connect(self._scan_failed)
        worker.cancelled.connect(self._scan_cancelled)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._thread_finished(generation))
        thread.start()

    def _retire_workers(self) -> None:
        active = self._gate.active
        if active is not None:
            self._gate.retire(active)
        for _thread, worker in self._runs.values():
            try:
                worker.cancel()
            except RuntimeError:
                pass

    def cancel(self) -> None:
        if self._gate.active is None:
            return
        self._retire_workers()
        self.docker.set_busy(False)
        self.docker.set_status("Cancelled. A running ONNX call may finish before cleanup.")

    def deactivate(self) -> None:
        self._retire_workers()
        self._remove_overlay()
        self.snapshot = None
        self.gaps = []
        self._published_generation = None
        self.resolved_ids.clear()
        self.invalidated_ids.clear()
        self.docker.set_regions([])
        self.docker.set_busy(False)
        self.docker.set_status("GapFill is inactive.")

    def shutdown(self) -> None:
        self._shutting_down = True
        self._gate.close()
        for _thread, worker in self._runs.values():
            try:
                worker.cancel()
            except RuntimeError:
                pass
        self._remove_overlay()
        self.snapshot = None
        self.gaps = []
        self._published_generation = None
        self.resolved_ids.clear()
        self.invalidated_ids.clear()

    def _thread_finished(self, generation: int) -> None:
        run = self._runs.pop(generation, None)
        if run is not None:
            thread, _worker = run
            thread.deleteLater()
        if self._gate.accepts(generation):
            self.docker.set_busy(False)

    def _scan_progress(self, generation: int, stage: str, done: int, total: int) -> None:
        if (
            self._gate.accepts(generation)
            and self._published_generation != generation
            and self._context_is_current(generation)
        ):
            self.docker.update_progress(stage, done, total)

    def _scan_failed(self, generation: int, message: str) -> None:
        if not self._gate.accepts(generation) or self._published_generation == generation:
            return
        self.gaps = []
        self.docker.show_error(
            "GapFill could not load or run its color-prediction model.\n" + message
        )

    def _scan_cancelled(self, generation: int) -> None:
        if self._gate.accepts(generation) and self._published_generation != generation:
            self.docker.set_status("Cancelled.")

    def _scan_completed(self, generation: int, gaps: list[GapRegion]) -> None:
        if not self._gate.accepts(generation) or self._published_generation == generation:
            return
        if not self._context_is_current(generation):
            self._gate.retire(generation)
            self.gaps = []
            self.docker.set_regions([])
            self.docker.show_error(
                "The scanned document/view disappeared or changed. Scan the intended canvas again."
            )
            return
        try:
            validate_scan_context(self.document, self.view, self.snapshot.context)
        except Exception as error:
            self._gate.retire(generation)
            self.gaps = []
            self.docker.set_regions([])
            self.docker.show_error(f"The scan became stale before preview: {error}")
            return
        self._published_generation = generation
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
                f"{len(gaps)} gaps were detected, but interactive preview is unavailable: {error}"
            )

    def _remove_overlay(self) -> None:
        if self.overlay is not None:
            self.overlay.close()
            self.overlay.deleteLater()
            self.overlay = None

    def _invalidate_session(self, message: str) -> None:
        generation = self._gate.active
        if generation is not None:
            self._gate.retire(generation)
        self._remove_overlay()
        self.snapshot = None
        self.gaps = []
        self._published_generation = None
        self.resolved_ids.clear()
        self.invalidated_ids.clear()
        self.docker.set_regions([])
        self.docker.show_error(message)

    def _context_is_current(self, generation: int) -> bool:
        app = Krita.instance()
        window = app.activeWindow()
        return (
            self._gate.accepts(generation)
            and self.snapshot is not None
            and self.snapshot.context.generation == generation
            and self.document is not None
            and app.activeDocument() == self.document
            and window is not None
            and window.activeView() == self.view
            and self.view.document() == self.document
        )

    def _install_overlay(self) -> None:
        self._remove_overlay()
        require_supported_canvas_state(self.view)
        window = Krita.instance().activeWindow()
        qwindow = window.qwindow() if window else None
        canvas_widget = resolve_canvas_widget(qwindow, QWidget)
        require_supported_widget_state(canvas_widget)
        bridge = canvas_color_bridge(self.view, self.snapshot.context)
        self.overlay = GapFillOverlay(canvas_widget, self.view, bridge)
        settings = self.docker.current_settings()
        self.overlay.set_style(
            settings.highlight_color, settings.marker_radius, settings.sweep_radius
        )
        self.overlay.applyRequested.connect(self.apply_ids)
        self.overlay.previewColorChanged.connect(self._preview_changed)
        self.overlay.interactionCancelled.connect(self._preview_cancelled)
        self.overlay.mappingUnsupported.connect(self._overlay_unsupported)

    def _overlay_unsupported(self, message: str) -> None:
        self._remove_overlay()
        self.docker.show_error(message)

    def _preview_changed(self, _gap_id: str, _color) -> None:
        pass

    def _preview_cancelled(self, _gap_id: str) -> None:
        self.docker.set_regions(self.gaps)

    def _render_preview_image(self) -> QImage:
        if self.snapshot is None:
            raise RuntimeError("No host snapshot is available.")
        height, width = self.snapshot.images.coloring.shape[:2]
        image = qimage_from_rgba(np.zeros((height, width, 4), dtype=np.uint8))
        bridge = canvas_color_bridge(self.view, self.snapshot.context)
        for gap in self.gaps:
            if gap.color is None:
                continue
            ys, xs = np.divmod(gap.indices, width)
            qcolor = bridge.source_rgb_to_qcolor(gap.color)
            for px, py in zip(xs.tolist(), ys.tolist()):
                image.setPixelColor(px, py, qcolor)
        return image

    def _refresh_overlay_images(self) -> None:
        if self.overlay is None or self.snapshot is None:
            return
        self.overlay.set_content(
            self.gaps,
            self._render_preview_image(),
            self.snapshot.images.composite,
        )

    def set_preview_color(self, gap_ids: list[str], color) -> None:
        if self.snapshot is None:
            return
        bridge = canvas_color_bridge(self.view, self.snapshot.context)
        source_color = bridge.qcolor_to_source_rgb(self._qcolor(color))
        selected = set(gap_ids)
        for gap in self.gaps:
            if gap.id in selected:
                gap.preview_rgb = source_color
        self._refresh_overlay_images()
        self.docker.set_regions(self.gaps)

    @staticmethod
    def _qcolor(color):
        from .qt_compat import QColor

        return QColor(*color)

    def apply_ids(self, gap_ids: list[str]) -> None:
        generation = self._gate.active
        if not gap_ids or generation is None or self.snapshot is None:
            return
        if not self._context_is_current(generation):
            self._invalidate_session(
                "The scanned document/view changed. The frozen GapFill session was invalidated."
            )
            return
        selected_ids = set(gap_ids)
        already_resolved = selected_ids & self.resolved_ids
        if already_resolved:
            self.docker.show_error(
                "A resolved GapFill candidate cannot be applied twice: "
                + ", ".join(sorted(already_resolved))
            )
            return
        selected = [gap for gap in self.gaps if gap.id in selected_ids]
        if not selected:
            return
        selected_actual_ids = {gap.id for gap in selected}
        applied_support = {
            int(index)
            for gap in selected
            for index in np.asarray(gap.target_indices, dtype=np.int64).tolist()
        }
        conflicting_ids = {
            gap.id
            for gap in self.gaps
            if gap.id not in selected_actual_ids
            and any(int(index) in applied_support for index in gap.indices.tolist())
        }
        try:
            result = apply_gap_colors(
                self.document, self.view, self.snapshot.context, selected
            )
        except (StaleScanError, NativeHostError) as error:
            self._invalidate_session(
                "The frozen GapFill session could not be preserved and was invalidated: "
                f"{error}"
            )
            return
        except Exception as error:
            self.docker.show_error(f"Failed to apply gap colors: {error}")
            return
        self.snapshot = replace(self.snapshot, context=result.context)
        self.resolved_ids.update(selected_actual_ids)
        self.invalidated_ids.update(conflicting_ids)
        removed_ids = selected_actual_ids | conflicting_ids
        self.gaps = [gap for gap in self.gaps if gap.id not in removed_ids]
        self.docker.set_regions(self.gaps)
        if not self.gaps:
            self._gate.retire(generation)
            self._remove_overlay()
            self.snapshot = None
            self._published_generation = None
            self.docker.set_status(
                f"Applied and verified {result.changed_pixels} pixels in one native transaction. "
                "All candidates in this frozen analysis session are resolved."
            )
            return

        self._refresh_overlay_images()
        conflict_note = (
            f" {len(conflicting_ids)} overlapping candidate(s) were invalidated without rescanning."
            if conflicting_ids
            else ""
        )
        self.docker.set_status(
            f"Applied and verified {result.changed_pixels} pixels in one native transaction. "
            f"{len(self.gaps)} frozen candidate(s) remain active.{conflict_note}"
        )

    def apply_all(self) -> None:
        self.apply_ids([gap.id for gap in self.gaps])
