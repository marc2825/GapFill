from __future__ import annotations

import os
from time import monotonic

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gapfill_krita.engine.types import LayerImages  # noqa: E402
from gapfill_krita.host_contract import GenerationGate  # noqa: E402
from gapfill_krita.worker import GapFillWorker  # noqa: E402
from PyQt6.QtCore import QCoreApplication, QThread  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QCoreApplication.instance() or QCoreApplication([])


def _images() -> LayerImages:
    rgba = np.zeros((3, 3, 4), dtype=np.uint8)
    return LayerImages(rgba, rgba.copy(), rgba.copy())


def _run_thread(app, worker: GapFillWorker):
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    events = []
    worker.completed.connect(lambda generation, gaps: events.append(("completed", generation)))
    worker.cancelled.connect(lambda generation: events.append(("cancelled", generation)))
    worker.failed.connect(lambda generation, message: events.append(("failed", generation)))
    thread.start()
    deadline = monotonic() + 3
    while thread.isRunning() and monotonic() < deadline:
        app.processEvents()
        thread.wait(5)
    app.processEvents()
    assert thread.wait(1000)
    return events


def test_cancel_before_model_initialization_never_completes(app, monkeypatch) -> None:
    import gapfill_krita.worker as worker_module

    model_loads = []

    class Predictor:
        def __init__(self, _path):
            model_loads.append(True)

    monkeypatch.setattr(worker_module, "GapFillPredictor", Predictor)
    worker = GapFillWorker(31, _images(), 10, "model.onnx", False)
    worker.cancel()
    events = _run_thread(app, worker)
    assert events == [("cancelled", 31)]
    assert model_loads == []


def test_cancel_immediately_after_prediction_suppresses_completed(app, monkeypatch) -> None:
    import gapfill_krita.worker as worker_module

    worker = GapFillWorker(32, _images(), 10, "model.onnx", False)

    monkeypatch.setattr(worker_module, "detect_gap_regions", lambda *args, **kwargs: [object()])

    class Predictor:
        def __init__(self, _path):
            pass

        def predict_all(self, images, gaps, **kwargs):
            worker.cancel()

    monkeypatch.setattr(worker_module, "GapFillPredictor", Predictor)
    events = _run_thread(app, worker)
    assert events == [("cancelled", 32)]


def test_generation_is_attached_to_all_terminal_signals(app, monkeypatch) -> None:
    import gapfill_krita.worker as worker_module

    monkeypatch.setattr(worker_module, "detect_gap_regions", lambda *args, **kwargs: [])

    class Predictor:
        def __init__(self, _path):
            pass

        def predict_all(self, images, gaps, **kwargs):
            return gaps

    monkeypatch.setattr(worker_module, "GapFillPredictor", Predictor)
    events = _run_thread(app, GapFillWorker(77, _images(), 10, "model.onnx", False))
    assert events == [("completed", 77)]


def test_queued_terminal_delivery_is_gated_after_lifecycle_changes(app) -> None:
    from PyQt6.QtCore import QTimer

    delivered = []
    context = {"present": True}

    def queue(gate, generation, label):
        QTimer.singleShot(
            0,
            lambda: delivered.append(label)
            if gate.accepts(generation) and context["present"]
            else None,
        )

    gate = GenerationGate()
    scan_a = gate.start()
    queue(gate, scan_a, "deactivated-a")
    gate.retire(scan_a)  # Deactivate just before completed delivery.
    app.processEvents()

    scan_a = gate.start()
    queue(gate, scan_a, "superseded-a")
    scan_b = gate.start()  # B starts before A's queued callback is delivered.
    app.processEvents()
    assert gate.accepts(scan_b)

    queue(gate, scan_b, "missing-view")
    context["present"] = False
    app.processEvents()

    context["present"] = True
    queue(gate, scan_b, "shutdown")
    gate.close()
    app.processEvents()
    assert delivered == []
