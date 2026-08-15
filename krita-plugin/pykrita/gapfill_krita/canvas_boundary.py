"""Fail-closed boundary around Krita's undocumented canvas QWidget."""

from __future__ import annotations


class UnsupportedCanvasState(RuntimeError):
    pass


def _class_name(widget) -> str:
    return str(widget.metaObject().className()).lower()


def resolve_canvas_widget(qwindow, widget_type):
    if qwindow is None:
        raise RuntimeError("Krita's active window has no QWidget.")
    candidates = []
    for widget in qwindow.findChildren(widget_type):
        if not widget.isVisible():
            continue
        name = _class_name(widget)
        if "canvas" in name and "controller" not in name and "docker" not in name:
            candidates.append(widget)
    if len(candidates) != 1:
        raise RuntimeError(
            "Krita's active canvas QWidget could not be uniquely identified; "
            "interactive overlays are disabled for this window/view layout."
        )
    return candidates[0]


def require_supported_canvas_state(view) -> None:
    canvas = view.canvas() if view is not None else None
    if canvas is None:
        raise UnsupportedCanvasState("The active view has no LibKis Canvas.")
    rotation = float(canvas.rotation())
    if abs(rotation) > 1e-6:
        raise UnsupportedCanvasState(
            "Interactive GapFill overlays are disabled while canvas rotation is active."
        )
    if bool(canvas.mirror()):
        raise UnsupportedCanvasState(
            "Interactive GapFill overlays are disabled while canvas mirroring is active."
        )


def require_supported_widget_state(widget) -> None:
    if widget is None or not widget.isVisible():
        raise UnsupportedCanvasState("The bound Krita canvas widget is no longer visible.")
    ratio_getter = getattr(widget, "devicePixelRatioF", None)
    ratio = float(ratio_getter()) if callable(ratio_getter) else 1.0
    if abs(ratio - 1.0) > 1e-6:
        raise UnsupportedCanvasState(
            "Interactive GapFill overlays are disabled on unqualified HiDPI canvas widgets."
        )
