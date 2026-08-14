#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "gapfill"
GUIDE_VARIANTS = {
    "D007_guide_enclosure": "guide_as_boundary",
    "D008_isolated_guide_pixel_open": "guide_as_boundary",
    "D009_guide_stroke_to_exterior": "guide_as_boundary",
    "D010_mixed_line_guide_enclosure": "combined_boundaries",
}


def expected(case: dict) -> list[dict] | None:
    if case["id"].startswith("D012_"):
        return None
    variant = GUIDE_VARIANTS.get(case["id"])
    if variant is None:
        canonical = [item for item in case["expectations"] if item.get("canonical")]
        if not canonical:
            return None
        variant = (
            "canonical_full_geometry_then_scope"
            if case["id"] == "D013_selection_boundary"
            else canonical[0]["variant"]
        )
    return next(
        item["result"]["components"]
        for item in case["expectations"]
        if item["variant"] == variant
    )


def binary(values: list[list[int]], predicate) -> str:
    return "".join("1" if predicate(value) else "0" for row in values for value in row)


def parse_output(output: str) -> list[dict]:
    components = []
    for line in output.splitlines():
        encoded_id, encoded_pixels, encoded_application, encoded_box, encoded_center = (
            line.split("|")
        )
        pixels = [int(value) for value in encoded_pixels.split(",") if value]
        application = [
            int(value) for value in encoded_application.split(",") if value
        ]
        components.append(
            {
                "id": int(encoded_id),
                "kind": "transparent",
                "pixel_indices": pixels,
                "application_pixel_indices": application,
                "pixel_count": len(pixels),
                "centroid": [int(value) for value in encoded_center.split(",")],
                "bbox": [int(value) for value in encoded_box.split(",")],
            }
        )
    return components


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: test_csp_phase4_detection.py DETECTION_PROBE")
    probe = Path(sys.argv[1])
    cases = json.loads(
        (FIXTURE_ROOT / "detection" / "cases.json").read_text(encoding="utf-8")
    )["cases"]
    checked = 0
    for case in cases:
        expected_components = expected(case)
        if expected_components is None:
            continue
        rasters = case["rasters"]
        coloring = rasters["coloring_rgba"]
        alpha = [
            [coloring["palette"][symbol][3] for symbol in row]
            for row in coloring["rows"]
        ]
        use_selection = case["id"].startswith(("D013_", "D014_"))
        selection_rows = rasters["selection"]["rows"]
        selection = binary(selection_rows, lambda value: value > 0)
        command = [
            str(probe),
            str(case["width"]),
            str(case["height"]),
            str(case["threshold"]),
            binary(alpha, lambda value: value == 0),
            binary(rasters["line_alpha"]["rows"], lambda value: value > 0),
            binary(rasters["guide_alpha"]["rows"], lambda value: value > 0),
            selection if use_selection else "-",
        ]
        actual = parse_output(subprocess.run(command, check=True, text=True,
                                             capture_output=True).stdout)
        scoped = []
        flat_selection = [value > 0 for row in selection_rows for value in row]
        for component in expected_components:
            pixels = component["pixel_indices"]
            application = (
                [index for index in pixels if flat_selection[index]]
                if use_selection
                else pixels
            )
            if not application:
                continue
            scoped.append(
                {
                    key: value
                    for key, value in component.items()
                    if key not in ("touches_image_edge", "touches_selection_edge")
                }
                | {"application_pixel_indices": application}
            )
        if actual != scoped:
            raise AssertionError(
                f"{case['id']}\nexpected={scoped!r}\nactual={actual!r}"
            )
        checked += 1
    if checked != 13:
        raise AssertionError(f"expected 13 normalized cases, checked {checked}")
    print(f"CSP Phase 4 normalized detection: {checked}/13 cases passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
