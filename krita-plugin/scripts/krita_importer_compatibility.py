#!/usr/bin/env python3
"""Faithful, host-independent Krita Python Plugin Importer discovery check."""

from __future__ import annotations

import argparse
import configparser
import json
import zipfile
from pathlib import Path
from typing import Any


def source_module(namelist: list[str], name: str) -> str | None:
    """Mirror Krita 5.3.3 PluginImporter.get_source_module exactly."""
    for filename in namelist:
        if filename.endswith(f"/{name}/") or filename == f"{name}/":
            if f"{filename}__init__.py" in namelist:
                return filename
    return None


def source_action(namelist: list[str], name: str) -> str | None:
    expected = f"{name}.action"
    for filename in namelist:
        if filename.endswith(".action") and filename.rsplit("/", 1)[-1] == expected:
            return filename
    return None


def discover_plugins(archive: zipfile.ZipFile) -> list[dict[str, Any]]:
    """Return the plugin records the Krita 5.3.3 importer would discover."""
    namelist = archive.namelist()
    plugins: list[dict[str, Any]] = []
    for filename in namelist:
        if not filename.endswith(".desktop"):
            continue
        config = configparser.ConfigParser()
        config.read_string(archive.read(filename).decode("utf-8"))
        name = config["Desktop Entry"]["X-KDE-Library"]
        ui_name = config["Desktop Entry"]["Name"]
        module = source_module(namelist, name)
        if module:
            plugins.append(
                {
                    "action": source_action(namelist, name),
                    "desktop": filename,
                    "module": module,
                    "name": name,
                    "ui_name": ui_name,
                }
            )
    return plugins


def diagnosis(archive: zipfile.ZipFile, module_name: str) -> str:
    namelist = archive.namelist()
    if f"{module_name}/__init__.py" not in namelist:
        return "MODULE_INIT_ABSENT"
    if source_module(namelist, module_name) is None:
        return "REQUIRED_MODULE_DIRECTORY_ENTRY_ABSENT"
    return "PLUGIN_DISCOVERABLE"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--module", default="gapfill_krita")
    arguments = parser.parse_args()
    with zipfile.ZipFile(arguments.archive) as archive:
        result = {
            "diagnosis": diagnosis(archive, arguments.module),
            "plugins": discover_plugins(archive),
        }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
