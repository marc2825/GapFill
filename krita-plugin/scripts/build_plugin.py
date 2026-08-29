#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent
REPOSITORY_ROOT = PLUGIN_ROOT.parent
SOURCE_PACKAGE = PLUGIN_ROOT / "pykrita" / "gapfill_krita"
DESKTOP_FILE = PLUGIN_ROOT / "pykrita" / "gapfill_krita.desktop"
ACTION_FILE = PLUGIN_ROOT / "actions" / "gapfill_krita.action"
MODEL_FILE = REPOSITORY_ROOT / "web" / "public" / "models" / "unet32.onnx"
MODEL_INFO = REPOSITORY_ROOT / "web" / "public" / "models" / "model_info.json"
NATIVE_HELPER_FILENAME = "gapfill_krita_native_5_3_3.cp313-win_amd64.pyd"
NATIVE_HELPER_SHA256 = "ad2fa7463d59dca74a92dc867734b38eb7aa49821b163547da442147348f8746"
ARCHIVE_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FILE_EXTERNAL_ATTR = 0o100644 << 16
DIRECTORY_EXTERNAL_ATTR = (0o40755 << 16) | 0x10


def ignored(_directory: str, entries: list[str]) -> set[str]:
    return {
        entry
        for entry in entries
        if entry in {"__pycache__", "_vendor"} or entry.endswith((".pyc", ".pyo"))
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build(
    output: Path, vendor: Path | None = None, native_helper: Path | None = None
) -> Path:
    if not MODEL_FILE.is_file() or MODEL_FILE.stat().st_size == 0:
        raise FileNotFoundError(f"Required ONNX model is missing: {MODEL_FILE}")
    if not DESKTOP_FILE.is_file():
        raise FileNotFoundError(f"Krita desktop entry is missing: {DESKTOP_FILE}")
    if not ACTION_FILE.is_file():
        raise FileNotFoundError(f"Krita action metadata is missing: {ACTION_FILE}")
    if native_helper is not None:
        if native_helper.name != NATIVE_HELPER_FILENAME or not native_helper.is_file():
            raise FileNotFoundError(
                f"Expected the version-pinned native helper {NATIVE_HELPER_FILENAME}: "
                f"{native_helper}"
            )
        actual_native_hash = sha256_file(native_helper)
        if actual_native_hash != NATIVE_HELPER_SHA256:
            raise RuntimeError(
                "Native helper SHA-256 mismatch: "
                f"expected {NATIVE_HELPER_SHA256}, received {actual_native_hash}."
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gapfill-krita-") as temporary:
        staging = Path(temporary)
        shutil.copy2(DESKTOP_FILE, staging / DESKTOP_FILE.name)
        action_target = staging / "actions" / ACTION_FILE.name
        action_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ACTION_FILE, action_target)
        target_package = staging / "gapfill_krita"
        shutil.copytree(SOURCE_PACKAGE, target_package, ignore=ignored)
        model_dir = target_package / "resources" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MODEL_FILE, model_dir / MODEL_FILE.name)
        shutil.copy2(MODEL_INFO, model_dir / MODEL_INFO.name)
        if vendor is not None:
            if not vendor.is_dir():
                raise FileNotFoundError(f"Vendor directory does not exist: {vendor}")
            shutil.copytree(
                vendor,
                target_package / "_vendor",
                dirs_exist_ok=True,
                ignore=ignored,
            )
        if native_helper is not None:
            native_dir = target_package / "_native"
            native_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(native_helper, native_dir / NATIVE_HELPER_FILENAME)

        with zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            members = sorted(
                staging.rglob("*"),
                key=lambda path: (
                    path.relative_to(staging).as_posix() + ("/" if path.is_dir() else "")
                ),
            )
            for path in members:
                relative = path.relative_to(staging).as_posix()
                if path.is_dir():
                    info = zipfile.ZipInfo(
                        f"{relative}/",
                        date_time=ARCHIVE_TIMESTAMP,
                    )
                    info.create_system = 3
                    info.compress_type = zipfile.ZIP_STORED
                    info.external_attr = DIRECTORY_EXTERNAL_ATTR
                    archive.writestr(info, b"")
                if path.is_file():
                    info = zipfile.ZipInfo(
                        relative,
                        date_time=ARCHIVE_TIMESTAMP,
                    )
                    info.create_system = 3
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = FILE_EXTERNAL_ATTR
                    archive.writestr(info, path.read_bytes(), compresslevel=9)
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
    parser.add_argument(
        "--native-helper",
        type=Path,
        help=(
            "Exact version-pinned Windows x64 CPython 3.13/Krita 5.3.3 native helper."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    result = build(
        arguments.output.resolve(),
        arguments.vendor.resolve() if arguments.vendor else None,
        arguments.native_helper.resolve() if arguments.native_helper else None,
    )
    print(result)
