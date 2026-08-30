from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from .colors import UNASSIGNED_MATERIAL_RGB, modal_rgb
from .patches import PATCH_SIZE, PatchBounds, canonical_boundary_from_rgba
from .types import Rgb

DEFAULT_COLOR_TOLERANCE = 30


@dataclass(frozen=True)
class RegionSelection:
    label: int
    mean_probability: float
    rgb: Rgb
    pixel_indices: tuple[int, ...]


def build_line_region_labels(line_art: np.ndarray) -> np.ndarray:
    """Label full-image Line-fill regions in first-row-major order."""

    boundary = canonical_boundary_from_rgba(line_art)
    height, width = boundary.shape
    labels = np.zeros((height, width), dtype=np.int32)
    next_label = 0
    for start_y in range(height):
        for start_x in range(width):
            if boundary[start_y, start_x] or labels[start_y, start_x] != 0:
                continue
            next_label += 1
            labels[start_y, start_x] = next_label
            queue = deque([(start_x, start_y)])
            while queue:
                x, y = queue.popleft()
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    if boundary[ny, nx] or labels[ny, nx] != 0:
                        continue
                    labels[ny, nx] = next_label
                    queue.append((nx, ny))
    return labels


def extract_label_patch(
    labels: np.ndarray, bounds: PatchBounds, size: int = PATCH_SIZE
) -> np.ndarray:
    if labels.ndim != 2 or not np.issubdtype(labels.dtype, np.integer):
        raise ValueError("Semantic labels must be a two-dimensional integer map.")
    patch = np.zeros((size, size), dtype=np.int32)
    if bounds.source_width and bounds.source_height:
        source = labels[
            bounds.source_y : bounds.source_y + bounds.source_height,
            bounds.source_x : bounds.source_x + bounds.source_width,
        ]
        y0, x0 = bounds.destination_y, bounds.destination_x
        patch[y0 : y0 + bounds.source_height, x0 : x0 + bounds.source_width] = source
    return patch


def select_region_prediction(
    coloring: np.ndarray,
    labels: np.ndarray,
    probabilities: np.ndarray,
) -> RegionSelection:
    """Select a painted Line-derived region and its D-06 modal RGB."""

    if labels.shape != probabilities.shape or labels.shape != coloring.shape[:2]:
        raise ValueError("Labels, probabilities, and coloring patch must match.")
    if coloring.dtype != np.uint8 or coloring.ndim != 3 or coloring.shape[2] != 4:
        raise ValueError("Coloring patch must use uint8 RGBA pixels.")
    if not np.issubdtype(labels.dtype, np.integer) or np.any(labels < 0):
        raise ValueError("Semantic labels must be nonnegative integers.")
    if not np.issubdtype(probabilities.dtype, np.floating):
        raise ValueError("Model probabilities must be floating point.")
    if not np.isfinite(probabilities).all():
        raise ValueError("Model probabilities must all be finite.")
    if np.any(probabilities < 0.0) or np.any(probabilities > 1.0):
        raise ValueError("Model probabilities must be within [0, 1].")

    ordered_labels: list[int] = []
    seen: set[int] = set()
    for raw_label in labels.reshape(-1):
        label = int(raw_label)
        if label > 0 and label not in seen:
            seen.add(label)
            ordered_labels.append(label)

    best_label = 0
    best_mean = float("-inf")
    for label in ordered_labels:
        mask = labels == label
        if not np.any(mask & (coloring[..., 3] > 0)):
            continue
        # The model was trained on complete semantic-region masks. Transparent
        # gap pixels therefore participate in this mean, but never in RGB mode.
        mean = float(np.asarray(probabilities[mask], dtype=np.float64).mean())
        if mean > best_mean:
            best_mean = mean
            best_label = label

    if best_label == 0:
        raise ValueError("No painted semantic region is available for prediction.")
    selected = labels == best_label
    painted = selected & (coloring[..., 3] > 0)
    rgb = modal_rgb(coloring[painted])
    if rgb is None:
        raise ValueError("The selected semantic region has no painted color.")
    return RegionSelection(
        label=best_label,
        mean_probability=best_mean,
        rgb=rgb,
        pixel_indices=tuple(int(index) for index in np.flatnonzero(selected)),
    )


def segment_colored_regions(
    coloring: np.ndarray,
    line_art: np.ndarray,
    guides: np.ndarray,
    tolerance: int = DEFAULT_COLOR_TOLERANCE,
) -> tuple[np.ndarray, int]:
    if coloring.shape != line_art.shape or coloring.shape != guides.shape:
        raise ValueError("Postprocessing patch dimensions must match.")
    height, width = coloring.shape[:2]
    blocked = (coloring[..., 3] == 0) | (line_art[..., 3] > 0) | (guides[..., 3] > 0)
    labels = np.zeros((height, width), dtype=np.int32)
    region_count = 0
    for start_y in range(height):
        for start_x in range(width):
            if blocked[start_y, start_x] or labels[start_y, start_x]:
                continue
            region_count += 1
            target = coloring[start_y, start_x, :3].astype(np.int16)
            labels[start_y, start_x] = region_count
            queue = deque([(start_x, start_y)])
            while queue:
                x, y = queue.pop()
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    if blocked[ny, nx] or labels[ny, nx]:
                        continue
                    difference = np.abs(coloring[ny, nx, :3].astype(np.int16) - target).sum()
                    if difference <= tolerance:
                        labels[ny, nx] = region_count
                        queue.append((nx, ny))
    return labels, region_count


def select_region_color(
    coloring: np.ndarray,
    labels: np.ndarray,
    region_count: int,
    probabilities: np.ndarray,
    fallback: Rgb = UNASSIGNED_MATERIAL_RGB,
) -> Rgb:
    if region_count <= 0:
        return fallback
    try:
        return select_region_prediction(coloring, labels, probabilities).rgb
    except ValueError:
        return fallback


def select_legacy_region_color(
    coloring: np.ndarray,
    labels: np.ndarray,
    region_count: int,
    probabilities: np.ndarray,
    fallback: Rgb = UNASSIGNED_MATERIAL_RGB,
) -> Rgb:
    """Reproduce the frozen Phase 2 colored-component characterization."""

    if labels.shape != probabilities.shape or labels.shape != coloring.shape[:2]:
        raise ValueError("Labels, probabilities, and coloring patch must match.")
    best_label = 0
    best_mean = float("-inf")
    finite = np.isfinite(probabilities)
    for label in range(1, region_count + 1):
        mask = (labels == label) & finite
        if not mask.any():
            continue
        mean = float(probabilities[mask].mean())
        if mean > best_mean:
            best_mean = mean
            best_label = label
    if best_label == 0:
        return fallback
    pixels = coloring[labels == best_label]
    packed = (
        (pixels[:, 0].astype(np.uint32) << 16)
        | (pixels[:, 1].astype(np.uint32) << 8)
        | pixels[:, 2].astype(np.uint32)
    )
    values, counts = np.unique(packed, return_counts=True)
    value = int(values[int(np.argmax(counts))])
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)
