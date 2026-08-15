from __future__ import annotations

import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gapfill_krita.engine.types import GapKind, GapRegion  # noqa: E402
from gapfill_krita.overlay import GapFillOverlay  # noqa: E402
from gapfill_krita.qt_compat import qimage_from_rgba  # noqa: E402
from PyQt6 import sip  # noqa: E402
from PyQt6.QtCore import QEvent, QPointF  # noqa: E402
from PyQt6.QtGui import QColor, QTransform  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402


class _Canvas:
    def __init__(self):
        self.angle = 0.0
        self.mirrored = False

    def rotation(self):
        return self.angle

    def mirror(self):
        return self.mirrored


class _View:
    def __init__(self):
        self._canvas = _Canvas()
        self.transform = QTransform()
        self.transform.translate(17.0, 23.0)
        self.transform.scale(2.0, 2.0)

    def canvas(self):
        return self._canvas

    def flakeToImageTransform(self):
        return QTransform()

    def flakeToCanvasTransform(self):
        return self.transform


class _Bridge:
    def source_rgb_to_qcolor(self, color):
        return QColor(*color)


class _CanvasWidget(QWidget):
    pass


def _app():
    return QApplication.instance() or QApplication([])


def _gap():
    return GapRegion(
        "gap-0",
        np.asarray([5], dtype=np.int64),
        (1, 1),
        GapKind.TRANSPARENT,
        predicted_rgb=(7, 29, 211),
        application_indices=np.asarray([5], dtype=np.int64),
    )


def test_pan_zoom_mapping_hit_test_sampling_and_preview_alignment() -> None:
    app = _app()
    canvas = _CanvasWidget()
    canvas.resize(240, 180)
    canvas.show()
    view = _View()
    overlay = GapFillOverlay(canvas, view, _Bridge())
    gap = _gap()
    composite = np.zeros((4, 4, 4), dtype=np.uint8)
    composite[1, 1] = (13, 117, 241, 255)
    preview = qimage_from_rgba(np.zeros_like(composite))
    overlay.set_content([gap], preview, composite)
    app.processEvents()

    expected = view.transform.map(QPointF(1.5, 1.5))
    actual = overlay._screen_center(gap)
    assert (actual.x(), actual.y()) == (expected.x(), expected.y())
    assert overlay._hit_gap(expected) is gap
    assert overlay._sample_color(expected) == (13, 117, 241)
    composite[1, 1, 3] = 128
    assert overlay._sample_color(expected) is None
    composite[1, 1, 3] = 255
    overlay._paint_gap_color(gap, gap.color)
    displayed = overlay.preview_image.pixelColor(1, 1)
    assert (displayed.red(), displayed.green(), displayed.blue()) == (7, 29, 211)

    overlay.close()
    canvas.close()


def test_rotation_change_disables_interaction_and_parent_destruction_owns_overlay() -> None:
    app = _app()
    canvas = _CanvasWidget()
    canvas.resize(120, 90)
    canvas.show()
    view = _View()
    overlay = GapFillOverlay(canvas, view, _Bridge())
    messages = []
    overlay.mappingUnsupported.connect(messages.append)
    view.canvas().angle = 13.0
    overlay._sync_geometry()
    assert messages and "rotation" in messages[-1]
    assert not overlay.isEnabled()

    canvas.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    assert sip.isdeleted(overlay)
