"""Narrow LibKis acquisition, color-conversion, and mutation boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np

try:
    from krita import Krita, ManagedColor, Selection
except ImportError:  # Pure adapter-contract tests run outside a Krita process.
    Krita = ManagedColor = Selection = None  # type: ignore[assignment]

from .engine.pixels import bgra_bytes_to_rgba
from .engine.types import GapRegion, LayerImages, Rgb
from .host_contract import (
    HostObservation,
    HostSnapshot,
    NodeState,
    ScanContext,
    StaleScanError,
    build_application_plan,
    image_sha256,
    require_fresh,
    require_supported_size,
)
from .qt_compat import QByteArray, QColor, QUuid

SUPPORTED_MODEL = "RGBA"
SUPPORTED_DEPTH = "U8"
NORMAL_BLEND = "normal"


@dataclass(frozen=True)
class ApplyResult:
    changed_pixels: int
    atomic_undo: bool


def iter_nodes(root) -> Iterable:
    for child in root.childNodes():
        yield child
        yield from iter_nodes(child)


def node_label(node) -> str:
    path = []
    current = node
    while current is not None and current.parentNode() is not None:
        path.append(current.name() or "(unnamed)")
        current = current.parentNode()
    return " / ".join(reversed(path))


def _uuid_text(value) -> str:
    return str(value.toString() if hasattr(value, "toString") else value)


def _point_tuple(point) -> tuple[int, int]:
    return (int(point.x()), int(point.y()))


def _rect_tuple(rect) -> tuple[int, int, int, int]:
    return (int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))


def _layer_style(node) -> str:
    getter = getattr(node, "layerStyleToAsl", None)
    return str(getter()) if callable(getter) else ""


def _ancestor_signature(node) -> tuple[tuple[object, ...], ...]:
    result = []
    current = node.parentNode()
    while current is not None and current.parentNode() is not None:
        result.append(
            (
                _uuid_text(current.uniqueId()),
                current.type(),
                bool(current.visible()),
                int(current.opacity()),
                str(current.blendingMode()),
                bool(current.inheritAlpha()),
            )
        )
        current = current.parentNode()
    return tuple(result)


def node_state(node) -> NodeState:
    children = tuple(
        (_uuid_text(child.uniqueId()), str(child.type())) for child in node.childNodes()
    )
    return NodeState(
        unique_id=_uuid_text(node.uniqueId()),
        node_type=str(node.type()),
        position=_point_tuple(node.position()),
        bounds=_rect_tuple(node.bounds()),
        color_model=str(node.colorModel()),
        color_depth=str(node.colorDepth()),
        color_profile=str(node.colorProfile()),
        locked=bool(node.locked()),
        alpha_locked=bool(node.alphaLocked()),
        animated=bool(node.animated()),
        visible=bool(node.visible()),
        opacity=int(node.opacity()),
        blending_mode=str(node.blendingMode()),
        inherit_alpha=bool(node.inheritAlpha()),
        layer_style=_layer_style(node),
        child_signature=children,
        ancestor_signature=_ancestor_signature(node),
    )


def _require_rgba_u8(node) -> None:
    model = str(node.colorModel())
    depth = str(node.colorDepth())
    if model != SUPPORTED_MODEL or depth != SUPPORTED_DEPTH:
        raise ValueError(
            f'Layer "{node.name()}" uses {model}/{depth}. GapFill requires RGBA/U8.'
        )


def _require_neutral_ancestors(state: NodeState, label: str) -> None:
    for ancestor in state.ancestor_signature:
        _identifier, _kind, visible, opacity, blending, inherit = ancestor
        if not visible or opacity != 255 or blending != NORMAL_BLEND or inherit:
            raise RuntimeError(
                f"{label} has a hidden, translucent, blended, or inherit-alpha parent; "
                "that host geometry is not qualified."
            )


def require_supported_target(document, node) -> NodeState:
    state = node_state(node)
    if state.node_type != "paintlayer":
        raise RuntimeError("The selected Coloring node must be a Paint Layer.")
    _require_rgba_u8(node)
    if state.position != (int(document.xOffset()), int(document.yOffset())):
        raise RuntimeError(
            "Moved/offset Coloring layers are not qualified for safe raw-pixel apply."
        )
    if state.child_signature:
        raise RuntimeError(
            "Coloring layers with masks or child effects are not supported for safe apply."
        )
    if state.layer_style:
        raise RuntimeError("Coloring layers with layer styles are not supported for safe apply.")
    if state.locked or state.alpha_locked:
        raise RuntimeError("Unlock the Coloring layer and disable its alpha lock.")
    if state.animated:
        raise RuntimeError("Animated Coloring layers are not supported.")
    if not state.visible or state.opacity != 255 or state.blending_mode != NORMAL_BLEND:
        raise RuntimeError("Coloring must be visible, fully opaque, and use Normal blending.")
    if state.inherit_alpha:
        raise RuntimeError("Coloring with inherit-alpha enabled is not supported.")
    _require_neutral_ancestors(state, "Coloring")
    return state


def _require_supported_projection(node, label: str) -> NodeState:
    _require_rgba_u8(node)
    state = node_state(node)
    if not state.visible:
        raise RuntimeError(f"{label} must be visible.")
    _require_neutral_ancestors(state, label)
    return state


def _require_profiles(root, nodes: Iterable) -> None:
    _require_rgba_u8(root)
    expected = str(root.colorProfile())
    for node in nodes:
        if node is not None and str(node.colorProfile()) != expected:
            raise RuntimeError(
                "Mixed node profiles are not qualified for deterministic host snapshots."
            )


def read_node_rgba(
    node, width: int, height: int, *, x: int = 0, y: int = 0, projection: bool
) -> np.ndarray:
    _require_rgba_u8(node)
    getter = node.projectionPixelData if projection else node.pixelData
    return bgra_bytes_to_rgba(getter(x, y, width, height), width, height)


def _read_selection(document, width: int, height: int, x: int, y: int):
    selection = document.selection()
    if selection is None:
        return None
    data = np.frombuffer(bytes(selection.pixelData(x, y, width, height)), dtype=np.uint8)
    if data.size != width * height:
        raise RuntimeError(
            f"Krita returned {data.size} selection bytes; expected {width * height}."
        )
    return data.reshape((height, width)).copy()


def _empty_guides(width: int, height: int) -> np.ndarray:
    return np.zeros((height, width, 4), dtype=np.uint8)


def _observation(
    document,
    view,
    target_state: Optional[NodeState],
    line_state: Optional[NodeState],
    guide_state: Optional[NodeState],
    selection,
    coloring,
    line,
    guides,
    composite,
) -> HostObservation:
    active = document.activeNode()
    root = document.rootNode()
    return HostObservation(
        document_key=id(document),
        view_key=id(view),
        document_geometry=(
            int(document.xOffset()),
            int(document.yOffset()),
            int(document.width()),
            int(document.height()),
        ),
        source_space=(
            str(root.colorModel()),
            str(root.colorDepth()),
            str(root.colorProfile()),
        ),
        target=target_state,
        line=line_state,
        guides=guide_state,
        active_node_id=_uuid_text(active.uniqueId()) if active is not None else None,
        selection_present=selection is not None,
        selection_sha256=image_sha256(selection) if selection is not None else None,
        coloring_sha256=image_sha256(coloring),
        line_sha256=image_sha256(line),
        guides_sha256=image_sha256(guides),
        composite_sha256=image_sha256(composite),
    )


def snapshot_host(document, view, coloring_node, line_node, guides_node, generation: int):
    """Acquire one immutable, document-coordinate snapshot on the UI thread."""
    width, height = int(document.width()), int(document.height())
    require_supported_size(width, height)
    x, y = int(document.xOffset()), int(document.yOffset())
    target_state = require_supported_target(document, coloring_node)
    line_state = _require_supported_projection(line_node, "Line Art")
    guide_state = (
        _require_supported_projection(guides_node, "Guides")
        if guides_node is not None
        else None
    )
    root = document.rootNode()
    _require_profiles(root, (coloring_node, line_node, guides_node))
    coloring = read_node_rgba(coloring_node, width, height, x=x, y=y, projection=False)
    line = read_node_rgba(line_node, width, height, x=x, y=y, projection=True)
    guides = (
        read_node_rgba(guides_node, width, height, x=x, y=y, projection=True)
        if guides_node is not None
        else _empty_guides(width, height)
    )
    composite = read_node_rgba(root, width, height, x=x, y=y, projection=True)
    selection = _read_selection(document, width, height, x, y)
    observation = _observation(
        document,
        view,
        target_state,
        line_state,
        guide_state,
        selection,
        coloring,
        line,
        guides,
        composite,
    )
    return HostSnapshot.create(
        LayerImages(coloring, line, guides, composite),
        selection,
        ScanContext(generation, observation),
        take_ownership=True,
    )


def snapshot_layers(document, coloring_node, line_node, guides_node=None) -> LayerImages:
    """Compatibility helper for scripts; the controller uses :func:`snapshot_host`."""
    width, height = int(document.width()), int(document.height())
    require_supported_size(width, height)
    x, y = int(document.xOffset()), int(document.yOffset())
    coloring = read_node_rgba(coloring_node, width, height, x=x, y=y, projection=False)
    line = read_node_rgba(line_node, width, height, x=x, y=y, projection=True)
    guides = (
        read_node_rgba(guides_node, width, height, x=x, y=y, projection=True)
        if guides_node is not None
        else _empty_guides(width, height)
    )
    root = document.rootNode()
    composite = read_node_rgba(root, width, height, x=x, y=y, projection=True)
    images = LayerImages(coloring, line, guides, composite)
    images.validate()
    return images


def resolve_node(document, unique_id: str):
    try:
        node = document.nodeByUniqueID(QUuid(unique_id))
    except Exception:
        node = None
    if node is not None and _uuid_text(node.uniqueId()) == unique_id:
        return node
    root = document.rootNode()
    if _uuid_text(root.uniqueId()) == unique_id:
        return root
    return next((item for item in iter_nodes(root) if _uuid_text(item.uniqueId()) == unique_id), None)


def observe_context(document, view, context: ScanContext):
    expected = context.observation
    width, height = int(document.width()), int(document.height())
    require_supported_size(width, height)
    x, y = int(document.xOffset()), int(document.yOffset())
    target = resolve_node(document, expected.target.unique_id) if expected.target else None
    line_node = resolve_node(document, expected.line.unique_id) if expected.line else None
    guide_node = resolve_node(document, expected.guides.unique_id) if expected.guides else None
    root = document.rootNode()
    coloring = (
        read_node_rgba(target, width, height, x=x, y=y, projection=False)
        if target is not None
        else np.zeros((height, width, 4), dtype=np.uint8)
    )
    line = (
        read_node_rgba(line_node, width, height, x=x, y=y, projection=True)
        if line_node is not None
        else np.zeros((height, width, 4), dtype=np.uint8)
    )
    guides = (
        read_node_rgba(guide_node, width, height, x=x, y=y, projection=True)
        if guide_node is not None
        else _empty_guides(width, height)
    )
    composite = read_node_rgba(root, width, height, x=x, y=y, projection=True)
    selection = _read_selection(document, width, height, x, y)
    return (
        _observation(
            document,
            view,
            node_state(target) if target is not None else None,
            node_state(line_node) if line_node is not None else None,
            node_state(guide_node) if guide_node is not None else None,
            selection,
            coloring,
            line,
            guides,
            composite,
        ),
        target,
        coloring,
    )


def validate_scan_context(document, view, context: ScanContext):
    observation, target, coloring = observe_context(document, view, context)
    require_fresh(context, observation)
    if target is None:
        raise StaleScanError("The scanned target no longer exists.")
    require_supported_target(document, target)
    return target, coloring


class CanvasColorBridge:
    """Convert frozen source-profile RGB through the active canvas at the host edge."""

    def __init__(self, canvas, source_space: tuple[str, str, str], target_space):
        self.canvas = canvas
        self.source_space = source_space
        self.target_space = target_space
        self._display_cache: dict[Rgb, QColor] = {}

    @staticmethod
    def _managed(space: tuple[str, str, str], rgb: Rgb, alpha: int = 255):
        if space[:2] != (SUPPORTED_MODEL, SUPPORTED_DEPTH):
            raise RuntimeError("Canvas color conversion requires RGBA/U8.")
        managed = ManagedColor(*space)
        components = managed.components()
        components[:4] = [
            rgb[2] / 255.0,
            rgb[1] / 255.0,
            rgb[0] / 255.0,
            alpha / 255.0,
        ]
        managed.setComponents(components)
        return managed

    @staticmethod
    def _components_rgb(managed) -> Rgb:
        values = managed.componentsOrdered()
        return tuple(max(0, min(255, int(round(float(value) * 255.0)))) for value in values[:3])

    def source_rgb_to_qcolor(self, rgb: Rgb) -> QColor:
        cached = self._display_cache.get(rgb)
        if cached is None:
            cached = self._managed(self.source_space, rgb).colorForCanvas(self.canvas)
            self._display_cache[rgb] = QColor(cached)
        return QColor(cached)

    def source_rgba_to_qcolor(self, rgba) -> QColor:
        rgb = (int(rgba[0]), int(rgba[1]), int(rgba[2]))
        return self._managed(self.source_space, rgb, int(rgba[3])).colorForCanvas(
            self.canvas
        )

    def qcolor_to_source_rgb(self, qcolor: QColor) -> Rgb:
        managed = ManagedColor.fromQColor(qcolor, self.canvas)
        if not managed.setColorSpace(*self.source_space):
            raise RuntimeError("Krita could not convert the sampled canvas color to the source profile.")
        return self._components_rgb(managed)

    def source_rgb_to_target(self, rgb: Rgb):
        managed = ManagedColor.fromQColor(self.source_rgb_to_qcolor(rgb), self.canvas)
        if not managed.setColorSpace(*self.target_space):
            raise RuntimeError("Krita could not convert the prediction to the Coloring profile.")
        return managed, self._components_rgb(managed)


def canvas_color_bridge(view, context: ScanContext) -> CanvasColorBridge:
    observation = context.observation
    if observation.target is None:
        raise RuntimeError("The scan has no Coloring profile provenance.")
    target = (
        observation.target.color_model,
        observation.target.color_depth,
        observation.target.color_profile,
    )
    return CanvasColorBridge(view.canvas(), observation.source_space, target)


def _require_deterministic_view(view) -> None:
    required = (
        "eraserMode",
        "setEraserMode",
        "globalAlphaLock",
        "setGlobalAlphaLock",
        "currentBlendingMode",
        "setCurrentBlendingMode",
        "paintingOpacity",
        "setPaintingOpacity",
        "paintingFlow",
        "setPaintingFlow",
    )
    missing = [name for name in required if not callable(getattr(view, name, None))]
    if missing:
        raise RuntimeError(
            "This Krita build does not expose the public view-state controls required for "
            "deterministic apply: " + ", ".join(missing)
        )


def _rgba_to_bgra_bytes(image: np.ndarray) -> QByteArray:
    return QByteArray(np.ascontiguousarray(image[..., [2, 1, 0, 3]]).tobytes())


def _managed_signature(color) -> tuple[object, ...]:
    metadata = []
    for name in ("colorModel", "colorDepth", "colorProfile"):
        getter = getattr(color, name, None)
        metadata.append(str(getter()) if callable(getter) else None)
    return (*metadata, tuple(float(value) for value in color.components()))


def apply_gap_colors(
    document, view, context: ScanContext, gaps: list[GapRegion]
) -> ApplyResult:
    """Apply and verify fills while restoring exact user-visible host state.

    Public LibKis does not expose an undo macro around selection actions. The
    operation therefore cannot truthfully promise one-step atomic Undo; callers
    surface that limitation and the real-host release gate remains open.
    """
    if not gaps:
        return ApplyResult(0, False)
    target, before = validate_scan_context(document, view, context)
    plan = build_application_plan(gaps, before)
    _require_deterministic_view(view)
    action = Krita.instance().action("fill_selection_foreground_color")
    if action is None or not action.isEnabled():
        raise RuntimeError("Krita's foreground-selection fill action is unavailable or disabled.")

    width, height = int(document.width()), int(document.height())
    x, y = int(document.xOffset()), int(document.yOffset())
    bridge = canvas_color_bridge(view, context)
    converted = []
    expected = before.copy()
    expected_flat = expected.reshape((-1, 4))
    for color, indices in plan.groups:
        managed, target_rgb = bridge.source_rgb_to_target(color)
        expected_flat[indices, :3] = target_rgb
        expected_flat[indices, 3] = 255
        converted.append((managed, indices))

    original_node = document.activeNode()
    original_selection = document.selection()
    selection_present = original_selection is not None
    saved_selection = original_selection.duplicate() if selection_present else None
    saved_selection_bytes = (
        bytes(original_selection.pixelData(x, y, width, height)) if selection_present else None
    )
    original_foreground = view.foregroundColor()
    original_foreground_signature = _managed_signature(original_foreground)
    original_eraser = bool(view.eraserMode())
    original_alpha_lock = bool(view.globalAlphaLock())
    original_blending = str(view.currentBlendingMode())
    original_opacity = float(view.paintingOpacity())
    original_flow = float(view.paintingFlow())
    mutation_error = None
    recovery_error = None
    try:
        document.setActiveNode(target)
        view.setEraserMode(False)
        view.setGlobalAlphaLock(False)
        view.setCurrentBlendingMode(NORMAL_BLEND)
        view.setPaintingOpacity(1.0)
        view.setPaintingFlow(1.0)
        for managed, indices in converted:
            document.setActiveNode(target)
            mask = np.zeros(width * height, dtype=np.uint8)
            mask[indices] = 255
            selection = Selection()
            selection.setPixelData(QByteArray(mask.tobytes()), x, y, width, height)
            document.setSelection(selection)
            view.setForeGroundColor(managed)
            if document.activeNode() != target:
                raise RuntimeError("Krita did not activate the scanned Coloring target.")
            if not action.isEnabled():
                raise RuntimeError("Krita disabled the fill action during apply.")
            action.trigger()
            document.waitForDone()
            if document.activeNode() != target:
                raise RuntimeError("Krita changed the active target during apply.")
        after = read_node_rgba(target, width, height, x=x, y=y, projection=False)
        if not np.array_equal(after, expected):
            raise RuntimeError(
                "Krita's fill action did not produce the exact requested target pixels."
            )
    except Exception as error:
        mutation_error = error
        try:
            current = read_node_rgba(target, width, height, x=x, y=y, projection=False)
            if not np.array_equal(current, before):
                if not target.setPixelData(_rgba_to_bgra_bytes(before), x, y, width, height):
                    raise RuntimeError("Krita rejected emergency pixel recovery.")
                document.refreshProjection()
                document.waitForDone()
                recovered = read_node_rgba(
                    target, width, height, x=x, y=y, projection=False
                )
                if not np.array_equal(recovered, before):
                    raise RuntimeError("Exact source-pixel recovery failed.")
        except Exception as error:
            recovery_error = error
    finally:
        view.setForeGroundColor(original_foreground)
        view.setPaintingFlow(original_flow)
        view.setPaintingOpacity(original_opacity)
        view.setCurrentBlendingMode(original_blending)
        view.setGlobalAlphaLock(original_alpha_lock)
        view.setEraserMode(original_eraser)
        document.setSelection(saved_selection if selection_present else None)
        if original_node is not None:
            document.setActiveNode(original_node)
        document.waitForDone()

    restored = document.selection()
    if selection_present != (restored is not None):
        raise RuntimeError("Krita did not restore the semantic selection presence.")
    if selection_present and bytes(restored.pixelData(x, y, width, height)) != saved_selection_bytes:
        raise RuntimeError("Krita did not restore the exact original selection pixels.")
    if document.activeNode() != original_node:
        raise RuntimeError("Krita did not restore the original active node.")
    if _managed_signature(view.foregroundColor()) != original_foreground_signature:
        raise RuntimeError("Krita did not restore the exact foreground color.")
    if (
        bool(view.eraserMode()) != original_eraser
        or bool(view.globalAlphaLock()) != original_alpha_lock
        or str(view.currentBlendingMode()) != original_blending
        or float(view.paintingOpacity()) != original_opacity
        or float(view.paintingFlow()) != original_flow
    ):
        raise RuntimeError("Krita did not restore the original view/tool state.")
    if recovery_error is not None:
        raise RuntimeError(f"Apply failed and emergency recovery failed: {recovery_error}")
    if mutation_error is not None:
        raise mutation_error
    return ApplyResult(int(plan.indices.size), False)
