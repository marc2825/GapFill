"""Compute and analyze nearest same-color regions."""

from __future__ import annotations

import os
import signal
from collections import Counter, defaultdict

import cv2
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from tqdm import tqdm

from ..data_loader import RegionDataLoader
from .core import annotate_region_labels, detect_regions
from .timeout import SampleTimeoutError, raise_sample_timeout


def _collect_region_info(region_labels, painted_image):
    """
    Collect coords/size/representative color for each non-background label in one scan.

    Args:
        region_labels: Region label map obtained by detect_regions (background is 0)
        painted_image: Painted image (grayscale or color)

    Returns:
        dict: Mapping from region label to region metadata. Each value contains:
              - "coords": NumPy array of (row, col) pixel coordinates
              - "size": Number of pixels in the region
              - "color": Most frequent color in the region from painted_image
    """

    coords_by_label = defaultdict(list)
    color_counts_by_label = defaultdict(Counter)
    # Mode color is more robust, but the first sampled color (previous rule) is sufficient when misalignment between line art and colored images is unlikely.
    # colors_by_label = {}
    ys, xs = np.where(region_labels != 0)

    if painted_image.ndim == 2:
        for y, x in zip(ys, xs):
            label = int(region_labels[y, x])
            coords_by_label[label].append((y, x))
            color = int(painted_image[y, x])
            color_counts_by_label[label][color] += 1
            # colors_by_label.setdefault(label, color)
    else:
        for y, x in zip(ys, xs):
            label = int(region_labels[y, x])
            coords_by_label[label].append((y, x))
            color = tuple(int(channel) for channel in painted_image[y, x]) # assume no alpha channel
            color_counts_by_label[label][color] += 1
            # colors_by_label.setdefault(label, color)

    regions_info = {}
    for label in sorted(coords_by_label):
        coords = np.asarray(coords_by_label[label], dtype=np.int32)
        representative_color = color_counts_by_label[label].most_common(1)[0][0]
        regions_info[label] = {
            "coords": coords,
            "size": coords.shape[0],
            "color": representative_color,
            # "color": colors_by_label[label],
        }

    return regions_info


def compute_nearest_same_color(region_labels, painted_image, size_threshold):
    """
    From the region label map obtained by detect_regions and the painted image painted_image,
    for each region with size <= size_threshold, calculate the L1 (Manhattan) distance
    to the nearest region that has the same color and a size > size_threshold.

    Args:
        region_labels: Region label map obtained by detect_regions (background is 0)
        painted_image: Painted image (grayscale or color)
        size_threshold: Upper limit for target gap size (regions <= size_threshold are "small regions (potential gaps)";
                        "large regions" are regions with size > size_threshold)

    Returns:
        results_df: DataFrame containing the following information for each target region:
                    'region_id', 'color', 'size',
                    'nearest_region_id', 'min_L1_distance'
    """
    # Implementation of Appendix A.3 / Figure 19(b):
    # for each small region, find the nearest larger region with the same color and record the minimum L1 pixel distance.
    regions_info = _collect_region_info(region_labels, painted_image)

    small_regions = {}
    large_regions = {}
    for label, info in regions_info.items():
        if info["size"] <= size_threshold:
            small_regions[label] = info
        else:
            large_regions[label] = info

    # Group large regions by color
    large_groups = {}
    for label, info in large_regions.items():
        color = info["color"]
        large_groups.setdefault(color, []).append(label)

    # Build one KDTree per color from all pixels of large same-color regions.
    large_trees = {}
    for color, labels in large_groups.items():
        coords_list = []
        label_list = []
        for cand_label in labels:
            coords = large_regions[cand_label]["coords"]
            coords_list.append(coords)
            label_list.append(np.full(coords.shape[0], cand_label, dtype=np.int32))

        all_coords = np.concatenate(coords_list, axis=0)
        all_labels = np.concatenate(label_list, axis=0)
        large_trees[color] = {"tree": cKDTree(all_coords), "labels": all_labels}

    results = []
    # Target is small regions only (size <= size_threshold)
    for label, info in small_regions.items():
        color = info["color"]
        if color not in large_trees:
            results.append(
                {
                    "region_id": label,
                    "color": color,
                    "size": info["size"],
                    "nearest_region_id": None,
                    "min_L1_distance": None,
                }
            )
            continue

        coords_small = info["coords"]
        tree_info = large_trees[color]
        distances, indices = tree_info["tree"].query(coords_small, k=1, p=1) # L1 distance
        best_pos = int(np.argmin(distances))
        min_distance = float(distances[best_pos])
        nearest_label = int(tree_info["labels"][indices[best_pos]])

        ## Previous brute-force implementation:
        ## Sped up with KDTree (another option is multi source BFS etc.)
        # min_distance = np.inf
        # nearest_label = None
        # for cand_label in large_groups[color]:
        #     coords_large = large_regions[cand_label]["coords"]
        #     distances = cdist(coords_small, coords_large, metric="cityblock")
        #     current_min = distances.min()
        #     if current_min < min_distance:
        #         min_distance = current_min
        #         nearest_label = cand_label

        results.append(
            {
                "region_id": label,
                "color": color,
                "size": info["size"],
                "nearest_region_id": nearest_label,
                "min_L1_distance": min_distance,
            }
        )

    results_df = pd.DataFrame(results)
    return results_df


def analyze_nearest_same_color(
    colored_dir,
    line_art_dir,
    output_dir,
    num_samples=None,
    flood_threshold=128,
    region_size_threshold=10,
    timeout_seconds=30,
    save_raw_data=True,
):
    """
    For each sample in the entire dataset, detect regions from line art and calculate
    the color of each region and the shortest L1 distance (Manhattan distance)
    between same-color regions from the painted image.

    Args:
        data_dir: Dataset directory (must have line_art and colored subdirectories)
        output_dir: Output directory (saves result CSVs and visualization images)
        num_samples: Maximum number of samples to analyze. If None, analyze all samples.
        flood_threshold: Threshold for binarizing line art
        region_size_threshold: Upper limit for target region size (only regions <= x are targeted)
        timeout_seconds: Processing timeout in seconds for each sample
        save_raw_data: Whether to save results as CSV (if True, saves all results together)

    Returns:
        DataFrame summarizing analysis results across all samples
    """
    os.makedirs(output_dir, exist_ok=True)

    if save_raw_data:
        raw_data_dir = os.path.join(output_dir, "raw_data")
        os.makedirs(raw_data_dir, exist_ok=True)

    # Output directory for combined images: line art with region numbers alongside colored image
    combined_dir = os.path.join(output_dir, "combined")
    os.makedirs(combined_dir, exist_ok=True)

    data_loader = RegionDataLoader(line_art_dir=line_art_dir, colored_dir=colored_dir)
    sample_count = len(data_loader) if num_samples is None else min(num_samples, len(data_loader))

    all_nearest_data = []
    signal.signal(signal.SIGALRM, raise_sample_timeout)

    for i in tqdm(range(sample_count), desc="Analyzing nearest same color"):
        signal.alarm(timeout_seconds)
        filename = "<unknown>"
        try:
            sample = data_loader[i]
            line_art_np = sample["line_art_np"]
            colored_np = sample["colored_np"]
            filename = sample["filename"]

            # Implementation of Appendix A.1 and A.2:
            # region counts and size distributions are derived from this per-frame connected-component labeling.
            region_labels, _ = detect_regions(line_art_np, threshold=flood_threshold)

            colored_bgr = cv2.cvtColor(colored_np, cv2.COLOR_RGB2BGR)
            annotated_line_art = annotate_region_labels(line_art_np, region_labels)
            try:
                combined_image = np.hstack([annotated_line_art, colored_bgr])
            except ValueError:
                # Handle case where heights (number of rows) do not match
                height1 = annotated_line_art.shape[0]
                height2 = colored_bgr.shape[0]
                if height1 != height2:
                    min_height = min(height1, height2)
                    annotated_line_art_cropped = annotated_line_art[:min_height, :]
                    colored_bgr_cropped = colored_bgr[:min_height, :]
                    combined_image = np.hstack([annotated_line_art_cropped, colored_bgr_cropped])
                    print("Warning: Image heights differed; cropped to minimum height.")
                else:
                    raise

            cv2.imwrite(os.path.join(combined_dir, f"{filename}_combined.png"), combined_image)

            df_nearest = compute_nearest_same_color(region_labels, colored_np, size_threshold=region_size_threshold)
            if df_nearest.empty:
                continue

            # Add sample name and append to results
            df_nearest["filename"] = filename
            all_nearest_data.append(df_nearest)

        except SampleTimeoutError:
            print(f"Sample {filename} skipped due to timeout")
            continue
        finally:
            signal.alarm(0)

    if all_nearest_data:
        result_df = pd.concat(all_nearest_data, ignore_index=True)
        output_csv = os.path.join(output_dir, "nearest_same_color_analysis.csv")
        result_df.to_csv(output_csv, index=False)
        print(f"Nearest same color analysis results saved to {output_csv}")
        return result_df

    print("No nearest same color results to save.")
    return pd.DataFrame()
