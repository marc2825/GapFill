"""Patch manipulation helpers shared by preprocessing and visualization."""

from __future__ import annotations

import cv2
import numpy as np


def validate_model_crop_size(crop_size: int) -> None:
    """Validate the spatial size required by the four-stage U-Net."""
    if crop_size <= 0:
        raise ValueError(f"crop_size must be positive, got {crop_size}")
    if crop_size % 16 != 0:
        raise ValueError(f"crop_size must be a multiple of 16, got {crop_size}")


def augment_patch(image: np.ndarray) -> list[np.ndarray]:
    """Create rotated and flipped copies of a patch."""
    augmented = []

    # 90, 180, 270 degree rotations
    for k in range(1, 4):
        augmented.append(np.rot90(image, k).copy())

    # Horizontal and vertical flips
    augmented.append(np.fliplr(image).copy())
    augmented.append(np.flipud(image).copy())

    # 90 degree rotation + flip
    rotated_90 = np.rot90(image, 1)
    augmented.append(np.fliplr(rotated_90).copy())
    augmented.append(np.flipud(rotated_90).copy())

    return augmented


def centered_crop_bounds(center_row: int, center_col: int, crop_size: int) -> tuple[int, int, int, int]:
    """Return an unclipped square crop window centered on the given coordinates."""
    r_start = center_row - crop_size // 2
    c_start = center_col - crop_size // 2
    return r_start, r_start + crop_size, c_start, c_start + crop_size


def region_centroid(region_labels: np.ndarray, region_id: int) -> tuple[int, int] | None:
    """Return the integer row/column centroid of a labeled region."""
    coords = np.column_stack(np.where(region_labels == region_id))
    if coords.size == 0:
        return None
    centroid = np.mean(coords, axis=0).astype(int)
    return int(centroid[0]), int(centroid[1])


def crop_and_pad(image: np.ndarray, crop_size: int, r_start: int, r_end: int, c_start: int, c_end: int) -> np.ndarray:
    """Crop an image and pad only on sides where the requested window exceeds it."""
    height, width = image.shape[:2]
    r0, c0 = max(r_start, 0), max(c_start, 0)
    r1, c1 = min(r_end, height), min(c_end, width)
    patch = image[r0:r1, c0:c1]

    # Previous rule: distribute all missing pixels evenly on both sides. (insufficient at corners)
    # pad_vert = crop_size - patch.shape[0]
    # pad_horiz = crop_size - patch.shape[1]
    # top, bottom = pad_vert // 2, pad_vert - (pad_vert // 2)
    # left, right = pad_horiz // 2, pad_horiz - (pad_horiz // 2)

    top = max(0, -r_start)
    bottom = max(0, r_end - height)
    left = max(0, -c_start)
    right = max(0, c_end - width)

    patch = cv2.copyMakeBorder(
        patch,
        top,
        bottom,
        left,
        right,
        borderType=cv2.BORDER_CONSTANT,
        value=0,
    )
    if patch.shape[:2] != (crop_size, crop_size):
        raise ValueError(f"Expected patch size {(crop_size, crop_size)}, got {patch.shape[:2]}")
    return patch


def create_region_patches(line_art: np.ndarray, region_labels: np.ndarray, region_id: int, nearest_region_id: int, crop_size: int, flood_threshold: int, r_start: int, r_end: int, c_start: int, c_end: int) -> tuple[np.ndarray, np.ndarray]:
    """Create the two-channel model input and nearest-region target patch."""
    # Figure 6(b) / ① Line art mask: binarize (line=1, background=0).
    _, line_mask = cv2.threshold(line_art, flood_threshold, 1, cv2.THRESH_BINARY_INV)
    line_patch = crop_and_pad(line_mask, crop_size, r_start, r_end, c_start, c_end)

    # Figure 6(c) / ② Target region mask: (region_labels == region_id → 1, else 0).
    target_region_mask = (region_labels == region_id).astype(np.uint8)
    region_patch = crop_and_pad(target_region_mask, crop_size, r_start, r_end, c_start, c_end)

    # Figure 7(d) / ③ Nearest region mask: (region_labels == nearest_region_id → 1, else 0).
    nearest_region_mask = (region_labels == nearest_region_id).astype(np.uint8)
    nearest_patch = crop_and_pad(nearest_region_mask, crop_size, r_start, r_end, c_start, c_end)

    # Section 4.2.1 / Figure 6(b,c): U-Net input is the 2-channel stack of
    input_patch = np.stack([line_patch, region_patch], axis=-1)
    return input_patch, nearest_patch
