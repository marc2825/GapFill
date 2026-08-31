from __future__ import annotations

from threading import Event

from .engine.detection import detect_gap_regions
from .engine.inference import GapFillPredictor
from .engine.types import ModelBoundaryMode
from .host_contract import HostSnapshot
from .qt_compat import QObject, pyqtSignal, pyqtSlot


class GapFillWorker(QObject):
    progress = pyqtSignal(int, str, int, int)
    completed = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)
    cancelled = pyqtSignal(int)
    finished = pyqtSignal(int)

    def __init__(
        self,
        generation: int,
        snapshot,
        threshold: int,
        model_path,
        allow_greedy: bool,
        model_boundary_mode: ModelBoundaryMode = ModelBoundaryMode.LINE_ONLY,
    ):
        super().__init__()
        self.generation = generation
        self.snapshot = snapshot
        self.threshold = threshold
        self.model_path = model_path
        self.allow_greedy = allow_greedy
        self.model_boundary_mode = model_boundary_mode
        self._cancelled = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @pyqtSlot()
    def run(self) -> None:
        try:
            if self._cancelled.is_set():
                raise InterruptedError("GapFill scan was cancelled.")
            if isinstance(self.snapshot, HostSnapshot):
                images = self.snapshot.images
                detection_source = self.snapshot.detection_geometry
            else:
                # Kept for focused worker tests and external pure tooling. The
                # controller always supplies an immutable HostSnapshot.
                images = self.snapshot
                detection_source = images
            gaps = detect_gap_regions(
                detection_source,
                self.threshold,
                cancel_requested=self._cancelled.is_set,
                progress=lambda done, total: self.progress.emit(
                    self.generation, "Detecting gaps", done, total
                ),
            )
            if self._cancelled.is_set():
                raise InterruptedError("GapFill scan was cancelled.")
            predictor = GapFillPredictor(self.model_path)
            predictor.predict_all(
                images,
                gaps,
                model_boundary_mode=self.model_boundary_mode,
                allow_greedy_on_inference_error=self.allow_greedy,
                cancel_requested=self._cancelled.is_set,
                progress=lambda done, total: self.progress.emit(
                    self.generation, "Predicting colors", done, total
                ),
            )
            # The runtime call itself is synchronous. This explicit boundary
            # prevents a cancel/deactivate immediately before signal delivery
            # from publishing a completed batch.
            if self._cancelled.is_set():
                raise InterruptedError("GapFill scan was cancelled.")
            self.completed.emit(self.generation, gaps)
        except InterruptedError:
            self.cancelled.emit(self.generation)
        except Exception as error:
            self.failed.emit(self.generation, str(error))
        finally:
            self.finished.emit(self.generation)
