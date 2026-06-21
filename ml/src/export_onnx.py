"""CLI entrypoint: export a trained GapFill checkpoint to ONNX for the web app."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config


DEFAULT_WEB_ONNX_PATH = config.ROOT_DIR.parent / "web" / "public" / "models" / "unet32.onnx"


def get_tensor_shape(value_info) -> list[int]:
    return [dimension.dim_value for dimension in value_info.type.tensor_type.shape.dim]


def write_model_info(output_path: Path) -> Path:
    """Write human-readable model metadata next to the exported ONNX file."""
    import onnx

    model = onnx.load(output_path)
    onnx.checker.check_model(model)

    model_input = model.graph.input[0]
    model_output = model.graph.output[0]
    opset_version = next(
        opset.version for opset in model.opset_import if opset.domain in ("", "ai.onnx")
    )
    model_info = {
        "name": "GapFill Nearest-Region U-Net",
        "version": "1.0",
        "model_file": output_path.name,
        "opset_version": opset_version,
        "input_name": model_input.name,
        "input_type": "float32",
        "input_shape": get_tensor_shape(model_input),
        "output_name": model_output.name,
        "output_type": "float32",
        "output_shape": get_tensor_shape(model_output),
        "input_description": "2-channel binary masks: [line_art_mask, gap_mask]",
        "output_description": "Probability map (0-1 values)",
        "channels": {
            "0": "Line Art and Guides mask (1=boundary, 0=transparent)",
            "1": "Target gap mask (1=gap region, 0=other)",
        },
    }

    info_path = output_path.with_name("model_info.json")
    info_path.write_text(json.dumps(model_info, indent=2) + "\n", encoding="utf-8")
    return info_path


def validate_crop_size(crop_size: int) -> None:
    if crop_size <= 0:
        raise ValueError(f"crop_size must be positive, got {crop_size}")
    if crop_size % 16 != 0:
        raise ValueError(f"crop_size must be a multiple of 16, got {crop_size}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a trained GapFill model checkpoint to ONNX")
    parser.add_argument(
        "--model_path",
        default=str(config.BEST_MODEL_PATH),
        help=f"Path to the trained PyTorch checkpoint (default: {config.BEST_MODEL_PATH})",
    )
    parser.add_argument(
        "--output_path",
        default=str(DEFAULT_WEB_ONNX_PATH),
        help=f"Output ONNX path (default: {DEFAULT_WEB_ONNX_PATH})",
    )
    parser.add_argument(
        "--crop_size",
        type=int,
        default=config.PATCH_SIZE,
        help=f"Square model input size used for export (default: {config.PATCH_SIZE})",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Device used while exporting the model (default: cpu)",
    )
    parser.add_argument(
        "--opset_version",
        type=int,
        default=18,
        help="ONNX opset version (default: 18)",
    )
    return parser


def load_state_dict(model_path: str, device):
    import torch

    state_dict = torch.load(model_path, map_location=device, weights_only=True)
    if "state_dict" in state_dict:
        state_dict = state_dict["state_dict"]
    if any(key.startswith("module.") for key in state_dict):
        state_dict = {key.removeprefix("module."): value for key, value in state_dict.items()}
    return state_dict


def export_onnx(args: argparse.Namespace) -> None:
    import torch

    from .models.nearest_region import NearestRegionUNet

    validate_crop_size(args.crop_size)

    device = torch.device(args.device)
    model = NearestRegionUNet(in_channels=2, out_channels=1).to(device)
    model.load_state_dict(load_state_dict(args.model_path, device))
    model.eval()

    dummy_input = torch.zeros(1, 2, args.crop_size, args.crop_size, dtype=torch.float32, device=device)
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with torch.no_grad():
        torch.onnx.export(
            model,
            dummy_input,
            str(output_path),
            export_params=True,
            external_data=False,
            opset_version=args.opset_version,
            do_constant_folding=True,
            input_names=["input_mask"],
            output_names=["nearest_region_mask"],
        )

    # PyTorch defaults to external weights. Remove an artifact left by an older
    # export now that this browser model is deliberately stored as one file.
    stale_external_data_path = output_path.with_name(f"{output_path.name}.data")
    if stale_external_data_path.exists():
        stale_external_data_path.unlink()

    info_path = write_model_info(output_path)
    print(f"Exported ONNX model: {output_path}")
    print(f"Wrote model documentation: {info_path}")


def main() -> None:
    export_onnx(build_parser().parse_args())


if __name__ == "__main__":
    main()
