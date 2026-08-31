from __future__ import annotations

import numpy as np
from gapfill_krita.engine.detection import detect_gap_regions
from gapfill_krita.engine.patches import build_model_tensor
from gapfill_krita.engine.types import (
    GapKind,
    GapRegion,
    LayerImages,
    ModelBoundaryMode,
)


def _images(size: int = 40) -> LayerImages:
    shape = (size, size, 4)
    return LayerImages(
        np.zeros(shape, dtype=np.uint8),
        np.zeros(shape, dtype=np.uint8),
        np.zeros(shape, dtype=np.uint8),
    )


def _gap(
    x: int = 20,
    y: int = 20,
    *,
    width: int = 40,
    kind: GapKind = GapKind.TRANSPARENT,
) -> GapRegion:
    return GapRegion(
        "gap-0",
        np.asarray([y * width + x], dtype=np.int64),
        (x, y),
        kind,
    )


def _active(channel: np.ndarray) -> set[tuple[int, int]]:
    return {tuple(point) for point in np.argwhere(channel != 0)}


def test_default_mode_is_byte_identical_to_published_line_only_tensor() -> None:
    images = _images()
    images.line_art[20, 19] = (0, 0, 0, 255)
    images.guides[20, 21, 3] = 255
    gap = _gap()

    default_tensor, default_bounds = build_model_tensor(images, gap)
    explicit_tensor, explicit_bounds = build_model_tensor(
        images, gap, mode=ModelBoundaryMode.LINE_ONLY
    )

    assert default_bounds == explicit_bounds
    assert default_tensor.tobytes() == explicit_tensor.tobytes()
    assert _active(default_tensor[0, 0]) == {(16, 15)}
    assert _active(default_tensor[0, 1]) == {(16, 16)}


def test_line_or_guides_mode_composes_normalized_boundaries_with_exact_or() -> None:
    images = _images()
    images.line_art[20, 19] = (0, 0, 0, 255)
    images.guides[20, 21] = (230, 230, 230, 1)

    tensor, _bounds = build_model_tensor(
        images, _gap(), mode=ModelBoundaryMode.LINE_OR_GUIDES
    )

    assert _active(tensor[0, 0]) == {(16, 15), (16, 17)}
    assert _active(tensor[0, 1]) == {(16, 16)}


def test_line_or_guides_removes_only_the_target_guide_gap_before_or() -> None:
    images = _images()
    images.line_art[20, 19] = (0, 0, 0, 255)
    images.guides[20, 20, 3] = 255
    images.guides[20, 21, 3] = 255

    tensor, _bounds = build_model_tensor(
        images,
        _gap(kind=GapKind.GUIDE),
        mode=ModelBoundaryMode.LINE_OR_GUIDES,
    )

    assert _active(tensor[0, 0]) == {(16, 15), (16, 17)}
    assert _active(tensor[0, 1]) == {(16, 16)}


def test_mode_changes_only_prediction_channel_zero() -> None:
    images = _images()
    images.guides[20, 21, 3] = 255
    gap = _gap()

    line_only, bounds_a = build_model_tensor(
        images, gap, mode=ModelBoundaryMode.LINE_ONLY
    )
    line_or_guides, bounds_b = build_model_tensor(
        images, gap, mode=ModelBoundaryMode.LINE_OR_GUIDES
    )

    assert bounds_a == bounds_b
    assert not np.array_equal(line_only[0, 0], line_or_guides[0, 0])
    assert np.array_equal(line_only[0, 1], line_or_guides[0, 1])


def test_guides_define_detection_topology_in_both_prediction_modes() -> None:
    images = _images(5)
    images.coloring[..., 3] = 255
    images.coloring[1:4, 1:4, 3] = 0
    images.guides[1, 1:4, 3] = 255
    images.guides[3, 1:4, 3] = 255
    images.guides[1:4, 1, 3] = 255
    images.guides[1:4, 3, 3] = 255

    before = detect_gap_regions(images, 10)
    for mode in ModelBoundaryMode:
        # Tensor policy is downstream of detection and cannot alter candidates.
        after = detect_gap_regions(images, 10)
        assert [(gap.indices.tolist(), gap.center) for gap in after] == [
            (gap.indices.tolist(), gap.center) for gap in before
        ]
        if after:
            build_model_tensor(images, after[0], mode=mode)
