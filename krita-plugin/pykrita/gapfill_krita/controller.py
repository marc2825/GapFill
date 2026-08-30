from __future__ import annotations

from dataclasses import dataclass, replace
from functools import partial
from typing import Literal, Optional

import numpy as np
from krita import Krita

from .canvas_boundary import (
    require_supported_canvas_state,
    require_supported_widget_state,
    resolve_canvas_widget,
)
from .engine.types import GapRegion, Rgb
from .host_contract import (
    GenerationGate,
    HostSnapshot,
    ScanContext,
    StaleScanError,
    require_fresh,
)
from .krita_adapter import (
    apply_gap_colors,
    canvas_color_bridge,
    observe_context,
    snapshot_host,
    validate_scan_context,
)
from .model import find_model_path
from .native_backend import NativeHostError
from .overlay import GapFillOverlay
from .qt_compat import QImage, QThread, QTimer, QWidget, qimage_from_rgba
from .worker import GapFillWorker


@dataclass(frozen=True)
class _SessionCheckpoint:
    context: ScanContext
    unresolved_ids: tuple[str, ...]
    resolved_ids: frozenset[str]
    invalidated_ids: frozenset[str]
    preview_colors: tuple[tuple[str, Optional[Rgb]], ...]


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
        self._frozen_gaps: tuple[GapRegion, ...] = ()
        self._session_checkpoints: list[_SessionCheckpoint] = []
        self._checkpoint_index: Optional[int] = None
        self._history_action_connections: dict[
            Literal["undo", "redo"], tuple[object, object]
        ] = {}
        self._history_binding_diagnostic = "History actions are not bound."
        self._pending_history_direction: Optional[Literal["undo", "redo"]] = None
        self._host_reconciliation_scheduled = False
        self._host_reconciliation_token = 0

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
        self._clear_session_history()
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
        self._bind_history_actions(app)
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
        self._clear_session_history()
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
        self._clear_session_history()
        self._disconnect_history_actions()

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
        self._start_session_history(gaps)
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
        self._clear_session_history()
        self.docker.set_regions([])
        self.docker.show_error(message)

    def _bind_history_actions(self, app=None) -> None:
        self._disconnect_history_actions()
        app = app or Krita.instance()
        if app is None:
            self._history_binding_diagnostic = "Krita application is unavailable."
            return
        missing = []
        for action_id, direction in (("edit_undo", "undo"), ("edit_redo", "redo")):
            try:
                action = app.action(action_id)
            except Exception:
                action = None
            if action is None:
                missing.append(action_id)
                continue
            callback = partial(
                self._history_action_triggered_from_signal, direction
            )
            action.triggered.connect(callback)
            self._history_action_connections[direction] = (action, callback)
        if missing:
            self._history_binding_diagnostic = (
                "Unavailable current-window history action(s): " + ", ".join(missing)
            )
        else:
            self._history_binding_diagnostic = "Current-window Undo/Redo actions are bound."

    def _disconnect_history_actions(self) -> None:
        for action, callback in self._history_action_connections.values():
            try:
                action.triggered.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        self._history_action_connections.clear()
        self._history_binding_diagnostic = "History actions are not bound."

    def _history_action_triggered_from_signal(
        self, direction: Literal["undo", "redo"], _checked: bool = False
    ) -> None:
        self.history_action_triggered(direction)

    def _clear_session_history(self) -> None:
        self._frozen_gaps = ()
        self._session_checkpoints = []
        self._checkpoint_index = None
        self._pending_history_direction = None
        self._host_reconciliation_scheduled = False
        self._host_reconciliation_token += 1

    def _checkpoint(self, context: ScanContext) -> _SessionCheckpoint:
        return _SessionCheckpoint(
            context=context,
            unresolved_ids=tuple(gap.id for gap in self.gaps),
            resolved_ids=frozenset(self.resolved_ids),
            invalidated_ids=frozenset(self.invalidated_ids),
            preview_colors=tuple((gap.id, gap.preview_rgb) for gap in self._frozen_gaps),
        )

    def _start_session_history(self, gaps: list[GapRegion]) -> None:
        if self.snapshot is None:
            return
        self._frozen_gaps = tuple(gaps)
        self._session_checkpoints = [self._checkpoint(self.snapshot.context)]
        self._checkpoint_index = 0

    def _refresh_current_checkpoint_state(self) -> None:
        if self.snapshot is None or self._checkpoint_index is None:
            return
        self._session_checkpoints[self._checkpoint_index] = self._checkpoint(
            self.snapshot.context
        )

    def _append_session_checkpoint(self) -> None:
        if self.snapshot is None or self._checkpoint_index is None:
            return
        del self._session_checkpoints[self._checkpoint_index + 1 :]
        self._session_checkpoints.append(self._checkpoint(self.snapshot.context))
        self._checkpoint_index += 1

    def history_action_triggered(self, direction: Literal["undo", "redo"]) -> None:
        if not self._session_checkpoints or self.snapshot is None:
            return
        if self._pending_history_direction is not None:
            self._invalidate_session(
                "Overlapping document-history actions made the frozen GapFill session ambiguous."
            )
            return
        self._pending_history_direction = direction
        self._schedule_host_reconciliation()

    def canvas_changed(self) -> None:
        if not self._session_checkpoints or self.snapshot is None:
            return
        generation = self._gate.active
        if generation is None or not self._context_is_current(generation):
            self._invalidate_session(
                "The active document/view changed. The frozen GapFill session was invalidated."
            )
            return
        self._schedule_host_reconciliation()

    def _schedule_host_reconciliation(self) -> None:
        if self._host_reconciliation_scheduled:
            return
        self._host_reconciliation_scheduled = True
        token = self._host_reconciliation_token
        QTimer.singleShot(0, lambda: self._run_scheduled_host_reconciliation(token))

    def _run_scheduled_host_reconciliation(self, token: int) -> None:
        if token != self._host_reconciliation_token:
            return
        self._host_reconciliation_scheduled = False
        direction = self._pending_history_direction
        self._pending_history_direction = None
        if not self._session_checkpoints or self.snapshot is None:
            return
        if direction is None:
            self._verify_current_checkpoint()
        else:
            self._reconcile_history(direction)

    def _observe_current_context(self):
        if self.snapshot is None or self.document is None or self.view is None:
            raise StaleScanError("The frozen GapFill host context is unavailable.")
        self.document.waitForDone()
        return observe_context(self.document, self.view, self.snapshot.context)[0]

    def _verify_current_checkpoint(self) -> None:
        if self._checkpoint_index is None:
            return
        checkpoint = self._session_checkpoints[self._checkpoint_index]
        try:
            require_fresh(checkpoint.context, self._observe_current_context())
        except Exception as error:
            self._invalidate_session(
                "The document changed outside a known GapFill transaction; "
                f"the frozen session was invalidated: {error}"
            )

    def _reconcile_history(self, direction: Literal["undo", "redo"]) -> None:
        if self._checkpoint_index is None:
            return
        offset = -1 if direction == "undo" else 1
        expected_index = self._checkpoint_index + offset
        if not 0 <= expected_index < len(self._session_checkpoints):
            self._invalidate_session(
                f"The {direction.title()} operation was not an adjacent known GapFill transaction."
            )
            return
        checkpoint = self._session_checkpoints[expected_index]
        try:
            require_fresh(checkpoint.context, self._observe_current_context())
            self._restore_session_checkpoint(expected_index)
        except Exception as error:
            self._invalidate_session(
                f"The {direction.title()} result did not match the expected exact GapFill "
                f"checkpoint; the frozen session was invalidated: {error}"
            )

    def _restore_session_checkpoint(self, index: int) -> None:
        if self.snapshot is None:
            raise StaleScanError("The frozen GapFill snapshot is unavailable.")
        checkpoint = self._session_checkpoints[index]
        by_id = {gap.id: gap for gap in self._frozen_gaps}
        if set(by_id) != {gap_id for gap_id, _color in checkpoint.preview_colors}:
            raise StaleScanError("The frozen GapFill candidate identity set changed.")
        current_unresolved = {gap.id: gap.preview_rgb for gap in self.gaps}
        for gap_id, color in checkpoint.preview_colors:
            by_id[gap_id].preview_rgb = color
        try:
            restored = [by_id[gap_id] for gap_id in checkpoint.unresolved_ids]
        except KeyError as error:
            raise StaleScanError("A frozen GapFill candidate disappeared.") from error
        self._restore_unresolved_preview_state(restored, current_unresolved)
        self.snapshot = replace(self.snapshot, context=checkpoint.context)
        self.gaps = restored
        self.resolved_ids = set(checkpoint.resolved_ids)
        self.invalidated_ids = set(checkpoint.invalidated_ids)
        self._checkpoint_index = index
        self.docker.set_regions(self.gaps)
        if self.gaps:
            if self.overlay is None:
                self._install_overlay()
            self._refresh_overlay_images()
        else:
            self._remove_overlay()
        self.docker.set_status(
            f"Restored frozen GapFill checkpoint {index + 1}/"
            f"{len(self._session_checkpoints)} after document history navigation; "
            f"{len(self.gaps)} candidate(s) are unresolved."
        )

    @staticmethod
    def _restore_unresolved_preview_state(
        restored: list[GapRegion], current_unresolved: dict[str, Optional[Rgb]]
    ) -> None:
        for gap in restored:
            if gap.id in current_unresolved:
                gap.preview_rgb = current_unresolved[gap.id]
            else:
                # A candidate resurrected by Undo must return to its immutable
                # frozen prediction, not a correction committed by the undone Apply.
                gap.preview_rgb = None

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
        self._refresh_current_checkpoint_state()

    def _preview_cancelled(self, _gap_id: str) -> None:
        self._refresh_current_checkpoint_state()
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
        self._refresh_current_checkpoint_state()
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
        self._refresh_current_checkpoint_state()
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
        self._append_session_checkpoint()
        self.docker.set_regions(self.gaps)
        if not self.gaps:
            self._remove_overlay()
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
