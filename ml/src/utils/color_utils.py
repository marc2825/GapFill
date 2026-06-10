"""Color selection helpers shared by inference and visualization."""

from __future__ import annotations

import random
from collections import Counter

import cv2
import numpy as np


def get_weighted_most_frequent_color(colored_img: np.ndarray, region_labels: np.ndarray, mask_prob: np.ndarray):
    """Return the representative BGR color of the region with the highest mean mask probability."""
    # Implementation of Section 4.2.1 / Figure 6(e):
    # Choose the painted region whose average predicted likelihood is highest, then return that region's representative color.
    unique_labels = np.unique(region_labels)
    region_weights = {}
    region_colors = {}

    for label in unique_labels:
        region_mask = region_labels == label
        region_area = np.sum(region_mask)
        region_pixels = colored_img[region_mask]
        if len(region_pixels) == 0:
            continue

        # Get the most frequent color of the region instead of the average.
        color_counter = Counter(tuple(int(channel) for channel in pixel) for pixel in region_pixels)
        region_colors[label] = max(color_counter.items(), key=lambda item: item[1])[0]
        mask_in_region = mask_prob[region_mask]
        region_weights[label] = np.sum(mask_in_region) / region_area if region_area > 0 else 0

    max_weight = -1
    best_label = None
    for label, weight in region_weights.items():
        if weight > max_weight:
            max_weight = weight
            best_label = label

    if best_label is not None and best_label in region_colors:
        return region_colors[best_label]
    return (0, 0, 0)


def get_adjacent_pixels_most_frequent_color(colored_img: np.ndarray, region_mask: np.ndarray):
    """
    Get the most frequent BGR color of pixels adjacent (8-neighbor) to the target region.

    Returns the randomly selected tied BGR color, all tied colors, and 1 / tie count.
    """
    # Create adjacent mask using an 8-neighbor one-pixel dilation.
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(region_mask.astype(np.uint8), kernel, iterations=1)
    adjacent_mask = (dilated > 0) & (region_mask == 0)

    if not np.any(adjacent_mask):
        return (0, 0, 0), [(0, 0, 0)], 0.0

    adjacent_pixels = colored_img[adjacent_mask]

    counter = Counter(tuple(int(channel) for channel in pixel) for pixel in adjacent_pixels)
    max_count = max(counter.values())
    tied_colors = [color for color, count in counter.items() if count == max_count]

    selected_color = random.choice(tied_colors)
    exact_match_factor = 1.0 / len(tied_colors)
    return selected_color, tied_colors, exact_match_factor
