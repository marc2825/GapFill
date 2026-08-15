from __future__ import annotations

import pytest
from gapfill_krita.canvas_boundary import (
    UnsupportedCanvasState,
    require_supported_canvas_state,
    require_supported_widget_state,
    resolve_canvas_widget,
)


class _Meta:
    def __init__(self, name):
        self._name = name

    def className(self):
        return self._name


class _Widget:
    def __init__(self, class_name, visible=True, ratio=1.0):
        self.class_name = class_name
        self.visible = visible
        self.ratio = ratio

    def isVisible(self):
        return self.visible

    def metaObject(self):
        return _Meta(self.class_name)

    def devicePixelRatioF(self):
        return self.ratio


class _Window:
    def __init__(self, children):
        self.children = children

    def findChildren(self, _kind):
        return self.children


class _Canvas:
    def __init__(self, rotation=0.0, mirror=False):
        self._rotation = rotation
        self._mirror = mirror

    def rotation(self):
        return self._rotation

    def mirror(self):
        return self._mirror


class _View:
    def __init__(self, canvas):
        self._canvas = canvas

    def canvas(self):
        return self._canvas


def test_widget_discovery_has_no_area_fallback() -> None:
    canvas = _Widget("KisOpenGLCanvas2")
    docker = _Widget("GapFillDocker")
    assert resolve_canvas_widget(_Window([canvas, docker]), object) is canvas
    with pytest.raises(RuntimeError, match="uniquely"):
        resolve_canvas_widget(_Window([canvas, _Widget("KisCanvasWidget")]), object)
    with pytest.raises(RuntimeError, match="uniquely"):
        resolve_canvas_widget(_Window([docker]), object)


def test_rotation_and_mirror_fail_closed() -> None:
    require_supported_canvas_state(_View(_Canvas()))
    with pytest.raises(UnsupportedCanvasState, match="rotation"):
        require_supported_canvas_state(_View(_Canvas(rotation=15.0)))
    with pytest.raises(UnsupportedCanvasState, match="mirroring"):
        require_supported_canvas_state(_View(_Canvas(mirror=True)))


def test_hidden_and_unqualified_hidpi_widgets_fail_closed() -> None:
    require_supported_widget_state(_Widget("Canvas", ratio=1.0))
    with pytest.raises(UnsupportedCanvasState, match="no longer visible"):
        require_supported_widget_state(_Widget("Canvas", visible=False))
    with pytest.raises(UnsupportedCanvasState, match="HiDPI"):
        require_supported_widget_state(_Widget("Canvas", ratio=2.0))
