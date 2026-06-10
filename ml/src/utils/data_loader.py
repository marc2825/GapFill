"""Data loading helpers for the UNet pipeline."""

from __future__ import annotations

import glob
import os
from typing import Any

import cv2
import h5py
import numpy as np
import torch
import torch.distributed as dist
from torch.utils.data import DataLoader, Dataset
from torch.utils.data.distributed import DistributedSampler

from src import config


class PatchDataset(Dataset):
    """Dataset for training patches saved as HDF5 or NPY files."""

    def __init__(self, data_dir: str, crop_size: int = config.PATCH_SIZE, use_hdf5: bool = config.USE_HDF5):
        self.data_dir = data_dir
        self.crop_size = crop_size
        self.use_hdf5 = use_hdf5

        if use_hdf5:
            self.inputs_h5_path = os.path.join(data_dir, "inputs.h5")
            self.targets_h5_path = os.path.join(data_dir, "targets.h5")
            if not os.path.exists(self.inputs_h5_path) or not os.path.exists(self.targets_h5_path):
                raise FileNotFoundError(f"HDF5 files not found in {data_dir}")
            with (
                h5py.File(self.inputs_h5_path, "r") as f_in,
                h5py.File(self.targets_h5_path, "r") as f_tgt,
            ):
                input_shape = tuple(f_in["patches"].shape)
                target_shape = tuple(f_tgt["patches"].shape)
            if input_shape[0] != target_shape[0]:
                raise ValueError(f"HDF5 input and target lengths do not match: {input_shape[0]} inputs, {target_shape[0]} targets")
            if input_shape[1:] != (crop_size, crop_size, 2):
                raise ValueError(f"Unexpected HDF5 input patch shape: {input_shape[1:]}")
            if target_shape[1:] != (crop_size, crop_size):
                raise ValueError(f"Unexpected HDF5 target patch shape: {target_shape[1:]}")
            self.length = input_shape[0]
        else:
            self.inputs_dir = os.path.join(data_dir, "inputs")
            self.targets_dir = os.path.join(data_dir, "targets")
            self.input_files = sorted(glob.glob(os.path.join(self.inputs_dir, "patch_*.npy")))
            target_files = sorted(glob.glob(os.path.join(self.targets_dir, "patch_*.npy")))
            input_names = [os.path.basename(path) for path in self.input_files]
            target_names = [os.path.basename(path) for path in target_files]
            if input_names != target_names:
                raise ValueError("NPY input and target filenames do not match")
            self.length = len(self.input_files)

        if self.length == 0:
            raise ValueError(f"No training patches found in {data_dir}")

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        if self.use_hdf5:
            with h5py.File(self.inputs_h5_path, "r") as f_in:
                input_patch = np.array(f_in["patches"][idx])
            with h5py.File(self.targets_h5_path, "r") as f_tgt:
                target_patch = np.array(f_tgt["patches"][idx])
        else:
            input_path = self.input_files[idx]
            target_path = os.path.join(self.targets_dir, os.path.basename(input_path))
            input_patch = np.load(input_path)
            target_patch = np.load(target_path)

        if input_patch.shape != (self.crop_size, self.crop_size, 2):
            raise ValueError(f"Unexpected input patch shape: {input_patch.shape}")
        if target_patch.shape != (self.crop_size, self.crop_size):
            raise ValueError(f"Unexpected target patch shape: {target_patch.shape}")

        input_tensor = torch.from_numpy(input_patch).float().permute(2, 0, 1)
        target_tensor = torch.from_numpy(target_patch).float().unsqueeze(0)
        return {"input": input_tensor, "target": target_tensor}


def create_batch_dataloaders(
    data_dir: str,
    batch_size: int = config.BATCH_SIZE,
    num_workers: int = config.NUM_WORKERS,
    pin_memory: bool = True,
    drop_last: bool = False,
    crop_size: int = config.PATCH_SIZE,
    use_hdf5: bool = config.USE_HDF5,
):
    """Create DataLoaders from image-level train/validation patch directories."""
    train_ds = PatchDataset(os.path.join(data_dir, "train"), crop_size=crop_size, use_hdf5=use_hdf5)
    val_ds = PatchDataset(os.path.join(data_dir, "val"), crop_size=crop_size, use_hdf5=use_hdf5)

    if dist.is_available() and dist.is_initialized():
        train_sampler = DistributedSampler(train_ds, shuffle=True)
        val_sampler = DistributedSampler(val_ds, shuffle=False)
    else:
        train_sampler = None
        val_sampler = None

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        shuffle=(train_sampler is None),
        sampler=train_sampler,
        num_workers=num_workers,
        pin_memory=pin_memory,
        drop_last=drop_last,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        sampler=val_sampler,
        num_workers=num_workers,
        pin_memory=pin_memory,
        drop_last=False,
    )

    return train_loader, val_loader, train_sampler, val_sampler


class RegionDataLoader:
    """Loader for aligned line-art/colored pairs used by region analysis."""

    def __init__(self, line_art_dir: str, colored_dir: str):
        self.line_art_dir = line_art_dir
        self.colored_dir = colored_dir

        line_art_files = {
            f
            for f in os.listdir(line_art_dir)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".tga"))
        }
        colored_files = {
            f
            for f in os.listdir(colored_dir)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".tga"))
        }

        self.common_files = sorted(line_art_files.intersection(colored_files))

    def __len__(self) -> int:
        return len(self.common_files)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        filename = self.common_files[idx]
        line_art_path = os.path.join(self.line_art_dir, filename)
        colored_path = os.path.join(self.colored_dir, filename)

        line_art_np = cv2.imread(line_art_path, cv2.IMREAD_GRAYSCALE)
        colored_bgr = cv2.imread(colored_path, cv2.IMREAD_COLOR)
        if line_art_np is None or colored_bgr is None:
            raise ValueError(f"Failed to load pair: {filename}")

        if line_art_np.shape[:2] != colored_bgr.shape[:2]:
            colored_bgr = cv2.resize(
                colored_bgr,
                (line_art_np.shape[1], line_art_np.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )

        colored_rgb = cv2.cvtColor(colored_bgr, cv2.COLOR_BGR2RGB)

        return {
            "line_art_np": line_art_np,
            "colored_np": colored_rgb,
            "filename": filename,
        }
