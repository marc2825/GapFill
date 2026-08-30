from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .canvas_boundary import require_supported_canvas_state, require_supported_widget_state
from .engine.types import GapRegion, Rgb
from .qt_compat import (
    DASH_LINE,
    ENTER,
    LEAVE,
    LEFT_BUTTON,
    MOUSE_BUTTON_PRESS,
    MOUSE_BUTTON_RELEASE,
    MOUSE_MOVE,
    ROUND_CAP,
    SOLID_LINE,
    WA_NO_BACKGROUND,
    WA_TRANSLUCENT,
    WA_TRANSPARENT_MOUSE,
    QApplication,
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
    global_position,
    pyqtSignal,
    qimage_from_rgba,
)


@dataclass(frozen=True)
class _MagnifierGeometry:
    target: QRectF
    source_left: int
    source_top: int
    source_size: int


class GapFillOverlay(QWidget):
    """Interactive canvas overlay for previews, markers, correction, and sweep."""

    applyRequested = pyqtSignal(object)
    previewColorChanged = pyqtSignal(str, object)
    interactionCancelled = pyqtSignal(str)
    mappingUnsupported = pyqtSignal(str)

    MARKER_RADIUS = 14.0
    MAGNIFIER_SOURCE_SIZE = 64
    MAGNIFIER_SCALE = 5
    MAGNIFIER_MARGIN = 12
    SWEEP_TRAIL_COLOR = (226, 242, 170, 112)
    SWEEP_TRAIL_WIDTH = 7.0
    SWEEP_TRAIL_MIN_DISTANCE = 2.0
    MAX_SWEEP_TRAIL_POINTS = 2048

    def __init__(self, canvas_widget, view, color_bridge, parent=None):
        super().__init__(parent or canvas_widget)
        self.canvas_widget = canvas_widget
        self.view = view
        self.color_bridge = color_bridge
        self.gaps: list[GapRegion] = []
        self.preview_image = QImage()
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
        self._sweep_trail: list[QPointF] = []
        self._cancel_rect = QRectF()
        self._magnifier_rect = QRectF()
        self._magnifier_gap_id: Optional[str] = None
        self._last_transform = QTransform()
        self._mapping_valid = True
        self._canvas_mouse_tracking = canvas_widget.hasMouseTracking()
        self._event_filter_installed = False

        self.setAttribute(WA_NO_BACKGROUND, True)
        self.setAttribute(WA_TRANSLUCENT, True)
        # This full-canvas widget paints the preview but must not become the
        # canvas's pointer target. Observe the real canvas passively and only
        # consume an explicit GapFill press/drag/release interaction.
        self.setAttribute(WA_TRANSPARENT_MOUSE, True)
        canvas_widget.setMouseTracking(True)
        application = QApplication.instance()
        if application is None:
            raise RuntimeError("GapFill requires an active Qt application.")
        self._event_filter_target = application
        application.installEventFilter(self)
        self._event_filter_installed = True
        self.setGeometry(canvas_widget.rect())
        self.raise_()
        self.show()
        self._geometry_timer = QTimer(self)
        self._geometry_timer.timeout.connect(self._sync_geometry)
        self._geometry_timer.start(100)

    def closeEvent(self, event) -> None:
        self._geometry_timer.stop()
        if self._event_filter_installed:
            self._event_filter_target.removeEventFilter(self)
            self._event_filter_installed = False
        if not self._canvas_mouse_tracking:
            self.canvas_widget.setMouseTracking(False)
        self._clear_pointer_state()
        super().closeEvent(event)

    def eventFilter(self, watched, event) -> bool:
        if not self._mapping_valid:
            return super().eventFilter(watched, event)
        event_type = event.type()
        canvas_target = self._is_canvas_event_target(watched)
        active_gesture = bool(self.correction_id or self.sweeping)
        if not canvas_target and not (
            active_gesture and event_type in (MOUSE_MOVE, MOUSE_BUTTON_RELEASE)
        ):
            return super().eventFilter(watched, event)
        if event_type == MOUSE_BUTTON_PRESS:
            point = self._map_event_point(watched, event)
            handled = self._handle_pointer_press(point, event.button())
            if handled:
                event.accept()
            return handled
        if event_type == MOUSE_MOVE:
            point = self._map_event_point(watched, event)
            self._handle_pointer_move(point, event.buttons())
            # The initiating press was claimed, so Krita's tool has no active
            # stroke. Let moves through so its visible canvas cursor continues
            # to track the physical pointer during GapFill drags.
            return False
        if event_type == MOUSE_BUTTON_RELEASE:
            point = self._map_event_point(watched, event)
            handled = self._handle_pointer_release(point, event.button())
            if handled:
                event.accept()
            return handled
        if event_type == LEAVE and watched is self.canvas_widget:
            self._handle_pointer_leave()
            return False
        if event_type == ENTER:
            return False
        return super().eventFilter(watched, event)

    def _is_canvas_event_target(self, watched) -> bool:
        return isinstance(watched, QWidget) and (
            watched is self.canvas_widget or self.canvas_widget.isAncestorOf(watched)
        )

    def _map_event_point(self, watched, event) -> QPointF:
        if not isinstance(watched, QWidget):
            return QPointF(self.mapFromGlobal(global_position(event)))
        if not self._is_canvas_event_target(watched):
            return QPointF(self.mapFromGlobal(global_position(event)))
        watched_point = event_position(event).toPoint()
        canvas_point = self.canvas_widget.mapFrom(watched, watched_point)
        return QPointF(self.mapFrom(self.canvas_widget, canvas_point))

    def _sync_geometry(self) -> None:
        try:
            require_supported_canvas_state(self.view)
            require_supported_widget_state(self.canvas_widget)
            transform = self._image_to_canvas()
        except Exception as error:
            if self._mapping_valid:
                self._mapping_valid = False
                self.setEnabled(False)
                self.hide()
                self.mappingUnsupported.emit(str(error))
            return
        changed = False
        if self.parent() is self.canvas_widget and self.geometry() != self.canvas_widget.rect():
            self.setGeometry(self.canvas_widget.rect())
            changed = True
        if transform != self._last_transform:
            self._last_transform = transform
            changed = True
        if changed:
            self.update()

    def set_content(
        self,
        gaps: list[GapRegion],
        preview_image: QImage,
        composite_rgba: np.ndarray,
    ) -> None:
        self.gaps = gaps
        self.preview_image = preview_image
        self.composite_rgba = composite_rgba
        self.hovered_id = None
        if self.correction_id and self._gap_by_id(self.correction_id) is None:
            self.correction_id = None
            self._correction_original_color = None
            self.drag_position = None
        self._clear_magnifier_geometry()
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
            raise RuntimeError("Krita returned a non-invertible image transform.")
        return image_to_flake * self.view.flakeToCanvasTransform()

    def _canvas_to_image(self) -> QTransform:
        transform, invertible = self._image_to_canvas().inverted()
        if not invertible:
            raise RuntimeError("Krita returned a non-invertible canvas transform.")
        return transform

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

    def _append_sweep_trail(self, point: QPointF) -> None:
        sample = QPointF(point)
        if self._sweep_trail:
            previous = self._sweep_trail[-1]
            if (
                math.hypot(sample.x() - previous.x(), sample.y() - previous.y())
                < self.SWEEP_TRAIL_MIN_DISTANCE
            ):
                return
        if len(self._sweep_trail) >= self.MAX_SWEEP_TRAIL_POINTS:
            self._sweep_trail = self._sweep_trail[::2]
        self._sweep_trail.append(sample)

    def _sample_source_pixel(self, x: int, y: int) -> Optional[Rgb]:
        if self.composite_rgba is None:
            return None
        height, width = self.composite_rgba.shape[:2]
        if not (0 <= x < width and 0 <= y < height):
            return None
        pixel = self.composite_rgba[y, x]
        # Sampling a semi-transparent source as an opaque fill is not a
        # perceptually stable operation without a defined backdrop.
        if pixel[3] != 255:
            return None
        return (int(pixel[0]), int(pixel[1]), int(pixel[2]))

    def _sample_color(self, canvas_point: QPointF) -> Optional[Rgb]:
        image_point = self._canvas_to_image().map(canvas_point)
        return self._sample_source_pixel(
            int(math.floor(image_point.x())), int(math.floor(image_point.y()))
        )

    @staticmethod
    def _inside_image_rect(point: QPointF, rectangle: QRectF) -> bool:
        return (
            rectangle.left() <= point.x() < rectangle.right()
            and rectangle.top() <= point.y() < rectangle.bottom()
        )

    def _magnifier_geometry(self, gap: GapRegion) -> _MagnifierGeometry:
        source_size = self.MAGNIFIER_SOURCE_SIZE
        display_size = source_size * self.MAGNIFIER_SCALE
        source_left = int(gap.center[0] - source_size // 2)
        source_top = int(gap.center[1] - source_size // 2)
        center = self._screen_center(gap)
        left = min(
            max(0.0, center.x() + self.marker_radius + 8),
            max(0.0, self.width() - display_size),
        )
        top = min(
            max(0.0, center.y() - display_size / 2),
            max(0.0, self.height() - display_size),
        )
        return _MagnifierGeometry(
            QRectF(left, top, display_size, display_size),
            source_left,
            source_top,
            source_size,
        )

    def _sample_magnifier(
        self, point: QPointF, gap: GapRegion
    ) -> tuple[bool, Optional[Rgb]]:
        geometry = self._magnifier_geometry(gap)
        target = geometry.target
        if not self._inside_image_rect(point, target):
            return False, None
        local_x = int(
            math.floor((point.x() - target.left()) * geometry.source_size / target.width())
        )
        local_y = int(
            math.floor((point.y() - target.top()) * geometry.source_size / target.height())
        )
        image_x = geometry.source_left + min(geometry.source_size - 1, local_x)
        image_y = geometry.source_top + min(geometry.source_size - 1, local_y)
        return True, self._sample_source_pixel(image_x, image_y)

    def _sample_correction_color(self, point: QPointF) -> Optional[Rgb]:
        gap = self._gap_by_id(self.correction_id)
        if gap is not None:
            hit, color = self._sample_magnifier(point, gap)
            if hit:
                return color
        return self._sample_color(point)

    def _clear_magnifier_geometry(self) -> None:
        self._magnifier_rect = QRectF()
        self._magnifier_gap_id = None
        self._cancel_rect = QRectF()

    def _paint_gap_color(self, gap: GapRegion, color: Optional[Rgb]) -> None:
        """Update only one small gap instead of rebuilding full-document images."""
        if color is None or self.composite_rgba is None:
            return
        width = self.composite_rgba.shape[1]
        ys, xs = np.divmod(gap.indices, width)
        qcolor = self.color_bridge.source_rgb_to_qcolor(color)
        for x, y in zip(xs.tolist(), ys.tolist()):
            self.preview_image.setPixelColor(x, y, qcolor)

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
            self._clear_magnifier_geometry()
            self.interactionCancelled.emit(gap_id)
            self.update()

    def _handle_pointer_press(self, point: QPointF, button) -> bool:
        if button != LEFT_BUTTON:
            return False
        gap = self._hit_gap(point)
        if gap is not None:
            self.correction_id = gap.id
            self._correction_original_color = gap.preview_rgb
            self.drag_position = point
            color = self._sample_correction_color(point)
            if color is not None:
                gap.preview_rgb = color
                self._paint_gap_color(gap, color)
                self.previewColorChanged.emit(gap.id, color)
        else:
            self.sweeping = True
            self.swept_ids.clear()
            self._last_sweep_position = point
            self._sweep_trail = [QPointF(point)]
            self._collect_swept(point, point)
        self.update()
        return True

    def mousePressEvent(self, event) -> None:
        if self._handle_pointer_press(event_position(event), event.button()):
            event.accept()
        else:
            event.ignore()

    def _handle_pointer_move(self, point: QPointF, _buttons) -> None:
        if self.correction_id:
            # Hovering the magnifier's X is an explicit cancellation gesture.
            if self._cancel_rect.contains(point):
                self._cancel_correction()
                return
            self.drag_position = point
            color = self._sample_correction_color(point)
            gap = self._gap_by_id(self.correction_id)
            if color is not None and gap is not None:
                gap.preview_rgb = color
                self._paint_gap_color(gap, color)
                self.previewColorChanged.emit(gap.id, color)
        elif self.sweeping and self._last_sweep_position is not None:
            self._collect_swept(self._last_sweep_position, point)
            self._last_sweep_position = point
            self._append_sweep_trail(point)
        else:
            gap = self._hit_gap(point)
            self.hovered_id = gap.id if gap else None
            if gap is None:
                self._clear_magnifier_geometry()
        self.update()

    def mouseMoveEvent(self, event) -> None:
        self._handle_pointer_move(event_position(event), event.buttons())
        event.ignore()

    def _handle_pointer_release(self, _point: QPointF, button) -> bool:
        if button != LEFT_BUTTON:
            return False
        handled = bool(self.correction_id or self.sweeping)
        if self.correction_id:
            gap_id = self.correction_id
            self.correction_id = None
            self._correction_original_color = None
            self.drag_position = None
            self._clear_magnifier_geometry()
            self.applyRequested.emit([gap_id])
        elif self.sweeping:
            selected = list(self.swept_ids)
            self.sweeping = False
            self.swept_ids.clear()
            self._last_sweep_position = None
            self._sweep_trail.clear()
            if selected:
                self.applyRequested.emit(selected)
        self.update()
        return handled

    def mouseReleaseEvent(self, event) -> None:
        if self._handle_pointer_release(event_position(event), event.button()):
            event.accept()
        else:
            event.ignore()

    def _handle_pointer_leave(self) -> None:
        if self.correction_id or self.sweeping:
            return
        self.hovered_id = None
        self._clear_magnifier_geometry()
        self.update()

    def _clear_pointer_state(self) -> None:
        self.hovered_id = None
        self.correction_id = None
        self._correction_original_color = None
        self.sweeping = False
        self.swept_ids.clear()
        self.drag_position = None
        self._last_sweep_position = None
        self._sweep_trail.clear()
        self._clear_magnifier_geometry()

    def paintEvent(self, _event) -> None:
        try:
            require_supported_canvas_state(self.view)
            require_supported_widget_state(self.canvas_widget)
        except Exception as error:
            self.mappingUnsupported.emit(str(error))
            return
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
        if len(self._sweep_trail) >= 2:
            painter.setPen(
                QPen(
                    QColor(*self.SWEEP_TRAIL_COLOR),
                    self.SWEEP_TRAIL_WIDTH,
                    SOLID_LINE,
                    ROUND_CAP,
                )
            )
            for start, end in zip(self._sweep_trail, self._sweep_trail[1:]):
                painter.drawLine(start, end)
        for gap in self.gaps:
            center = self._screen_center(gap)
            painter.setPen(selected_pen if gap.id in self.swept_ids else marker_pen)
            painter.drawEllipse(center, self.marker_radius, self.marker_radius)

        active_gap = self._gap_by_id(self.correction_id or self.hovered_id)
        magnifier_geometry = None
        if active_gap is not None:
            magnifier_geometry = self._paint_magnifier(painter, active_gap)
        else:
            self._clear_magnifier_geometry()
        if (
            self.correction_id
            and self.drag_position is not None
            and magnifier_geometry is not None
        ):
            painter.setPen(QPen(self.highlight, 2.0, DASH_LINE))
            painter.drawLine(self.drag_position, magnifier_geometry.target.center())
        painter.end()

    def _paint_magnifier(
        self, painter: QPainter, gap: GapRegion
    ) -> Optional[_MagnifierGeometry]:
        if self.composite_rgba is None:
            self._clear_magnifier_geometry()
            return None
        geometry = self._magnifier_geometry(gap)
        source_size = geometry.source_size
        source_left = geometry.source_left
        source_top = geometry.source_top
        magnifier = qimage_from_rgba(
            np.zeros((source_size, source_size, 4), dtype=np.uint8)
        )
        height, width = self.composite_rgba.shape[:2]
        for local_y in range(source_size):
            image_y = source_top + local_y
            if not 0 <= image_y < height:
                continue
            for local_x in range(source_size):
                image_x = source_left + local_x
                if not 0 <= image_x < width:
                    continue
                pixel = self.composite_rgba[image_y, image_x]
                if pixel[3] != 0:
                    magnifier.setPixelColor(
                        local_x,
                        local_y,
                        self.color_bridge.source_rgba_to_qcolor(pixel),
                    )
        for item in self.gaps:
            if item.color is None:
                continue
            ys, xs = np.divmod(item.indices, width)
            qcolor = self.color_bridge.source_rgb_to_qcolor(item.color)
            for image_x, image_y in zip(xs.tolist(), ys.tolist()):
                local_x, local_y = image_x - source_left, image_y - source_top
                if 0 <= local_x < source_size and 0 <= local_y < source_size:
                    magnifier.setPixelColor(local_x, local_y, qcolor)
        target = geometry.target
        self._magnifier_rect = QRectF(target)
        self._magnifier_gap_id = gap.id
        painter.setPen(QPen(QColor("#202020"), 2.0))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRect(target.adjusted(-2, -2, 2, 2))
        painter.drawImage(target, magnifier, QRectF(0, 0, source_size, source_size))
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
        return geometry
