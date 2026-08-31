from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .types import GapKind, GapRegion, LayerImages, ModelBoundaryMode, RgbaImage

PATCH_SIZE = 32


def canonical_boundary_from_rgba(rgba: RgbaImage) -> np.ndarray:
    """Return the training-faithful Line boundary for logical byte RGBA.

    Straight-alpha pixels are composited over byte white after the fixed-point
    grayscale conversion used by OpenCV. Values at or below 128 are boundary.
    Profile/render conversion into these logical bytes remains a Phase 6 host
    concern.
    """

    image = np.asarray(rgba)
    if image.ndim != 3 or image.shape[2] != 4 or image.dtype != np.uint8:
        raise ValueError("Canonical Line conversion requires uint8 RGBA pixels.")
    values = image.astype(np.uint32)
    luma = (
        values[..., 0] * 4899
        + values[..., 1] * 9617
        + values[..., 2] * 1868
        + 8192
    ) >> 14
    alpha = values[..., 3]
    composited = (luma * alpha + 255 * (255 - alpha) + 127) // 255
    return composited <= 128


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
    return coloring, line_art, guides, gap_mask


def build_legacy_model_patches(
    images: LayerImages, gap: GapRegion, size: int = PATCH_SIZE
) -> tuple[ImagePatch, ImagePatch, ImagePatch, np.ndarray]:
    """Reproduce the frozen Phase 2 Guide-composed characterization only."""

    coloring, line_art, guides, gap_mask = build_model_patches(images, gap, size)
    if gap.kind.value == "guide":
        guides.rgba[gap_mask > 0, 3] = 0
    return coloring, line_art, guides, gap_mask


def build_line_only_boundary(line_art: ImagePatch) -> np.ndarray:
    """Return the published 1.0.2 Line-only model boundary."""

    return canonical_boundary_from_rgba(line_art.rgba)


def build_line_or_guides_boundary(
    line_art: ImagePatch,
    guides: ImagePatch,
    gap_mask: np.ndarray,
    gap_kind: GapKind,
) -> np.ndarray:
    """Compose canonical Line with the normalized binary Guide boundary.

    Krita's normalized Guide contract is any nonzero alpha, matching detection.
    For a target Guide gap, only its own pixels are removed before composition.
    """

    line_boundary = build_line_only_boundary(line_art)
    guide_boundary = guides.rgba[..., 3] > 0
    if gap_kind is GapKind.GUIDE:
        guide_boundary = guide_boundary.copy()
        guide_boundary[gap_mask > 0] = False
    return line_boundary | guide_boundary


def build_model_tensor(
    images: LayerImages,
    gap: GapRegion,
    size: int = PATCH_SIZE,
    mode: ModelBoundaryMode = ModelBoundaryMode.LINE_ONLY,
) -> tuple[np.ndarray, PatchBounds]:
    """Build an NCHW float32 input under an explicit boundary policy."""

    images.validate()
    _, line_art, guides, gap_mask = build_model_patches(images, gap, size)
    if mode is ModelBoundaryMode.LINE_ONLY:
        boundary = build_line_only_boundary(line_art)
    elif mode is ModelBoundaryMode.LINE_OR_GUIDES:
        boundary = build_line_or_guides_boundary(
            line_art, guides, gap_mask, gap.kind
        )
    else:
        raise ValueError(f"Unsupported model boundary mode: {mode!r}.")
    boundary = boundary.astype(np.float32)
    tensor = np.stack((boundary, gap_mask), axis=0)[None, ...]
    expected = (1, 2, size, size)
    if tensor.shape != expected or tensor.dtype != np.float32:
        raise ValueError(f"Generated invalid model input: {tensor.shape} / {tensor.dtype}.")
    if not np.logical_or(tensor == 0.0, tensor == 1.0).all():
        raise ValueError("Generated model input is not binary.")
    return tensor, line_art.bounds
