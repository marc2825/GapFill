#!/usr/bin/env python3
"""Fail-closed verification for the committed GapFill frozen release artifact."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent
REPOSITORY_ROOT = PLUGIN_ROOT.parent
DEFAULT_ARTIFACT = (
    PLUGIN_ROOT / "release" / "artifacts" / "gapfill-krita-windows-x86_64.zip"
)
DEFAULT_FREEZE = PLUGIN_ROOT / "release" / "freeze.json"
DEFAULT_ENTRIES = PLUGIN_ROOT / "release" / "artifact-entries.json"
PUBLICATION_GOVERNANCE = (
    "GAPFILL_1_0_0_FROZEN_ARTIFACT_PUBLICATION_V1_GOVERNANCE_ADOPTED"
)
HOTFIX_GOVERNANCE = "GAPFILL_1_0_1_IMPORTER_PACKAGING_HOTFIX_V1_GOVERNANCE_ADOPTED"
INTERACTION_PATCH_GOVERNANCE = (
    "GAPFILL_1_0_2_INTERACTION_LIFECYCLE_PATCH_V1_GOVERNANCE_ADOPTED"
)
MODEL_INPUT_MODES_GOVERNANCE = (
    "GAPFILL_1_1_0_MODEL_INPUT_MODES_V1_GOVERNANCE_ADOPTED"
)
PUBLICATION_GOVERNANCE_BY_VERSION = {
    "1.0.0": PUBLICATION_GOVERNANCE,
    "1.0.1": HOTFIX_GOVERNANCE,
    "1.0.2": INTERACTION_PATCH_GOVERNANCE,
    "1.1.0": MODEL_INPUT_MODES_GOVERNANCE,
}
PUBLICATION_MODE = "FROZEN_ARTIFACT_VERIFY_AND_PUBLISH"
QUALIFIED_PLATFORM = "windows-x86_64"
PASS_TOKEN = "FROZEN_RELEASE_ARTIFACT_VERIFICATION_PASS"


class VerificationError(RuntimeError):
    """The frozen release identity or archive structure did not match."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"Cannot read JSON {path}: {error}") from error
    require(isinstance(value, dict), f"Expected a JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise VerificationError(f"Cannot hash {path}: {error}") from error
    return digest.hexdigest()


def normalized_member_path(name: str) -> str:
    require(bool(name), "ZIP member path is empty.")
    require("\\" not in name, f"ZIP member path uses a backslash: {name!r}")
    directory = name.endswith("/")
    path_name = name[:-1] if directory else name
    require(bool(path_name), "ZIP member path is the archive root.")
    path = PurePosixPath(path_name)
    require(not path.is_absolute(), f"ZIP member path is absolute: {name!r}")
    require(not PureWindowsPath(name).drive, f"ZIP member path has a drive: {name!r}")
    require(".." not in path.parts, f"ZIP member path traverses upward: {name!r}")
    normalized = path.as_posix() + ("/" if directory else "")
    require(normalized == name, f"ZIP member path is not normalized: {name!r}")
    return normalized


def compression_name(method: int) -> str:
    names = {
        zipfile.ZIP_STORED: "stored",
        zipfile.ZIP_DEFLATED: "deflate",
        zipfile.ZIP_BZIP2: "bzip2",
        zipfile.ZIP_LZMA: "lzma",
    }
    return names.get(method, f"unknown:{method}")


def repository_relative(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError as error:
        raise VerificationError(
            f"Frozen artifact is outside the repository: {path.resolve()}"
        ) from error


def discover_plugins(archive: zipfile.ZipFile) -> list[dict[str, str | None]]:
    """Mirror the Krita 5.3.3 Python Plugin Importer discovery predicate."""
    namelist = archive.namelist()
    plugins: list[dict[str, str | None]] = []
    for desktop in namelist:
        if not desktop.endswith(".desktop"):
            continue
        config = configparser.ConfigParser()
        try:
            config.read_string(archive.read(desktop).decode("utf-8"))
            name = config["Desktop Entry"]["X-KDE-Library"]
            ui_name = config["Desktop Entry"]["Name"]
        except (UnicodeError, configparser.Error, KeyError) as error:
            raise VerificationError(f"Cannot parse desktop metadata {desktop}: {error}") from error
        module = None
        for filename in namelist:
            if filename.endswith(f"/{name}/") or filename == f"{name}/":
                if f"{filename}__init__.py" in namelist:
                    module = filename
                    break
        if module is None:
            continue
        action = next(
            (
                filename
                for filename in namelist
                if filename.endswith(f"/{name}.action")
                or filename == f"{name}.action"
            ),
            None,
        )
        plugins.append(
            {
                "action": action,
                "desktop": desktop,
                "module": module,
                "name": name,
                "ui_name": ui_name,
            }
        )
    return plugins


def verify_frozen_release(
    artifact: Path,
    freeze_path: Path,
    entries_path: Path,
    expected_tag: str,
    *,
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    freeze = load_json(freeze_path)
    manifest = load_json(entries_path)

    version = freeze.get("overall_plugin_version")
    release_tag = freeze.get("release_tag")
    require(isinstance(version, str) and bool(version), "Overall plug-in version is missing.")
    expected_governance = PUBLICATION_GOVERNANCE_BY_VERSION.get(version)
    require(expected_governance is not None, f"Unsupported frozen release version: {version}")
    require(release_tag == f"krita-v{version}", "Release tag does not match the version.")
    require(release_tag == expected_tag, "Invoked tag does not match frozen release metadata.")
    require(
        freeze.get("publication_governance") == expected_governance,
        "Frozen-artifact publication governance does not match.",
    )
    require(
        freeze.get("publication_mode") == PUBLICATION_MODE,
        "Frozen-artifact publication mode does not match.",
    )
    require(
        freeze.get("qualified_release_platform") == QUALIFIED_PLATFORM,
        "Qualified release platform does not match.",
    )

    artifact_metadata = freeze.get("artifact")
    require(isinstance(artifact_metadata, dict), "Frozen artifact metadata is missing.")
    expected_name = freeze.get("frozen_artifact_filename")
    expected_sha = freeze.get("frozen_artifact_sha256")
    expected_size = freeze.get("frozen_artifact_size")
    expected_count = artifact_metadata.get("entry_count")
    expected_file_count = artifact_metadata.get("file_entry_count", expected_count)
    expected_directory_count = artifact_metadata.get("directory_entry_count", 0)
    expected_repository_path = freeze.get("frozen_artifact_repository_path")

    require(artifact.name == expected_name, "Frozen artifact filename does not match.")
    require(
        repository_relative(artifact, repository_root) == expected_repository_path,
        "Frozen artifact repository path does not match.",
    )
    require(artifact_metadata.get("filename") == expected_name, "Artifact filename drifted.")
    require(artifact_metadata.get("sha256") == expected_sha, "Artifact SHA metadata drifted.")
    require(artifact_metadata.get("size") == expected_size, "Artifact size metadata drifted.")
    require(manifest.get("artifact_filename") == expected_name, "Manifest filename drifted.")
    require(manifest.get("artifact_sha256") == expected_sha, "Manifest SHA drifted.")
    require(manifest.get("artifact_size") == expected_size, "Manifest size drifted.")
    require(manifest.get("entry_count") == expected_count, "Manifest entry count drifted.")
    require(
        manifest.get("file_entry_count", expected_count) == expected_file_count,
        "Manifest file-entry count drifted.",
    )
    require(
        manifest.get("directory_entry_count", 0) == expected_directory_count,
        "Manifest directory-entry count drifted.",
    )

    try:
        actual_size = artifact.stat().st_size
    except OSError as error:
        raise VerificationError(f"Cannot stat frozen artifact {artifact}: {error}") from error
    require(actual_size == expected_size, "Frozen artifact byte size does not match.")
    actual_sha = sha256_file(artifact)
    require(actual_sha == expected_sha, "Frozen artifact SHA-256 does not match.")

    expected_entries = manifest.get("entries")
    require(isinstance(expected_entries, list), "Artifact entry manifest is missing.")
    expected_paths = [entry.get("path") for entry in expected_entries]
    require(all(isinstance(path, str) for path in expected_paths), "Manifest path is invalid.")
    require(expected_paths == sorted(expected_paths), "Manifest paths are not sorted.")
    require(len(expected_paths) == len(set(expected_paths)), "Manifest has duplicate paths.")
    require(len(expected_paths) == expected_count, "Manifest entry list count does not match.")
    for path in expected_paths:
        normalized_member_path(path)

    try:
        with zipfile.ZipFile(artifact) as archive:
            members = archive.infolist()
            actual_paths = [normalized_member_path(member.filename) for member in members]
            require(len(actual_paths) == len(set(actual_paths)), "ZIP has duplicate member paths.")
            require(len(actual_paths) == expected_count, "ZIP entry count does not match.")
            if manifest.get("schema") == 2:
                require(
                    actual_paths == expected_paths,
                    "ZIP member ordering or path set does not match.",
                )
            else:
                require(set(actual_paths) == set(expected_paths), "ZIP path set does not match.")
            actual_file_count = sum(not member.is_dir() for member in members)
            actual_directory_count = sum(member.is_dir() for member in members)
            require(actual_file_count == expected_file_count, "ZIP file-entry count does not match.")
            require(
                actual_directory_count == expected_directory_count,
                "ZIP directory-entry count does not match.",
            )
            by_path = {member.filename: member for member in members}

            for expected in expected_entries:
                path = expected["path"]
                member = by_path[path]
                expected_kind = expected.get("kind", "file")
                require(
                    member.is_dir() == (expected_kind == "directory"),
                    f"Entry kind differs: {path}",
                )
                require(member.file_size == expected.get("size"), f"Entry size differs: {path}")
                require(
                    member.compress_size == expected.get("compressed_size"),
                    f"Compressed entry size differs: {path}",
                )
                require(
                    compression_name(member.compress_type) == expected.get("compression"),
                    f"Compression method differs: {path}",
                )
                digest = hashlib.sha256()
                with archive.open(member) as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(block)
                require(digest.hexdigest() == expected.get("sha256"), f"Entry SHA differs: {path}")
                if "date_time" in expected:
                    require(
                        list(member.date_time) == expected.get("date_time"),
                        f"Entry timestamp differs: {path}",
                    )
                if "external_attr" in expected:
                    require(
                        member.external_attr == expected.get("external_attr"),
                        f"Entry external attributes differ: {path}",
                    )
                if "create_system" in expected:
                    require(
                        member.create_system == expected.get("create_system"),
                        f"Entry create-system differs: {path}",
                    )

            importer_compatibility = freeze.get("importer_compatibility")
            if version in {"1.0.1", "1.0.2", "1.1.0"}:
                require(
                    isinstance(importer_compatibility, dict),
                    "Importer compatibility metadata is missing.",
                )
                required_directory = importer_compatibility.get(
                    "required_module_directory_entry"
                )
                require(
                    required_directory == "gapfill_krita/",
                    "Required importer module directory metadata differs.",
                )
                require(required_directory in actual_paths, "Required module directory is absent.")
                require(
                    "gapfill_krita/__init__.py" in actual_paths,
                    "Required module __init__.py is absent.",
                )
                plugins = discover_plugins(archive)
                expected_ui_name = (
                    "GapFill" if version == "1.0.1" else "GapFill for Krita"
                )
                require(
                    plugins
                    == [
                        {
                            "action": "actions/gapfill_krita.action",
                            "desktop": "gapfill_krita.desktop",
                            "module": "gapfill_krita/",
                            "name": "gapfill_krita",
                            "ui_name": expected_ui_name,
                        }
                    ],
                    "Krita importer discovery result differs.",
                )
            else:
                require(
                    actual_directory_count == 0,
                    "Historical 1.0.0 ZIP unexpectedly contains directory entries.",
                )
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        if isinstance(error, VerificationError):
            raise
        raise VerificationError(f"Frozen artifact ZIP validation failed: {error}") from error

    return {
        "artifact": repository_relative(artifact, repository_root),
        "directory_entry_count": expected_directory_count,
        "entry_count": expected_count,
        "file_entry_count": expected_file_count,
        "sha256": actual_sha,
        "size": actual_size,
        "tag": expected_tag,
        "version": version,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    parser.add_argument("--expected-tag", required=True)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    try:
        result = verify_frozen_release(
            arguments.artifact,
            arguments.freeze,
            arguments.entries,
            arguments.expected_tag,
        )
    except VerificationError as error:
        raise SystemExit(f"FROZEN_RELEASE_ARTIFACT_VERIFICATION_FAIL: {error}") from error
    print(PASS_TOKEN)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
