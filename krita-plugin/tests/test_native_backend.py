from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from gapfill_krita import native_backend


def _qualified_identity(**changes):
    values = {
        "os_name": "nt",
        "machine": "AMD64",
        "python": (3, 13, 5),
        "krita": "5.3.3 (git 858d352)",
        "qt": "5.15.7",
    }
    values.update(changes)
    return native_backend.NativeHostIdentity(**values)


def _abi_info(**changes):
    values = {
        "helper_version": "1.0.0-krita-5.3.3-858d352",
        "architecture": "x86_64/AMD64",
        "python_abi": "cp313-win_amd64",
        "expected_krita": "5.3.3 (git 858d352)",
        "expected_qt": "5.15.7",
        "crt": "UCRT",
        "cxx_standard_library": "libc++",
        "write_primitive": "KisPaintDevice::writeBytes",
        "transaction": "KisTransaction/endAndTake",
        "production_version_pinned": 1,
    }
    values.update(changes)
    return values


def test_native_loader_accepts_only_exact_hash_module_and_abi(tmp_path, monkeypatch):
    helper_path = tmp_path / native_backend.NATIVE_FILENAME
    helper_path.write_bytes(b"native helper test payload")
    monkeypatch.setattr(
        native_backend,
        "NATIVE_SHA256",
        hashlib.sha256(helper_path.read_bytes()).hexdigest(),
    )
    module = SimpleNamespace(
        __file__=str(helper_path),
        abi_info=_abi_info,
        apply_exact_patch=lambda **_request: {},
    )
    imported = []

    loaded = native_backend.load_native_helper(
        None,
        identity=_qualified_identity(),
        helper_path=helper_path,
        importer=lambda name: imported.append(name) or module,
    )

    assert loaded is module
    assert imported == [
        "gapfill_krita._native.gapfill_krita_native_5_3_3"
    ]


@pytest.mark.parametrize(
    "changes",
    [
        {"os_name": "posix"},
        {"machine": "ARM64"},
        {"python": (3, 13, 4)},
        {"krita": "5.3.2"},
        {"qt": "5.15.8"},
    ],
)
def test_native_loader_rejects_every_unsupported_host_before_import(
    tmp_path, changes
):
    imported = []
    with pytest.raises(native_backend.NativeHostError, match="supports only"):
        native_backend.load_native_helper(
            None,
            identity=_qualified_identity(**changes),
            helper_path=tmp_path / native_backend.NATIVE_FILENAME,
            importer=lambda name: imported.append(name),
        )
    assert imported == []


def test_native_loader_rejects_missing_or_wrong_binary_before_import(
    tmp_path, monkeypatch
):
    imported = []
    missing = tmp_path / native_backend.NATIVE_FILENAME
    with pytest.raises(native_backend.NativeHostError, match="missing"):
        native_backend.load_native_helper(
            None,
            identity=_qualified_identity(),
            helper_path=missing,
            importer=lambda name: imported.append(name),
        )

    missing.write_bytes(b"wrong")
    monkeypatch.setattr(native_backend, "NATIVE_SHA256", "0" * 64)
    with pytest.raises(native_backend.NativeHostError, match="SHA-256"):
        native_backend.load_native_helper(
            None,
            identity=_qualified_identity(),
            helper_path=missing,
            importer=lambda name: imported.append(name),
        )
    assert imported == []


def test_native_loader_rejects_import_and_abi_failures(tmp_path, monkeypatch):
    helper_path = tmp_path / native_backend.NATIVE_FILENAME
    helper_path.write_bytes(b"native helper test payload")
    monkeypatch.setattr(
        native_backend,
        "NATIVE_SHA256",
        hashlib.sha256(helper_path.read_bytes()).hexdigest(),
    )

    def broken_import(_name):
        raise ImportError("missing dependency")

    with pytest.raises(native_backend.NativeHostError, match="missing dependency"):
        native_backend.load_native_helper(
            None,
            identity=_qualified_identity(),
            helper_path=helper_path,
            importer=broken_import,
        )

    bad_module = SimpleNamespace(
        __file__=str(helper_path),
        abi_info=lambda: _abi_info(expected_qt="6.0"),
        apply_exact_patch=lambda **_request: {},
    )
    with pytest.raises(native_backend.NativeHostError, match="ABI metadata mismatch"):
        native_backend.load_native_helper(
            None,
            identity=_qualified_identity(),
            helper_path=helper_path,
            importer=lambda _name: bad_module,
        )


def test_native_loader_rejects_preloaded_module_from_another_path(
    tmp_path, monkeypatch
):
    helper_path = tmp_path / native_backend.NATIVE_FILENAME
    helper_path.write_bytes(b"native helper test payload")
    other_path = tmp_path / "other.pyd"
    other_path.write_bytes(helper_path.read_bytes())
    monkeypatch.setattr(
        native_backend,
        "NATIVE_SHA256",
        hashlib.sha256(helper_path.read_bytes()).hexdigest(),
    )
    module = SimpleNamespace(
        __file__=str(other_path),
        abi_info=_abi_info,
        apply_exact_patch=lambda **_request: {},
    )
    with pytest.raises(native_backend.NativeHostError, match="unexpected path"):
        native_backend.load_native_helper(
            None,
            identity=_qualified_identity(),
            helper_path=helper_path,
            importer=lambda _name: module,
        )


def test_native_loader_maps_abi_metadata_exception(tmp_path, monkeypatch):
    helper_path = tmp_path / native_backend.NATIVE_FILENAME
    helper_path.write_bytes(b"native helper test payload")
    monkeypatch.setattr(
        native_backend,
        "NATIVE_SHA256",
        hashlib.sha256(helper_path.read_bytes()).hexdigest(),
    )

    def broken_abi():
        raise RuntimeError("controlled ABI exception")

    module = SimpleNamespace(
        __file__=str(helper_path),
        abi_info=broken_abi,
        apply_exact_patch=lambda **_request: {},
    )
    with pytest.raises(native_backend.NativeHostError, match="identity/ABI.*controlled"):
        native_backend.load_native_helper(
            None,
            identity=_qualified_identity(),
            helper_path=helper_path,
            importer=lambda _name: module,
        )
