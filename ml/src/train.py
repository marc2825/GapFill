"""CLI entrypoint: train NearestRegionUNet."""

from __future__ import annotations

import argparse

from . import config
from .pipelines.train_pipeline import train_model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train the flood fill color estimation model")
    parser.add_argument("--device", type=str, default="cuda", help="Device to use for training (cuda or cpu)")
    parser.add_argument("--output_dir", type=str, default=str(config.DEFAULT_MODEL_DIR), help=f"Output directory for results (default: {config.DEFAULT_MODEL_DIR})")
    parser.add_argument("--data_dir", type=str, default=str(config.PATCH_DATA_DIR), help=f"Directory with inputs.h5 / targets.h5 (default: {config.PATCH_DATA_DIR})")
    parser.add_argument("--batch_size", type=int, default=config.BATCH_SIZE, help="Batch size")
    parser.add_argument("--num_workers", type=int, default=config.NUM_WORKERS, help="DataLoader workers")
    parser.add_argument("--crop_size", type=int, default=config.PATCH_SIZE, help="Patch crop size")
    parser.add_argument("--use_hdf5", dest="use_hdf5", action="store_true", help="Use HDF5 training patches")
    parser.add_argument("--use_npy", dest="use_hdf5", action="store_false", help="Use NPY training patches")
    parser.set_defaults(use_hdf5=config.USE_HDF5)
    parser.add_argument("--num_epochs", type=int, default=config.NUM_EPOCHS, help="Number of epochs to train")
    parser.add_argument("--lr", type=float, default=config.LEARNING_RATE, help="Learning rate")
    parser.add_argument("--weight_decay", type=float, default=config.WEIGHT_DECAY, help="Optimizer weight decay")
    parser.add_argument("--save_interval", type=int, default=config.SAVE_INTERVAL, help="Interval for saving models")
    parser.add_argument("--patience", type=int, default=config.EARLY_STOPPING_PATIENCE, help="Early stopping patience")
    parser.add_argument("--backend", type=str, default="nccl", help="Distributed backend (nccl/gloo)")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    train_model(args)


if __name__ == "__main__":
    main()
