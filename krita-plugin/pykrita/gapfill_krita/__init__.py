"""GapFill for Krita plugin entry point."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_vendor = Path(__file__).resolve().parent / "_vendor"
_dll_directory = None
if _vendor.is_dir():
    sys.path.insert(0, str(_vendor))
    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        # Keep the handle alive or Windows removes the DLL search path again.
        _dll_directory = os.add_dll_directory(str(_vendor))

try:
    import krita  # noqa: F401
except ImportError:
    # Core modules remain importable for tests and external tooling.
    pass
else:
    from .plugin import register

    register()
