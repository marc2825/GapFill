"""Fail-closed loader for the version-pinned Krita native transaction helper."""

from __future__ import annotations

import hashlib
import importlib
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable

from .qt_compat import qVersion

EXPECTED_KRITA = "5.3.3 (git 858d352)"
EXPECTED_QT = "5.15.7"
EXPECTED_PYTHON = (3, 13, 5)
EXPECTED_MACHINE = "AMD64"
NATIVE_MODULE_NAME = "gapfill_krita_native_5_3_3"
NATIVE_FILENAME = f"{NATIVE_MODULE_NAME}.cp313-win_amd64.pyd"
NATIVE_SHA256 = "ad2fa7463d59dca74a92dc867734b38eb7aa49821b163547da442147348f8746"
NATIVE_HELPER_VERSION = "1.0.0-krita-5.3.3-858d352"


class NativeHostError(RuntimeError):
    """The installed native helper cannot safely serve the current host."""


@dataclass(frozen=True)
class NativeHostIdentity:
    os_name: str
    machine: str
    python: tuple[int, int, int]
    krita: str
    qt: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def current_host_identity(application) -> NativeHostIdentity:
    return NativeHostIdentity(
        os_name=os.name,
        machine=platform.machine(),
        python=sys.version_info[:3],
        krita=str(application.version()),
        qt=str(qVersion()),
    )


def require_supported_host(identity: NativeHostIdentity) -> None:
    expected = NativeHostIdentity(
        os_name="nt",
        machine=EXPECTED_MACHINE,
        python=EXPECTED_PYTHON,
        krita=EXPECTED_KRITA,
        qt=EXPECTED_QT,
    )
    if identity != expected:
        raise NativeHostError(
            "GapFill native Apply supports only Windows x64, Krita "
            f"{EXPECTED_KRITA}, Qt {EXPECTED_QT}, and CPython "
            f"{'.'.join(map(str, EXPECTED_PYTHON))}; received "
            f"os={identity.os_name!r}, machine={identity.machine!r}, "
            f"python={identity.python!r}, krita={identity.krita!r}, qt={identity.qt!r}."
        )


def native_helper_path() -> Path:
    return Path(__file__).resolve().parent / "_native" / NATIVE_FILENAME


def _validate_abi(module: ModuleType) -> None:
    info = module.abi_info()
    expected = {
        "helper_version": NATIVE_HELPER_VERSION,
        "architecture": "x86_64/AMD64",
        "python_abi": "cp313-win_amd64",
        "expected_krita": EXPECTED_KRITA,
        "expected_qt": EXPECTED_QT,
        "crt": "UCRT",
        "cxx_standard_library": "libc++",
        "write_primitive": "KisPaintDevice::writeBytes",
        "transaction": "KisTransaction/endAndTake",
        "production_version_pinned": 1,
    }
    mismatches = {
        key: (expected_value, info.get(key))
        for key, expected_value in expected.items()
        if info.get(key) != expected_value
    }
    if mismatches:
        raise NativeHostError(f"GapFill native helper ABI metadata mismatch: {mismatches}")
    if not callable(getattr(module, "apply_exact_patch", None)):
        raise NativeHostError("GapFill native helper has no apply_exact_patch operation.")


def _validate_loaded_path(module: ModuleType, expected_path: Path) -> None:
    loaded_value = getattr(module, "__file__", None)
    if not loaded_value:
        raise NativeHostError("The loaded GapFill native helper has no module file identity.")
    loaded_path = Path(loaded_value)
    if os.path.normcase(str(loaded_path.resolve())) != os.path.normcase(
        str(expected_path.resolve())
    ):
        raise NativeHostError(
            "The loaded GapFill native helper came from an unexpected path: "
            f"expected {expected_path}, received {loaded_path}."
        )
    loaded_hash = _sha256(loaded_path)
    if loaded_hash != NATIVE_SHA256:
        raise NativeHostError(
            "The loaded GapFill native helper failed its SHA-256 check: "
            f"expected {NATIVE_SHA256}, received {loaded_hash}."
        )


def load_native_helper(
    application,
    *,
    identity: NativeHostIdentity | None = None,
    helper_path: Path | None = None,
    importer: Callable[[str], ModuleType] = importlib.import_module,
) -> ModuleType:
    """Load the one supported helper or fail without any mutation fallback."""

    require_supported_host(identity or current_host_identity(application))
    path = helper_path or native_helper_path()
    if not path.is_file():
        raise NativeHostError(
            f"The version-pinned GapFill native helper is missing: {path}. "
            "Install the Windows x64 Krita 5.3.3 qualification bundle."
        )
    actual_hash = _sha256(path)
    if actual_hash != NATIVE_SHA256:
        raise NativeHostError(
            "The GapFill native helper failed its SHA-256 check: "
            f"expected {NATIVE_SHA256}, received {actual_hash}."
        )
    try:
        module = importer(f"{__package__}._native.{NATIVE_MODULE_NAME}")
    except Exception as error:
        raise NativeHostError(f"The GapFill native helper could not load: {error}") from error
    try:
        _validate_loaded_path(module, path)
        _validate_abi(module)
    except NativeHostError:
        raise
    except Exception as error:
        raise NativeHostError(
            f"The GapFill native helper failed identity/ABI validation: {error}"
        ) from error
    return module
