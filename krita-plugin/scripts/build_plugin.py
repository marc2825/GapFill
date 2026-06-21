#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent
REPOSITORY_ROOT = PLUGIN_ROOT.parent
SOURCE_PACKAGE = PLUGIN_ROOT / "pykrita" / "gapfill_krita"
DESKTOP_FILE = PLUGIN_ROOT / "pykrita" / "gapfill_krita.desktop"
MODEL_FILE = REPOSITORY_ROOT / "web" / "public" / "models" / "unet32.onnx"
MODEL_INFO = REPOSITORY_ROOT / "web" / "public" / "models" / "model_info.json"


def ignored(_directory: str, entries: list[str]) -> set[str]:
    return {
        entry
        for entry in entries
        if entry in {"__pycache__", "_vendor"} or entry.endswith((".pyc", ".pyo"))
    }


def build(output: Path, vendor: Path | None = None) -> Path:
    if not MODEL_FILE.is_file() or MODEL_FILE.stat().st_size == 0:
        raise FileNotFoundError(f"Required ONNX model is missing: {MODEL_FILE}")
    if not DESKTOP_FILE.is_file():
        raise FileNotFoundError(f"Krita desktop entry is missing: {DESKTOP_FILE}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gapfill-krita-") as temporary:
        staging = Path(temporary)
        shutil.copy2(DESKTOP_FILE, staging / DESKTOP_FILE.name)
        target_package = staging / "gapfill_krita"
        shutil.copytree(SOURCE_PACKAGE, target_package, ignore=ignored)
        model_dir = target_package / "resources" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MODEL_FILE, model_dir / MODEL_FILE.name)
        shutil.copy2(MODEL_INFO, model_dir / MODEL_INFO.name)
        if vendor is not None:
            if not vendor.is_dir():
                raise FileNotFoundError(f"Vendor directory does not exist: {vendor}")
            shutil.copytree(vendor, target_package / "_vendor", dirs_exist_ok=True)

        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging).as_posix())
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an importable GapFill Krita plugin ZIP.")
    parser.add_argument(
        "--output",
        type=Path,
        default=PLUGIN_ROOT / "dist" / "gapfill-krita.zip",
    )
    parser.add_argument(
        "--vendor",
        type=Path,
        help="Optional site-packages directory to bundle as gapfill_krita/_vendor.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    result = build(
        arguments.output.resolve(), arguments.vendor.resolve() if arguments.vendor else None
    )
    print(result)
