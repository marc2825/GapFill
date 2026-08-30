"""Narrow LibKis acquisition, color-conversion, and mutation boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np

try:
    from krita import Krita, ManagedColor
except ImportError:  # Pure adapter-contract tests run outside a Krita process.
    Krita = ManagedColor = None  # type: ignore[assignment]

from .engine.pixels import bgra_bytes_to_rgba
from .engine.types import GapRegion, LayerImages, Rgb
from .host_contract import (
    HostObservation,
    HostSnapshot,
    NodeState,
    ScanContext,
    StaleScanError,
    advance_context_after_owned_mutation,
    build_application_plan,
    image_sha256,
    require_fresh,
    require_supported_size,
)
from .native_backend import NativeHostError, load_native_helper
from .qt_compat import QColor, QUuid

SUPPORTED_MODEL = "RGBA"
SUPPORTED_DEPTH = "U8"
NORMAL_BLEND = "normal"


@dataclass(frozen=True)
class ApplyResult:
    changed_pixels: int
    atomic_undo: bool
    native_contract: dict[str, object]
    context: ScanContext


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
        image_root_id=_uuid_text(root.uniqueId()),
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


def _read_node_raw(node, width: int, height: int, x: int, y: int) -> bytes:
    raw = bytes(node.pixelData(x, y, width, height))
    expected_size = width * height * 4
    if len(raw) != expected_size:
        raise RuntimeError(
            f"Krita returned {len(raw)} raw Coloring bytes; expected {expected_size}."
        )
    return raw


def _target_rgb_to_native_bgra(rgb: Rgb) -> bytes:
    """Encode one already-converted target-profile color in Krita's RGBA/U8 storage."""

    if len(rgb) != 3 or any(value < 0 or value > 255 for value in rgb):
        raise ValueError(f"Invalid target-profile RGB value: {rgb!r}")
    return bytes((rgb[2], rgb[1], rgb[0], 255))


def build_native_patch_runs(
    indices: np.ndarray,
    width: int,
    height: int,
    expected_before: bytes,
    expected_after: bytes,
    *,
    origin_x: int = 0,
    origin_y: int = 0,
) -> tuple[tuple[int, int, int, bytes, bytes], ...]:
    """Merge a strict sorted pixel plan into non-overlapping horizontal runs."""

    if width <= 0 or height <= 0:
        raise ValueError("Native patch dimensions must be positive.")
    expected_size = width * height * 4
    if len(expected_before) != expected_size or len(expected_after) != expected_size:
        raise ValueError("Native patch images must contain exactly width * height * 4 bytes.")
    values = np.asarray(indices)
    if values.ndim != 1 or values.dtype.kind not in "iu" or values.size == 0:
        raise ValueError("Native patch indices must be a non-empty integer vector.")
    normalized = values.astype(np.int64, copy=False)
    if np.any(normalized < 0) or np.any(normalized >= width * height):
        raise ValueError("Native patch index is outside the image bounds.")
    if normalized.size > 1 and np.any(normalized[1:] <= normalized[:-1]):
        raise ValueError("Native patch indices must be strictly sorted without duplicates.")

    runs: list[tuple[int, int, int, bytes, bytes]] = []
    start = int(normalized[0])
    previous = start
    for raw_value in normalized[1:]:
        value = int(raw_value)
        same_row = value // width == previous // width
        if value != previous + 1 or not same_row:
            runs.append(
                _native_run(
                    start,
                    previous,
                    width,
                    expected_before,
                    expected_after,
                    origin_x,
                    origin_y,
                )
            )
            start = value
        previous = value
    runs.append(
        _native_run(
            start,
            previous,
            width,
            expected_before,
            expected_after,
            origin_x,
            origin_y,
        )
    )
    return tuple(runs)


def _native_run(
    start: int,
    end: int,
    width: int,
    expected_before: bytes,
    expected_after: bytes,
    origin_x: int,
    origin_y: int,
) -> tuple[int, int, int, bytes, bytes]:
    count = end - start + 1
    byte_start = start * 4
    byte_end = (end + 1) * 4
    before = expected_before[byte_start:byte_end]
    after = expected_after[byte_start:byte_end]
    if before == after:
        raise ValueError("Native patch run does not change any raw bytes.")
    return (
        origin_x + start % width,
        origin_y + start // width,
        count,
        before,
        after,
    )


def _require_successful_native_result(
    result: object, *, run_count: int, pixel_count: int
) -> dict[str, object]:
    if not isinstance(result, dict):
        raise NativeHostError("The GapFill native helper returned a malformed result.")
    status = result.get("status")
    if status != "SUCCESS":
        detail = str(result.get("detail", "no detail"))
        if status in {"STALE_REJECTED", "TARGET_REJECTED"}:
            raise StaleScanError(f"Native target validation rejected the stale scan: {detail}")
        if status == "MUTATION_FAILURE" and not bool(result.get("rollback_verified")):
            raise NativeHostError(
                "Native Apply failed and could not verify byte-exact rollback: " + detail
            )
        raise NativeHostError(f"Native Apply rejected the operation ({status}): {detail}")
    expected = {
        "run_count": run_count,
        "pixel_count": pixel_count,
        "start_stroke_calls": 1,
        "end_stroke_calls": 1,
        "top_level_undo_commands": 1,
        "transaction_commands": 1,
        "transaction_started": 1,
        "transaction_published": 1,
        "production_version_pinned": 1,
    }
    mismatches = {
        key: (value, result.get(key))
        for key, value in expected.items()
        if result.get(key) != value
    }
    if mismatches:
        raise NativeHostError(f"Native Apply command contract mismatch: {mismatches}")
    return result


def apply_gap_colors(
    document, view, context: ScanContext, gaps: list[GapRegion]
) -> ApplyResult:
    """Apply one complete exact patch through the pinned native transaction helper."""
    if not gaps:
        return ApplyResult(0, True, {}, context)
    target, before = validate_scan_context(document, view, context)
    plan = build_application_plan(gaps, before)
    width, height = int(document.width()), int(document.height())
    x, y = int(document.xOffset()), int(document.yOffset())
    bridge = canvas_color_bridge(view, context)
    expected_before = _read_node_raw(target, width, height, x, y)
    snapshot_before = np.ascontiguousarray(before[..., [2, 1, 0, 3]]).tobytes()
    if expected_before != snapshot_before:
        raise StaleScanError("Coloring pixels changed while preparing native Apply.")
    expected_after = bytearray(expected_before)
    for color, indices in plan.groups:
        _managed, target_rgb = bridge.source_rgb_to_target(color)
        replacement = _target_rgb_to_native_bgra(target_rgb)
        for raw_index in indices:
            index = int(raw_index)
            expected_after[index * 4 : index * 4 + 4] = replacement

    runs = build_native_patch_runs(
        plan.indices,
        width,
        height,
        expected_before,
        bytes(expected_after),
        origin_x=x,
        origin_y=y,
    )
    helper = load_native_helper(Krita.instance())
    try:
        native_result = helper.apply_exact_patch(
            image_root_uuid=context.observation.image_root_id,
            target_uuid=context.observation.target.unique_id,
            expected_width=width,
            expected_height=height,
            expected_origin_x=x,
            expected_origin_y=y,
            expected_color_model=SUPPORTED_MODEL,
            expected_color_depth=SUPPORTED_DEPTH,
            expected_profile=context.observation.target.color_profile,
            runs=runs,
        )
    except Exception as error:
        raise NativeHostError(f"The GapFill native Apply call failed: {error}") from error
    contract = _require_successful_native_result(
        native_result, run_count=len(runs), pixel_count=int(plan.indices.size)
    )
    document.waitForDone()
    actual_after = _read_node_raw(target, width, height, x, y)
    if actual_after != bytes(expected_after):
        raise NativeHostError(
            "Native Apply returned success but the complete Coloring layer failed exact "
            "raw-byte validation. Do not continue editing; invoke Undo once."
        )
    expected_coloring = bgra_bytes_to_rgba(bytes(expected_after), width, height)
    try:
        observation, observed_target, observed_coloring = observe_context(
            document, view, context
        )
        if observed_target is None or not np.array_equal(
            observed_coloring, expected_coloring
        ):
            raise StaleScanError(
                "Coloring pixels changed while advancing the verified GapFill session."
            )
        advanced_context = advance_context_after_owned_mutation(
            context,
            observation,
            expected_coloring_sha256=image_sha256(expected_coloring),
        )
    except StaleScanError:
        raise
    except Exception as error:
        raise NativeHostError(
            "Native Apply succeeded, but the continued-session checkpoint could not be read: "
            f"{error}"
        ) from error
    return ApplyResult(int(plan.indices.size), True, contract, advanced_context)
