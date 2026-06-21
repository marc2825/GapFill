from __future__ import annotations

from collections import deque

import numpy as np

from .colors import UNASSIGNED_MATERIAL_RGB, modal_rgb
from .types import Rgb

DEFAULT_COLOR_TOLERANCE = 30


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
    if labels.shape != probabilities.shape or labels.shape != coloring.shape[:2]:
        raise ValueError("Labels, probabilities, and coloring patch must match.")
    if region_count <= 0:
        return fallback

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
    return modal_rgb(coloring[labels == best_label]) or fallback
