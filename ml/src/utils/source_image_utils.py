"""Source-image loading helpers for visualization workflows."""

from __future__ import annotations

import os

import cv2

from src.utils.flood_fill.core import detect_regions


def load_visualization_source(filename: str, line_art_dir: str, colored_dir: str, flood_threshold: int, cache: dict):
    """Load line art, colored image, and labels, caching successful results."""
    if filename in cache:
        return cache[filename]

    line_art_path = os.path.join(line_art_dir, filename)
    line_art = cv2.imread(line_art_path, cv2.IMREAD_GRAYSCALE)
    if line_art is None:
        print(f"Could not load {line_art_path}")
        return None

    colored_path = os.path.join(colored_dir, filename)
    if not os.path.exists(colored_path):
        colored_path = os.path.join(colored_dir, os.path.splitext(filename)[0] + ".png")
        if not os.path.exists(colored_path):
            print(f"Could not find colored image for {filename}")
            return None

    colored_img = cv2.imread(colored_path)
    if colored_img is None:
        print(f"Could not load {colored_path}")
        return None

    region_labels, _ = detect_regions(line_art, threshold=flood_threshold)
    cache[filename] = line_art, colored_path, colored_img, region_labels
    return cache[filename]
