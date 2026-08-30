from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "krita-plugin" / "release"
ARTIFACT = (
    RELEASE
    / "artifacts"
    / "1.0.2"
    / "gapfill-for-krita-windows-x86_64.zip"
)
FREEZE = RELEASE / "1.0.2" / "freeze.json"
MANIFEST = RELEASE / "1.0.2" / "artifact-entries.json"
PREDECESSOR = (
    RELEASE / "artifacts" / "1.0.1" / "gapfill-krita-windows-x86_64.zip"
)

VERIFY_SPEC = importlib.util.spec_from_file_location(
    "gapfill_release_102_verify",
    ROOT / "krita-plugin" / "scripts" / "verify_frozen_release.py",
)
assert VERIFY_SPEC is not None and VERIFY_SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(VERIFY)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def payloads(archive: zipfile.ZipFile) -> dict[str, str]:
    return {
        member.filename: hashlib.sha256(archive.read(member)).hexdigest()
        for member in archive.infolist()
        if not member.is_dir()
    }


def test_release_102_frozen_artifact_verifies_exactly() -> None:
    assert VERIFY.verify_frozen_release(
        ARTIFACT, FREEZE, MANIFEST, "krita-v1.0.2"
    ) == {
        "artifact": (
            "krita-plugin/release/artifacts/1.0.2/"
            "gapfill-for-krita-windows-x86_64.zip"
        ),
        "directory_entry_count": 117,
        "entry_count": 1012,
        "file_entry_count": 895,
        "sha256": "34121098dc8f9e50707f686f5585176d0d7067858f21d241e190a2f4f25fa54b",
        "size": 48223574,
        "tag": "krita-v1.0.2",
        "version": "1.0.2",
    }


def test_release_102_version_naming_and_source_are_exact() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert freeze["overall_plugin_version"] == "1.0.2"
    assert freeze["release_tag"] == "krita-v1.0.2"
    assert freeze["product"] == {
        "docker_name": "GapFill",
        "plugin_manager_name": "GapFill for Krita",
        "release_title": "GapFill for Krita 1.0.2",
        "technical_identity": "gapfill_krita",
        "user_facing_name": "GapFill for Krita",
    }
    assert freeze["source"]["commit"] == (
        "d0e1fbfb825d983d5a208f9b3990418a821f1160"
    )
    assert freeze["artifact_entry_manifest"]["sha256"] == sha256(MANIFEST)


def test_release_102_payload_delta_is_exact_and_contains_no_development_material() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    with zipfile.ZipFile(ARTIFACT) as current, zipfile.ZipFile(PREDECESSOR) as old:
        current_payloads = payloads(current)
        old_payloads = payloads(old)
        assert set(current_payloads) == set(old_payloads)
        changed = sorted(
            name
            for name in current_payloads
            if current_payloads[name] != old_payloads[name]
        )
        assert changed == freeze["payload_delta_from_1_0_1"]["changed_files"]
        names = current.namelist()
        assert "gapfill_krita/" in names
        assert not any(
            "offf" in name.lower()
            or "overflow-floodfill" in name.lower()
            or "__pycache__" in name
            or name.endswith((".pyc", ".pyo", ".jsonl"))
            or ":memory:.ses" in name
            or "/tests/" in name
            or "host_tests" in name
            for name in names
        )


def test_release_102_frozen_identities_and_bounded_host_evidence_are_exact() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert freeze["identities"] == {
        "fixture_manifest_sha256": (
            "6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c"
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
    }
    assert freeze["host_evidence"] == {
        "bounded_interaction_smoke": (
            "GAPFILL INTERACTION PATCH BOUNDED REAL-HOST SMOKE PASS"
        ),
        "manual_external_mutation": (
            "MANUAL_EXTERNAL_MUTATION_FAIL_CLOSED_SMOKE_SKIPPED_BY_SCOPE"
        ),
        "manual_external_mutation_automated_regression": "PASS",
        "record": "docs/addon-interaction-1.0.2.md",
    }
