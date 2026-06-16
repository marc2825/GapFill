from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np

from src.utils.data_loader import ChunkBatchSampler, PatchDataset, create_batch_dataloaders


class ChunkBatchSamplerTest(unittest.TestCase):
    def test_batches_stay_within_chunks_and_cover_dataset(self):
        sampler = ChunkBatchSampler(
            dataset_size=11,
            batch_size=2,
            chunk_size=4,
            shuffle=True,
            seed=7,
        )

        batches = list(sampler)

        self.assertEqual(sorted(index for batch in batches for index in batch), list(range(11)))
        self.assertEqual(len(batches), len(sampler))
        for batch in batches:
            self.assertEqual(len({index // 4 for index in batch}), 1)

    def test_distributed_ranks_have_equal_batch_counts(self):
        samplers = [
            ChunkBatchSampler(
                dataset_size=11,
                batch_size=2,
                chunk_size=4,
                shuffle=True,
                seed=7,
                num_replicas=3,
                rank=rank,
            )
            for rank in range(3)
        ]

        rank_batches = [list(sampler) for sampler in samplers]

        self.assertEqual([len(batches) for batches in rank_batches], [2, 2, 2])
        covered_indices = {
            index
            for batches in rank_batches
            for batch in batches
            for index in batch
        }
        self.assertEqual(covered_indices, set(range(11)))

    def test_epoch_changes_shuffle_order(self):
        sampler = ChunkBatchSampler(
            dataset_size=16,
            batch_size=2,
            chunk_size=4,
            shuffle=True,
            seed=7,
        )
        epoch_zero = list(sampler)
        sampler.set_epoch(1)
        epoch_one = list(sampler)

        self.assertNotEqual(epoch_zero, epoch_one)

    def test_batch_can_combine_multiple_chunks(self):
        sampler = ChunkBatchSampler(
            dataset_size=12,
            batch_size=8,
            chunk_size=4,
            shuffle=False,
        )

        self.assertEqual(list(sampler), [list(range(8)), list(range(8, 12))])


class PatchDatasetTest(unittest.TestCase):
    def _write_split(self, split_dir: Path, sample_count: int = 10) -> None:
        split_dir.mkdir(parents=True)
        inputs = np.zeros((sample_count, 16, 16, 2), dtype=np.uint8)
        targets = np.zeros((sample_count, 16, 16), dtype=np.uint8)
        for index in range(sample_count):
            inputs[index] = index
            targets[index] = index + 20

        with h5py.File(split_dir / "inputs.h5", "w") as inputs_h5:
            inputs_h5.create_dataset("patches", data=inputs, chunks=(4, 16, 16, 2))
        with h5py.File(split_dir / "targets.h5", "w") as targets_h5:
            targets_h5.create_dataset("patches", data=targets, chunks=(4, 16, 16))

    def test_batched_hdf5_read_preserves_requested_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            split_dir = Path(temp_dir) / "train"
            self._write_split(split_dir)
            dataset = PatchDataset(str(split_dir), crop_size=16, use_hdf5=True)

            samples = dataset.__getitems__([3, 1, 7, 6])

            self.assertEqual([sample["input"][0, 0, 0].item() for sample in samples], [3, 1, 7, 6])
            self.assertEqual([sample["target"][0, 0, 0].item() for sample in samples], [23, 21, 27, 26])
            self.assertIsNotNone(dataset._inputs_h5)
            self.assertIsNotNone(dataset._targets_h5)
            dataset.close()

    def test_hdf5_dataloaders_use_chunk_local_batches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            self._write_split(data_dir / "train")
            self._write_split(data_dir / "val", sample_count=5)

            train_loader, val_loader, train_sampler, val_sampler = create_batch_dataloaders(
                str(data_dir),
                batch_size=2,
                num_workers=0,
                pin_memory=False,
                crop_size=16,
                use_hdf5=True,
            )

            train_indices = []
            for batch in train_loader:
                indices = [int(value) for value in batch["input"][:, 0, 0, 0]]
                train_indices.extend(indices)
                self.assertEqual(len({index // 4 for index in indices}), 1)

            val_indices = [
                int(value)
                for batch in val_loader
                for value in batch["input"][:, 0, 0, 0]
            ]
            self.assertEqual(sorted(train_indices), list(range(10)))
            self.assertEqual(val_indices, list(range(5)))
            self.assertIsInstance(train_sampler, ChunkBatchSampler)
            self.assertIsInstance(val_sampler, ChunkBatchSampler)

    def test_hdf5_dataloader_works_with_persistent_workers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            self._write_split(data_dir / "train")
            self._write_split(data_dir / "val", sample_count=5)

            train_loader, _, _, _ = create_batch_dataloaders(
                str(data_dir),
                batch_size=2,
                num_workers=2,
                pin_memory=False,
                crop_size=16,
                use_hdf5=True,
            )

            first_epoch = sorted(
                int(value)
                for batch in train_loader
                for value in batch["input"][:, 0, 0, 0]
            )
            second_epoch = sorted(
                int(value)
                for batch in train_loader
                for value in batch["input"][:, 0, 0, 0]
            )
            self.assertEqual(first_epoch, list(range(10)))
            self.assertEqual(second_epoch, list(range(10)))

    def test_npy_dataloader_behavior_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            for split_name in ("train", "val"):
                inputs_dir = data_dir / split_name / "inputs"
                targets_dir = data_dir / split_name / "targets"
                inputs_dir.mkdir(parents=True)
                targets_dir.mkdir(parents=True)
                for index in range(4):
                    filename = f"patch_{index:08d}.npy"
                    np.save(inputs_dir / filename, np.full((16, 16, 2), index, dtype=np.uint8))
                    np.save(targets_dir / filename, np.full((16, 16), index + 20, dtype=np.uint8))

            train_loader, val_loader, train_sampler, val_sampler = create_batch_dataloaders(
                str(data_dir),
                batch_size=2,
                num_workers=0,
                pin_memory=False,
                crop_size=16,
                use_hdf5=False,
            )

            train_values = sorted(
                int(value)
                for batch in train_loader
                for value in batch["input"][:, 0, 0, 0]
            )
            val_values = [
                int(value)
                for batch in val_loader
                for value in batch["input"][:, 0, 0, 0]
            ]
            self.assertEqual(train_values, list(range(4)))
            self.assertEqual(val_values, list(range(4)))
            self.assertIsNone(train_sampler)
            self.assertIsNone(val_sampler)


if __name__ == "__main__":
    unittest.main()
