from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from gapfill_krita.engine.detection import detect_gap_regions
from gapfill_krita.engine.types import DetectionGeometry, GapRegion

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "gapfill"

# Phase 4 does not rewrite the frozen corpus. Guide detection uses the existing
# boundary variants by explicit maintainer direction; faint rasterization stays
# empirical and is therefore not asserted by this normalized-geometry test.
GUIDE_VARIANTS = {
    "D007_guide_enclosure": "guide_as_boundary",
    "D008_isolated_guide_pixel_open": "guide_as_boundary",
    "D009_guide_stroke_to_exterior": "guide_as_boundary",
    "D010_mixed_line_guide_enclosure": "combined_boundaries",
}


def _load_cases() -> list[dict]:
    path = FIXTURE_ROOT / "detection" / "cases.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def _rgba(raster: dict) -> np.ndarray:
    rows = raster["rows"]
    result = np.zeros((len(rows), len(rows[0]), 4), dtype=np.uint8)
    for y, row in enumerate(rows):
        for x, symbol in enumerate(row):
            result[y, x] = raster["palette"][symbol]
    return result


def _u8(raster: dict) -> np.ndarray:
    return np.asarray(raster["rows"], dtype=np.uint8)


def _expected(case: dict) -> list[dict] | None:
    if case["id"].startswith("D012_"):
        return None
    variant = GUIDE_VARIANTS.get(case["id"])
    if variant is None:
        canonical = [item for item in case["expectations"] if item.get("canonical")]
        if not canonical:
            return None
        # D013 has two canonical projections. Full geometry before selection is
        # the Phase 4 detector contract; application scope is checked separately.
        if case["id"] == "D013_selection_boundary":
            variant = "canonical_full_geometry_then_scope"
        else:
            variant = canonical[0]["variant"]
    expectation = next(
        item for item in case["expectations"] if item["variant"] == variant
    )
    return expectation["result"]["components"]


def _actual(regions: list[GapRegion], width: int) -> list[dict]:
    result = []
    for region in regions:
        pixels = sorted(int(value) for value in region.indices)
        application = sorted(int(value) for value in region.target_indices)
        bounds = region.metadata["bounds"]
        result.append(
            {
                "id": int(region.id.removeprefix("gap-")),
                "kind": region.kind.value,
                "pixel_indices": pixels,
                "application_pixel_indices": application,
                "pixel_count": len(pixels),
                "centroid": [int(region.center[0]), int(region.center[1])],
                "bbox": [
                    int(bounds[0]),
                    int(bounds[1]),
                    int(bounds[2]) - int(bounds[0]),
                    int(bounds[3]) - int(bounds[1]),
                ],
            }
        )
    return result


def test_krita_normalized_detection_matches_frozen_phase2_components() -> None:
    checked = 0
    for case in _load_cases():
        expected = _expected(case)
        if expected is None:
            continue
        rgba = _rgba(case["rasters"]["coloring_rgba"])
        selection = _u8(case["rasters"]["selection"]) > 0
        use_selection = case["id"].startswith(("D013_", "D014_"))
        geometry = DetectionGeometry(
            coloring_gap=rgba[..., 3] == 0,
            line_boundary=_u8(case["rasters"]["line_alpha"]) > 0,
            guide_boundary=_u8(case["rasters"]["guide_alpha"]) > 0,
            selection_scope=selection if use_selection else None,
        )
        actual = _actual(
            detect_gap_regions(geometry, int(case["threshold"])), int(case["width"])
        )
        expected_with_scope = []
        for component in expected:
            pixels = component["pixel_indices"]
            application = (
                [index for index in pixels if selection.flat[index]]
                if use_selection
                else pixels
            )
            if not application:
                continue
            expected_with_scope.append(
                {
                    key: value
                    for key, value in component.items()
                    if key not in ("touches_image_edge", "touches_selection_edge")
                }
                | {"application_pixel_indices": application}
            )
        assert actual == expected_with_scope, case["id"]
        checked += 1
    assert checked == 13

