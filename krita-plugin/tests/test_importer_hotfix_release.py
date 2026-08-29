from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "krita-plugin" / "release"
PREDECESSOR = RELEASE / "artifacts" / "gapfill-krita-windows-x86_64.zip"
HOTFIX = RELEASE / "artifacts" / "1.0.1" / "gapfill-krita-windows-x86_64.zip"
HOTFIX_FREEZE = RELEASE / "1.0.1" / "freeze.json"
HOTFIX_MANIFEST = RELEASE / "1.0.1" / "artifact-entries.json"

IMPORTER_SPEC = importlib.util.spec_from_file_location(
    "gapfill_hotfix_importer_compatibility",
    ROOT / "krita-plugin" / "scripts" / "krita_importer_compatibility.py",
)
VERIFY_SPEC = importlib.util.spec_from_file_location(
    "gapfill_hotfix_verify_frozen_release",
    ROOT / "krita-plugin" / "scripts" / "verify_frozen_release.py",
)
assert IMPORTER_SPEC is not None and IMPORTER_SPEC.loader is not None
assert VERIFY_SPEC is not None and VERIFY_SPEC.loader is not None
IMPORTER = importlib.util.module_from_spec(IMPORTER_SPEC)
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
IMPORTER_SPEC.loader.exec_module(IMPORTER)
VERIFY_SPEC.loader.exec_module(VERIFY)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_payloads(archive: zipfile.ZipFile) -> dict[str, tuple[int, str]]:
    return {
        member.filename: (
            member.file_size,
            hashlib.sha256(archive.read(member)).hexdigest(),
        )
        for member in archive.infolist()
        if not member.is_dir()
    }


def file_metadata(archive: zipfile.ZipFile) -> dict[str, tuple[object, ...]]:
    return {
        member.filename: (
            member.compress_type,
            member.compress_size,
            member.file_size,
            member.CRC,
            member.date_time,
            member.external_attr,
            member.create_system,
        )
        for member in archive.infolist()
        if not member.is_dir()
    }


def test_committed_hotfix_verifies_as_exact_1_0_1_release() -> None:
    result = VERIFY.verify_frozen_release(
        HOTFIX,
        HOTFIX_FREEZE,
        HOTFIX_MANIFEST,
        "krita-v1.0.1",
    )
    assert result == {
        "artifact": (
            "krita-plugin/release/artifacts/1.0.1/"
            "gapfill-krita-windows-x86_64.zip"
        ),
        "directory_entry_count": 117,
        "entry_count": 1012,
        "file_entry_count": 895,
        "sha256": "e001ad4db0a049db23f2839d780ff0ede810fc3f21c2d3fc574ef8bc12c93b19",
        "size": 48218711,
        "tag": "krita-v1.0.1",
        "version": "1.0.1",
    }


def test_hotfix_preserves_every_predecessor_file_payload_and_zip_metadata() -> None:
    with zipfile.ZipFile(PREDECESSOR) as predecessor, zipfile.ZipFile(HOTFIX) as hotfix:
        assert file_payloads(hotfix) == file_payloads(predecessor)
        assert file_metadata(hotfix) == file_metadata(predecessor)


def test_hotfix_directory_entries_are_complete_safe_and_canonical() -> None:
    with zipfile.ZipFile(HOTFIX) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        directories = [member.filename for member in members if member.is_dir()]
        files = [member.filename for member in members if not member.is_dir()]

        expected_directories: set[str] = set()
        for filename in files:
            parent = PurePosixPath(filename).parent
            while parent != PurePosixPath("."):
                expected_directories.add(f"{parent.as_posix()}/")
                parent = parent.parent

        assert names == sorted(names)
        assert len(names) == len(set(names)) == 1012
        assert files and len(files) == 895
        assert directories == sorted(expected_directories)
        assert len(directories) == 117
        assert "gapfill_krita/" in directories
        assert "gapfill_krita/__init__.py" in files

        for member in members:
            name = member.filename
            core = name[:-1] if member.is_dir() else name
            path = PurePosixPath(core)
            assert not path.is_absolute()
            assert not PureWindowsPath(name).drive
            assert ".." not in path.parts
            assert "\\" not in name
            if member.is_dir():
                assert member.date_time == (1980, 1, 1, 0, 0, 0)
                assert member.compress_type == zipfile.ZIP_STORED
                assert member.external_attr == (0o40755 << 16) | 0x10
                assert member.create_system == 3


def test_hotfix_importer_discovery_and_freeze_metadata_are_exact() -> None:
    freeze = json.loads(HOTFIX_FREEZE.read_text(encoding="utf-8"))
    manifest = json.loads(HOTFIX_MANIFEST.read_text(encoding="utf-8"))
    assert freeze["overall_plugin_version"] == "1.0.1"
    assert freeze["release_tag"] == "krita-v1.0.1"
    assert freeze["publication_governance"] == (
        "GAPFILL_1_0_1_IMPORTER_PACKAGING_HOTFIX_V1_GOVERNANCE_ADOPTED"
    )
    assert freeze["predecessor"]["release_tag"] == "krita-v1.0.0"
    assert freeze["predecessor"]["artifact_sha256"] == (
        "7001c1bf92aa7abb5840baf52fe07457ab06cb80074297488e67ded212ab74e2"
    )
    assert freeze["semantic_payload_relation"] == (
        "FILE_ENTRIES_BYTE_IDENTICAL_TO_1_0_0"
    )
    assert freeze["build"]["builder_sha256"] == sha256(
        ROOT / "krita-plugin" / "scripts" / "build_plugin.py"
    )
    assert freeze["artifact_entry_manifest"]["sha256"] == sha256(HOTFIX_MANIFEST)
    assert manifest["artifact_sha256"] == sha256(HOTFIX)
    with zipfile.ZipFile(PREDECESSOR) as predecessor:
        assert IMPORTER.diagnosis(predecessor, "gapfill_krita") == (
            "REQUIRED_MODULE_DIRECTORY_ENTRY_ABSENT"
        )
        assert IMPORTER.discover_plugins(predecessor) == []
    with zipfile.ZipFile(HOTFIX) as hotfix:
        assert IMPORTER.diagnosis(hotfix, "gapfill_krita") == "PLUGIN_DISCOVERABLE"
        assert IMPORTER.discover_plugins(hotfix) == [
            {
                "action": "actions/gapfill_krita.action",
                "desktop": "gapfill_krita.desktop",
                "module": "gapfill_krita/",
                "name": "gapfill_krita",
                "ui_name": "GapFill",
            }
        ]


def test_hotfix_production_identities_remain_frozen() -> None:
    freeze = json.loads(HOTFIX_FREEZE.read_text(encoding="utf-8"))
    assert freeze["identities"] == {
        "display_oracle_v2_sha256": (
            "a0d6a02bcc678ed316a18e26da17a693293e0ac22d4579d992de6eeb21844f35"
        ),
        "lifecycle_sha256": (
            "94b42368efc0df7c37333fe864f57593254557c2b181676106efd0a45e535e5f"
        ),
        "model_sidecar_sha256": (
            "2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5"
        ),
        "native_helper_sha256": (
            "ad2fa7463d59dca74a92dc867734b38eb7aa49821b163547da442147348f8746"
        ),
        "onnx_sha256": (
            "8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78"
        ),
        "production_semantic_sha256": (
            "b3812c8a00aa359097d9395b13d27e55433b311584a00e6906de0f426f5acc38"
        ),
    }
