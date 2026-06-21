from __future__ import annotations

from threading import Event

from .engine.detection import detect_gap_regions
from .engine.inference import GapFillPredictor
from .qt_compat import QObject, pyqtSignal, pyqtSlot


class GapFillWorker(QObject):
    progress = pyqtSignal(str, int, int)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, images, threshold: int, model_path, allow_greedy: bool):
        super().__init__()
        self.images = images
        self.threshold = threshold
        self.model_path = model_path
        self.allow_greedy = allow_greedy
        self._cancelled = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @pyqtSlot()
    def run(self) -> None:
        try:
            gaps = detect_gap_regions(
                self.images,
                self.threshold,
                cancel_requested=self._cancelled.is_set,
                progress=lambda done, total: self.progress.emit("Detecting gaps", done, total),
            )
            predictor = GapFillPredictor(self.model_path)
            predictor.predict_all(
                self.images,
                gaps,
                allow_greedy_on_inference_error=self.allow_greedy,
                cancel_requested=self._cancelled.is_set,
                progress=lambda done, total: self.progress.emit("Predicting colors", done, total),
            )
            self.completed.emit(gaps)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()
