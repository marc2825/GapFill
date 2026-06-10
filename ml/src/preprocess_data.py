"""CLI entrypoint: create training patches in HDF5 format."""

from __future__ import annotations

import argparse

from . import config
from .pipelines.preprocess_data_pipeline import create_training_patches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create HDF5 or NPY training patches from nearest same color CSV.")
    parser.add_argument("--csv_file", type=str, default=str(config.REGION_ANALYSIS_CSV_PATH), help=f"Path to the nearest same color analysis CSV file (default: {config.REGION_ANALYSIS_CSV_PATH})")
    parser.add_argument("--line_art_dir", type=str, required=True, help="Directory containing line art images.")
    parser.add_argument("--output_dir", type=str, default=str(config.PATCH_DATA_DIR), help=f"Output directory for training patches (default: {config.PATCH_DATA_DIR})")
    parser.add_argument("--crop_size", type=int, default=config.PATCH_SIZE, help="Crop size (square) for training patches.")
    parser.add_argument("--flood_threshold", type=int, default=128, help="Threshold used for binarization and region detection.")
    parser.add_argument("--train_val_split", type=float, default=config.TRAIN_VAL_SPLIT, help="Fraction of source images assigned to training.")
    parser.add_argument("--seed", type=int, default=0, help="Random seed used for the image-level train/validation split.")
    parser.add_argument("--use_hdf5", dest="use_hdf5", action="store_true", help="Save training patches as inputs.h5 / targets.h5")
    parser.add_argument("--use_npy", dest="use_hdf5", action="store_false", help="Save training patches under inputs/ / targets/ as NPY files")
    parser.set_defaults(use_hdf5=config.USE_HDF5)
    parser.add_argument("--no_augment", action="store_false", dest="augment", help="Disable data augmentation.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    create_training_patches(
        csv_file=args.csv_file,
        crop_size=args.crop_size,
        line_art_dir=args.line_art_dir,
        output_dir=args.output_dir,
        flood_threshold=args.flood_threshold,
        augment=args.augment,
        use_hdf5=args.use_hdf5,
        train_val_split=args.train_val_split,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
