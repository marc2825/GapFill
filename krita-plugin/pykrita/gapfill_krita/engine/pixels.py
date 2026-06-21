from __future__ import annotations

import numpy as np


def bgra_bytes_to_rgba(raw: object, width: int, height: int) -> np.ndarray:
    """Convert Krita's integer-RGBA byte order (BGRA) to engine RGBA."""
    expected = width * height * 4
    data = np.frombuffer(bytes(raw), dtype=np.uint8)  # type: ignore[arg-type]
    if data.size != expected:
        raise RuntimeError(f"Krita returned {data.size} pixel bytes; expected {expected}.")
    bgra = data.reshape((height, width, 4))
    return bgra[..., [2, 1, 0, 3]].copy()
