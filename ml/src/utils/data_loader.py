"""Data loading helpers for the UNet pipeline."""

from __future__ import annotations

import glob
import math
import os
from typing import Any

import cv2
import h5py
import numpy as np
import torch
import torch.distributed as dist
from torch.utils.data import DataLoader, Dataset, Sampler
from torch.utils.data.distributed import DistributedSampler

from src import config


class ChunkBatchSampler(Sampler[list[int]]):
    """Yield batches in shuffled storage-chunk order."""

    def __init__(
        self,
        dataset_size: int,
        batch_size: int,
        chunk_size: int,
        shuffle: bool,
        drop_last: bool = False,
        seed: int = 0,
        num_replicas: int | None = None,
        rank: int | None = None,
    ):
        if dataset_size <= 0:
            raise ValueError(f"dataset_size must be positive, got {dataset_size}")
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")

        if num_replicas is None:
            num_replicas = dist.get_world_size() if dist.is_available() and dist.is_initialized() else 1
        if rank is None:
            rank = dist.get_rank() if dist.is_available() and dist.is_initialized() else 0
        if not 0 <= rank < num_replicas:
            raise ValueError(f"rank must be in [0, {num_replicas}), got {rank}")

        self.dataset_size = dataset_size
        self.batch_size = batch_size
        self.chunk_size = chunk_size
        self.shuffle = shuffle
        self.drop_last = drop_last
        self.seed = seed
        self.num_replicas = num_replicas
        self.rank = rank
        self.epoch = 0

        self.global_batch_count = dataset_size // batch_size if drop_last else math.ceil(dataset_size / batch_size)
        self.total_batch_count = math.ceil(self.global_batch_count / num_replicas) * num_replicas

    def __iter__(self):
        rng = np.random.default_rng(self.seed + self.epoch)
        full_chunk_count, remainder = divmod(self.dataset_size, self.chunk_size)
        chunk_starts = np.arange(full_chunk_count, dtype=np.int64) * self.chunk_size
        if self.shuffle:
            rng.shuffle(chunk_starts)
        if remainder:
            chunk_starts = np.append(chunk_starts, full_chunk_count * self.chunk_size)

        first_batches: list[list[int]] = []
        global_batch_index = 0
        pending_indices: list[int] = []
        for chunk_start in chunk_starts:
            chunk_stop = min(int(chunk_start) + self.chunk_size, self.dataset_size)
            indices = np.arange(int(chunk_start), chunk_stop, dtype=np.int64)
            if self.shuffle:
                rng.shuffle(indices)
            pending_indices.extend(indices.tolist())

            while len(pending_indices) >= self.batch_size:
                batch_list = pending_indices[: self.batch_size]
                pending_indices = pending_indices[self.batch_size :]
                if len(first_batches) < self.num_replicas:
                    first_batches.append(batch_list)
                if global_batch_index % self.num_replicas == self.rank:
                    yield batch_list
                global_batch_index += 1

        if pending_indices and not self.drop_last:
            if len(first_batches) < self.num_replicas:
                first_batches.append(pending_indices)
            if global_batch_index % self.num_replicas == self.rank:
                yield pending_indices
            global_batch_index += 1

        # Keep every DDP rank on the same number of batches.
        for padding_index in range(self.total_batch_count - self.global_batch_count):
            batch_list = first_batches[padding_index % len(first_batches)]
            if global_batch_index % self.num_replicas == self.rank:
                yield batch_list
            global_batch_index += 1

    def __len__(self) -> int:
        return self.total_batch_count // self.num_replicas

    def set_epoch(self, epoch: int) -> None:
        self.epoch = epoch


class PatchDataset(Dataset):
    """Dataset for training patches saved as HDF5 or NPY files."""

    def __init__(self, data_dir: str, crop_size: int = config.PATCH_SIZE, use_hdf5: bool = config.USE_HDF5):
        self.data_dir = data_dir
        self.crop_size = crop_size
        self.use_hdf5 = use_hdf5
        self._inputs_h5 = None
        self._targets_h5 = None

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
                input_chunks = f_in["patches"].chunks
                target_chunks = f_tgt["patches"].chunks
            if input_shape[0] != target_shape[0]:
                raise ValueError(f"HDF5 input and target lengths do not match: {input_shape[0]} inputs, {target_shape[0]} targets")
            if input_shape[1:] != (crop_size, crop_size, 2):
                raise ValueError(f"Unexpected HDF5 input patch shape: {input_shape[1:]}")
            if target_shape[1:] != (crop_size, crop_size):
                raise ValueError(f"Unexpected HDF5 target patch shape: {target_shape[1:]}")
            if input_chunks is None or target_chunks is None:
                raise ValueError("HDF5 patch datasets must use chunked storage")
            if input_chunks[0] != target_chunks[0]:
                raise ValueError(f"HDF5 input and target chunk sizes do not match: {input_chunks[0]} and {target_chunks[0]}")
            self.length = input_shape[0]
            self.chunk_size = input_chunks[0]
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

    def _get_hdf5_datasets(self):
        if self._inputs_h5 is None:
            self._inputs_h5 = h5py.File(self.inputs_h5_path, "r")
            self._targets_h5 = h5py.File(self.targets_h5_path, "r")
        return self._inputs_h5["patches"], self._targets_h5["patches"]

    def close(self) -> None:
        for handle_name in ("_inputs_h5", "_targets_h5"):
            handle = getattr(self, handle_name, None)
            if handle is not None:
                handle.close()
                setattr(self, handle_name, None)

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_inputs_h5"] = None
        state["_targets_h5"] = None
        return state

    def __del__(self):
        self.close()

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        if self.use_hdf5:
            inputs, targets = self._get_hdf5_datasets()
            input_patch = np.array(inputs[idx])
            target_patch = np.array(targets[idx])
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

    def __getitems__(self, indices: list[int]) -> list[dict[str, torch.Tensor]]:
        if not self.use_hdf5:
            return [self[index] for index in indices]
        if not indices:
            return []

        index_array = np.asarray(indices, dtype=np.int64)
        if np.any(index_array < 0) or np.any(index_array >= self.length):
            raise IndexError("HDF5 patch index out of range")

        input_patches = np.empty((len(indices), self.crop_size, self.crop_size, 2), dtype=np.uint8)
        target_patches = np.empty((len(indices), self.crop_size, self.crop_size), dtype=np.uint8)
        inputs, targets = self._get_hdf5_datasets()

        # Each sampler batch normally belongs to one chunk. Grouping here also
        # keeps direct callers efficient if they provide indices from several chunks.
        chunk_ids = index_array // self.chunk_size
        for chunk_id in np.unique(chunk_ids):
            positions = np.flatnonzero(chunk_ids == chunk_id)
            selected_indices = index_array[positions]
            read_start = int(selected_indices.min())
            read_stop = int(selected_indices.max()) + 1
            input_block = inputs[read_start:read_stop]
            target_block = targets[read_start:read_stop]
            offsets = selected_indices - read_start
            input_patches[positions] = input_block[offsets]
            target_patches[positions] = target_block[offsets]

        input_tensors = torch.from_numpy(input_patches).float().permute(0, 3, 1, 2)
        target_tensors = torch.from_numpy(target_patches).float().unsqueeze(1)
        return [
            {"input": input_tensors[position], "target": target_tensors[position]}
            for position in range(len(indices))
        ]


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

    loader_options = {
        "num_workers": num_workers,
        "pin_memory": pin_memory,
        "persistent_workers": num_workers > 0,
    }
    if use_hdf5:
        train_sampler = ChunkBatchSampler(
            len(train_ds),
            batch_size=batch_size,
            chunk_size=train_ds.chunk_size,
            shuffle=True,
            drop_last=drop_last,
        )
        val_sampler = ChunkBatchSampler(
            len(val_ds),
            batch_size=batch_size,
            chunk_size=val_ds.chunk_size,
            shuffle=False,
        )
        train_loader = DataLoader(train_ds, batch_sampler=train_sampler, **loader_options)
        val_loader = DataLoader(val_ds, batch_sampler=val_sampler, **loader_options)
    else:
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
            drop_last=drop_last,
            **loader_options,
        )
        val_loader = DataLoader(
            val_ds,
            batch_size=batch_size,
            shuffle=False,
            sampler=val_sampler,
            drop_last=False,
            **loader_options,
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
