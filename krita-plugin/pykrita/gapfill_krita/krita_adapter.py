from __future__ import annotations

from collections import defaultdict
from typing import Iterable

import numpy as np
from krita import Krita, ManagedColor, Selection

from .engine.pixels import bgra_bytes_to_rgba
from .engine.types import GapRegion, LayerImages, Rgb
from .qt_compat import QByteArray

SUPPORTED_MODEL = "RGBA"
SUPPORTED_DEPTH = "U8"


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


def _require_rgba_u8(node) -> None:
    model = node.colorModel()
    depth = node.colorDepth()
    if model != SUPPORTED_MODEL or depth != SUPPORTED_DEPTH:
        raise ValueError(
            f'Layer "{node.name()}" uses {model}/{depth}. GapFill currently '
            "requires RGBA/U8 layers so its model receives the same pixel format used in training."
        )


def read_node_rgba(node, width: int, height: int, *, projection: bool) -> np.ndarray:
    _require_rgba_u8(node)
    getter = node.projectionPixelData if projection else node.pixelData
    return bgra_bytes_to_rgba(getter(0, 0, width, height), width, height)


def snapshot_layers(document, coloring_node, line_node, guides_node=None) -> LayerImages:
    width, height = document.width(), document.height()
    coloring = read_node_rgba(coloring_node, width, height, projection=False)
    line_art = read_node_rgba(line_node, width, height, projection=True)
    if guides_node is None:
        guides = np.zeros_like(coloring)
    else:
        guides = read_node_rgba(guides_node, width, height, projection=True)
    root = document.rootNode()
    _require_rgba_u8(root)
    composite = bgra_bytes_to_rgba(root.projectionPixelData(0, 0, width, height), width, height)
    images = LayerImages(coloring, line_art, guides, composite)
    images.validate()
    return images


def apply_gap_colors(document, view, target_node, gaps: list[GapRegion]) -> None:
    """Fill gaps through Krita's selection action so edits remain undoable."""
    if not gaps:
        return
    if target_node.type() != "paintlayer":
        raise RuntimeError("The selected Coloring node must be a Paint Layer.")
    if target_node.locked():
        raise RuntimeError("The selected Coloring layer is locked.")
    if target_node.alphaLocked():
        raise RuntimeError(
            "Disable alpha lock on the Coloring layer before filling transparent gaps."
        )
    action = Krita.instance().action("fill_selection_foreground_color")
    if action is None:
        raise RuntimeError("Krita's foreground-selection fill action is unavailable.")

    width, height = document.width(), document.height()
    grouped: dict[Rgb, list[np.ndarray]] = defaultdict(list)
    for gap in gaps:
        color = gap.color
        if color is None:
            raise RuntimeError(f"{gap.id} has no predicted color.")
        grouped[color].append(gap.indices)

    original_node = document.activeNode()
    original_selection = document.selection()
    saved_selection = original_selection.duplicate() if original_selection is not None else None
    original_foreground = view.foregroundColor()
    try:
        document.setActiveNode(target_node)
        for color, index_groups in grouped.items():
            mask = np.zeros(width * height, dtype=np.uint8)
            mask[np.concatenate(index_groups)] = 255
            selection = Selection()
            selection.setPixelData(QByteArray(mask.tobytes()), 0, 0, width, height)
            document.setSelection(selection)
            managed = ManagedColor(
                target_node.colorModel(),
                target_node.colorDepth(),
                target_node.colorProfile(),
            )
            components = managed.components()
            components[:4] = [
                color[0] / 255.0,
                color[1] / 255.0,
                color[2] / 255.0,
                1.0,
            ]
            managed.setComponents(components)
            view.setForeGroundColor(managed)
            action.trigger()
            document.waitForDone()
    finally:
        view.setForeGroundColor(original_foreground)
        document.setSelection(saved_selection if saved_selection is not None else Selection())
        if original_node is not None:
            document.setActiveNode(original_node)
