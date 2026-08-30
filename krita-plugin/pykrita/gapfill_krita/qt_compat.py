"""Small compatibility surface for Krita 5 (PyQt5) and Krita 6 (PyQt6)."""

try:
    from PyQt6.QtCore import (
        QByteArray,
        QEvent,
        QObject,
        QPointF,
        QRect,
        QRectF,
        QSettings,
        Qt,
        QThread,
        QTimer,
        QUuid,
        pyqtSignal,
        pyqtSlot,
        qVersion,
    )
    from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF, QTransform
    from PyQt6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QColorDialog,
        QComboBox,
        QDockWidget,
        QDoubleSpinBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    QT6 = True
    LEFT_BUTTON = Qt.MouseButton.LeftButton
    NO_BUTTON = Qt.MouseButton.NoButton
    DASH_LINE = Qt.PenStyle.DashLine
    SOLID_LINE = Qt.PenStyle.SolidLine
    ROUND_CAP = Qt.PenCapStyle.RoundCap
    WA_TRANSPARENT_MOUSE = Qt.WidgetAttribute.WA_TransparentForMouseEvents
    WA_NO_BACKGROUND = Qt.WidgetAttribute.WA_NoSystemBackground
    WA_TRANSLUCENT = Qt.WidgetAttribute.WA_TranslucentBackground
    ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
    KEEP_ASPECT = Qt.AspectRatioMode.KeepAspectRatio
    FAST_TRANSFORM = Qt.TransformationMode.FastTransformation
    IMAGE_RGBA8888 = QImage.Format.Format_RGBA8888
    IMAGE_GRAYSCALE8 = QImage.Format.Format_Grayscale8
    USER_ROLE = Qt.ItemDataRole.UserRole
    DOCK_RIGHT = Qt.DockWidgetArea.RightDockWidgetArea
    MOUSE_BUTTON_PRESS = QEvent.Type.MouseButtonPress
    MOUSE_MOVE = QEvent.Type.MouseMove
    MOUSE_BUTTON_RELEASE = QEvent.Type.MouseButtonRelease
    ENTER = QEvent.Type.Enter
    LEAVE = QEvent.Type.Leave
except ImportError:
    from PyQt5.QtCore import (
        QByteArray,
        QEvent,
        QObject,
        QPointF,
        QRect,
        QRectF,
        QSettings,
        Qt,
        QThread,
        QTimer,
        QUuid,
        pyqtSignal,
        pyqtSlot,
        qVersion,
    )
    from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPolygonF, QTransform
    from PyQt5.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QColorDialog,
        QComboBox,
        QDockWidget,
        QDoubleSpinBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )

    QT6 = False
    LEFT_BUTTON = Qt.LeftButton
    NO_BUTTON = Qt.NoButton
    DASH_LINE = Qt.DashLine
    SOLID_LINE = Qt.SolidLine
    ROUND_CAP = Qt.RoundCap
    WA_TRANSPARENT_MOUSE = Qt.WA_TransparentForMouseEvents
    WA_NO_BACKGROUND = Qt.WA_NoSystemBackground
    WA_TRANSLUCENT = Qt.WA_TranslucentBackground
    ALIGN_CENTER = Qt.AlignCenter
    KEEP_ASPECT = Qt.KeepAspectRatio
    FAST_TRANSFORM = Qt.FastTransformation
    IMAGE_RGBA8888 = QImage.Format_RGBA8888
    IMAGE_GRAYSCALE8 = QImage.Format_Grayscale8
    USER_ROLE = Qt.UserRole
    DOCK_RIGHT = Qt.RightDockWidgetArea
    MOUSE_BUTTON_PRESS = QEvent.MouseButtonPress
    MOUSE_MOVE = QEvent.MouseMove
    MOUSE_BUTTON_RELEASE = QEvent.MouseButtonRelease
    ENTER = QEvent.Enter
    LEAVE = QEvent.Leave


def event_position(event):
    return event.position() if QT6 else event.localPos()


def global_position(event):
    return event.globalPosition().toPoint() if QT6 else event.globalPos()


def qimage_from_rgba(image):
    height, width = image.shape[:2]
    return QImage(image.data, width, height, width * 4, IMAGE_RGBA8888).copy()
