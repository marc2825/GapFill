from __future__ import annotations

import configparser
import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "krita-plugin" / "scripts"
IMPORTER_SPEC = importlib.util.spec_from_file_location(
    "gapfill_krita_importer_compatibility",
    SCRIPTS / "krita_importer_compatibility.py",
)
BUILD_SPEC = importlib.util.spec_from_file_location(
    "gapfill_krita_build_plugin",
    SCRIPTS / "build_plugin.py",
)
assert IMPORTER_SPEC is not None and IMPORTER_SPEC.loader is not None
assert BUILD_SPEC is not None and BUILD_SPEC.loader is not None
IMPORTER = importlib.util.module_from_spec(IMPORTER_SPEC)
BUILD = importlib.util.module_from_spec(BUILD_SPEC)
IMPORTER_SPEC.loader.exec_module(IMPORTER)
BUILD_SPEC.loader.exec_module(BUILD)

FROZEN_1_0_0 = (
    ROOT
    / "krita-plugin"
    / "release"
    / "artifacts"
    / "gapfill-krita-windows-x86_64.zip"
)


def desktop_metadata(archive: zipfile.ZipFile) -> configparser.SectionProxy:
    config = configparser.ConfigParser()
    config.read_string(archive.read("gapfill_krita.desktop").decode("utf-8"))
    return config["Desktop Entry"]


def test_frozen_1_0_0_permanently_reproduces_known_importer_defect() -> None:
    with zipfile.ZipFile(FROZEN_1_0_0) as archive:
        names = archive.namelist()
        metadata = desktop_metadata(archive)
        assert metadata["X-KDE-Library"] == "gapfill_krita"
        assert metadata["Name"] == "GapFill"
        assert "gapfill_krita/__init__.py" in names
        assert "gapfill_krita/" not in names
        assert IMPORTER.discover_plugins(archive) == []
        assert IMPORTER.diagnosis(archive, "gapfill_krita") == (
            "REQUIRED_MODULE_DIRECTORY_ENTRY_ABSENT"
        )


def test_builder_output_is_discovered_as_exactly_one_gapfill_plugin(tmp_path: Path) -> None:
    candidate = BUILD.build(tmp_path / "candidate.zip")
    with zipfile.ZipFile(candidate) as archive:
        assert IMPORTER.diagnosis(archive, "gapfill_krita") == "PLUGIN_DISCOVERABLE"
        assert IMPORTER.discover_plugins(archive) == [
            {
                "action": "actions/gapfill_krita.action",
                "desktop": "gapfill_krita.desktop",
                "module": "gapfill_krita/",
                "name": "gapfill_krita",
                "ui_name": "GapFill",
            }
        ]
