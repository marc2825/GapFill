from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

import numpy as np
from numpy.typing import NDArray

RgbaImage = NDArray[np.uint8]
FlatIndices = NDArray[np.int64]
Rgb = Tuple[int, int, int]


class GapKind(str, Enum):
    TRANSPARENT = "transparent"
    GUIDE = "guide"


@dataclass
class LayerImages:
    """Full-document RGBA/U8 snapshots used by the engine."""

    coloring: RgbaImage
    line_art: RgbaImage
    guides: RgbaImage
    composite: Optional[RgbaImage] = None

    def validate(self) -> None:
        expected = self.coloring.shape
        if len(expected) != 3 or expected[2] != 4:
            raise ValueError("Coloring image must have shape (height, width, 4).")
        for name, image in (
            ("line_art", self.line_art),
            ("guides", self.guides),
        ):
            if image.shape != expected:
                raise ValueError(f"{name} image dimensions do not match coloring.")
            if image.dtype != np.uint8:
                raise ValueError(f"{name} image must use uint8 RGBA pixels.")
        if self.coloring.dtype != np.uint8:
            raise ValueError("Coloring image must use uint8 RGBA pixels.")
        if self.composite is not None and self.composite.shape != expected:
            raise ValueError("Composite image dimensions do not match coloring.")

    @property
    def height(self) -> int:
        return int(self.coloring.shape[0])

    @property
    def width(self) -> int:
        return int(self.coloring.shape[1])


@dataclass
class GapRegion:
    id: str
    indices: FlatIndices
    center: Tuple[int, int]
    kind: GapKind
    predicted_rgb: Optional[Rgb] = None
    preview_rgb: Optional[Rgb] = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def pixel_count(self) -> int:
        return int(self.indices.size)

    @property
    def color(self) -> Optional[Rgb]:
        return self.preview_rgb or self.predicted_rgb
