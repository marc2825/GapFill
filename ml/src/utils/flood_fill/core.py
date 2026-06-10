"""Core flood-fill region utility functions."""

from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage


def detect_regions(line_art, threshold=128):
    """
    Detect connected fillable regions from line art using thresholding and connected-component labeling (same as BFS/DFS-based).

    Args:
        line_art: Grayscale line art image (NumPy array)
        threshold: Threshold value for treating pixels as lines

    Returns:
        region_labels: Label map of regions
        num_regions: Number of detected regions
    """
    # Appendix A.1 and A.2 both start from this segmentation step:
    # count connected enclosed regions per frame, then measure each region's size in pixels.
    # Binarize (make lines black(0), background white(255))
    _, binary = cv2.threshold(line_art, threshold, 255, cv2.THRESH_BINARY)

    region_labels, num_regions = ndimage.label(binary)

    return region_labels, num_regions


def annotate_region_labels(line_art, region_labels):
    """
    Generate an image with region numbers drawn on the line art image.

    Args:
        line_art: Grayscale or color line art image (NumPy array)
        region_labels: Region label map obtained by detect_regions

    Returns:
        annotated: BGR image with region numbers drawn
    """
    # This annotated view corresponds to Figure 18(a): line art overlaid with region IDs (random colors).
    if len(line_art.shape) == 2:
        annotated = cv2.cvtColor(line_art, cv2.COLOR_GRAY2BGR)
    else:
        annotated = line_art.copy()

    unique_labels = np.unique(region_labels)
    for label in unique_labels:
        if label == 0:  # Skip background
            continue

        coords = np.column_stack(np.where(region_labels == label))
        if coords.size == 0:
            continue

        centroid = np.mean(coords, axis=0).astype(int)
        cv2.putText(
            annotated,
            str(label),
            (centroid[1], centroid[0]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )
    return annotated
