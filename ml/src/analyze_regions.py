"""CLI entrypoint: analyze nearest same-color regions and create the source CSV."""

from __future__ import annotations

import argparse

from . import config
from .utils.flood_fill.nearest_same_color import analyze_nearest_same_color


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze nearest same color distances in line art dataset")
    parser.add_argument("--colored_dir", type=str, default=str(config.COLORED_DIR), help=f"Path to the colored dataset directory (default: {config.COLORED_DIR})")
    parser.add_argument("--line_art_dir", type=str, default=str(config.LINE_ART_DIR), help=f"Path to the line art dataset directory (default: {config.LINE_ART_DIR})")
    parser.add_argument("--output_dir", type=str, default=str(config.REGION_ANALYSIS_OUTPUT_DIR), help=f"Output directory for nearest same color analysis results (default: {config.REGION_ANALYSIS_OUTPUT_DIR})")
    parser.add_argument("--num_samples", type=int, default=None, help="Number of samples to analyze. If omitted, analyze all samples.")
    parser.add_argument("--flood_threshold", type=int, default=128, help="Threshold for flood fill (line detection)")
    parser.add_argument("--region_size_threshold", type=int, default=config.REGION_SIZE_THRESHOLD, help=f"Maximum region size to analyze (default: {config.REGION_SIZE_THRESHOLD})")
    parser.add_argument("--timeout_seconds", type=int, default=30, help="Timeout seconds for each sample processing")
    parser.add_argument("--no_raw_data", action="store_true", help="Do not save raw data CSV files")
    parser.add_argument("--save_combined_images", action="store_true", help="Save line-art region labels and colored images side by side")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    analyze_nearest_same_color(
        colored_dir=args.colored_dir,
        line_art_dir=args.line_art_dir,
        output_dir=args.output_dir,
        num_samples=args.num_samples,
        flood_threshold=args.flood_threshold,
        region_size_threshold=args.region_size_threshold,
        timeout_seconds=args.timeout_seconds,
        save_raw_data=not args.no_raw_data,
        save_combined_images=args.save_combined_images,
    )


if __name__ == "__main__":
    main()
