from __future__ import annotations

import math
from typing import Optional

import numpy as np

from .engine.types import GapRegion, Rgb
from .qt_compat import (
    DASH_LINE,
    LEFT_BUTTON,
    ROUND_CAP,
    SOLID_LINE,
    WA_NO_BACKGROUND,
    WA_TRANSLUCENT,
    QColor,
    QImage,
    QPainter,
    QPen,
    QPointF,
    QRectF,
    QTimer,
    QTransform,
    QWidget,
    event_position,
    pyqtSignal,
)


class GapFillOverlay(QWidget):
    """Interactive canvas overlay for previews, markers, correction, and sweep."""

    applyRequested = pyqtSignal(object)
    previewColorChanged = pyqtSignal(str, object)
    interactionCancelled = pyqtSignal(str)

    MARKER_RADIUS = 14.0
    MAGNIFIER_SOURCE_SIZE = 64
    MAGNIFIER_SCALE = 5
    MAGNIFIER_MARGIN = 12

    def __init__(self, canvas_widget, view, parent=None):
        super().__init__(parent or canvas_widget)
        self.canvas_widget = canvas_widget
        self.view = view
        self.gaps: list[GapRegion] = []
        self.preview_image = QImage()
        self.magnifier_image = QImage()
        self.composite_rgba: Optional[np.ndarray] = None
        self.highlight = QColor("#00D9FF")
        self.marker_radius = self.MARKER_RADIUS
        self.sweep_radius = 18.0
        self.hovered_id: Optional[str] = None
        self.correction_id: Optional[str] = None
        self._correction_original_color: Optional[Rgb] = None
        self.sweeping = False
        self.swept_ids: set[str] = set()
        self.drag_position: Optional[QPointF] = None
        self._last_sweep_position: Optional[QPointF] = None
        self._cancel_rect = QRectF()
        self._last_transform = QTransform()

        self.setAttribute(WA_NO_BACKGROUND, True)
        self.setAttribute(WA_TRANSLUCENT, True)
        self.setMouseTracking(True)
        self.setGeometry(canvas_widget.rect())
        self.raise_()
        self.show()
        self._geometry_timer = QTimer(self)
        self._geometry_timer.timeout.connect(self._sync_geometry)
        self._geometry_timer.start(100)

    def closeEvent(self, event) -> None:
        self._geometry_timer.stop()
        super().closeEvent(event)

    def _sync_geometry(self) -> None:
        changed = False
        if self.parent() is self.canvas_widget and self.geometry() != self.canvas_widget.rect():
            self.setGeometry(self.canvas_widget.rect())
            changed = True
        transform = self._image_to_canvas()
        if transform != self._last_transform:
            self._last_transform = transform
            changed = True
        if changed:
            self.update()

    def set_content(
        self,
        gaps: list[GapRegion],
        preview_image: QImage,
        magnifier_image: QImage,
        composite_rgba: np.ndarray,
    ) -> None:
        self.gaps = gaps
        self.preview_image = preview_image
        self.magnifier_image = magnifier_image
        self.composite_rgba = composite_rgba
        self.hovered_id = None
        self.update()

    def set_style(self, color: str, marker_radius: float, sweep_radius: float) -> None:
        self.highlight = QColor(color)
        self.marker_radius = marker_radius
        self.sweep_radius = sweep_radius
        self.update()

    def _image_to_canvas(self) -> QTransform:
        flake_to_image = self.view.flakeToImageTransform()
        image_to_flake, invertible = flake_to_image.inverted()
        if not invertible:
            return QTransform()
        return self.view.flakeToCanvasTransform() * image_to_flake

    def _canvas_to_image(self) -> QTransform:
        transform, invertible = self._image_to_canvas().inverted()
        return transform if invertible else QTransform()

    def _screen_center(self, gap: GapRegion) -> QPointF:
        return self._image_to_canvas().map(QPointF(gap.center[0] + 0.5, gap.center[1] + 0.5))

    def _gap_by_id(self, gap_id: Optional[str]) -> Optional[GapRegion]:
        return next((gap for gap in self.gaps if gap.id == gap_id), None)

    def _hit_gap(self, point: QPointF) -> Optional[GapRegion]:
        nearest = None
        nearest_distance = self.marker_radius
        for gap in self.gaps:
            center = self._screen_center(gap)
            distance = math.hypot(point.x() - center.x(), point.y() - center.y())
            if distance <= nearest_distance:
                nearest = gap
                nearest_distance = distance
        return nearest

    @staticmethod
    def _distance_to_segment(point: QPointF, start: QPointF, end: QPointF) -> float:
        vx, vy = end.x() - start.x(), end.y() - start.y()
        wx, wy = point.x() - start.x(), point.y() - start.y()
        length_squared = vx * vx + vy * vy
        if length_squared == 0:
            return math.hypot(wx, wy)
        ratio = max(0.0, min(1.0, (wx * vx + wy * vy) / length_squared))
        projection_x = start.x() + ratio * vx
        projection_y = start.y() + ratio * vy
        return math.hypot(point.x() - projection_x, point.y() - projection_y)

    def _collect_swept(self, start: QPointF, end: QPointF) -> None:
        for gap in self.gaps:
            if self._distance_to_segment(self._screen_center(gap), start, end) <= self.sweep_radius:
                self.swept_ids.add(gap.id)

    def _sample_color(self, canvas_point: QPointF) -> Optional[Rgb]:
        if self.composite_rgba is None:
            return None
        image_point = self._canvas_to_image().map(canvas_point)
        x, y = int(math.floor(image_point.x())), int(math.floor(image_point.y()))
        height, width = self.composite_rgba.shape[:2]
        if not (0 <= x < width and 0 <= y < height):
            return None
        pixel = self.composite_rgba[y, x]
        if pixel[3] == 0:
            return None
        return (int(pixel[0]), int(pixel[1]), int(pixel[2]))

    def _paint_gap_color(self, gap: GapRegion, color: Optional[Rgb]) -> None:
        """Update only one small gap instead of rebuilding full-document images."""
        if color is None or self.composite_rgba is None:
            return
        width = self.composite_rgba.shape[1]
        ys, xs = np.divmod(gap.indices, width)
        self.composite_rgba[ys, xs, :3] = color
        self.composite_rgba[ys, xs, 3] = 255
        qcolor = QColor(*color, 255)
        for x, y in zip(xs.tolist(), ys.tolist()):
            self.preview_image.setPixelColor(x, y, qcolor)
            self.magnifier_image.setPixelColor(x, y, qcolor)

    def _cancel_correction(self) -> None:
        gap_id = self.correction_id
        if gap_id:
            gap = self._gap_by_id(gap_id)
            if gap:
                gap.preview_rgb = self._correction_original_color
                self._paint_gap_color(gap, gap.color)
            self.correction_id = None
            self._correction_original_color = None
            self.drag_position = None
            self.interactionCancelled.emit(gap_id)
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != LEFT_BUTTON:
            event.ignore()
            return
        point = event_position(event)
        gap = self._hit_gap(point)
        if gap is not None:
            self.correction_id = gap.id
            self._correction_original_color = gap.preview_rgb
            self.drag_position = point
            color = self._sample_color(point)
            if color is not None:
                gap.preview_rgb = color
                self._paint_gap_color(gap, color)
                self.previewColorChanged.emit(gap.id, color)
        else:
            self.sweeping = True
            self.swept_ids.clear()
            self._last_sweep_position = point
            self._collect_swept(point, point)
        event.accept()
        self.update()

    def mouseMoveEvent(self, event) -> None:
        point = event_position(event)
        if self.correction_id:
            # Hovering the magnifier's X is an explicit cancellation gesture.
            if self._cancel_rect.contains(point):
                self._cancel_correction()
                event.accept()
                return
            self.drag_position = point
            color = self._sample_color(point)
            gap = self._gap_by_id(self.correction_id)
            if color is not None and gap is not None:
                gap.preview_rgb = color
                self._paint_gap_color(gap, color)
                self.previewColorChanged.emit(gap.id, color)
        elif self.sweeping and self._last_sweep_position is not None:
            self._collect_swept(self._last_sweep_position, point)
            self._last_sweep_position = point
        else:
            gap = self._hit_gap(point)
            self.hovered_id = gap.id if gap else None
        event.accept()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != LEFT_BUTTON:
            event.ignore()
            return
        if self.correction_id:
            gap_id = self.correction_id
            self.correction_id = None
            self._correction_original_color = None
            self.drag_position = None
            self.applyRequested.emit([gap_id])
        elif self.sweeping:
            selected = list(self.swept_ids)
            self.sweeping = False
            self.swept_ids.clear()
            self._last_sweep_position = None
            if selected:
                self.applyRequested.emit(selected)
        event.accept()
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
            if hasattr(QPainter, "RenderHint")
            else QPainter.Antialiasing
        )
        transform = self._image_to_canvas()
        if not self.preview_image.isNull():
            painter.save()
            painter.setTransform(transform)
            for gap in self.gaps:
                bounds = gap.metadata.get("bounds")
                if bounds is None:
                    width = self.preview_image.width()
                    ys, xs = np.divmod(gap.indices, width)
                    bounds = (
                        int(xs.min()),
                        int(ys.min()),
                        int(xs.max()) + 1,
                        int(ys.max()) + 1,
                    )
                    gap.metadata["bounds"] = bounds
                x0, y0, x1, y1 = bounds
                rectangle = QRectF(x0, y0, x1 - x0, y1 - y0)
                painter.drawImage(rectangle, self.preview_image, rectangle)
            painter.restore()

        marker_pen = QPen(self.highlight, 2.0, SOLID_LINE, ROUND_CAP)
        selected_pen = QPen(QColor("#FFD600"), 4.0, SOLID_LINE, ROUND_CAP)
        painter.setBrush(QColor(0, 0, 0, 0))
        for gap in self.gaps:
            center = self._screen_center(gap)
            painter.setPen(selected_pen if gap.id in self.swept_ids else marker_pen)
            painter.drawEllipse(center, self.marker_radius, self.marker_radius)

        active_gap = self._gap_by_id(self.correction_id or self.hovered_id)
        if active_gap is not None:
            self._paint_magnifier(painter, active_gap)
        if self.correction_id and self.drag_position is not None:
            painter.setPen(QPen(self.highlight, 2.0, DASH_LINE))
            painter.drawLine(self.drag_position, self._screen_center(active_gap))
        painter.end()

    def _paint_magnifier(self, painter: QPainter, gap: GapRegion) -> None:
        source_size = self.MAGNIFIER_SOURCE_SIZE
        display_size = source_size * self.MAGNIFIER_SCALE
        source = QRectF(
            gap.center[0] - source_size / 2,
            gap.center[1] - source_size / 2,
            source_size,
            source_size,
        )
        center = self._screen_center(gap)
        left = min(
            max(0.0, center.x() + self.marker_radius + 8),
            max(0.0, self.width() - display_size),
        )
        top = min(
            max(0.0, center.y() - display_size / 2),
            max(0.0, self.height() - display_size),
        )
        target = QRectF(left, top, display_size, display_size)
        painter.setPen(QPen(QColor("#202020"), 2.0))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRect(target.adjusted(-2, -2, 2, 2))
        painter.drawImage(target, self.magnifier_image, source)
        marker_center = target.center()
        painter.setPen(QPen(QColor(255, 255, 255, 210), 2.0))
        painter.setBrush(QColor(0, 0, 0, 70))
        painter.drawEllipse(marker_center, 8.0, 8.0)

        self._cancel_rect = QRectF(target.left() + 6, target.bottom() - 26, 20, 20)
        painter.setPen(QPen(QColor("#FFFFFF"), 3.0, SOLID_LINE, ROUND_CAP))
        painter.setBrush(QColor(0, 0, 0, 150))
        painter.drawEllipse(self._cancel_rect)
        painter.drawLine(
            self._cancel_rect.topLeft() + QPointF(5, 5),
            self._cancel_rect.bottomRight() - QPointF(5, 5),
        )
        painter.drawLine(
            self._cancel_rect.bottomLeft() + QPointF(5, -5),
            self._cancel_rect.topRight() + QPointF(-5, 5),
        )
