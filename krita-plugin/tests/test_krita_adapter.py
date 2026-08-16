from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest
from gapfill_krita import krita_adapter as adapter
from gapfill_krita.engine.types import GapKind, GapRegion


class _Uuid:
    def __init__(self, value):
        self.value = str(value)

    def toString(self):
        return self.value


class _Point:
    def __init__(self, x=0, y=0):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y


class _Rect(_Point):
    def __init__(self, x, y, width, height):
        super().__init__(x, y)
        self._width = width
        self._height = height

    def width(self):
        return self._width

    def height(self):
        return self._height


def _bgra(image):
    return np.ascontiguousarray(image[..., [2, 1, 0, 3]]).tobytes()


class _Node:
    def __init__(self, identifier, image, kind="paintlayer", parent=None):
        self.identifier = identifier
        self.image = image.copy()
        self.kind = kind
        self.parent = parent
        self.children = []
        self.pos = _Point()
        self.is_locked = False
        self.alpha_locked = False
        self.is_animated = False
        self.is_visible = True
        self.node_opacity = 255
        self.blend = "normal"
        self.inherit = False
        self.style = ""
        self.profile = "sRGB-elle-V2-srgbtrc.icc"
        if parent is not None:
            parent.children.append(self)

    def uniqueId(self):
        return _Uuid(self.identifier)

    def type(self):
        return self.kind

    def name(self):
        return self.identifier

    def parentNode(self):
        return self.parent

    def childNodes(self):
        return self.children

    def position(self):
        return self.pos

    def bounds(self):
        height, width = self.image.shape[:2]
        return _Rect(self.pos.x(), self.pos.y(), width, height)

    def colorModel(self):
        return "RGBA"

    def colorDepth(self):
        return "U8"

    def colorProfile(self):
        return self.profile

    def locked(self):
        return self.is_locked

    def alphaLocked(self):
        return self.alpha_locked

    def animated(self):
        return self.is_animated

    def visible(self):
        return self.is_visible

    def opacity(self):
        return self.node_opacity

    def blendingMode(self):
        return self.blend

    def inheritAlpha(self):
        return self.inherit

    def layerStyleToAsl(self):
        return self.style

    def pixelData(self, _x, _y, _width, _height):
        return _bgra(self.image)

    def projectionPixelData(self, _x, _y, _width, _height):
        return _bgra(self.image)

    def setPixelData(self, value, _x, _y, width, height):
        bgra = np.frombuffer(bytes(value), dtype=np.uint8).reshape((height, width, 4))
        self.image = bgra[..., [2, 1, 0, 3]].copy()
        return True


class _Selection:
    def __init__(self, data=None):
        self.data = None if data is None else np.asarray(data, dtype=np.uint8).copy()

    def setPixelData(self, value, _x, _y, width, height):
        self.data = np.frombuffer(bytes(value), dtype=np.uint8).reshape((height, width)).copy()

    def pixelData(self, _x, _y, _width, _height):
        return self.data.tobytes()

    def duplicate(self):
        return _Selection(self.data)


class _Managed:
    PROFILE_ROUNDTRIP = {
        "ACEScg-elle-V4-g10.icc": {
            (13, 117, 241): (56, 122, 236),
            (201, 37, 83): (166, 33, 82),
        }
    }

    def __init__(self, model="RGBA", depth="U8", profile="profile"):
        self.space = (model, depth, profile)
        self.values = [0.0, 0.0, 0.0, 1.0]
        self.set_history = []

    def components(self):
        return list(self.values)

    def componentsOrdered(self):
        return [self.values[2], self.values[1], self.values[0], self.values[3]]

    def setComponents(self, values):
        self.values = list(values)
        self.set_history.append(list(values))

    def colorForCanvas(self, _canvas):
        ordered = tuple(round(value * 255) for value in self.componentsOrdered()[:3])
        converted = self.PROFILE_ROUNDTRIP.get(self.space[2], {}).get(ordered, ordered)
        return adapter.QColor(*converted)

    @classmethod
    def fromQColor(cls, color, _canvas):
        result = cls()
        result.values = [color.blueF(), color.greenF(), color.redF(), color.alphaF()]
        return result

    def setColorSpace(self, model, depth, profile):
        self.space = (model, depth, profile)
        return True


class _Document:
    def __init__(self, root, target, line, selection=None):
        self.root = root
        self.target = target
        self.line = line
        self._selection = selection
        self._active = target
        self.selection_history = []
        self.pending_actions = []
        self.wait_count = 0

    def width(self):
        return self.target.image.shape[1]

    def height(self):
        return self.target.image.shape[0]

    def xOffset(self):
        return 0

    def yOffset(self):
        return 0

    def rootNode(self):
        return self.root

    def activeNode(self):
        return self._active

    def setActiveNode(self, node):
        self._active = node

    def selection(self):
        return self._selection

    def setSelection(self, selection):
        self._selection = selection
        self.selection_history.append(selection)

    def nodeByUniqueID(self, identifier):
        value = identifier.toString()
        return next(
            (node for node in (self.root, self.target, self.line) if node.identifier == value),
            None,
        )

    def waitForDone(self):
        self.wait_count += 1
        while self.pending_actions:
            self.pending_actions.pop(0)()

    def refreshProjection(self):
        pass


class _View:
    def __init__(self, document):
        self._document = document
        self._foreground = _Managed()
        self._eraser = True
        self._alpha = True
        self._blend = "multiply"
        self._opacity = 0.25
        self._flow = 0.5

    def document(self):
        return self._document

    def canvas(self):
        return object()

    def foregroundColor(self):
        return self._foreground

    def setForeGroundColor(self, value):
        self._foreground = value

    def eraserMode(self):
        return self._eraser

    def setEraserMode(self, value):
        self._eraser = value

    def globalAlphaLock(self):
        return self._alpha

    def setGlobalAlphaLock(self, value):
        self._alpha = value

    def currentBlendingMode(self):
        return self._blend

    def setCurrentBlendingMode(self, value):
        self._blend = value

    def paintingOpacity(self):
        return self._opacity

    def setPaintingOpacity(self, value):
        self._opacity = value

    def paintingFlow(self):
        return self._flow

    def setPaintingFlow(self, value):
        self._flow = value


class _Action:
    def __init__(
        self, document, view, *, no_op=False, enabled=True, raise_after=False
    ):
        self.document = document
        self.view = view
        self.no_op = no_op
        self.enabled = enabled
        self.raise_after = raise_after

    def isEnabled(self):
        return self.enabled

    def trigger(self):
        if self.no_op:
            return
        assert not self.view.eraserMode()
        assert not self.view.globalAlphaLock()
        assert self.view.currentBlendingMode() == "normal"
        assert self.view.paintingOpacity() == 1.0
        assert self.view.paintingFlow() == 1.0
        def apply():
            mask = self.document.selection().data > 0
            values = self.view.foregroundColor().componentsOrdered()
            rgb = [round(value * 255) for value in values[:3]]
            self.document.activeNode().image[mask, :3] = rgb
            self.document.activeNode().image[mask, 3] = 255
            if self.raise_after:
                raise RuntimeError("controlled action failure")

        self.document.pending_actions.append(apply)


@dataclass
class _App:
    action_value: object

    def action(self, _name):
        return self.action_value


class _Krita:
    app = None

    @classmethod
    def instance(cls):
        return cls.app


@pytest.fixture
def host(monkeypatch):
    rgba = np.zeros((3, 3, 4), dtype=np.uint8)
    root = _Node("{00000000-0000-0000-0000-000000000001}", rgba, "grouplayer")
    target = _Node("{00000000-0000-0000-0000-000000000002}", rgba, parent=root)
    line = _Node("{00000000-0000-0000-0000-000000000003}", rgba, parent=root)
    document = _Document(root, target, line)
    view = _View(document)
    monkeypatch.setattr(adapter, "Selection", _Selection)
    monkeypatch.setattr(adapter, "ManagedColor", _Managed)
    monkeypatch.setattr(adapter, "Krita", _Krita)
    return document, view, target, line


def _gap(identifier, index, color):
    return GapRegion(
        identifier,
        np.asarray([index], dtype=np.int64),
        (index % 3, index // 3),
        GapKind.TRANSPARENT,
        predicted_rgb=color,
        application_indices=np.asarray([index], dtype=np.int64),
    )


def test_apply_normalizes_and_exactly_restores_user_state(host) -> None:
    document, view, target, line = host
    original_foreground = view.foregroundColor()
    snapshot = adapter.snapshot_host(document, view, target, line, None, 4)
    _Krita.app = _App(_Action(document, view))

    result = adapter.apply_gap_colors(
        document,
        view,
        snapshot.context,
        [_gap("gap-0", 4, (17, 83, 201)), _gap("gap-1", 5, (9, 6, 3))],
    )

    assert result.changed_pixels == 2
    assert result.atomic_undo is False
    assert target.image.reshape((-1, 4))[4].tolist() == [17, 83, 201, 255]
    assert target.image.reshape((-1, 4))[5].tolist() == [9, 6, 3, 255]
    assert document.selection() is None
    assert document.selection_history[-1] is None
    assert document.activeNode() is target
    assert view.foregroundColor() is original_foreground
    assert (view.eraserMode(), view.globalAlphaLock()) == (True, True)
    assert (view.currentBlendingMode(), view.paintingOpacity(), view.paintingFlow()) == (
        "multiply",
        0.25,
        0.5,
    )


def test_soft_selection_is_restored_exactly(host) -> None:
    document, view, target, line = host
    soft = np.arange(9, dtype=np.uint8).reshape((3, 3))
    document._selection = _Selection(soft)
    snapshot = adapter.snapshot_host(document, view, target, line, None, 5)
    _Krita.app = _App(_Action(document, view))
    adapter.apply_gap_colors(document, view, snapshot.context, [_gap("gap-0", 4, (1, 2, 3))])
    assert np.array_equal(document.selection().data, soft)


def test_failed_postcondition_recovers_pixels_and_state(host) -> None:
    document, view, target, line = host
    before = target.image.copy()
    snapshot = adapter.snapshot_host(document, view, target, line, None, 6)
    _Krita.app = _App(_Action(document, view, no_op=True))
    with pytest.raises(RuntimeError, match="did not produce"):
        adapter.apply_gap_colors(
            document, view, snapshot.context, [_gap("gap-0", 4, (101, 77, 33))]
        )
    assert np.array_equal(target.image, before)
    assert document.selection() is None
    assert (view.eraserMode(), view.globalAlphaLock()) == (True, True)


def test_action_exception_after_partial_mutation_recovers_pixels(host) -> None:
    document, view, target, line = host
    before = target.image.copy()
    snapshot = adapter.snapshot_host(document, view, target, line, None, 61)
    _Krita.app = _App(_Action(document, view, raise_after=True))
    with pytest.raises(RuntimeError, match="controlled action failure"):
        adapter.apply_gap_colors(
            document, view, snapshot.context, [_gap("gap-0", 4, (101, 77, 33))]
        )
    assert np.array_equal(target.image, before)
    assert document.selection() is None


def test_missing_or_disabled_action_fails_before_user_state_mutation(host) -> None:
    document, view, target, line = host
    snapshot = adapter.snapshot_host(document, view, target, line, None, 7)
    before = target.image.copy()
    for action in (None, _Action(document, view, enabled=False)):
        _Krita.app = _App(action)
        with pytest.raises(RuntimeError, match="unavailable or disabled"):
            adapter.apply_gap_colors(
                document, view, snapshot.context, [_gap("gap-0", 4, (101, 77, 33))]
            )
        assert np.array_equal(target.image, before)
        assert document.selection() is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda node: setattr(node, "pos", _Point(1, 0)), "Moved/offset"),
        (lambda node: node.children.append(_Node("mask", node.image, "transparencymask")), "masks"),
        (lambda node: setattr(node, "node_opacity", 128), "fully opaque"),
        (lambda node: setattr(node, "blend", "multiply"), "Normal blending"),
        (lambda node: setattr(node, "is_animated", True), "Animated"),
    ],
)
def test_unsupported_target_configurations_fail_before_snapshot(host, change, message) -> None:
    document, view, target, line = host
    change(target)
    with pytest.raises(RuntimeError, match=message):
        adapter.snapshot_host(document, view, target, line, None, 8)


@pytest.mark.parametrize("rgb", [(13, 117, 241), (201, 37, 83)])
def test_canvas_bridge_preserves_asymmetric_components(host, rgb) -> None:
    document, view, target, line = host
    snapshot = adapter.snapshot_host(document, view, target, line, None, 9)
    bridge = adapter.canvas_color_bridge(view, snapshot.context)
    managed = bridge._managed(bridge.source_space, rgb)
    assert [round(value * 255) for value in managed.set_history[-1]] == [
        rgb[2],
        rgb[1],
        rgb[0],
        255,
    ]
    assert [round(value * 255) for value in managed.components()] != [*rgb, 255]
    assert [round(value * 255) for value in managed.componentsOrdered()] == [*rgb, 255]
    qcolor = bridge.source_rgb_to_qcolor(rgb)
    assert (qcolor.red(), qcolor.green(), qcolor.blue()) == rgb
    assert bridge.qcolor_to_source_rgb(qcolor) == rgb


@pytest.mark.parametrize(
    ("rgb", "expected"),
    [
        ((13, 117, 241), (56, 122, 236)),
        ((201, 37, 83), (166, 33, 82)),
    ],
)
def test_canvas_bridge_extracts_ordered_alternate_profile_rgb(host, rgb, expected) -> None:
    document, view, target, line = host
    alternate = "ACEScg-elle-V4-g10.icc"
    for node in (document.root, target, line):
        node.profile = alternate
    snapshot = adapter.snapshot_host(document, view, target, line, None, 10)
    bridge = adapter.canvas_color_bridge(view, snapshot.context)

    managed, target_rgb = bridge.source_rgb_to_target(rgb)

    assert target_rgb == expected
    assert [round(value * 255) for value in managed.components()[:3]] == [
        expected[2],
        expected[1],
        expected[0],
    ]
    assert [round(value * 255) for value in managed.componentsOrdered()[:3]] == list(
        expected
    )


def test_canvas_bridge_rejects_unsupported_managed_color_space(host) -> None:
    with pytest.raises(RuntimeError, match="requires RGBA/U8"):
        adapter.CanvasColorBridge._managed(("CMYKA", "U8", "profile"), (1, 2, 3))


def test_apply_waits_for_native_action_without_event_processing(host) -> None:
    document, view, target, line = host
    snapshot = adapter.snapshot_host(document, view, target, line, None, 11)
    _Krita.app = _App(_Action(document, view))

    result = adapter.apply_gap_colors(
        document, view, snapshot.context, [_gap("gap-0", 4, (13, 117, 241))]
    )

    assert result.changed_pixels == 1
    assert document.wait_count >= 1
    assert target.image.reshape((-1, 4))[4].tolist() == [13, 117, 241, 255]
