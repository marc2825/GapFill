"""Model inference workflow for nearest-region patch evaluation (+visualization)."""

from __future__ import annotations

import csv
import os
from collections import OrderedDict

import numpy as np
import pandas as pd
import torch
from tqdm import tqdm

from src import config
from src.models.nearest_region import NearestRegionUNet
from src.utils.color_utils import get_weighted_most_frequent_color
from src.utils.patch_utils import centered_crop_bounds, create_region_patches, crop_and_pad, region_centroid, validate_model_crop_size
from src.utils.source_image_utils import load_visualization_source
from src.utils.visualization_io import COLOR_COMPARISON_COLUMNS, create_patch_output_paths, read_region_csv, save_patch_pair, validate_patch_shapes, write_color_summary
from src.utils.visualization_utils import create_visualization_grid


def load_model_for_inference(model_path: str, device: torch.device) -> NearestRegionUNet:
    """Load NearestRegionUNet for inference and switch it to evaluation mode."""
    model = NearestRegionUNet(in_channels=2, out_channels=1).to(device)
    state_dict = torch.load(model_path, map_location=device, weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    return model


def run_model_inference(model, model_input_patch: np.ndarray, device: torch.device) -> np.ndarray:
    """Run inference and return the original (1, 1, H, W) NumPy output."""
    # Convert (H, W, 2) to (1, 2, H, W).
    input_tensor = torch.from_numpy(np.transpose(model_input_patch, (2, 0, 1)).astype(np.float32)).unsqueeze(0).to(device)
    # Implementation of Section 4.2.1 / Figure 6(d): predict the same-color likelihood map.
    with torch.no_grad():
        predicted_tensor = model(input_tensor)
    return predicted_tensor.cpu().numpy()


def run_inference_pipeline(csv_file: str, crop_size: int, line_art_dir: str, colored_dir: str, output_dir: str, model_path: str = str(config.BEST_MODEL_PATH), samples: int | None = None, flood_threshold: int = 128, show_labels: bool = False, save_raw_predictions: bool = False, comparison_crop_size: int | None = None, results_only: bool = False) -> None:
    """Run inference and evaluation, optionally saving raw arrays and visualization PNGs."""
    validate_model_crop_size(crop_size)
    if samples is not None and samples <= 0:
        raise ValueError(f"samples must be positive or None, got {samples}")
    if results_only and save_raw_predictions:
        raise ValueError("save_raw_predictions cannot be enabled when results_only is True")
    if comparison_crop_size is None:
        comparison_crop_size = crop_size
    if not 0 < comparison_crop_size <= crop_size:
        raise ValueError(f"comparison_crop_size must be between 1 and crop_size ({crop_size}), got {comparison_crop_size}")

    paths = create_patch_output_paths(
        output_dir,
        create_input_target_dirs=save_raw_predictions,
        create_prediction_dir=save_raw_predictions,
        create_visualization_dir=not results_only,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not results_only:
        print(f"Using device: {device}")
    model = load_model_for_inference(model_path, device)
    if not results_only:
        print(f"Model loaded from {model_path}")

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

            predicted_nearest_patch = None
            try:
                batched_predicted_nearest_patch = run_model_inference(model, model_input_patch, device)
                if save_raw_predictions:
                    np.save(os.path.join(paths.predictions, base_name + ".npy"), batched_predicted_nearest_patch)
                predicted_nearest_patch = batched_predicted_nearest_patch[0, 0]
            except (RuntimeError, TypeError, ValueError) as error:
                print(f"Error during inference for {filename}: {error}")

            ground_truth_color = None
            predicted_color = None

            if np.any(ground_truth_nearest_patch) and predicted_nearest_patch is not None:
                region_labels_patch = crop_and_pad(region_labels, crop_size, r_start, r_end, c_start, c_end)
                ground_truth_nearest_mask = ground_truth_nearest_patch == 1 if ground_truth_nearest_patch.max() <= 1 else ground_truth_nearest_patch == 255
                ground_truth_color = get_weighted_most_frequent_color(colored_patch, region_labels_patch, ground_truth_nearest_mask)

                if comparison_crop_size == crop_size:
                    comparison_region_labels = region_labels_patch
                    comparison_colored_patch = colored_patch
                    comparison_predicted_nearest_patch = predicted_nearest_patch
                else:
                    patch_center = crop_size // 2
                    comp_r_start, comp_r_end, comp_c_start, comp_c_end = centered_crop_bounds(patch_center, patch_center, comparison_crop_size)
                    comparison_region_labels = crop_and_pad(region_labels_patch, comparison_crop_size, comp_r_start, comp_r_end, comp_c_start, comp_c_end)
                    comparison_colored_patch = crop_and_pad(colored_patch, comparison_crop_size, comp_r_start, comp_r_end, comp_c_start, comp_c_end)
                    comparison_predicted_nearest_patch = crop_and_pad(predicted_nearest_patch, comparison_crop_size, comp_r_start, comp_r_end, comp_c_start, comp_c_end)

                predicted_nearest_probability = comparison_predicted_nearest_patch if comparison_predicted_nearest_patch.max() <= 1 else comparison_predicted_nearest_patch / 255.0
                predicted_color = get_weighted_most_frequent_color(comparison_colored_patch, comparison_region_labels, predicted_nearest_probability)

                match_score = 0
                if ground_truth_color is not None and predicted_color is not None:
                    total_patches_with_colors += 1
                    match_score = int(ground_truth_color == predicted_color)
                    total_match_score += match_score

                color_comparison_writer.writerow([filename, patch_count, ground_truth_color, predicted_color, match_score])

            if not results_only and predicted_nearest_patch is not None:
                visualization_path = os.path.join(paths.visualizations, base_name + "_visualization.png")
                create_visualization_grid(colored_path, model_input_patch, predicted_nearest_patch, ground_truth_nearest_patch, visualization_path, (center_row, center_col), crop_size, ground_truth_color, predicted_color, original_colored=colored_img, show_labels=show_labels)

            patch_count += 1

    write_color_summary(output_dir, paths.summary, paths.color_comparison, patch_count, total_patches_with_colors, total_match_score, artifacts_saved=not results_only)
