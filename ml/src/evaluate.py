"""CLI entrypoint: GapFill model / greedy baseline evaluation (inference) with optional visualization."""

from __future__ import annotations

import argparse

from . import config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GapFill model or greedy color prediction evaluation")

    # Configure subcommands
    subparsers = parser.add_subparsers(dest="mode", help="Operation mode")

    # Parser for GapFill model inference mode
    gapfill_parser = subparsers.add_parser("gapfill", help="Run GapFill model inference, evaluation, and visualization")
    gapfill_parser.add_argument("--csv_file", default=str(config.REGION_ANALYSIS_CSV_PATH), help=f"Path to the nearest same color analysis CSV file (default: {config.REGION_ANALYSIS_CSV_PATH})")
    gapfill_parser.add_argument("--line_art_dir", default=str(config.LINE_ART_DIR), help=f"Directory containing line art images (default: {config.LINE_ART_DIR})")
    gapfill_parser.add_argument("--colored_dir", default=str(config.COLORED_DIR), help=f"Directory containing colored images (default: {config.COLORED_DIR})")
    gapfill_parser.add_argument("--output_dir", default=str(config.DEFAULT_EVALUATION_DIR), help=f"Output directory for CSV, summary, patches, and visualizations (default: {config.DEFAULT_EVALUATION_DIR})")
    gapfill_parser.add_argument("--crop_size", type=int, default=config.PATCH_SIZE, help=f"Model input patch size (square) (default: {config.PATCH_SIZE})")
    gapfill_parser.add_argument("--comparison_crop_size", type=int, default=None, help="Central crop size used to select the predicted color. If omitted, use the full crop_size.")
    gapfill_parser.add_argument("--flood_threshold", type=int, default=128, help="Threshold used for flood fill (for detect_regions) (default: 128)")
    gapfill_parser.add_argument("--model_path", default=str(config.BEST_MODEL_PATH), help=f"Path to the trained model weights (default: {config.BEST_MODEL_PATH})")
    gapfill_parser.add_argument("--samples", type=int, default=None, help="Maximum number of samples to process. If omitted, process all eligible samples.")
    gapfill_parser.add_argument("--show_labels", action="store_true", help="Show a small description in each visualization panel")
    gapfill_parser.add_argument("--save_raw_predictions", action="store_true", help="Save input, target, and raw model prediction arrays as NPY files")
    gapfill_parser.add_argument("--results_only", action="store_true", help="Save only color_comparison.csv and color_summary.txt, skipping per-patch arrays and visualizations")

    # Parser for greedy prediction mode
    greedy_parser = subparsers.add_parser("greedy", help="Run greedy baseline evaluation and visualization")
    greedy_parser.add_argument("--csv_file", default=str(config.REGION_ANALYSIS_CSV_PATH), help=f"Path to the nearest same color analysis CSV file (default: {config.REGION_ANALYSIS_CSV_PATH})")
    greedy_parser.add_argument("--line_art_dir", default=str(config.LINE_ART_DIR), help=f"Directory containing line art images (default: {config.LINE_ART_DIR})")
    greedy_parser.add_argument("--colored_dir", default=str(config.COLORED_DIR), help=f"Directory containing colored images (default: {config.COLORED_DIR})")
    greedy_parser.add_argument("--output_dir", default=str(config.DEFAULT_GREEDY_EVALUATION_DIR), help=f"Output directory for CSV, summary, patches, and visualizations (default: {config.DEFAULT_GREEDY_EVALUATION_DIR})")
    greedy_parser.add_argument("--crop_size", type=int, default=config.PATCH_SIZE, help=f"Patch size (square) used by the greedy baseline (default: {config.PATCH_SIZE})")
    greedy_parser.add_argument("--flood_threshold", type=int, default=128, help="Threshold used for flood fill (for detect_regions) (default: 128)")
    greedy_parser.add_argument("--samples", type=int, default=None, help="Maximum number of samples to process. If omitted, process all eligible samples.")
    greedy_parser.add_argument("--show_labels", action="store_true", help="Show a small description in each visualization panel")
    greedy_parser.add_argument("--save_raw_predictions", action="store_true", help="Save input and target arrays used by the greedy baseline as NPY files")
    greedy_parser.add_argument("--results_only", action="store_true", help="Save only color_comparison.csv and color_summary.txt, skipping per-patch arrays and visualizations")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Branch processing based on mode
    if args.mode == "gapfill":
        from .pipelines.inference_pipeline import run_inference_pipeline

        run_inference_pipeline(
            args.csv_file,
            args.crop_size,
            args.line_art_dir,
            args.colored_dir,
            args.output_dir,
            args.model_path,
            args.samples,
            args.flood_threshold,
            args.show_labels,
            args.save_raw_predictions,
            args.comparison_crop_size,
            args.results_only,
        )
    elif args.mode == "greedy":
        from .pipelines.greedy_pipeline import run_greedy_pipeline

        run_greedy_pipeline(
            args.csv_file,
            args.crop_size,
            args.line_art_dir,
            args.colored_dir,
            args.output_dir,
            args.flood_threshold,
            args.samples,
            args.show_labels,
            args.save_raw_predictions,
            args.results_only,
        )
    else:
        build_parser().print_help()


if __name__ == "__main__":
    main()
