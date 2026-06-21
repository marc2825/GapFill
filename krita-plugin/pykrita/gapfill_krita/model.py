from __future__ import annotations

import os
from pathlib import Path

MODEL_FILENAME = "unet32.onnx"


def find_model_path() -> Path:
    configured = os.environ.get("GAPFILL_KRITA_MODEL")
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    package_root = Path(__file__).resolve().parent
    candidates.append(package_root / "resources" / "models" / MODEL_FILENAME)
    # Development checkout: reuse the web model without duplicating a 25 MB file.
    try:
        repository_root = Path(__file__).resolve().parents[3]
        candidates.append(repository_root / "web" / "public" / "models" / MODEL_FILENAME)
    except IndexError:
        pass
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]
