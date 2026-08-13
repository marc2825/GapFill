from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from gapfill_krita.engine.detection import detect_gap_regions
from gapfill_krita.engine.patches import build_model_patches
from gapfill_krita.engine.postprocessing import segment_colored_regions, select_region_color
from gapfill_krita.engine.types import GapKind, GapRegion, LayerImages

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "gapfill"


def _load(relative: str) -> dict:
    return json.loads((FIXTURE_ROOT / relative).read_text(encoding="utf-8"))


def _rgba(raster: dict) -> np.ndarray:
    height = len(raster["rows"])
    width = len(raster["rows"][0])
    result = np.zeros((height, width, 4), dtype=np.uint8)
    for y, row in enumerate(raster["rows"]):
        for x, symbol in enumerate(row):
            result[y, x] = raster["palette"][symbol]
    return result


def _u8(raster: dict) -> np.ndarray:
    return np.asarray(raster["rows"], dtype=np.uint8)


def _images(case: dict) -> LayerImages:
    coloring = _rgba(case["rasters"]["coloring_rgba"])
    line = np.zeros_like(coloring)
    guide = np.zeros_like(coloring)
    line[..., 3] = _u8(case["rasters"]["line_alpha"])
    guide[..., 3] = _u8(case["rasters"]["guide_alpha"])
    return LayerImages(coloring=coloring, line_art=line, guides=guide)


def _components(regions: list[GapRegion], width: int, height: int) -> list[dict]:
    result = []
    for region in regions:
        indices = sorted(int(value) for value in region.indices)
        xs = [index % width for index in indices]
        ys = [index // width for index in indices]
        bounds = region.metadata["bounds"]
        result.append(
            {
                "id": 0,
                "kind": region.kind.value,
                "pixel_indices": indices,
                "pixel_count": len(indices),
                "centroid": [sum(xs) // len(xs), sum(ys) // len(ys)],
                "bbox": [
                    int(bounds[0]),
                    int(bounds[1]),
                    int(bounds[2]) - int(bounds[0]),
                    int(bounds[3]) - int(bounds[1]),
                ],
                "touches_image_edge": any(
                    x == 0 or y == 0 or x + 1 == width or y + 1 == height
                    for x, y in zip(xs, ys)
                ),
                "touches_selection_edge": False,
            }
        )
    result.sort(key=lambda item: item["pixel_indices"][0])
    for index, item in enumerate(result):
        item["id"] = index
    return result


def test_shared_detection_fixtures_characterize_current_krita_behavior() -> None:
    cases = {case["id"]: case for case in _load("detection/cases.json")["cases"]}
    rows = _load("parity/characterization.json")["detection"]
    assert len(rows) >= 14
    for row in rows:
        case = cases[row["case_id"]]
        images = _images(case)
        actual = _components(
            detect_gap_regions(images, int(case["threshold"])),
            images.width,
            images.height,
        )
        assert actual == row["observations"]["krita_current"], case["id"]


def test_shared_patch_fixtures_characterize_current_krita_behavior() -> None:
    data = _load("patch/cases.json")
    for case in data["cases"]:
        source = case["source"]
        width, height = int(source["width"]), int(source["height"])
        variants = {item["variant"]: item["result"] for item in case["expectations"]}
        variant = (
            "suppress_target_guide"
            if case["id"] == "P006_target_guide_suppression"
            else "line_plus_guide"
            if case["id"] == "P005_guide_delta"
            else "training_line_only"
        )
        expected = variants[variant]
        coloring = np.full((height, width, 4), 255, dtype=np.uint8)
        line = np.zeros_like(coloring)
        guide = np.zeros_like(coloring)
        for index in source["gap_indices"]:
            coloring[int(index) // width, int(index) % width] = (0, 0, 0, 0)
        for index in source["line_active_indices"]:
            line[int(index) // width, int(index) % width, 3] = 255
        for index in source["guide_active_indices"]:
            guide[int(index) // width, int(index) % width, 3] = 255
        gap = GapRegion(
            id="gap-0",
            indices=np.asarray(source["gap_indices"], dtype=np.int64),
            center=tuple(expected["centroid"]),
            kind=(
                GapKind.GUIDE
                if case["id"] == "P006_target_guide_suppression"
                else GapKind.TRANSPARENT
            ),
        )
        _, line_patch, guide_patch, gap_mask = build_model_patches(
            LayerImages(coloring=coloring, line_art=line, guides=guide), gap
        )
        boundary = (line_patch.rgba[..., 3] > 0) | (guide_patch.rgba[..., 3] > 0)
        assert np.flatnonzero(boundary.reshape(-1)).tolist() == expected["tensor"][
            "channel_0_active_indices"
        ]
        assert np.flatnonzero(gap_mask.reshape(-1)).tolist() == expected["tensor"][
            "channel_1_active_indices"
        ]


def test_shared_postprocess_fixtures_characterize_current_krita_behavior() -> None:
    cases = {case["id"]: case for case in _load("postprocess/cases.json")["cases"]}
    rows = _load("parity/characterization.json")["postprocess"]
    for row in rows:
        case = cases[row["case_id"]]
        rgba = _rgba(case["coloring_rgba"])
        label_maps = case["label_maps"]
        label_name = (
            "colored_components"
            if "colored_components" in label_maps
            else "seed_relative"
            if "seed_relative" in label_maps
            else next(iter(label_maps))
        )
        if "seed_relative" in label_maps:
            blank = np.zeros_like(rgba)
            labels, _ = segment_colored_regions(rgba, blank, blank)
            assert labels.tolist() == label_maps["seed_relative"]
        labels = np.asarray(label_maps[label_name], dtype=np.int32)
        actual = select_region_color(
            rgba,
            labels,
            int(labels.max(initial=0)),
            np.asarray(case["probability_map"], dtype=np.float32),
        )
        assert list(actual) == row["observations"]["krita_current"]["rgb"], case["id"]
