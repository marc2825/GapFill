"""Hand-authored controlled inputs for the GapFill Phase 2 corpus."""

from __future__ import annotations

from copy import deepcopy

OPAQUE = [80, 100, 120, 255]
TRANSPARENT = [0, 0, 0, 0]


def _grid(width: int, height: int, value: int) -> list[list[int]]:
    return [[value for _ in range(width)] for _ in range(height)]


def _set(grid: list[list[int]], coords: list[tuple[int, int]], value: int) -> None:
    for x, y in coords:
        grid[y][x] = value


def _palette_rows(
    width: int,
    height: int,
    transparent: list[tuple[int, int]],
    *,
    overrides: dict[tuple[int, int], str] | None = None,
    extra_palette: dict[str, list[int]] | None = None,
) -> dict:
    rows = [["X" for _ in range(width)] for _ in range(height)]
    for x, y in transparent:
        rows[y][x] = "."
    if overrides:
        for (x, y), symbol in overrides.items():
            rows[y][x] = symbol
    palette = {"X": OPAQUE, ".": TRANSPARENT}
    if extra_palette:
        palette.update(extra_palette)
    return {
        "encoding": "palette_rgba8",
        "palette": palette,
        "rows": ["".join(row) for row in rows],
    }


def _rasters(
    width: int,
    height: int,
    coloring: dict,
    *,
    line: list[tuple[int, int]] | None = None,
    guide: list[tuple[int, int]] | None = None,
    selection: list[tuple[int, int]] | None = None,
    line_gray_overrides: dict[tuple[int, int], int] | None = None,
    line_alpha_overrides: dict[tuple[int, int], int] | None = None,
) -> dict:
    line_gray = _grid(width, height, 255)
    line_alpha = _grid(width, height, 0)
    _set(line_gray, line or [], 0)
    _set(line_alpha, line or [], 255)
    if line_gray_overrides:
        for (x, y), value in line_gray_overrides.items():
            line_gray[y][x] = value
    if line_alpha_overrides:
        for (x, y), value in line_alpha_overrides.items():
            line_alpha[y][x] = value
    guide_alpha = _grid(width, height, 0)
    _set(guide_alpha, guide or [], 255)
    selection_grid = _grid(width, height, 255 if selection is None else 0)
    if selection is not None:
        _set(selection_grid, selection, 255)
    return {
        "coloring_rgba": coloring,
        "line_gray": {"encoding": "rows_u8", "rows": line_gray},
        "line_alpha": {"encoding": "rows_u8", "rows": line_alpha},
        "guide_alpha": {"encoding": "rows_u8", "rows": guide_alpha},
        "selection": {"encoding": "rows_u8", "rows": selection_grid},
    }


def _policy(**overrides: object) -> dict:
    policy = {
        "threshold_policy": "inclusive",
        "edge_policy": "reject",
        "connectivity": 4,
        "alpha_policy": "exact_zero",
        "alpha_threshold": 0,
        "line_policy": "training_gray_128",
        "guide_policy": "boundary",
        "selection_policy": "whole",
        "selection_boundary_policy": "reject",
    }
    policy.update(overrides)
    return policy


def _expectation(
    name: str,
    classification: str,
    decision_ids: list[str],
    evidence_ids: list[str],
    *,
    canonical: bool = False,
    condition: str | None = None,
    **policy_overrides: object,
) -> dict:
    expectation = {
        "variant": name,
        "classification": classification,
        "canonical": canonical,
        "contract_role": (
            "canonical"
            if canonical
            else "noncanonical_reference"
            if classification == "NONCANONICAL_REFERENCE"
            else "characterization_variant"
        ),
        "decision_ids": decision_ids,
        "evidence_ids": evidence_ids,
        "policy": _policy(**policy_overrides),
    }
    if condition is not None:
        expectation["condition"] = condition
    return expectation


def detection_cases() -> list[dict]:
    cases: list[dict] = []

    width, height = 5, 5
    center = [(2, 2)]
    boundary = [(x, y) for y in range(height) for x in range(width) if (x, y) not in center]
    cases.append(
        {
            "id": "D001_one_pixel_enclosed",
            "title": "One-pixel enclosed gap",
            "family": "detection",
            "width": width,
            "height": height,
            "threshold": 2,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(width, height, center),
                line=boundary,
            ),
            "expectations": [
                _expectation(
                    "stable_default",
                    "STABLE",
                    ["DET-ENCLOSED", "D-05"],
                    ["PAPER-4.1.1", "ML-DETECT", "AUDIT-STABLE-CORE"],
                    canonical=True,
                )
            ],
        }
    )

    width, height = 15, 7
    gaps = [(2, 2), (2, 3), (6, 2), (6, 3), (7, 3), (11, 2), (12, 2), (11, 3), (12, 3)]
    boundary = [(x, y) for y in range(height) for x in range(width) if (x, y) not in gaps]
    cases.append(
        {
            "id": "D002_threshold_triplet",
            "title": "Components of size T-1, T, and T+1",
            "family": "detection",
            "width": width,
            "height": height,
            "threshold": 3,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(width, height, gaps),
                line=boundary,
            ),
            "expectations": [
                _expectation(
                    "strict_below_threshold",
                    "NONCANONICAL_REFERENCE",
                    ["D-01"],
                    ["PAPER-4.1.1"],
                    threshold_policy="strict",
                ),
                _expectation(
                    "inclusive_threshold",
                    "STABLE",
                    ["D-01"],
                    [
                        "PAPER-APPENDIX-A",
                        "ML-SIZE",
                        "CURRENT-IMPLEMENTATIONS",
                        "MAINTAINER-FREEZE-2026-08-13",
                    ],
                    canonical=True,
                    threshold_policy="inclusive",
                ),
            ],
        }
    )

    width, height = 5, 5
    gap = [(0, 2)]
    boundary = [(x, y) for y in range(height) for x in range(width) if (x, y) not in gap]
    cases.append(
        {
            "id": "D003_edge_touching_small",
            "title": "Small transparent component touching the image edge",
            "family": "detection",
            "width": width,
            "height": height,
            "threshold": 2,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(width, height, gap),
                line=boundary,
            ),
            "expectations": [
                _expectation(
                    "reject_open_edge",
                    "STABLE",
                    ["D-02"],
                    [
                        "PAPER-4.1.1",
                        "AUDIT-G03",
                        "MAINTAINER-FREEZE-2026-08-13",
                    ],
                    canonical=True,
                    edge_policy="reject",
                ),
                _expectation(
                    "allow_small_edge_component",
                    "NONCANONICAL_REFERENCE",
                    ["D-02"],
                    ["ML-DETECT", "WEB-DETECT"],
                    edge_policy="allow",
                ),
            ],
        }
    )

    width, height = 7, 7
    ring = [(x, y) for y in range(2, 5) for x in range(2, 5) if x in (2, 4) or y in (2, 4)]
    transparent = [(x, y) for y in range(height) for x in range(width) if (x, y) not in ring]
    cases.append(
        {
            "id": "D004_exterior_and_interior",
            "title": "Large exterior plus a one-pixel enclosed interior",
            "family": "detection",
            "width": width,
            "height": height,
            "threshold": 2,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(width, height, transparent),
                line=ring,
            ),
            "expectations": [
                _expectation(
                    "stable_small_interior",
                    "STABLE",
                    ["DET-ENCLOSED", "D-05"],
                    ["PAPER-4.1.1", "AUDIT-STABLE-CORE"],
                    canonical=True,
                )
            ],
        }
    )

    width, height = 5, 5
    gaps = [(2, 2), (3, 3)]
    boundary = [(x, y) for y in range(height) for x in range(width) if (x, y) not in gaps]
    cases.append(
        {
            "id": "D005_diagonal_connectivity",
            "title": "Diagonal candidate pixels under four/eight connectivity",
            "family": "detection",
            "width": width,
            "height": height,
            "threshold": 3,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(width, height, gaps),
                line=boundary,
            ),
            "expectations": [
                _expectation(
                    "four_neighbor_default",
                    "STABLE",
                    ["D-05"],
                    [
                        "ML-DETECT",
                        "CURRENT-DEFAULTS",
                        "AUDIT-STABLE-CORE",
                        "MAINTAINER-FREEZE-2026-08-13",
                    ],
                    canonical=True,
                    connectivity=4,
                ),
                _expectation(
                    "eight_neighbor_optional",
                    "NONCANONICAL_REFERENCE",
                    ["D-05"],
                    ["CSP-OPTION"],
                    connectivity=8,
                ),
            ],
        }
    )

    width, height = 7, 7
    ring = [(x, y) for y in range(2, 5) for x in range(2, 5) if x in (2, 4) or y in (2, 4)]
    transparent = [(x, y) for y in range(height) for x in range(width)]
    cases.append(
        {
            "id": "D006_line_art_enclosure",
            "title": "Ordinary line-art enclosure over transparent Coloring",
            "family": "detection",
            "width": width,
            "height": height,
            "threshold": 2,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(width, height, transparent),
                line=ring,
            ),
            "expectations": [
                _expectation(
                    "stable_line_enclosure",
                    "STABLE",
                    ["DET-ENCLOSED", "BOUNDARY-LINE-TRAINING"],
                    ["PAPER-4.1.1", "ML-DETECT"],
                    canonical=True,
                )
            ],
        }
    )

    cases.append(
        {
            "id": "D007_guide_enclosure",
            "title": "Guide-only enclosure over transparent Coloring",
            "family": "detection",
            "width": width,
            "height": height,
            "threshold": 2,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(width, height, transparent),
                guide=ring,
            ),
            "expectations": [
                _expectation(
                    "guide_as_boundary",
                    "EMPIRICAL_DECISION_REQUIRED",
                    ["GUIDE-DETECTION-COMPOSITION"],
                    ["PAPER-4.1.1"],
                    guide_policy="boundary",
                ),
                _expectation(
                    "guide_as_typed_candidate",
                    "EMPIRICAL_DECISION_REQUIRED",
                    ["GUIDE-DETECTION-COMPOSITION"],
                    ["WEB-DETECT", "KRITA-DETECT"],
                    guide_policy="typed_candidate",
                ),
                _expectation(
                    "guide_ignored",
                    "EMPIRICAL_DECISION_REQUIRED",
                    ["GUIDE-DETECTION-COMPOSITION"],
                    ["ML-TRAINING", "CSP-CURRENT"],
                    guide_policy="ignored",
                ),
            ],
        }
    )

    width, height = 5, 5
    transparent = [(x, y) for y in range(height) for x in range(width)]
    cases.append(
        {
            "id": "D008_isolated_guide_pixel_open",
            "title": "Isolated Guide pixel in an otherwise open transparent image",
            "family": "detection",
            "width": width,
            "height": height,
            "threshold": 1,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(width, height, transparent),
                guide=[(2, 2)],
            ),
            "expectations": [
                _expectation(
                    "guide_as_boundary",
                    "EMPIRICAL_DECISION_REQUIRED",
                    ["GUIDE-DETECTION-COMPOSITION"],
                    ["PAPER-4.1.1", "AUDIT-K12"],
                    guide_policy="boundary",
                ),
                _expectation(
                    "guide_as_typed_candidate",
                    "EMPIRICAL_DECISION_REQUIRED",
                    ["GUIDE-DETECTION-COMPOSITION"],
                    ["WEB-DETECT", "KRITA-DETECT"],
                    guide_policy="typed_candidate",
                ),
            ],
        }
    )

    guide_stroke = [(2, 0), (2, 1), (2, 2)]
    cases.append(
        {
            "id": "D009_guide_stroke_to_exterior",
            "title": "Guide stroke connected to the exterior",
            "family": "detection",
            "width": width,
            "height": height,
            "threshold": 3,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(width, height, transparent),
                guide=guide_stroke,
            ),
            "expectations": [
                _expectation(
                    "guide_as_boundary",
                    "EMPIRICAL_DECISION_REQUIRED",
                    ["GUIDE-DETECTION-COMPOSITION"],
                    ["PAPER-4.1.1"],
                    guide_policy="boundary",
                ),
                _expectation(
                    "typed_candidate_allow_edge",
                    "EMPIRICAL_DECISION_REQUIRED",
                    ["GUIDE-DETECTION-COMPOSITION", "D-02"],
                    ["WEB-DETECT"],
                    guide_policy="typed_candidate",
                    edge_policy="allow",
                ),
                _expectation(
                    "typed_candidate_reject_edge",
                    "EMPIRICAL_DECISION_REQUIRED",
                    ["GUIDE-DETECTION-COMPOSITION", "D-02"],
                    ["KRITA-DETECT"],
                    guide_policy="typed_candidate",
                    edge_policy="reject",
                ),
            ],
        }
    )

    width, height = 7, 7
    ring = [(x, y) for y in range(2, 5) for x in range(2, 5) if x in (2, 4) or y in (2, 4)]
    line_part = [(2, 2), (3, 2), (4, 2), (2, 3), (2, 4)]
    guide_part = [coord for coord in ring if coord not in line_part]
    transparent = [(x, y) for y in range(height) for x in range(width)]
    cases.append(
        {
            "id": "D010_mixed_line_guide_enclosure",
            "title": "Enclosure assembled from Line Art and Guide strokes",
            "family": "detection",
            "width": width,
            "height": height,
            "threshold": 2,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(width, height, transparent),
                line=line_part,
                guide=guide_part,
            ),
            "expectations": [
                _expectation(
                    "combined_boundaries",
                    "EMPIRICAL_DECISION_REQUIRED",
                    ["GUIDE-DETECTION-COMPOSITION"],
                    ["PAPER-4.1.1"],
                    guide_policy="boundary",
                ),
                _expectation(
                    "line_only",
                    "EMPIRICAL_DECISION_REQUIRED",
                    ["GUIDE-DETECTION-COMPOSITION"],
                    ["ML-TRAINING"],
                    guide_policy="ignored",
                ),
            ],
        }
    )

    width, height = 11, 3
    positions = [(1, 1), (3, 1), (5, 1), (7, 1), (9, 1)]
    symbols = ["0", "1", "7", "4", "F"]
    values = [0, 1, 127, 254, 255]
    overrides = {coord: symbol for coord, symbol in zip(positions, symbols)}
    palette = {symbol: [20, 30, 40, alpha] for symbol, alpha in zip(symbols, values)}
    boundary = [(x, y) for y in range(height) for x in range(width) if (x, y) not in positions]
    cases.append(
        {
            "id": "D011_alpha_sweep",
            "title": "Candidate alpha values 0, 1, 127, 254, and 255",
            "family": "detection",
            "width": width,
            "height": height,
            "threshold": 1,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(
                    width,
                    height,
                    [],
                    overrides=overrides,
                    extra_palette=palette,
                ),
                line=boundary,
            ),
            "expectations": [
                _expectation(
                    "exact_zero",
                    "STABLE",
                    ["D-03"],
                    [
                        "PAPER-4.1.1",
                        "WEB-DETECT",
                        "KRITA-DETECT",
                        "MAINTAINER-FREEZE-2026-08-13",
                    ],
                    canonical=True,
                    alpha_policy="exact_zero",
                ),
                _expectation(
                    "alpha_at_most_127",
                    "NONCANONICAL_REFERENCE",
                    ["D-03"],
                    ["CSP-ALPHA-OPTION"],
                    alpha_policy="at_most",
                    alpha_threshold=127,
                ),
                _expectation(
                    "alpha_at_most_254",
                    "NONCANONICAL_REFERENCE",
                    ["D-03"],
                    ["CSP-ALPHA-OPTION"],
                    alpha_policy="at_most",
                    alpha_threshold=254,
                ),
            ],
        }
    )

    width, height = 5, 5
    ring = [(x, y) for y in range(1, 4) for x in range(1, 4) if x in (1, 3) or y in (1, 3)]
    gate = (2, 1)
    transparent = [(x, y) for y in range(height) for x in range(width)]
    for gray in (0, 127, 128, 129, 254, 255):
        alpha = 255 - gray
        cases.append(
            {
                "id": f"D012_faint_line_{gray:03d}",
                "title": f"One enclosure pixel at gray {gray} / alpha {alpha}",
                "family": "detection_faint_line",
                "width": width,
                "height": height,
                "threshold": 1,
                "rasters": _rasters(
                    width,
                    height,
                    _palette_rows(width, height, transparent),
                    line=ring,
                    line_gray_overrides={gate: gray},
                    line_alpha_overrides={gate: alpha},
                ),
                "expectations": [
                    _expectation(
                        "training_gray_128",
                        "EMPIRICAL_DECISION_REQUIRED",
                        ["BOUNDARY-RASTERIZATION"],
                        ["ML-PATCH"],
                        line_policy="training_gray_128",
                    ),
                    _expectation(
                        "any_nonzero_alpha",
                        "EMPIRICAL_DECISION_REQUIRED",
                        ["BOUNDARY-RASTERIZATION"],
                        ["WEB-DETECT", "KRITA-DETECT"],
                        line_policy="any_alpha",
                    ),
                ],
            }
        )

    width, height = 5, 5
    gap = [(1, 2), (2, 2), (3, 2)]
    boundary = [(x, y) for y in range(height) for x in range(width) if (x, y) not in gap]
    cases.append(
        {
            "id": "D013_selection_boundary",
            "title": "Candidate clipped by a one-pixel selection",
            "family": "detection_selection",
            "width": width,
            "height": height,
            "threshold": 3,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(width, height, gap),
                line=boundary,
                selection=[(2, 2)],
            ),
            "expectations": [
                _expectation(
                    "canonical_full_geometry_then_scope",
                    "STABLE",
                    ["D-04"],
                    [
                        "PAPER-4.1.1",
                        "AUDIT-G03",
                        "MAINTAINER-FREEZE-2026-08-13",
                    ],
                    canonical=True,
                    condition="full image geometry is accessible before selection restriction",
                ),
                _expectation(
                    "canonical_clipped_domain_conservative_reject",
                    "STABLE",
                    ["D-04"],
                    ["CSP-SELECTION", "MAINTAINER-FREEZE-2026-08-13"],
                    canonical=True,
                    condition="only clipped geometry is accessible and the component touches that boundary",
                    selection_policy="selected",
                    selection_boundary_policy="reject",
                ),
                _expectation(
                    "noncanonical_selection_edge_encloses",
                    "NONCANONICAL_REFERENCE",
                    ["D-04"],
                    ["PRODUCT-POLICY"],
                    selection_policy="selected",
                    selection_boundary_policy="allow",
                ),
            ],
        }
    )

    width, height = 5, 5
    gap = [(2, 2)]
    boundary = [(x, y) for y in range(height) for x in range(width) if (x, y) not in gap]
    selected = [(x, y) for y in range(1, 4) for x in range(1, 4)]
    cases.append(
        {
            "id": "D014_selection_contains_gap",
            "title": "Selection fully contains an enclosed gap and its neighbors",
            "family": "detection_selection",
            "width": width,
            "height": height,
            "threshold": 2,
            "rasters": _rasters(
                width,
                height,
                _palette_rows(width, height, gap),
                line=boundary,
                selection=selected,
            ),
            "expectations": [
                _expectation(
                    "selection_contains_gap",
                    "STABLE",
                    ["DET-ENCLOSED", "D-04"],
                    [
                        "PAPER-4.1.1",
                        "CSP-SELECTION",
                        "MAINTAINER-FREEZE-2026-08-13",
                    ],
                    canonical=True,
                    selection_policy="selected",
                )
            ],
        }
    )
    return cases


def _indices(width: int, coords: list[tuple[int, int]]) -> list[int]:
    return sorted(y * width + x for x, y in coords)


def patch_cases() -> list[dict]:
    cases: list[dict] = []

    def add(
        case_id: str,
        title: str,
        width: int,
        height: int,
        gap: list[tuple[int, int]],
        line: list[tuple[int, int]],
        guide: list[tuple[int, int]],
        variants: list[dict] | None = None,
    ) -> None:
        cases.append(
            {
                "id": case_id,
                "title": title,
                "family": "patch",
                "source": {
                    "width": width,
                    "height": height,
                    "gap_indices": _indices(width, gap),
                    "line_active_indices": _indices(width, line),
                    "guide_active_indices": _indices(width, guide),
                },
                "expectations": variants
                or [
                    {
                        "variant": "training_line_only",
                        "classification": "STABLE",
                        "canonical": True,
                        "decision_ids": ["PATCH-GEOMETRY", "MODEL-CHANNELS"],
                        "evidence_ids": ["PAPER-4.2", "ML-PATCH"],
                        "guide_policy": "line_only",
                    }
                ],
            }
        )

    add(
        "P001_even_region_centroid",
        "Two-pixel region whose mean x coordinate is 4.5",
        10,
        10,
        [(4, 4), (5, 4)],
        [(3, 4), (6, 4)],
        [],
    )
    add(
        "P002_asymmetric_region_centroid",
        "Three-pixel asymmetric region with fractional x/y means",
        10,
        10,
        [(4, 4), (5, 4), (5, 5)],
        [(3, 4), (6, 5)],
        [],
    )

    width, height = 5, 4
    for suffix, center in (
        ("top_left", (0, 0)),
        ("top", (2, 0)),
        ("top_right", (4, 0)),
        ("left", (0, 2)),
        ("right", (4, 2)),
        ("bottom_left", (0, 3)),
        ("bottom", (2, 3)),
        ("bottom_right", (4, 3)),
    ):
        all_pixels = [(x, y) for y in range(height) for x in range(width)]
        line = [coord for coord in all_pixels if coord != center]
        add(
            f"P003_{suffix}",
            f"32x32 zero-padded patch at the {suffix.replace('_', ' ')}",
            width,
            height,
            [center],
            line,
            [],
        )

    add(
        "P004_target_gap_mask",
        "Multi-pixel target mask projects exact source indices",
        9,
        7,
        [(3, 3), (4, 3), (4, 4), (5, 4)],
        [(2, 3), (6, 4)],
        [],
    )

    guide_variants = [
        {
            "variant": "training_line_only",
            "classification": "EMPIRICAL_DECISION_REQUIRED",
            "canonical": False,
            "decision_ids": ["GUIDE-MODEL-COMPOSITION"],
            "evidence_ids": ["ML-PATCH"],
            "guide_policy": "line_only",
        },
        {
            "variant": "line_plus_guide",
            "classification": "EMPIRICAL_DECISION_REQUIRED",
            "canonical": False,
            "decision_ids": ["GUIDE-MODEL-COMPOSITION"],
            "evidence_ids": ["MODEL-METADATA", "WEB-PATCH", "KRITA-PATCH"],
            "guide_policy": "line_plus_guide",
        },
    ]
    add(
        "P005_guide_delta",
        "One Guide-only delta in model channel 0",
        7,
        7,
        [(3, 3)],
        [(2, 3)],
        [(4, 3)],
        guide_variants,
    )
    add(
        "P006_target_guide_suppression",
        "Target gap overlaps Guide pixels",
        7,
        7,
        [(3, 3), (3, 4)],
        [(2, 3)],
        [(3, 3), (3, 4), (4, 3)],
        [
            {
                "variant": "training_line_only",
                "classification": "EMPIRICAL_DECISION_REQUIRED",
                "canonical": False,
                "decision_ids": ["GUIDE-TARGET-SUPPRESSION"],
                "evidence_ids": ["ML-PATCH"],
                "guide_policy": "line_only",
            },
            {
                "variant": "line_plus_guide",
                "classification": "EMPIRICAL_DECISION_REQUIRED",
                "canonical": False,
                "decision_ids": ["GUIDE-TARGET-SUPPRESSION"],
                "evidence_ids": ["MODEL-METADATA"],
                "guide_policy": "line_plus_guide",
            },
            {
                "variant": "suppress_target_guide",
                "classification": "EMPIRICAL_DECISION_REQUIRED",
                "canonical": False,
                "decision_ids": ["GUIDE-TARGET-SUPPRESSION"],
                "evidence_ids": ["WEB-PATCH", "KRITA-PATCH"],
                "guide_policy": "line_plus_guide_suppress_target",
            },
        ],
    )
    return cases


def _patch_index(x: int, y: int) -> int:
    return y * 32 + x


def _rect_ring(cx: int, cy: int, radius: int) -> list[int]:
    result: set[int] = set()
    for x in range(cx - radius, cx + radius + 1):
        if 0 <= x < 32:
            if 0 <= cy - radius < 32:
                result.add(_patch_index(x, cy - radius))
            if 0 <= cy + radius < 32:
                result.add(_patch_index(x, cy + radius))
    for y in range(cy - radius, cy + radius + 1):
        if 0 <= y < 32:
            if 0 <= cx - radius < 32:
                result.add(_patch_index(cx - radius, y))
            if 0 <= cx + radius < 32:
                result.add(_patch_index(cx + radius, y))
    return sorted(result)


def model_cases() -> list[dict]:
    base_boundary = _rect_ring(16, 16, 4)
    base_gap = [_patch_index(16, 16)]
    cases = [
        {
            "id": "M001_no_guide",
            "title": "Centered square enclosure with no Guide delta",
            "semantic_role": "no_guide",
            "tensor": {
                "dtype": "float32",
                "shape": [1, 2, 32, 32],
                "channel_0_active_indices": base_boundary,
                "channel_1_active_indices": base_gap,
            },
        },
        {
            "id": "M002_one_guide_delta",
            "title": "M001 plus one controlled Guide pixel in channel 0",
            "semantic_role": "controlled_guide_delta",
            "controlled_delta_from": "M001_no_guide",
            "delta_indices": [_patch_index(22, 16)],
            "tensor": {
                "dtype": "float32",
                "shape": [1, 2, 32, 32],
                "channel_0_active_indices": sorted(
                    set(base_boundary) | {_patch_index(22, 16)}
                ),
                "channel_1_active_indices": base_gap,
            },
        },
        {
            "id": "M003_symmetric_geometry",
            "title": "Symmetric double-ring geometry with a 2x2 target",
            "semantic_role": "symmetric_geometry",
            "tensor": {
                "dtype": "float32",
                "shape": [1, 2, 32, 32],
                "channel_0_active_indices": sorted(
                    set(_rect_ring(16, 16, 7)) | set(_rect_ring(16, 16, 3))
                ),
                "channel_1_active_indices": [
                    _patch_index(15, 15),
                    _patch_index(16, 15),
                    _patch_index(15, 16),
                    _patch_index(16, 16),
                ],
            },
        },
        {
            "id": "M004_asymmetric_geometry",
            "title": "Asymmetric L-shaped context",
            "semantic_role": "asymmetric_geometry",
            "tensor": {
                "dtype": "float32",
                "shape": [1, 2, 32, 32],
                "channel_0_active_indices": sorted(
                    {_patch_index(7, y) for y in range(6, 27)}
                    | {_patch_index(x, 26) for x in range(7, 25)}
                    | {_patch_index(x, 10) for x in range(14, 23)}
                ),
                "channel_1_active_indices": [
                    _patch_index(15, 17),
                    _patch_index(16, 17),
                    _patch_index(16, 18),
                ],
            },
        },
        {
            "id": "M005_boundary_near_geometry",
            "title": "Target and enclosure near the zero-padded top-left boundary",
            "semantic_role": "boundary_near_geometry",
            "tensor": {
                "dtype": "float32",
                "shape": [1, 2, 32, 32],
                "channel_0_active_indices": _rect_ring(2, 2, 2),
                "channel_1_active_indices": [_patch_index(2, 2)],
            },
        },
        {
            "id": "M006_target_guide_present",
            "title": "Target Guide pixel remains in channel 0 and channel 1",
            "semantic_role": "target_guide_present",
            "tensor": {
                "dtype": "float32",
                "shape": [1, 2, 32, 32],
                "channel_0_active_indices": sorted(
                    set(base_boundary) | {_patch_index(16, 16)}
                ),
                "channel_1_active_indices": base_gap,
            },
        },
        {
            "id": "M007_target_guide_suppressed",
            "title": "Target Guide pixel is suppressed from channel 0",
            "semantic_role": "target_guide_suppressed",
            "controlled_delta_from": "M006_target_guide_present",
            "delta_indices": [_patch_index(16, 16)],
            "tensor": {
                "dtype": "float32",
                "shape": [1, 2, 32, 32],
                "channel_0_active_indices": base_boundary,
                "channel_1_active_indices": base_gap,
            },
        },
    ]
    for case in cases:
        case["classification"] = "EMPIRICAL_DECISION_REQUIRED"
        case["decision_ids"] = ["MODEL-SEMANTIC-OUTPUT"]
        case["evidence_ids"] = ["EXACT-ONNX-ARTIFACT"]
    return cases


def _rgba_case(palette: dict[str, list[int]], rows: list[str]) -> dict:
    return {"encoding": "palette_rgba8", "palette": palette, "rows": rows}


def postprocess_cases() -> list[dict]:
    return [
        {
            "id": "R001_manual_mean_winner",
            "title": "Fixed labels and probabilities with a manually verifiable winner",
            "width": 4,
            "height": 2,
            "coloring_rgba": _rgba_case(
                {
                    "R": [220, 20, 20, 255],
                    "B": [20, 20, 220, 255],
                },
                ["RRBB", "RRBB"],
            ),
            "label_maps": {"reviewed_semantic": [[1, 1, 2, 2], [1, 1, 2, 2]]},
            "probability_map": [[0.1, 0.3, 0.8, 0.6], [0.2, 0.2, 0.7, 0.7]],
            "expectations": [
                {
                    "variant": "reviewed_semantic",
                    "classification": "STABLE",
                    "canonical": True,
                    "decision_ids": ["REGION-MEAN", "REGION-MODAL-COLOR"],
                    "evidence_ids": ["PAPER-4.2", "MANUAL-ARITHMETIC"],
                    "label_map": "reviewed_semantic",
                    "include_label_zero": False,
                    "tie_policy": "first_encountered",
                }
            ],
        },
        {
            "id": "R002_label_zero",
            "title": "Label 0 has the highest artificial probability",
            "width": 3,
            "height": 2,
            "coloring_rgba": _rgba_case(
                {"K": [0, 0, 0, 255], "G": [40, 180, 40, 255]},
                ["KGG", "KGG"],
            ),
            "label_maps": {"line_labels": [[0, 1, 1], [0, 1, 1]]},
            "probability_map": [[0.99, 0.4, 0.4], [0.99, 0.4, 0.4]],
            "expectations": [
                {
                    "variant": "include_label_zero",
                    "classification": "EMPIRICAL_DECISION_REQUIRED",
                    "canonical": False,
                    "decision_ids": ["REGION-LABEL-ZERO"],
                    "evidence_ids": ["ML-POSTPROCESS"],
                    "label_map": "line_labels",
                    "include_label_zero": True,
                    "tie_policy": "first_encountered",
                },
                {
                    "variant": "exclude_label_zero",
                    "classification": "EMPIRICAL_DECISION_REQUIRED",
                    "canonical": False,
                    "decision_ids": ["REGION-LABEL-ZERO"],
                    "evidence_ids": ["PAPER-4.2", "WEB-POSTPROCESS", "KRITA-POSTPROCESS"],
                    "label_map": "line_labels",
                    "include_label_zero": False,
                    "tie_policy": "first_encountered",
                },
            ],
        },
        {
            "id": "R003_disconnected_same_rgb",
            "title": "Two disconnected painted areas have the same RGB",
            "width": 5,
            "height": 1,
            "coloring_rgba": _rgba_case(
                {"R": [200, 30, 30, 255], ".": [0, 0, 0, 0]},
                ["RR.RR"],
            ),
            "line_alpha": [[0, 0, 0, 0, 0]],
            "guide_alpha": [[0, 0, 0, 0, 0]],
            "label_maps": {
                "line_labels": [[1, 1, 1, 1, 1]],
                "colored_components": [[1, 1, 0, 2, 2]],
            },
            "probability_map": [[0.4, 0.4, 0.0, 0.8, 0.8]],
            "expectations": [
                {
                    "variant": "ml_line_labels",
                    "classification": "EMPIRICAL_DECISION_REQUIRED",
                    "canonical": False,
                    "decision_ids": ["REGION-CORRESPONDENCE"],
                    "evidence_ids": ["ML-POSTPROCESS"],
                    "label_map": "line_labels",
                    "include_label_zero": True,
                    "tie_policy": "first_encountered",
                },
                {
                    "variant": "colored_components",
                    "classification": "EMPIRICAL_DECISION_REQUIRED",
                    "canonical": False,
                    "decision_ids": ["REGION-CORRESPONDENCE"],
                    "evidence_ids": ["WEB-POSTPROCESS", "KRITA-POSTPROCESS"],
                    "label_map": "colored_components",
                    "include_label_zero": False,
                    "tie_policy": "first_encountered",
                },
            ],
        },
        {
            "id": "R004_tolerance_30_boundary",
            "title": "Neighbor colors at Manhattan differences 29, 30, and 31",
            "width": 4,
            "height": 1,
            "coloring_rgba": _rgba_case(
                {
                    "A": [0, 0, 0, 255],
                    "B": [29, 0, 0, 255],
                    "C": [30, 0, 0, 255],
                    "D": [31, 0, 0, 255],
                },
                ["ABCD"],
            ),
            "line_alpha": [[0, 0, 0, 0]],
            "guide_alpha": [[0, 0, 0, 0]],
            "label_maps": {"line_labels": [[1, 1, 1, 1]]},
            "probability_map": [[0.1, 0.2, 0.3, 0.9]],
            "segmentation_variants": ["seed_relative", "neighbor_transitive"],
            "expectations": [],
            "classification": "EMPIRICAL_DECISION_REQUIRED",
            "decision_ids": ["REGION-COLOR-TOLERANCE"],
            "evidence_ids": ["WEB-POSTPROCESS", "KRITA-POSTPROCESS", "CSP-OWNER"],
        },
        {
            "id": "R005_transitive_color_chain",
            "title": "Color chain 0 -> 20 -> 40 under tolerance 30",
            "width": 3,
            "height": 1,
            "coloring_rgba": _rgba_case(
                {
                    "A": [0, 0, 0, 255],
                    "B": [20, 0, 0, 255],
                    "C": [40, 0, 0, 255],
                },
                ["ABC"],
            ),
            "line_alpha": [[0, 0, 0]],
            "guide_alpha": [[0, 0, 0]],
            "label_maps": {"line_labels": [[1, 1, 1]]},
            "probability_map": [[0.1, 0.2, 0.9]],
            "segmentation_variants": ["seed_relative", "neighbor_transitive"],
            "expectations": [],
            "classification": "EMPIRICAL_DECISION_REQUIRED",
            "decision_ids": ["REGION-COLOR-TOLERANCE"],
            "evidence_ids": ["WEB-POSTPROCESS", "KRITA-POSTPROCESS", "CSP-OWNER"],
        },
        {
            "id": "R006_modal_tie",
            "title": "Selected region has a two-color modal tie",
            "width": 2,
            "height": 2,
            "coloring_rgba": _rgba_case(
                {"H": [240, 20, 20, 255], "L": [20, 20, 240, 255]},
                ["HL", "LH"],
            ),
            "label_maps": {"selected_region": [[1, 1], [1, 1]]},
            "probability_map": [[0.8, 0.8], [0.8, 0.8]],
            "expectations": [
                {
                    "variant": "first_encountered_tie",
                    "classification": "STABLE",
                    "canonical": True,
                    "contract_role": "canonical",
                    "decision_ids": ["D-06"],
                    "evidence_ids": [
                        "ML-POSTPROCESS",
                        "WEB-POSTPROCESS",
                        "MANUAL-TIE",
                        "AUDIT-K14",
                        "MAINTAINER-FREEZE-2026-08-13",
                    ],
                    "label_map": "selected_region",
                    "include_label_zero": False,
                    "tie_policy": "first_encountered",
                },
                {
                    "variant": "lowest_rgb_tie",
                    "classification": "NONCANONICAL_REFERENCE",
                    "canonical": False,
                    "contract_role": "noncanonical_reference",
                    "decision_ids": ["D-06"],
                    "evidence_ids": ["KRITA-POSTPROCESS"],
                    "label_map": "selected_region",
                    "include_label_zero": False,
                    "tie_policy": "lowest_rgb",
                },
            ],
        },
        {
            "id": "R007_antialiased_colors",
            "title": "Dominant flat color with two anti-aliased edge colors",
            "width": 5,
            "height": 1,
            "coloring_rgba": _rgba_case(
                {
                    "F": [100, 120, 140, 255],
                    "a": [101, 121, 141, 255],
                    "b": [99, 119, 139, 255],
                },
                ["aFFFb"],
            ),
            "label_maps": {"selected_region": [[1, 1, 1, 1, 1]]},
            "probability_map": [[0.6, 0.6, 0.6, 0.6, 0.6]],
            "expectations": [
                {
                    "variant": "modal_flat_color",
                    "classification": "STABLE",
                    "canonical": True,
                    "decision_ids": ["REGION-MODAL-COLOR"],
                    "evidence_ids": ["PAPER-4.2", "ML-POSTPROCESS", "MANUAL-COUNT"],
                    "label_map": "selected_region",
                    "include_label_zero": False,
                    "tie_policy": "first_encountered",
                }
            ],
        },
        {
            "id": "R008_line_vs_colored_regions",
            "title": "Line-derived region spans two opaque color components",
            "width": 5,
            "height": 2,
            "coloring_rgba": _rgba_case(
                {
                    "R": [200, 20, 20, 255],
                    "B": [20, 20, 200, 255],
                },
                ["RRRBB", "RRRBB"],
            ),
            "label_maps": {
                "line_labels": [[1, 1, 1, 1, 1], [1, 1, 1, 1, 1]],
                "colored_components": [[1, 1, 1, 2, 2], [1, 1, 1, 2, 2]],
            },
            "probability_map": [[0.1, 0.1, 0.1, 0.8, 0.8], [0.1, 0.1, 0.1, 0.8, 0.8]],
            "expectations": [
                {
                    "variant": "ml_line_labels",
                    "classification": "EMPIRICAL_DECISION_REQUIRED",
                    "canonical": False,
                    "decision_ids": ["REGION-CORRESPONDENCE"],
                    "evidence_ids": ["ML-POSTPROCESS"],
                    "label_map": "line_labels",
                    "include_label_zero": True,
                    "tie_policy": "first_encountered",
                },
                {
                    "variant": "colored_components",
                    "classification": "EMPIRICAL_DECISION_REQUIRED",
                    "canonical": False,
                    "decision_ids": ["REGION-CORRESPONDENCE"],
                    "evidence_ids": ["WEB-POSTPROCESS", "KRITA-POSTPROCESS"],
                    "label_map": "colored_components",
                    "include_label_zero": False,
                    "tie_policy": "first_encountered",
                },
            ],
        },
    ]


def policy_cases() -> dict:
    """Hand-reviewed policy contracts that do not need an image oracle."""

    common = {
        "classification": "STABLE",
        "canonical": True,
        "contract_role": "canonical",
        "evidence_ids": [
            "PAPER-HUMAN-CONTROL",
            "MAINTAINER-FREEZE-2026-08-13",
        ],
    }
    return {
        "schema": "gapfill-policy-cases-v1",
        "modal_color": [
            {
                **common,
                "id": "MP001_modal_participation",
                "title": "Only painted, included semantic-region pixels vote in row-major order",
                "decision_ids": ["D-06"],
                "evidence_ids": [
                    "PAPER-4.2",
                    "ML-POSTPROCESS",
                    "WEB-POSTPROCESS",
                    "AUDIT-K14",
                    "MAINTAINER-FREEZE-2026-08-13",
                ],
                "input": {
                    "width": 6,
                    "height": 1,
                    "coloring_rgba_row_major": [
                        [240, 20, 20, 0],
                        [20, 20, 240, 1],
                        [240, 20, 20, 255],
                        [10, 200, 10, 255],
                        [20, 20, 240, 255],
                        [240, 20, 20, 255],
                    ],
                    "semantic_region_pixel_indices": [4, 0, 3, 2, 1],
                    "excluded_pixel_indices": [3],
                },
                "expected": {
                    "participating_pixel_indices": [1, 2, 4],
                    "rgb": [20, 20, 240],
                },
                "provenance_note": "Index 0 is alpha-zero, index 3 is explicitly excluded, and index 5 is outside the semantic region. The alpha-1 and opaque pixels each vote once.",
            }
        ],
        "selection_scope": [
            {
                **common,
                "id": "S001_full_geometry_then_selection",
                "title": "Selection clips an enclosed component after full-image geometry is known",
                "decision_ids": ["D-04"],
                "evidence_ids": [
                    "PAPER-4.1.1",
                    "AUDIT-G03",
                    "AUDIT-C10",
                    "MAINTAINER-FREEZE-2026-08-13",
                ],
                "input": {
                    "full_geometry_accessible": True,
                    "component_enclosed_in_full_geometry": True,
                    "component_pixel_indices": [11, 12, 13],
                    "selection_pixel_indices": [12],
                    "touches_acquisition_boundary": False,
                },
                "expected": {
                    "geometry_status": "enclosed",
                    "component_pixel_indices": [11, 12, 13],
                    "eligible": True,
                    "application_pixel_indices": [12],
                    "selection_created_enclosure": False,
                },
                "provenance_note": "Component pixels are hand-derived from detection case D013; selection only restricts the application subset.",
            },
            {
                **common,
                "id": "S002_clipped_domain_boundary_indeterminate",
                "title": "A clipped-only component touching the acquisition boundary is indeterminate",
                "decision_ids": ["D-04"],
                "evidence_ids": [
                    "PAPER-4.1.1",
                    "AUDIT-G03",
                    "AUDIT-C10",
                    "MAINTAINER-FREEZE-2026-08-13",
                ],
                "input": {
                    "full_geometry_accessible": False,
                    "component_enclosed_in_full_geometry": None,
                    "component_pixel_indices": [12],
                    "selection_pixel_indices": [12],
                    "touches_acquisition_boundary": True,
                },
                "expected": {
                    "geometry_status": "indeterminate",
                    "component_pixel_indices": [12],
                    "eligible": False,
                    "application_pixel_indices": [],
                    "selection_created_enclosure": False,
                },
                "provenance_note": "Outside geometry is unavailable, so the selection edge cannot prove enclosure.",
            },
            {
                **common,
                "id": "S003_selection_excludes_enclosed_component",
                "title": "An enclosed component outside the selection is not eligible for application",
                "decision_ids": ["D-04"],
                "evidence_ids": [
                    "PAPER-4.1.1",
                    "AUDIT-G03",
                    "MAINTAINER-FREEZE-2026-08-13",
                ],
                "input": {
                    "full_geometry_accessible": True,
                    "component_enclosed_in_full_geometry": True,
                    "component_pixel_indices": [12],
                    "selection_pixel_indices": [],
                    "touches_acquisition_boundary": False,
                },
                "expected": {
                    "geometry_status": "enclosed",
                    "component_pixel_indices": [12],
                    "eligible": False,
                    "application_pixel_indices": [],
                    "selection_created_enclosure": False,
                },
                "provenance_note": "Geometry and application scope are separate decisions.",
            },
        ],
        "fallback_application": [
            {
                **common,
                "id": "F001_learned_high",
                "title": "A successful learned High prediction may enter Apply-High",
                "decision_ids": ["D-07"],
                "evidence_ids": [
                    "PAPER-HUMAN-CONTROL",
                    "AUDIT-K11",
                    "AUDIT-C03",
                    "MAINTAINER-FREEZE-2026-08-13",
                ],
                "input": {
                    "prediction_source": "learned",
                    "learned_inference_succeeded": True,
                    "reported_confidence_band": "high",
                    "explicit_user_confirmation": False,
                },
                "expected": {
                    "prediction_provenance": "learned",
                    "effective_confidence_band": "high",
                    "apply_high_eligible": True,
                    "requires_explicit_confirmation": False,
                    "manual_apply_eligible": True,
                },
            },
            {
                **common,
                "id": "F002_fallback_high_unconfirmed",
                "title": "A fallback carrying a High-like score is excluded until confirmed",
                "decision_ids": ["D-07"],
                "evidence_ids": [
                    "PAPER-HUMAN-CONTROL",
                    "AUDIT-K11",
                    "AUDIT-C02",
                    "AUDIT-C03",
                    "MAINTAINER-FREEZE-2026-08-13",
                ],
                "input": {
                    "prediction_source": "fallback",
                    "learned_inference_succeeded": False,
                    "reported_confidence_band": "high",
                    "explicit_user_confirmation": False,
                },
                "expected": {
                    "prediction_provenance": "fallback",
                    "effective_confidence_band": None,
                    "apply_high_eligible": False,
                    "requires_explicit_confirmation": True,
                    "manual_apply_eligible": False,
                },
            },
            {
                **common,
                "id": "F003_fallback_high_confirmed",
                "title": "Explicit confirmation permits manual fallback application, never Apply-High",
                "decision_ids": ["D-07"],
                "evidence_ids": [
                    "PAPER-HUMAN-CONTROL",
                    "AUDIT-K11",
                    "AUDIT-C03",
                    "MAINTAINER-FREEZE-2026-08-13",
                ],
                "input": {
                    "prediction_source": "fallback",
                    "learned_inference_succeeded": False,
                    "reported_confidence_band": "high",
                    "explicit_user_confirmation": True,
                },
                "expected": {
                    "prediction_provenance": "fallback",
                    "effective_confidence_band": None,
                    "apply_high_eligible": False,
                    "requires_explicit_confirmation": True,
                    "manual_apply_eligible": True,
                },
            },
        ],
    }


def synthetic_end_to_end_cases() -> list[dict]:
    return [
        {
            "id": "E001_synthetic_unambiguous",
            "title": "One line-enclosed transparent pixel beside one dominant red region",
            "annotation": "Detection is manually unambiguous. The final red color is an annotation for review, not an inference-derived truth.",
            "expected_gap_indices": [12],
            "reviewed_rgb": [210, 30, 40],
            "classification": "STABLE",
            "decision_ids": ["DET-ENCLOSED", "REGION-MODAL-COLOR"],
            "evidence_ids": ["PAPER-4.1.1", "PAPER-4.2", "MANUAL-ANNOTATION"],
        },
        {
            "id": "E002_synthetic_guide",
            "title": "Guide-only enclosure with a nearby flat green region",
            "annotation": "The enclosure is visually explicit, but Guide preprocessing remains empirical; no canonical model prediction is assigned.",
            "classification": "EMPIRICAL_DECISION_REQUIRED",
            "decision_ids": ["GUIDE-DETECTION-COMPOSITION", "GUIDE-MODEL-COMPOSITION"],
            "evidence_ids": ["PAPER-4.1.1", "MANUAL-ANNOTATION"],
        },
        {
            "id": "E003_synthetic_ambiguous_color",
            "title": "One gap equally adjacent to red and blue regions",
            "annotation": "Both colors are locally plausible. This fixture intentionally has no canonical final RGB.",
            "classification": "EMPIRICAL_DECISION_REQUIRED",
            "decision_ids": ["D-07", "REGION-CORRESPONDENCE"],
            "evidence_ids": ["PAPER-HUMAN-CONTROL", "MANUAL-ANNOTATION"],
        },
    ]


def clone(value: object) -> object:
    return deepcopy(value)
