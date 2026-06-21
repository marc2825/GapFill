from __future__ import annotations

from typing import Optional

import numpy as np

from .types import FlatIndices, Rgb, RgbaImage

UNASSIGNED_MATERIAL_RGB: Rgb = (255, 0, 255)
GREEDY_EXPANSION_RADIUS = 5


def rgb_to_hex(color: Rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*color)


def parse_hex_color(value: str) -> Optional[Rgb]:
    normalized = value.strip().lstrip("#")
    if len(normalized) != 6:
        return None
    try:
        return tuple(int(normalized[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return None


def modal_rgb(pixels: np.ndarray) -> Optional[Rgb]:
    if pixels.size == 0:
        return None
    packed = (
        (pixels[:, 0].astype(np.uint32) << 16)
        | (pixels[:, 1].astype(np.uint32) << 8)
        | pixels[:, 2].astype(np.uint32)
    )
    values, counts = np.unique(packed, return_counts=True)
    value = int(values[int(np.argmax(counts))])
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)


def predict_color_greedy(
    coloring: RgbaImage,
    indices: FlatIndices,
    excluded: Optional[np.ndarray] = None,
    fallback: Rgb = UNASSIGNED_MATERIAL_RGB,
) -> Rgb:
    """Choose the most common painted color around a gap."""
    if indices.size == 0:
        return fallback
    height, width = coloring.shape[:2]
    ys, xs = np.divmod(indices, width)
    x0 = max(0, int(xs.min()) - GREEDY_EXPANSION_RADIUS)
    y0 = max(0, int(ys.min()) - GREEDY_EXPANSION_RADIUS)
    x1 = min(width, int(xs.max()) + GREEDY_EXPANSION_RADIUS + 1)
    y1 = min(height, int(ys.max()) + GREEDY_EXPANSION_RADIUS + 1)

    region_mask = np.zeros((y1 - y0, x1 - x0), dtype=bool)
    region_mask[ys - y0, xs - x0] = True
    sample = coloring[y0:y1, x0:x1]
    eligible = (sample[..., 3] > 0) & ~region_mask
    if excluded is not None:
        eligible &= ~excluded[y0:y1, x0:x1]
    return modal_rgb(sample[eligible]) or fallback
