"""Image composition helpers for patch visualizations."""

from __future__ import annotations

import os

import cv2
import numpy as np

from src.utils.color_utils import get_weighted_most_frequent_color
from src.utils.flood_fill.core import detect_regions
from src.utils.patch_utils import centered_crop_bounds, crop_and_pad


def prepare_mask(mask: np.ndarray) -> np.ndarray:
    """Convert a binary/probability mask to a three-channel uint8 image."""
    if mask.max() <= 1:
        mask = (mask * 255).astype(np.uint8)
    else:
        mask = mask.astype(np.uint8)
    if len(mask.shape) == 2:
        mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    return mask


def resize_mask_to_image(mask: np.ndarray, image: np.ndarray) -> np.ndarray:
    """Resize a mask to an image using nearest-neighbor interpolation (Normally unnecessary, but kept as a safeguard)."""
    if mask.dtype == bool:
        mask = mask.astype(np.uint8)
    if mask.shape[0] != image.shape[0] or mask.shape[1] != image.shape[1]:
        return cv2.resize(mask, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    return mask


def mask_overlay(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Keep image pixels selected by a binary mask and black out the rest."""
    overlay = image.copy()
    for channel in range(3):
        overlay[:, :, channel] = overlay[:, :, channel] * mask
    return overlay


def resize_images_to_common_size(images: list[np.ndarray]) -> list[np.ndarray]:
    """Resize images to their shared maximum height and width."""
    max_height = max(image.shape[0] for image in images)
    max_width = max(image.shape[1] for image in images)
    resized = []
    for image in images:
        if image.shape[0] != max_height or image.shape[1] != max_width:
            resized.append(cv2.resize(image, (max_width, max_height)))
        else:
            resized.append(image)
    return resized


def compose_visualization_grid(images: list[np.ndarray]) -> np.ndarray:
    """Arrange nine images, supplied in display order, into a 3x3 grid."""
    resized = resize_images_to_common_size(images)
    top_row = cv2.hconcat(resized[0:3])
    middle_row = cv2.hconcat(resized[3:6])
    bottom_row = cv2.hconcat(resized[6:9])
    return cv2.vconcat([top_row, middle_row, bottom_row])


def add_image_label(image: np.ndarray, label: str) -> np.ndarray:
    """Draw a small label in the top-left corner of an image."""
    labeled = image.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 1
    base_width = cv2.getTextSize(label, font, 1.0, thickness)[0][0]
    font_scale = min(0.35, max(0.15, (image.shape[1] - 6) / max(base_width, 1)))
    (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
    cv2.rectangle(labeled, (0, 0), (text_width + 5, text_height + baseline + 5), (0, 0, 0), -1)
    cv2.putText(labeled, label, (3, text_height + 2), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    return labeled


def create_visualization_grid(colored_path: str, input_patch: np.ndarray, predicted_nearest_patch: np.ndarray, ground_truth_patch: np.ndarray | None = None, save_path: str | None = None, center_coords: tuple[int, int] | None = None, crop_size: int | None = None, gt_color=None, pred_color=None, original_colored: np.ndarray | None = None, show_labels: bool = False):
    """Create the existing nine-panel patch visualization."""
    if input_patch.ndim != 3 or input_patch.shape[2] != 2:
        raise ValueError(f"Expected input_patch shape (H, W, 2), got {input_patch.shape}")
    if predicted_nearest_patch.ndim != 2:
        raise ValueError(f"Expected predicted_nearest_patch shape (H, W), got {predicted_nearest_patch.shape}")
    if ground_truth_patch is not None and ground_truth_patch.ndim != 2:
        raise ValueError(f"Expected ground_truth_patch shape (H, W), got {ground_truth_patch.shape}")

    if original_colored is None:
        original_colored = cv2.imread(colored_path)
    if original_colored is None:
        raise ValueError(f"Colored image not found at: {colored_path}")

    if center_coords is not None and crop_size is not None:
        center_row, center_col = center_coords
        r_start, r_end, c_start, c_end = centered_crop_bounds(center_row, center_col, crop_size)
        colored = crop_and_pad(original_colored, crop_size, r_start, r_end, c_start, c_end)
    else:
        missing = [name for name, value in (("center_coords", center_coords), ("crop_size", crop_size)) if value is None]
        print(f"Skipping visualization for {colored_path}: missing {', '.join(missing)}")
        return

    line_art_mask = input_patch[:, :, 0]
    target_region_mask = input_patch[:, :, 1]
    line_art_vis = prepare_mask(line_art_mask)
    target_region_vis = prepare_mask(target_region_mask)
    predicted_nearest_vis = prepare_mask(predicted_nearest_patch)
    ground_truth_vis = prepare_mask(ground_truth_patch) if ground_truth_patch is not None else np.zeros_like(predicted_nearest_vis)

    target_mask_resized = resize_mask_to_image(target_region_mask, colored)

    ground_truth_overlay = np.zeros_like(colored)
    if ground_truth_patch is not None:
        ground_truth_overlay = mask_overlay(colored, resize_mask_to_image(ground_truth_patch, colored))

    predicted_nearest_mask_resized = resize_mask_to_image(predicted_nearest_patch, colored)
    predicted_nearest_overlay = mask_overlay(colored, predicted_nearest_mask_resized)

    gt_most_frequent_color_image = np.zeros_like(colored)
    gt_most_frequent_color_image[:] = gt_color

    line_art_gray = cv2.cvtColor(line_art_vis, cv2.COLOR_BGR2GRAY)
    region_labels, _ = detect_regions(line_art_gray, threshold=128)
    predicted_nearest_mask_prob = predicted_nearest_patch if predicted_nearest_patch.max() <= 1 else predicted_nearest_patch / 255.0
    predicted_nearest_mask_prob_resized = cv2.resize(predicted_nearest_mask_prob, (colored.shape[1], colored.shape[0]), interpolation=cv2.INTER_LINEAR)
    pred_most_frequent_color = pred_color
    if pred_color is None:
        pred_most_frequent_color = get_weighted_most_frequent_color(colored, region_labels, predicted_nearest_mask_prob_resized)
    pred_most_frequent_color_image = np.zeros_like(colored)
    pred_most_frequent_color_image[:] = pred_most_frequent_color

    colored_highlighted = colored.copy()
    colored_highlighted[target_mask_resized > 0] = [0, 255, 0]
    line_art_with_overlay = line_art_vis.copy()
    line_art_with_overlay[target_mask_resized > 0] = [0, 255, 0]

    images = [
        colored_highlighted,
        line_art_with_overlay,
        target_region_vis,
        predicted_nearest_vis,
        predicted_nearest_overlay,
        pred_most_frequent_color_image,
        ground_truth_vis,
        ground_truth_overlay,
        gt_most_frequent_color_image,
    ]
    if show_labels:
        labels = ["Colored + target", "Line art + target", "Target mask", "Predicted mask", "Predicted overlay", "Predicted color", "GT mask", "GT overlay", "GT color"]
        images = [add_image_label(image, label) for image, label in zip(images, labels)]

    grid = compose_visualization_grid(images)

    if save_path is not None:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        cv2.imwrite(save_path, grid)
        print(f"Visualization saved to {save_path}")

    if save_path is None:
        cv2.imshow("Enhanced Visualization", grid)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return grid
