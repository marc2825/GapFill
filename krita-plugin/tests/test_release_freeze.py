from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "krita-plugin" / "release"
FREEZE = RELEASE / "freeze.json"
SOURCE = RELEASE / "source-freeze.json"
ARTIFACT = RELEASE / "artifact-entries.json"
FROZEN_ZIP = RELEASE / "artifacts" / "gapfill-krita-windows-x86_64.zip"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_release_freeze_closes_exact_matrix_and_governance() -> None:
    freeze = load(FREEZE)
    assert freeze["freeze_status"] == "GAPFILL RELEASE/FREEZE READY"
    assert freeze["overall_plugin_version"] == "1.0.0"
    assert freeze["version_governance"] == (
        "GAPFILL_RELEASE_VERSION_V1_GOVERNANCE_ADOPTED"
    )
    assert freeze["release_tag"] == "krita-v1.0.0"
    assert freeze["phase65"]["status"] == "CLOSED"
    assert freeze["source_checkpoint"] == (
        "df4e18c0b3f5e4ca8135ca52cba0b415ad3d52c8"
    )
    expected = {letter: "PASS" for letter in "ABCDEFGHIJKLMNOPRSTUV"}
    expected["Q"] = "ROW_Q_HOST_CONDITION_UNAVAILABLE"
    assert freeze["host_matrix"] == expected
    assert freeze["rows"]["T"]["final_attempt"] == "T-v11"
    assert freeze["rows"]["U"]["final_attempt"] == "U-v1"
    assert freeze["rows"]["V"]["final_attempt"] == "V-v2"


def test_source_freeze_is_sorted_unique_and_preserves_historical_builder() -> None:
    source = load(SOURCE)
    entries = source["entries"]
    assert source["inventory_count"] == len(entries) == 901
    keys = [(item["path"], item["source_root"]) for item in entries]
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))
    with ZipFile(FROZEN_ZIP) as frozen:
        for item in entries:
            if item["source_root"] != "repository":
                continue
            if item["included_in_artifact"]:
                data = frozen.read(item["archive_path"])
                assert len(data) == item["size"]
                assert hashlib.sha256(data).hexdigest() == item["sha256"]
                continue
            if item["category"] == "package_builder":
                assert item == {
                    "archive_path": None,
                    "category": "package_builder",
                    "included_in_artifact": False,
                    "path": "krita-plugin/scripts/build_plugin.py",
                    "sha256": (
                        "7627318aab414c66fb0b396af09ae6e68c265e5af5054e7d539688f37f815455"
                    ),
                    "size": 5162,
                    "source_root": "repository",
                }
                continue
            path = ROOT / item["path"]
            assert path.stat().st_size == item["size"]
            assert sha256(path) == item["sha256"]
    shadowed = [item for item in entries if item["category"] == "shadowed_package_source"]
    assert len(shadowed) == 1
    assert shadowed[0]["included_in_artifact"] is False
    assert shadowed[0]["archive_path"] is None


def test_archive_manifest_is_complete_safe_and_matches_frozen_inputs() -> None:
    source = load(SOURCE)
    artifact = load(ARTIFACT)
    entries = artifact["entries"]
    assert artifact["entry_count"] == len(entries) == 895
    assert artifact["artifact_sha256"] == (
        "7001c1bf92aa7abb5840baf52fe07457ab06cb80074297488e67ded212ab74e2"
    )
    names = [item["path"] for item in entries]
    assert names == sorted(names)
    assert len(names) == len(set(names))
    forbidden = (":memory:", "__pycache__", ".pyc", "host_tests", ".git")
    assert not any(any(token in name for token in forbidden) for name in names)
    assert not any(name.startswith(("/", "\\")) or ".." in Path(name).parts for name in names)

    source_by_archive = {
        item["archive_path"]: item
        for item in source["entries"]
        if item["included_in_artifact"] and item["archive_path"] is not None
    }
    artifact_by_name = {item["path"]: item for item in entries}
    assert source_by_archive.keys() == artifact_by_name.keys()
    for name, item in source_by_archive.items():
        assert item["sha256"] == artifact_by_name[name]["sha256"]
        assert item["size"] == artifact_by_name[name]["size"]


def test_freeze_references_exact_manifests_and_historical_artifact() -> None:
    freeze = load(FREEZE)
    assert freeze["source_freeze"]["sha256"] == sha256(SOURCE)
    assert freeze["artifact_entry_manifest"]["sha256"] == sha256(ARTIFACT)
    assert freeze["artifact"]["filename"] == "gapfill-krita-windows-x86_64.zip"
    assert freeze["artifact"]["sha256"] == (
        "7001c1bf92aa7abb5840baf52fe07457ab06cb80074297488e67ded212ab74e2"
    )
    assert freeze["historical_qualified_artifact"]["comparison"] == (
        "A_ARTIFACT_BYTES_IDENTICAL"
    )
    assert freeze["historical_qualified_artifact"]["production_payload_drift"] is False
    assert freeze["reproducibility"] == {
        "build_a_equals_build_b": True,
        "byte_comparison": "PASS",
        "result": "PASS",
    }
    assert freeze["release_conventions"]["plugin_version_source"] == (
        "krita-plugin/release/freeze.json#overall_plugin_version"
    )
    assert freeze["release_conventions"]["release_version_status"] == (
        "GAPFILL_RELEASE_VERSION_V1_GOVERNANCE_ADOPTED"
    )


def test_release_scope_stays_narrow() -> None:
    freeze = load(FREEZE)
    limitations = "\n".join(freeze["known_limitations"])
    assert "Full Krita application close" in limitations
    assert "Mixed-profile behavior is not qualified" in limitations
    assert "Arbitrary other ICC profiles" in limitations
    assert "HDR and non-U8" in limitations
    assert "sleeves" in limitations
    assert freeze["csp"]["canonical_gapfill"] == "INSUFFICIENT_FOR_GAPFILL_PARITY"
    assert freeze["smoke"]["repository_source_on_import_path"] is False
