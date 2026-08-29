from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import warnings
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "krita-plugin" / "scripts" / "verify_frozen_release.py"
SPEC = importlib.util.spec_from_file_location("gapfill_verify_frozen_release", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VERIFY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERIFY
SPEC.loader.exec_module(VERIFY)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_zip(path: Path, entries: list[tuple[str, bytes]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)


def entry_manifest(path: Path) -> list[dict[str, object]]:
    with zipfile.ZipFile(path) as archive:
        return sorted(
            [
                {
                    "compressed_size": info.compress_size,
                    "compression": "deflate",
                    "path": info.filename,
                    "sha256": hashlib.sha256(archive.read(info)).hexdigest(),
                    "size": info.file_size,
                }
                for info in archive.infolist()
            ],
            key=lambda item: str(item["path"]),
        )


def synthetic_release(
    root: Path,
    actual_entries: list[tuple[str, bytes]],
    *,
    expected_entries: list[tuple[str, bytes]] | None = None,
) -> tuple[Path, Path, Path]:
    artifact = root / "release" / "artifacts" / "gapfill-krita-windows-x86_64.zip"
    write_zip(artifact, actual_entries)
    expected_zip = root / "expected.zip"
    write_zip(expected_zip, expected_entries or actual_entries)
    expected_manifest = entry_manifest(expected_zip)
    artifact_sha = sha256(artifact)
    artifact_size = artifact.stat().st_size
    entry_count = len(expected_manifest)

    manifest = {
        "artifact_filename": artifact.name,
        "artifact_sha256": artifact_sha,
        "artifact_size": artifact_size,
        "entries": expected_manifest,
        "entry_count": entry_count,
    }
    freeze = {
        "artifact": {
            "entry_count": entry_count,
            "filename": artifact.name,
            "sha256": artifact_sha,
            "size": artifact_size,
        },
        "frozen_artifact_filename": artifact.name,
        "frozen_artifact_repository_path": artifact.relative_to(root).as_posix(),
        "frozen_artifact_sha256": artifact_sha,
        "frozen_artifact_size": artifact_size,
        "overall_plugin_version": "1.0.0",
        "publication_governance": VERIFY.PUBLICATION_GOVERNANCE,
        "publication_mode": VERIFY.PUBLICATION_MODE,
        "qualified_release_platform": VERIFY.QUALIFIED_PLATFORM,
        "release_tag": "krita-v1.0.0",
    }
    freeze_path = root / "freeze.json"
    entries_path = root / "entries.json"
    freeze_path.write_text(json.dumps(freeze), encoding="utf-8")
    entries_path.write_text(json.dumps(manifest), encoding="utf-8")
    return artifact, freeze_path, entries_path


def verify_synthetic(root: Path, files: tuple[Path, Path, Path]) -> dict[str, object]:
    artifact, freeze, entries = files
    return VERIFY.verify_frozen_release(
        artifact,
        freeze,
        entries,
        "krita-v1.0.0",
        repository_root=root,
    )


def test_committed_frozen_artifact_and_governance_are_exact() -> None:
    result = VERIFY.verify_frozen_release(
        ROOT
        / "krita-plugin"
        / "release"
        / "artifacts"
        / "gapfill-krita-windows-x86_64.zip",
        ROOT / "krita-plugin" / "release" / "freeze.json",
        ROOT / "krita-plugin" / "release" / "artifact-entries.json",
        "krita-v1.0.0",
    )
    assert result["sha256"] == (
        "7001c1bf92aa7abb5840baf52fe07457ab06cb80074297488e67ded212ab74e2"
    )
    assert result["size"] == 48197787
    assert result["entry_count"] == 895

    freeze = json.loads(
        (ROOT / "krita-plugin" / "release" / "freeze.json").read_text()
    )
    assert freeze["publication_governance"] == VERIFY.PUBLICATION_GOVERNANCE
    assert freeze["publication_mode"] == VERIFY.PUBLICATION_MODE
    assert freeze["qualified_release_platform"] == "windows-x86_64"
    assert freeze["host_matrix"]["Q"] == "ROW_Q_HOST_CONDITION_UNAVAILABLE"
    assert freeze["identities"] == {
        "display_oracle_v2_sha256": (
            "a0d6a02bcc678ed316a18e26da17a693293e0ac22d4579d992de6eeb21844f35"
        ),
        "fixture_manifest_sha256": (
            "6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c"
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
        "overlay_sha256": (
            "e9aeb11334be91f81025ea2e1b19e2cd28bbe2b3da01f80c5ec66e3c07e5a609"
        ),
        "production_semantic_sha256": (
            "b3812c8a00aa359097d9395b13d27e55433b311584a00e6906de0f426f5acc38"
        ),
    }


def test_synthetic_valid_release_passes(tmp_path: Path) -> None:
    result = verify_synthetic(tmp_path, synthetic_release(tmp_path, [("payload", b"ok")]))
    assert result["entry_count"] == 1


def test_changed_zip_byte_is_rejected(tmp_path: Path) -> None:
    files = synthetic_release(tmp_path, [("payload", b"ok")])
    with files[0].open("ab") as handle:
        handle.write(b"changed")
    with pytest.raises(VERIFY.VerificationError, match="byte size"):
        verify_synthetic(tmp_path, files)


@pytest.mark.parametrize(
    ("actual", "expected", "message"),
    [
        ([("a", b"a")], [("a", b"a"), ("b", b"b")], "entry count"),
        ([("a", b"a"), ("b", b"b")], [("a", b"a")], "entry count"),
        ([("a", b"evil")], [("a", b"good")], "Entry SHA differs"),
        ([("../escape", b"x")], None, "traverses upward"),
    ],
)
def test_archive_structure_or_content_drift_is_rejected(
    tmp_path: Path,
    actual: list[tuple[str, bytes]],
    expected: list[tuple[str, bytes]] | None,
    message: str,
) -> None:
    files = synthetic_release(tmp_path, actual, expected_entries=expected)
    with pytest.raises(VERIFY.VerificationError, match=message):
        verify_synthetic(tmp_path, files)


def test_duplicate_archive_path_is_rejected(tmp_path: Path) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        files = synthetic_release(
            tmp_path,
            [("duplicate", b"one"), ("duplicate", b"two")],
            expected_entries=[("duplicate", b"one")],
        )
    with pytest.raises(VERIFY.VerificationError, match="duplicate"):
        verify_synthetic(tmp_path, files)


def test_wrong_version_and_tag_are_rejected(tmp_path: Path) -> None:
    files = synthetic_release(tmp_path, [("payload", b"ok")])
    freeze = json.loads(files[1].read_text())
    freeze["overall_plugin_version"] = "2.0.0"
    files[1].write_text(json.dumps(freeze), encoding="utf-8")
    with pytest.raises(VERIFY.VerificationError, match="version"):
        verify_synthetic(tmp_path, files)

    freeze["overall_plugin_version"] = "1.0.0"
    freeze["release_tag"] = "krita-v2.0.0"
    files[1].write_text(json.dumps(freeze), encoding="utf-8")
    with pytest.raises(VERIFY.VerificationError, match="version"):
        verify_synthetic(tmp_path, files)


def test_frozen_tag_workflow_verifies_before_windows_only_upload() -> None:
    workflow = (ROOT / ".github" / "workflows" / "krita-plugin-bundles.yml").read_text()
    frozen = workflow.split("  frozen-release:\n", 1)[1].split(
        "  development-bundles:\n", 1
    )[0]
    development = workflow.split("  development-bundles:\n", 1)[1]

    assert "github.event_name == 'push'" in frozen
    assert "refs/tags/krita-v" in frozen
    assert "verify_frozen_release.py" in frozen
    assert "gapfill-krita-windows-x86_64.zip" in frozen
    assert "pip install" not in frozen
    assert "requirements-runtime.txt" not in frozen
    assert "build_plugin.py" not in frozen
    assert "--native-helper" not in frozen
    assert "matrix.platform" not in frozen
    assert frozen.index("Verify exact frozen release artifact") < frozen.index(
        "Upload verified frozen Windows artifact"
    )

    assert "github.event_name == 'workflow_dispatch'" in development
    assert "development-gapfill-krita-${{ matrix.platform }}" in development
    assert "pip install -r krita-plugin/requirements-runtime.txt" in development
