#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = PLUGIN_ROOT.parent


def default_resource_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "krita"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "krita"
    return Path.home() / ".local" / "share" / "krita"


def copy_tree(source: Path, target: Path, dry_run: bool) -> None:
    print(f"{source} -> {target}")
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            source,
            target,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install the checkout into Krita's resource folder."
    )
    parser.add_argument("--resource-dir", type=Path, default=default_resource_dir())
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    resource = args.resource_dir.expanduser().resolve()
    package_source = PLUGIN_ROOT / "pykrita" / "gapfill_krita"
    package_target = resource / "pykrita" / "gapfill_krita"
    copy_tree(package_source, package_target, args.dry_run)

    files = [
        (
            PLUGIN_ROOT / "pykrita" / "gapfill_krita.desktop",
            resource / "pykrita" / "gapfill_krita.desktop",
        ),
        (
            PLUGIN_ROOT / "actions" / "gapfill_krita.action",
            resource / "actions" / "gapfill_krita.action",
        ),
        (
            REPOSITORY_ROOT / "web" / "public" / "models" / "unet32.onnx",
            package_target / "resources" / "models" / "unet32.onnx",
        ),
        (
            REPOSITORY_ROOT / "web" / "public" / "models" / "model_info.json",
            package_target / "resources" / "models" / "model_info.json",
        ),
    ]
    for source, target in files:
        if not source.is_file():
            raise FileNotFoundError(source)
        print(f"{source} -> {target}")
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    print("Restart Krita, enable GapFill under Python Plugin Manager, then restart once more.")


if __name__ == "__main__":
    main()
