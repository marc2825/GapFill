"""Patch-generation pipeline for HDF5 or NPY training data."""

from __future__ import annotations

import os
from contextlib import ExitStack
from glob import glob

import cv2
import h5py
import numpy as np
import pandas as pd
from tqdm import tqdm

from src import config
from src.utils.flood_fill.core import detect_regions
from src.utils.patch_utils import augment_patch, centered_crop_bounds, create_region_patches, region_centroid, validate_model_crop_size


def create_training_patches(csv_file, crop_size, line_art_dir, output_dir, flood_threshold=128, augment=True, use_hdf5=config.USE_HDF5, train_val_split=config.TRAIN_VAL_SPLIT, seed=0):
    """
    Create training patches based on a CSV file and save them as HDF5 or NPY files.

    Source images are split into train/validation sets before patch generation.
    Augmentation is applied only to training patches.
    """
    # Implementation of Section 4.2.2 / Figure 7(c,d):
    validate_model_crop_size(crop_size)
    if not 0.0 < train_val_split < 1.0:
        raise ValueError(f"train_val_split must be between 0 and 1, got {train_val_split}")
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV file not found: {csv_file}")
    if not os.path.isdir(line_art_dir):
        raise FileNotFoundError(f"line_art_dir not found: {line_art_dir}")

    df = pd.read_csv(csv_file)
    required_columns = {"filename", "region_id", "nearest_region_id"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns in CSV: {sorted(missing_columns)}")

    filenames = df["filename"].dropna().unique().tolist()
    if len(filenames) < 2:
        raise ValueError(f"At least 2 source images are required for train/validation split, got {len(filenames)}")
    shuffled_filenames = np.random.default_rng(seed).permutation(filenames).tolist()
    train_image_count = int(train_val_split * len(shuffled_filenames))
    if train_image_count == 0 or train_image_count == len(shuffled_filenames):
        raise ValueError(f"train_val_split={train_val_split} produces an empty train or validation set for {len(filenames)} images")
    train_filenames = set(shuffled_filenames[:train_image_count])

    os.makedirs(output_dir, exist_ok=True)

    with ExitStack() as stack:
        output_paths = {}
        if use_hdf5:
            datasets = {}
            for split_name in ("train", "val"):
                split_dir = os.path.join(output_dir, split_name)
                os.makedirs(split_dir, exist_ok=True)
                inputs_path = os.path.join(split_dir, "inputs.h5")
                targets_path = os.path.join(split_dir, "targets.h5")
                inputs_h5 = stack.enter_context(h5py.File(inputs_path, "w"))
                targets_h5 = stack.enter_context(h5py.File(targets_path, "w"))

                # Input: 2 channels (line-art mask, target-gap mask)
                dset_inputs = inputs_h5.create_dataset("patches", shape=(0, crop_size, crop_size, 2), maxshape=(None, crop_size, crop_size, 2), dtype=np.uint8, chunks=(128, crop_size, crop_size, 2))

                # Target: 1 channel (closest large same-color region mask)
                dset_targets = targets_h5.create_dataset("patches", shape=(0, crop_size, crop_size), maxshape=(None, crop_size, crop_size), dtype=np.uint8, chunks=(128, crop_size, crop_size))
                datasets[split_name] = (dset_inputs, dset_targets)
                output_paths[split_name] = (inputs_path, targets_path)

            def save_batch(split_name, input_batch, target_batch):
                batch_size = len(input_batch)
                if batch_size != len(target_batch):
                    raise ValueError("Input and target batch sizes must match")

                dset_inputs, dset_targets = datasets[split_name]
                current_size = dset_inputs.shape[0]
                new_size = current_size + batch_size
                dset_inputs.resize(new_size, axis=0)
                dset_targets.resize(new_size, axis=0)
                dset_inputs[current_size:new_size] = np.stack(input_batch)
                dset_targets[current_size:new_size] = np.stack(target_batch)
        else:
            npy_directories = {}
            npy_patch_counts = {"train": 0, "val": 0}
            for split_name in ("train", "val"):
                inputs_path = os.path.join(output_dir, split_name, "inputs")
                targets_path = os.path.join(output_dir, split_name, "targets")
                os.makedirs(inputs_path, exist_ok=True)
                os.makedirs(targets_path, exist_ok=True)
                for old_patch_path in glob(os.path.join(inputs_path, "patch_*.npy")) + glob(os.path.join(targets_path, "patch_*.npy")):
                    os.remove(old_patch_path)
                npy_directories[split_name] = (inputs_path, targets_path)
                output_paths[split_name] = (inputs_path, targets_path)

            def save_batch(split_name, input_batch, target_batch):
                batch_size = len(input_batch)
                if batch_size != len(target_batch):
                    raise ValueError("Input and target batch sizes must match")

                inputs_path, targets_path = npy_directories[split_name]
                for input_patch, target_patch in zip(input_batch, target_batch):
                    filename = f"patch_{npy_patch_counts[split_name]:08d}.npy"
                    np.save(os.path.join(inputs_path, filename), input_patch)
                    np.save(os.path.join(targets_path, filename), target_patch)
                    npy_patch_counts[split_name] += 1

        # --- Main Processing Loop ---
        patch_counts = {"train": 0, "val": 0}
        grouped_rows = df.groupby("filename", sort=False)
        for filename, rows in tqdm(grouped_rows, total=grouped_rows.ngroups, desc="Creating patches"):
            split_name = "train" if filename in train_filenames else "val"
            line_art_path = os.path.join(line_art_dir, filename)
            if not os.path.exists(line_art_path):
                print(f"Warning: File not found {line_art_path}")
                continue
            line_art = cv2.imread(line_art_path, cv2.IMREAD_GRAYSCALE)
            if line_art is None:
                print(f"Warning: Could not load {line_art_path}")
                continue

            region_labels, _ = detect_regions(line_art, threshold=flood_threshold)

            for row in rows.itertuples(index=False):
                if pd.isnull(row.nearest_region_id):
                    continue

                try:
                    region_id = int(row.region_id)
                    nearest_region_id = int(row.nearest_region_id)
                except (ValueError, TypeError):
                    continue

                center_coords = region_centroid(region_labels, region_id)
                if center_coords is None:
                    continue
                center_row, center_col = center_coords

                r_start, r_end, c_start, c_end = centered_crop_bounds(center_row, center_col, crop_size)
                input_patch, nearest_patch = create_region_patches(line_art, region_labels, region_id, nearest_region_id, crop_size, flood_threshold, r_start, r_end, c_start, c_end)

                if input_patch.shape != (crop_size, crop_size, 2):
                    raise ValueError(f"Unexpected input_patch shape: {input_patch.shape}")
                if nearest_patch.shape != (crop_size, crop_size):
                    raise ValueError(f"Unexpected nearest_patch shape: {nearest_patch.shape}")
                if not np.any(nearest_patch): # Keep only samples where the nearest same-color region is visible within the patch.
                    continue

                input_batch = [input_patch]
                target_batch = [nearest_patch]

                if split_name == "train" and augment:
                    input_batch.extend(augment_patch(input_patch))
                    target_batch.extend(augment_patch(nearest_patch))

                save_batch(split_name, input_batch, target_batch)
                patch_counts[split_name] += len(input_batch)

    if patch_counts["train"] == 0 or patch_counts["val"] == 0:
        raise ValueError(f"Patch generation produced an empty split: train={patch_counts['train']}, val={patch_counts['val']}")

    print(f"\nSuccessfully created {sum(patch_counts.values())} patches.")
    for split_name in ("train", "val"):
        inputs_path, targets_path = output_paths[split_name]
        print(f"{split_name}: {patch_counts[split_name]} patches")
        print(f"  Inputs saved to: {inputs_path}")
        print(f"  Targets saved to: {targets_path}")
