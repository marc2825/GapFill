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
    / "1.1.0"
    / "gapfill-for-krita-windows-x86_64.zip"
)
FREEZE = RELEASE / "1.1.0" / "freeze.json"
MANIFEST = RELEASE / "1.1.0" / "artifact-entries.json"
PREDECESSOR = (
    RELEASE
    / "artifacts"
    / "1.0.2"
    / "gapfill-for-krita-windows-x86_64.zip"
)

VERIFY_SPEC = importlib.util.spec_from_file_location(
    "gapfill_release_110_verify",
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


def test_release_110_frozen_artifact_verifies_exactly() -> None:
    assert VERIFY.verify_frozen_release(
        ARTIFACT, FREEZE, MANIFEST, "krita-v1.1.0"
    ) == {
        "artifact": (
            "krita-plugin/release/artifacts/1.1.0/"
            "gapfill-for-krita-windows-x86_64.zip"
        ),
        "directory_entry_count": 117,
        "entry_count": 1012,
        "file_entry_count": 895,
        "sha256": "541cba4b205d50ff307191afed349209c19d54506a0930413b9a92780a22a767",
        "size": 48225467,
        "tag": "krita-v1.1.0",
        "version": "1.1.0",
    }


def test_release_110_version_naming_source_and_tag_policy_are_exact() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert freeze["overall_plugin_version"] == "1.1.0"
    assert freeze["release_tag"] == "krita-v1.1.0"
    assert freeze["product"] == {
        "docker_name": "GapFill",
        "plugin_manager_name": "GapFill for Krita",
        "release_title": "GapFill for Krita 1.1.0",
        "technical_identity": "gapfill_krita",
        "user_facing_name": "GapFill for Krita",
    }
    assert freeze["source"] == {
        "branch": "main",
        "commit": "6093dc40a391711ec087692a53eade5f2b6834e9",
        "subject": "release(krita): prepare GapFill for Krita 1.1.0",
    }
    assert freeze["prospective_tag_target"] == {
        "selection": "FROZEN_CANDIDATE_COMMIT_CONTAINING_THIS_FREEZE_RECORD",
        "later_documentation_commits_are_tag_targets": False,
    }
    assert freeze["artifact_entry_manifest"]["sha256"] == sha256(MANIFEST)


def test_release_110_payload_delta_is_exact_and_contains_no_development_material() -> None:
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
        assert changed == freeze["payload_delta_from_1_0_2"]["changed_files"]
        names = current.namelist()
        assert "gapfill_krita/" in names
        assert not any(
            "offf" in name.lower()
            or "overflow-floodfill" in name.lower()
            or "__pycache__" in name
            or ".pytest_cache" in name
            or name.endswith((".pyc", ".pyo", ".jsonl", ".dmp", ".ses"))
            or "/tests/" in name
            or "host_tests" in name
            or "probe" in name.lower()
            for name in names
        )


def test_release_110_frozen_identities_and_host_scope_are_exact() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert freeze["identities"] == {
        "fixture_manifest_sha256": (
            "6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c"
        ),
        "model_sidecar_sha256": (
            "58ca7fb15c414fabdf65019fc42d341f30398d3dc27b81b97da9c5a4ebffa398"
        ),
        "native_helper_sha256": (
            "ad2fa7463d59dca74a92dc867734b38eb7aa49821b163547da442147348f8746"
        ),
        "onnx_sha256": (
            "8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78"
        ),
    }
    assert freeze["host_evidence"]["record"] == "docs/krita-model-input-modes.md"
    assert "BOUNDED REAL-HOST QUALIFICATION PASS" in (
        freeze["host_evidence"]["classification"]
    )
    assert "NOT ATTRIBUTED" in freeze["host_evidence"]["known_crash_classification"]
