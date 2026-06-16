"""Greedy color prediction method (baseline) workflow for nearest-region evaluation (+visualization)."""

from __future__ import annotations

import csv
import os
from collections import OrderedDict

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

from src.utils.color_utils import get_adjacent_pixels_most_frequent_color, get_weighted_most_frequent_color
from src.utils.patch_utils import centered_crop_bounds, create_region_patches, crop_and_pad, region_centroid
from src.utils.source_image_utils import load_visualization_source
from src.utils.visualization_io import COLOR_COMPARISON_COLUMNS, create_patch_output_paths, read_region_csv, save_patch_pair, validate_patch_shapes, write_color_summary
from src.utils.visualization_utils import create_visualization_grid


def run_greedy_pipeline(csv_file: str, crop_size: int, line_art_dir: str, colored_dir: str, output_dir: str, flood_threshold: int = 128, samples: int | None = None, show_labels: bool = False, save_raw_predictions: bool = False, results_only: bool = False) -> None:
    """Run greedy evaluation, optionally saving raw arrays and visualization PNGs."""
    if samples is not None and samples <= 0:
        raise ValueError(f"samples must be positive or None, got {samples}")
    if results_only and save_raw_predictions:
        raise ValueError("save_raw_predictions cannot be enabled when results_only is True")

    paths = create_patch_output_paths(
        output_dir,
        create_input_target_dirs=save_raw_predictions,
        create_prediction_dir=False,
        create_visualization_dir=not results_only,
    )
    df = read_region_csv(csv_file)
    image_cache = OrderedDict()
    patch_count = 0
    total_patches_with_colors = 0
    total_match_score = 0

    with open(paths.color_comparison, "w", newline="") as color_comparison_file:
        color_comparison_writer = csv.writer(color_comparison_file)
        color_comparison_writer.writerow(COLOR_COMPARISON_COLUMNS)

        for _, row in tqdm(df.iterrows(), total=len(df), desc="Evaluating samples"):
            if samples is not None and patch_count >= samples:
                break

            if pd.isnull(row.get("region_id")) or pd.isnull(row.get("nearest_region_id")):
                continue

            filename = row["filename"]
            try:
                target_region_id = int(row["region_id"])
                ground_truth_nearest_region_id = int(row["nearest_region_id"])
            except (TypeError, ValueError, OverflowError):
                continue

            source = load_visualization_source(filename, line_art_dir, colored_dir, flood_threshold, image_cache)
            if source is None:
                continue
            line_art, colored_path, colored_img, region_labels = source

            center_coords = region_centroid(region_labels, target_region_id)
            if center_coords is None:
                continue
            center_row, center_col = center_coords
            r_start, r_end, c_start, c_end = centered_crop_bounds(center_row, center_col, crop_size)
            model_input_patch, ground_truth_nearest_patch = create_region_patches(line_art, region_labels, target_region_id, ground_truth_nearest_region_id, crop_size, flood_threshold, r_start, r_end, c_start, c_end)
            validate_patch_shapes(model_input_patch, ground_truth_nearest_patch, crop_size)

            if not np.any(ground_truth_nearest_patch):
                continue

            colored_patch = crop_and_pad(colored_img, crop_size, r_start, r_end, c_start, c_end)
            is_all_white = np.all(colored_patch == 255) or np.all(colored_patch == [255, 255, 255])
            if is_all_white:
                patch_count += 1
                continue

            base_name = f"{os.path.splitext(filename)[0]}_patch_{patch_count}"
            if save_raw_predictions:
                save_patch_pair(paths, base_name, model_input_patch, ground_truth_nearest_patch)

            region_labels_patch = crop_and_pad(region_labels, crop_size, r_start, r_end, c_start, c_end)
            target_region_patch = model_input_patch[:, :, 1]
            predicted_color, tied_predicted_colors, exact_match_factor = get_adjacent_pixels_most_frequent_color(colored_patch, target_region_patch)

            ground_truth_nearest_mask = ground_truth_nearest_patch == 1 if ground_truth_nearest_patch.max() <= 1 else ground_truth_nearest_patch == 255
            ground_truth_color = get_weighted_most_frequent_color(colored_patch, region_labels_patch, ground_truth_nearest_mask)

            # Previous rule: tied predictions received zero credit.
            # exact_match = 0
            # if len(tied_predicted_colors) == 1 and ground_truth_color == predicted_color:
            #     exact_match = 1

            match_score = exact_match_factor if ground_truth_color in tied_predicted_colors else 0

            color_comparison_writer.writerow([filename, patch_count, ground_truth_color, predicted_color, match_score])
            total_patches_with_colors += 1
            total_match_score += match_score

            if not results_only:
                visualization_path = os.path.join(paths.visualizations, base_name + "_visualization.png")
                predicted_nearest_patch = np.zeros_like(ground_truth_nearest_patch)
                try:
                    create_visualization_grid(colored_path, model_input_patch, predicted_nearest_patch, ground_truth_nearest_patch, visualization_path, (center_row, center_col), crop_size, ground_truth_color, predicted_color, original_colored=colored_img, show_labels=show_labels)
                except (cv2.error, OSError, ValueError) as error:
                    print(f"Error visualizing {base_name}: {error}")

            patch_count += 1

    write_color_summary(output_dir, paths.summary, paths.color_comparison, patch_count, total_patches_with_colors, total_match_score, artifacts_saved=not results_only)
