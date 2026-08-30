from __future__ import annotations

import os

import numpy as np
import pytest

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
    def __init__(self, scale=2.0, translation=(17.0, 23.0)):
        self._canvas = _Canvas()
        self.flake_to_image = QTransform.fromScale(1.0 / scale, 1.0 / scale)
        self.flake_to_canvas = QTransform.fromTranslate(*translation)

    def canvas(self):
        return self._canvas

    def flakeToImageTransform(self):
        return self.flake_to_image

    def flakeToCanvasTransform(self):
        return self.flake_to_canvas


class _Bridge:
    def source_rgb_to_qcolor(self, color):
        return QColor(*color)

    def source_rgba_to_qcolor(self, color):
        return QColor(*color)


class _CanvasWidget(QWidget):
    pass


_APPLICATION = None


def _app():
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def _gap(gap_id="gap-0", center=(1, 1), index=5):
    return GapRegion(
        gap_id,
        np.asarray([index], dtype=np.int64),
        center,
        GapKind.TRANSPARENT,
        predicted_rgb=(7, 29, 211),
        application_indices=np.asarray([index], dtype=np.int64),
    )


def _overlay(scale, translation, *, size=(900, 700)):
    canvas = _CanvasWidget()
    canvas.resize(*size)
    canvas.show()
    overlay = GapFillOverlay(canvas, _View(scale, translation), _Bridge())
    return canvas, overlay


def _coordinates(point):
    return point.x(), point.y()


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

    expected = QPointF(20.0, 26.0)
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


@pytest.mark.parametrize(
    ("scale", "translation", "expected"),
    [
        (1.0, (0.0, 0.0), (25.5, 25.5)),
        (1.375, (0.0, 0.0), (35.0625, 35.0625)),
        (1.0, (-49.0, -45.0), (-23.5, -19.5)),
        (1.375, (417.0, 421.0), (452.0625, 456.0625)),
        (20.0, (-49.0, -45.0), (461.0, 465.0)),
    ],
)
def test_image_canvas_transform_order_and_reverse_mapping(
    scale, translation, expected
) -> None:
    _app()
    canvas, overlay = _overlay(scale, translation)

    forward = overlay._image_to_canvas().map(QPointF(25.5, 25.5))
    reverse = overlay._canvas_to_image().map(QPointF(*expected))
    assert _coordinates(forward) == pytest.approx(expected, abs=1e-9)
    assert _coordinates(reverse) == pytest.approx((25.5, 25.5), abs=1e-9)

    overlay.close()
    canvas.close()


@pytest.mark.parametrize(
    ("scale", "translation", "expected"),
    [
        (1.375, (417.0, 421.0), (452.0625, 456.0625)),
        (20.0, (-49.0, -45.0), (461.0, 465.0)),
    ],
)
def test_v6_exact_marker_hit_sweep_and_sampling(scale, translation, expected) -> None:
    _app()
    canvas, overlay = _overlay(scale, translation)
    gap = _gap("gap-1", (25, 25), 25 * 64 + 25)
    composite = np.zeros((64, 64, 4), dtype=np.uint8)
    composite[25, 25] = (13, 117, 241, 255)
    overlay.set_content([gap], qimage_from_rgba(np.zeros_like(composite)), composite)

    independent_point = QPointF(*expected)
    assert _coordinates(overlay._screen_center(gap)) == pytest.approx(expected, abs=1e-9)
    assert overlay._hit_gap(independent_point) is gap
    assert overlay._hit_gap(
        QPointF(expected[0] + overlay.marker_radius + 1.0, expected[1])
    ) is None

    overlay._collect_swept(independent_point, independent_point)
    assert overlay.swept_ids == {"gap-1"}
    assert overlay._sample_color(independent_point) == (13, 117, 241)

    overlay.close()
    canvas.close()


@pytest.mark.parametrize(
    ("scale", "translation", "expected"),
    [
        (1.375, (417.0, 421.0), (452.0625, 456.0625)),
        (20.0, (-49.0, -45.0), (461.0, 465.0)),
    ],
)
def test_v6_exact_preview_marker_and_magnifier_alignment(
    monkeypatch, scale, translation, expected
) -> None:
    from gapfill_krita import overlay as overlay_module

    class _RenderHint:
        Antialiasing = object()

    class _RecordingPainter:
        RenderHint = _RenderHint
        Antialiasing = _RenderHint.Antialiasing
        last = None

        def __init__(self, _device):
            type(self).last = self
            self.transforms = []
            self.images = []
            self.ellipses = []
            self.rectangles = []
            self.lines = []

        def setRenderHint(self, *_args):
            pass

        def save(self):
            pass

        def setTransform(self, transform):
            self.transforms.append(transform)

        def drawImage(self, *args):
            self.images.append(args)

        def restore(self):
            pass

        def setPen(self, _pen):
            pass

        def setBrush(self, _brush):
            pass

        def drawEllipse(self, *args):
            self.ellipses.append(args)

        def drawRect(self, rectangle):
            self.rectangles.append(rectangle)

        def drawLine(self, *args):
            self.lines.append(args)

        def end(self):
            pass

    _app()
    canvas, overlay = _overlay(scale, translation)
    gap = _gap("gap-1", (25, 25), 25 * 64 + 25)
    composite = np.zeros((64, 64, 4), dtype=np.uint8)
    overlay.set_content([gap], qimage_from_rgba(np.zeros_like(composite)), composite)
    monkeypatch.setattr(overlay_module, "QPainter", _RecordingPainter)

    overlay.paintEvent(None)
    painter = _RecordingPainter.last
    assert painter is not None
    assert len(painter.transforms) == 1
    preview_point = painter.transforms[0].map(QPointF(25.5, 25.5))
    assert _coordinates(preview_point) == pytest.approx(expected, abs=1e-9)
    marker_center = painter.ellipses[0][0]
    assert _coordinates(marker_center) == pytest.approx(expected, abs=1e-9)
    assert painter.images

    overlay._paint_magnifier(painter, gap)
    magnifier_target = painter.rectangles[-1].adjusted(2, 2, -2, -2)
    expected_left = min(
        max(0.0, expected[0] + overlay.marker_radius + 8),
        max(0.0, overlay.width() - 320),
    )
    expected_top = min(
        max(0.0, expected[1] - 160), max(0.0, overlay.height() - 320)
    )
    assert (magnifier_target.left(), magnifier_target.top()) == pytest.approx(
        (expected_left, expected_top), abs=1e-9
    )

    overlay.close()
    canvas.close()


def test_correction_samples_magnifier_source_instead_of_obscured_canvas() -> None:
    _app()
    canvas, overlay = _overlay(1.0, (0.0, 0.0), size=(420, 380))
    gap = _gap("gap-magnifier", (200, 350), 350 * 500 + 200)
    composite = np.zeros((500, 500, 4), dtype=np.uint8)
    overlay.set_content([gap], qimage_from_rgba(np.zeros_like(composite)), composite)
    overlay.correction_id = gap.id

    geometry = overlay._magnifier_geometry(gap)
    assert (geometry.target.left(), geometry.target.top()) == pytest.approx((100.0, 60.0))
    assert (geometry.source_left, geometry.source_top) == (168, 318)

    represented = (178, 328)
    obscured = (152, 112)
    composite[represented[1], represented[0]] = (255, 0, 0, 255)
    composite[obscured[1], obscured[0]] = (0, 0, 255, 255)
    point = QPointF(geometry.target.left() + 10 * 5 + 2.5, geometry.target.top() + 10 * 5 + 2.5)
    assert overlay._sample_color(point) == (0, 0, 255)
    assert overlay._sample_correction_color(point) == (255, 0, 0)
    assert overlay._sample_correction_color(point) != (0, 0, 255)

    class _MoveEvent:
        def __init__(self, position):
            self._position = position
            self.accepted = False

        def position(self):
            return self._position

        def accept(self):
            self.accepted = True

    changes = []
    overlay.previewColorChanged.connect(lambda gap_id, color: changes.append((gap_id, color)))
    event = _MoveEvent(point)
    overlay.mouseMoveEvent(event)
    assert event.accepted
    assert gap.preview_rgb == (255, 0, 0)
    assert changes[-1] == (gap.id, (255, 0, 0))

    composite[318, 168] = (1, 2, 3, 255)
    first = QPointF(geometry.target.left() + 0.1, geometry.target.top() + 0.1)
    assert overlay._sample_correction_color(first) == (1, 2, 3)

    composite[381, 231] = (4, 5, 6, 255)
    last = QPointF(geometry.target.right() - 0.1, geometry.target.bottom() - 0.1)
    assert overlay._sample_correction_color(last) == (4, 5, 6)

    outside = QPointF(geometry.target.left() - 1.0, geometry.target.top() + 52.5)
    composite[112, 99] = (7, 8, 9, 255)
    assert overlay._sample_correction_color(outside) == (7, 8, 9)

    overlay.correction_id = None
    assert overlay._sample_correction_color(point) == (0, 0, 255)

    overlay.close()
    canvas.close()


def test_connector_uses_cursor_and_final_clamped_magnifier_center(monkeypatch) -> None:
    from gapfill_krita import overlay as overlay_module

    class _RenderHint:
        Antialiasing = object()

    class _RecordingPainter:
        RenderHint = _RenderHint
        Antialiasing = _RenderHint.Antialiasing
        last = None

        def __init__(self, _device):
            type(self).last = self
            self.lines = []

        def setRenderHint(self, *_args):
            pass

        def save(self):
            pass

        def setTransform(self, _transform):
            pass

        def drawImage(self, *_args):
            pass

        def restore(self):
            pass

        def setPen(self, _pen):
            pass

        def setBrush(self, _brush):
            pass

        def drawEllipse(self, *_args):
            pass

        def drawRect(self, _rectangle):
            pass

        def drawLine(self, *args):
            self.lines.append(args)

        def end(self):
            pass

    _app()
    canvas, overlay = _overlay(1.0, (0.0, 0.0), size=(420, 380))
    gap = _gap("gap-connector", (200, 350), 350 * 500 + 200)
    composite = np.zeros((500, 500, 4), dtype=np.uint8)
    overlay.set_content([gap], qimage_from_rgba(np.zeros_like(composite)), composite)
    overlay.correction_id = gap.id
    overlay.drag_position = QPointF(17.0, 29.0)
    monkeypatch.setattr(overlay_module, "QPainter", _RecordingPainter)

    requested_left = overlay._screen_center(gap).x() + overlay.marker_radius + 8
    requested_top = overlay._screen_center(gap).y() - 160
    final_geometry = overlay._magnifier_geometry(gap)
    assert (requested_left, requested_top) != (
        final_geometry.target.left(),
        final_geometry.target.top(),
    )

    overlay.paintEvent(None)
    painter = _RecordingPainter.last
    connector_start, connector_end = painter.lines[-1]
    assert _coordinates(connector_start) == (17.0, 29.0)
    assert _coordinates(connector_end) == _coordinates(final_geometry.target.center())
    assert _coordinates(connector_end) != _coordinates(overlay._screen_center(gap))
    assert _coordinates(connector_end) != (
        requested_left + 160,
        requested_top + 160,
    )
    assert overlay._magnifier_gap_id == gap.id
    assert overlay._magnifier_rect == final_geometry.target

    overlay._cancel_correction()
    assert overlay.correction_id is None
    assert overlay.drag_position is None
    assert overlay._magnifier_rect.isNull()
    assert overlay._magnifier_gap_id is None

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
