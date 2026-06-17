"""Source-image loading helpers for visualization workflows."""

from __future__ import annotations

import os
from collections import OrderedDict

import cv2

from src.utils.flood_fill.core import detect_regions


DEFAULT_SOURCE_CACHE_SIZE = 2


def load_visualization_source(filename: str, line_art_dir: str, colored_dir: str, flood_threshold: int, cache: OrderedDict | dict | None = None, max_cache_size: int = DEFAULT_SOURCE_CACHE_SIZE):
    """Load line art, colored image, and labels using a bounded cache."""
    if max_cache_size < 0:
        raise ValueError(f"max_cache_size must be non-negative, got {max_cache_size}")
    if cache is None:
        cache = OrderedDict()
    if filename in cache:
        source = cache[filename]
        if hasattr(cache, "move_to_end"):
            cache.move_to_end(filename)
        return source

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

    if line_art.shape[:2] != colored_img.shape[:2]:
        colored_img = cv2.resize(
            colored_img,
            (line_art.shape[1], line_art.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        )

    region_labels, _ = detect_regions(line_art, threshold=flood_threshold)
    source = line_art, colored_path, colored_img, region_labels
    if cache is not None and max_cache_size > 0:
        cache[filename] = source
        if hasattr(cache, "move_to_end"):
            cache.move_to_end(filename)
        while len(cache) > max_cache_size:
            if hasattr(cache, "popitem"):
                try:
                    cache.popitem(last=False)
                except TypeError:
                    oldest_key = next(iter(cache))
                    cache.pop(oldest_key, None)
            else:
                break
    return source
