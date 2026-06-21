from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .types import GapRegion, LayerImages, RgbaImage

PATCH_SIZE = 32


@dataclass(frozen=True)
class PatchBounds:
    virtual_x: int
    virtual_y: int
    source_x: int
    source_y: int
    source_width: int
    source_height: int
    destination_x: int
    destination_y: int


@dataclass
class ImagePatch:
    rgba: RgbaImage
    valid: np.ndarray
    bounds: PatchBounds


def centered_patch_bounds(
    width: int, height: int, center: tuple[int, int], size: int = PATCH_SIZE
) -> PatchBounds:
    half = size // 2
    virtual_x = int(np.floor(center[0])) - half
    virtual_y = int(np.floor(center[1])) - half
    source_x = max(0, virtual_x)
    source_y = max(0, virtual_y)
    source_end_x = min(width, virtual_x + size)
    source_end_y = min(height, virtual_y + size)
    return PatchBounds(
        virtual_x=virtual_x,
        virtual_y=virtual_y,
        source_x=source_x,
        source_y=source_y,
        source_width=max(0, source_end_x - source_x),
        source_height=max(0, source_end_y - source_y),
        destination_x=source_x - virtual_x,
        destination_y=source_y - virtual_y,
    )


def extract_patch(image: RgbaImage, bounds: PatchBounds, size: int = PATCH_SIZE) -> ImagePatch:
    rgba = np.zeros((size, size, 4), dtype=np.uint8)
    valid = np.zeros((size, size), dtype=bool)
    if bounds.source_width and bounds.source_height:
        source = image[
            bounds.source_y : bounds.source_y + bounds.source_height,
            bounds.source_x : bounds.source_x + bounds.source_width,
        ]
        y0, x0 = bounds.destination_y, bounds.destination_x
        rgba[y0 : y0 + bounds.source_height, x0 : x0 + bounds.source_width] = source
        valid[y0 : y0 + bounds.source_height, x0 : x0 + bounds.source_width] = True
    return ImagePatch(rgba, valid, bounds)


def build_gap_mask(
    coloring_patch: ImagePatch,
    gap: GapRegion,
    document_width: int,
) -> np.ndarray:
    size = coloring_patch.rgba.shape[0]
    mask = np.zeros((size, size), dtype=np.float32)
    ys, xs = np.divmod(gap.indices, document_width)
    local_x = xs - coloring_patch.bounds.virtual_x
    local_y = ys - coloring_patch.bounds.virtual_y
    inside = (local_x >= 0) & (local_x < size) & (local_y >= 0) & (local_y < size)
    local_x, local_y = local_x[inside], local_y[inside]
    valid = coloring_patch.valid[local_y, local_x]
    transparent = coloring_patch.rgba[local_y, local_x, 3] == 0
    mask[local_y[valid & transparent], local_x[valid & transparent]] = 1.0
    return mask


def build_model_patches(
    images: LayerImages, gap: GapRegion, size: int = PATCH_SIZE
) -> tuple[ImagePatch, ImagePatch, ImagePatch, np.ndarray]:
    bounds = centered_patch_bounds(images.width, images.height, gap.center, size)
    coloring = extract_patch(images.coloring, bounds, size)
    line_art = extract_patch(images.line_art, bounds, size)
    guides = extract_patch(images.guides, bounds, size)
    gap_mask = build_gap_mask(coloring, gap, images.width)
    if gap.kind.value == "guide":
        guides.rgba[gap_mask > 0, 3] = 0
    return coloring, line_art, guides, gap_mask
