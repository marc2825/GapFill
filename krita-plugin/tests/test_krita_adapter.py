from __future__ import annotations

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


class _NativeHelper:
    def __init__(self, target):
        self.target = target
        self.calls = []
        self.mode = "success"

    def apply_exact_patch(self, **request):
        self.calls.append(request)
        runs = request["runs"]
        pixel_count = sum(run[2] for run in runs)
        if self.mode == "exception":
            raise RuntimeError("controlled native exception")
        if self.mode == "failure":
            return {
                "status": "MUTATION_FAILURE",
                "detail": "controlled native failure",
                "rollback_verified": True,
            }

        if self.mode != "no-op-success":
            width = request["expected_width"]
            origin_x = request["expected_origin_x"]
            origin_y = request["expected_origin_y"]
            raw = bytearray(_bgra(self.target.image))
            for x, y, count, before, replacement in runs:
                offset = ((y - origin_y) * width + (x - origin_x)) * 4
                size = count * 4
                assert raw[offset : offset + size] == before
                raw[offset : offset + size] = replacement
            if self.mode == "collateral-success":
                raw[0] = 127
            bgra = np.frombuffer(bytes(raw), dtype=np.uint8).reshape(
                self.target.image.shape
            )
            self.target.image = bgra[..., [2, 1, 0, 3]].copy()

        return {
            "status": "SUCCESS",
            "detail": "fake exact native transaction",
            "run_count": len(runs),
            "pixel_count": pixel_count,
            "start_stroke_calls": 1,
            "end_stroke_calls": 1,
            "top_level_undo_commands": 1,
            "transaction_commands": 1,
            "transaction_started": 1,
            "transaction_published": 1,
            "production_version_pinned": 1,
        }


class _App:
    def action(self, _name):
        raise AssertionError("the legacy fill action must be unreachable")


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
    document.native_helper = _NativeHelper(target)
    view = _View(document)
    monkeypatch.setattr(adapter, "ManagedColor", _Managed)
    monkeypatch.setattr(adapter, "Krita", _Krita)
    monkeypatch.setattr(
        adapter, "load_native_helper", lambda _application: document.native_helper
    )
    _Krita.app = _App()
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


def test_apply_all_uses_one_native_call_and_preserves_user_state(host) -> None:
    document, view, target, line = host
    original_foreground = view.foregroundColor()
    snapshot = adapter.snapshot_host(document, view, target, line, None, 4)
    result = adapter.apply_gap_colors(
        document,
        view,
        snapshot.context,
        [_gap("gap-0", 4, (17, 83, 201)), _gap("gap-1", 5, (9, 6, 3))],
    )

    assert result.changed_pixels == 2
    assert result.atomic_undo is True
    assert result.native_contract["top_level_undo_commands"] == 1
    assert result.context.generation == snapshot.context.generation
    adapter.validate_scan_context(document, view, result.context)
    with pytest.raises(RuntimeError, match="Coloring pixels changed"):
        adapter.validate_scan_context(document, view, snapshot.context)
    assert len(document.native_helper.calls) == 1
    assert document.native_helper.calls[0]["image_root_uuid"] == document.root.identifier
    assert document.native_helper.calls[0]["target_uuid"] == target.identifier
    assert target.image.reshape((-1, 4))[4].tolist() == [17, 83, 201, 255]
    assert target.image.reshape((-1, 4))[5].tolist() == [9, 6, 3, 255]
    assert document.selection() is None
    assert document.selection_history == []
    assert document.activeNode() is target
    assert view.foregroundColor() is original_foreground
    assert (view.eraserMode(), view.globalAlphaLock()) == (True, True)
    assert (view.currentBlendingMode(), view.paintingOpacity(), view.paintingFlow()) == (
        "multiply",
        0.25,
        0.5,
    )


def test_apply_selected_uses_one_native_call_without_touching_soft_selection(host) -> None:
    document, view, target, line = host
    soft = np.arange(9, dtype=np.uint8).reshape((3, 3))
    document._selection = _Selection(soft)
    snapshot = adapter.snapshot_host(document, view, target, line, None, 5)
    adapter.apply_gap_colors(document, view, snapshot.context, [_gap("gap-0", 4, (1, 2, 3))])
    assert np.array_equal(document.selection().data, soft)
    assert document.selection_history == []
    assert len(document.native_helper.calls) == 1


def test_apply_sends_exact_hidden_rgb_expected_before_and_native_bgra_after(host) -> None:
    document, view, target, line = host
    target.image.reshape((-1, 4))[4] = [91, 73, 55, 0]
    snapshot = adapter.snapshot_host(document, view, target, line, None, 51)

    adapter.apply_gap_colors(
        document, view, snapshot.context, [_gap("gap-0", 4, (13, 117, 241))]
    )

    run = document.native_helper.calls[0]["runs"][0]
    assert run[:3] == (1, 1, 1)
    assert run[3] == bytes((55, 73, 91, 0))
    assert run[4] == bytes((241, 117, 13, 255))


def test_failed_exact_postcondition_is_reported_without_fill_fallback(host) -> None:
    document, view, target, line = host
    before = target.image.copy()
    snapshot = adapter.snapshot_host(document, view, target, line, None, 6)
    document.native_helper.mode = "no-op-success"
    with pytest.raises(RuntimeError, match="complete Coloring layer failed"):
        adapter.apply_gap_colors(
            document, view, snapshot.context, [_gap("gap-0", 4, (101, 77, 33))]
        )
    assert np.array_equal(target.image, before)
    assert document.selection() is None
    assert len(document.native_helper.calls) == 1


def test_collateral_native_write_fails_strict_hidden_rgb_postcondition(host) -> None:
    document, view, target, line = host
    before = target.image.copy()
    snapshot = adapter.snapshot_host(document, view, target, line, None, 61)
    document.native_helper.mode = "collateral-success"
    with pytest.raises(RuntimeError, match="complete Coloring layer failed"):
        adapter.apply_gap_colors(
            document, view, snapshot.context, [_gap("gap-0", 4, (101, 77, 33))]
        )
    assert not np.array_equal(target.image, before)
    assert document.selection() is None
    assert len(document.native_helper.calls) == 1


def test_native_failure_maps_without_legacy_fill_fallback(host) -> None:
    document, view, target, line = host
    snapshot = adapter.snapshot_host(document, view, target, line, None, 7)
    before = target.image.copy()
    document.native_helper.mode = "failure"
    with pytest.raises(RuntimeError, match="controlled native failure"):
        adapter.apply_gap_colors(
            document, view, snapshot.context, [_gap("gap-0", 4, (101, 77, 33))]
        )
    assert np.array_equal(target.image, before)
    assert document.selection() is None
    assert len(document.native_helper.calls) == 1


def test_native_exception_maps_without_legacy_fill_fallback(host) -> None:
    document, view, target, line = host
    before = target.image.copy()
    snapshot = adapter.snapshot_host(document, view, target, line, None, 71)
    document.native_helper.mode = "exception"
    with pytest.raises(RuntimeError, match="native Apply call failed.*controlled"):
        adapter.apply_gap_colors(
            document, view, snapshot.context, [_gap("gap-0", 4, (101, 77, 33))]
        )
    assert np.array_equal(target.image, before)
    assert document.selection() is None
    assert len(document.native_helper.calls) == 1


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


def test_apply_waits_for_native_transaction_without_event_processing(host) -> None:
    document, view, target, line = host
    snapshot = adapter.snapshot_host(document, view, target, line, None, 11)
    result = adapter.apply_gap_colors(
        document, view, snapshot.context, [_gap("gap-0", 4, (13, 117, 241))]
    )

    assert result.changed_pixels == 1
    assert document.wait_count >= 1
    assert target.image.reshape((-1, 4))[4].tolist() == [13, 117, 241, 255]


def test_native_patch_runs_merge_only_contiguous_same_row_pixels() -> None:
    before = bytes(3 * 2 * 4)
    after = bytearray(before)
    for index, bgra in ((0, b"\x03\x02\x01\xff"), (1, b"\x03\x02\x01\xff"), (3, b"\x06\x05\x04\xff")):
        after[index * 4 : index * 4 + 4] = bgra

    runs = adapter.build_native_patch_runs(
        np.asarray([0, 1, 3], dtype=np.int64), 3, 2, before, bytes(after)
    )

    assert [(x, y, count) for x, y, count, _old, _new in runs] == [
        (0, 0, 2),
        (0, 1, 1),
    ]
    assert runs[0][3] == bytes(8)
    assert runs[0][4] == b"\x03\x02\x01\xff" * 2


@pytest.mark.parametrize(
    "indices",
    [
        np.asarray([1, 1], dtype=np.int64),
        np.asarray([2, 1], dtype=np.int64),
        np.asarray([-1], dtype=np.int64),
        np.asarray([9], dtype=np.int64),
        np.asarray([1.0]),
    ],
)
def test_native_patch_runs_reject_duplicate_unsorted_out_of_bounds_or_noninteger(
    indices,
) -> None:
    before = bytes(3 * 3 * 4)
    after = bytearray(before)
    after[4:8] = b"\x03\x02\x01\xff"
    with pytest.raises(ValueError):
        adapter.build_native_patch_runs(indices, 3, 3, before, bytes(after))


def test_native_patch_runs_reject_bad_payload_lengths_and_no_op() -> None:
    with pytest.raises(ValueError, match="exactly"):
        adapter.build_native_patch_runs(np.asarray([0]), 1, 1, b"", b"")
    with pytest.raises(ValueError, match="does not change"):
        adapter.build_native_patch_runs(np.asarray([0]), 1, 1, bytes(4), bytes(4))
