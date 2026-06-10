"""Output helpers shared by visualization workflows."""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd


COLOR_COMPARISON_COLUMNS = ("filename", "patch_id", "gt_color", "pred_color", "match_score")
REQUIRED_REGION_COLUMNS = {"filename", "region_id", "nearest_region_id"}


@dataclass(frozen=True)
class PatchOutputPaths:
    inputs: str
    targets: str
    predictions: str
    visualizations: str
    color_comparison: str
    summary: str


def create_patch_output_paths(output_dir: str, create_input_target_dirs: bool = False, create_prediction_dir: bool = False, create_visualization_dir: bool = True) -> PatchOutputPaths:
    """Create and return the output paths used by patch visualization workflows."""
    os.makedirs(output_dir, exist_ok=True)
    inputs_dir = os.path.join(output_dir, "inputs")
    targets_dir = os.path.join(output_dir, "targets")
    predictions_dir = os.path.join(output_dir, "predictions")
    visualizations_dir = os.path.join(output_dir, "visualizations")
    if create_input_target_dirs:
        os.makedirs(inputs_dir, exist_ok=True)
        os.makedirs(targets_dir, exist_ok=True)
    if create_prediction_dir:
        os.makedirs(predictions_dir, exist_ok=True)
    if create_visualization_dir:
        os.makedirs(visualizations_dir, exist_ok=True)
    return PatchOutputPaths(
        inputs=inputs_dir,
        targets=targets_dir,
        predictions=predictions_dir,
        visualizations=visualizations_dir,
        color_comparison=os.path.join(output_dir, "color_comparison.csv"),
        summary=os.path.join(output_dir, "color_summary.txt"),
    )


def read_region_csv(csv_file: str) -> pd.DataFrame:
    """Read a region CSV and validate the columns used by visualization workflows."""
    df = pd.read_csv(csv_file)
    missing_columns = REQUIRED_REGION_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns in CSV: {sorted(missing_columns)}")
    return df


def validate_patch_shapes(input_patch: np.ndarray, nearest_patch: np.ndarray, crop_size: int) -> None:
    """Validate the model input and target shapes before saving or inference."""
    expected_input_shape = (crop_size, crop_size, 2)
    expected_target_shape = (crop_size, crop_size)
    if input_patch.shape != expected_input_shape:
        raise ValueError(f"Unexpected input_patch shape: {input_patch.shape}")
    if nearest_patch.shape != expected_target_shape:
        raise ValueError(f"Unexpected nearest_patch shape: {nearest_patch.shape}")


def save_patch_pair(paths: PatchOutputPaths, base_name: str, input_patch: np.ndarray, nearest_patch: np.ndarray) -> None:
    """Save one model input patch and its nearest-region target."""
    np.save(os.path.join(paths.inputs, base_name + ".npy"), input_patch)
    np.save(os.path.join(paths.targets, base_name + ".npy"), nearest_patch)


def write_color_summary(output_dir: str, summary_path: str, color_comparison_path: str, patch_count: int, total_patches_with_colors: int, total_match_score: float, artifacts_saved: bool = True) -> None:
    """Print and save the color-comparison summary."""
    match_score_rate = total_match_score / total_patches_with_colors * 100 if total_patches_with_colors > 0 else 0
    count_label = "Total patches" if artifacts_saved else "Evaluated samples"

    print(f"{count_label}: {patch_count}")
    print("Color comparison summary:")
    print(f"  - Color match score: {match_score_rate:.2f}% ({total_match_score}/{total_patches_with_colors})")
    print(f"  - Results saved to {color_comparison_path}")

    with open(summary_path, "w") as summary_file:
        summary_file.write("Color comparison summary:\n")
        summary_file.write(f"  - {count_label}: {patch_count}\n")
        summary_file.write(f"  - Patches with valid colors: {total_patches_with_colors}\n")
        summary_file.write(f"  - Color match score: {match_score_rate:.2f}% ({total_match_score}/{total_patches_with_colors})\n")
