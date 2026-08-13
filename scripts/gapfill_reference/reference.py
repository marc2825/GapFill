"""Small independent reference operations used to build Phase 2 fixtures.

This module deliberately does not import the web, Krita, CSP, or ML production
implementations. Its policies are explicit so the frozen canonical rules and
the remaining empirical or noncanonical comparison variants cannot be confused.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


@dataclass(frozen=True)
class DetectionPolicy:
    threshold_policy: str = "inclusive"
    edge_policy: str = "reject"
    connectivity: int = 4
    alpha_policy: str = "exact_zero"
    alpha_threshold: int = 0
    line_policy: str = "training_gray_128"
    guide_policy: str = "boundary"
    selection_policy: str = "whole"
    selection_boundary_policy: str = "reject"


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_palette_rgba(raster: dict) -> np.ndarray:
    rows = raster["rows"]
    palette = raster["palette"]
    if not rows:
        return np.zeros((0, 0, 4), dtype=np.uint8)
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("Palette raster rows have inconsistent widths.")
    result = np.zeros((len(rows), width, 4), dtype=np.uint8)
    for y, row in enumerate(rows):
        for x, symbol in enumerate(row):
            value = palette[symbol]
            if len(value) != 4:
                raise ValueError(f"Palette entry {symbol!r} is not RGBA.")
            result[y, x] = value
    return result


def decode_rows_u8(raster: dict) -> np.ndarray:
    rows = raster["rows"]
    result = np.asarray(rows, dtype=np.uint8)
    if result.ndim != 2:
        raise ValueError("rows_u8 raster must be two-dimensional.")
    return result


def encode_rows_u8(values: np.ndarray) -> dict:
    array = np.asarray(values, dtype=np.uint8)
    if array.ndim != 2:
        raise ValueError("Only two-dimensional u8 rasters can be encoded.")
    return {"encoding": "rows_u8", "rows": array.astype(int).tolist()}


def _line_boundary(case: dict, policy: DetectionPolicy) -> np.ndarray:
    rasters = case["rasters"]
    height = case["height"]
    width = case["width"]
    if policy.line_policy == "none":
        return np.zeros((height, width), dtype=bool)
    if policy.line_policy == "training_gray_128":
        return decode_rows_u8(rasters["line_gray"]) <= 128
    if policy.line_policy == "any_alpha":
        return decode_rows_u8(rasters["line_alpha"]) > 0
    raise ValueError(f"Unsupported line policy: {policy.line_policy}")


def _alpha_candidate(alpha: np.ndarray, policy: DetectionPolicy) -> np.ndarray:
    if policy.alpha_policy == "exact_zero":
        return alpha == 0
    if policy.alpha_policy == "at_most":
        return alpha <= policy.alpha_threshold
    raise ValueError(f"Unsupported alpha policy: {policy.alpha_policy}")


def _neighbor_offsets(connectivity: int) -> tuple[tuple[int, int], ...]:
    if connectivity == 4:
        return ((-1, 0), (1, 0), (0, -1), (0, 1))
    if connectivity == 8:
        return (
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (1, -1),
            (-1, 1),
            (1, 1),
        )
    raise ValueError(f"Unsupported connectivity: {connectivity}")


def detect_components(case: dict, policy: DetectionPolicy) -> list[dict]:
    """Detect components using only the explicitly supplied policy."""

    width = int(case["width"])
    height = int(case["height"])
    threshold = int(case["threshold"])
    rgba = decode_palette_rgba(case["rasters"]["coloring_rgba"])
    if rgba.shape != (height, width, 4):
        raise ValueError(f"Coloring shape mismatch for {case['id']}.")

    line_boundary = _line_boundary(case, policy)
    guide = decode_rows_u8(case["rasters"]["guide_alpha"]) > 0
    candidates = _alpha_candidate(rgba[..., 3], policy) & ~line_boundary
    kinds = np.zeros((height, width), dtype=np.uint8)

    if policy.guide_policy == "boundary":
        candidates &= ~guide
        kinds[candidates] = 1
    elif policy.guide_policy == "typed_candidate":
        kinds[candidates & ~guide] = 1
        kinds[candidates & guide] = 2
    elif policy.guide_policy == "ignored":
        kinds[candidates] = 1
    else:
        raise ValueError(f"Unsupported guide policy: {policy.guide_policy}")

    selection = decode_rows_u8(case["rasters"]["selection"])
    if policy.selection_policy == "selected":
        kinds[selection == 0] = 0
    elif policy.selection_policy != "whole":
        raise ValueError(f"Unsupported selection policy: {policy.selection_policy}")

    visited = np.zeros((height, width), dtype=bool)
    offsets = _neighbor_offsets(policy.connectivity)
    components: list[dict] = []

    for seed_y in range(height):
        for seed_x in range(width):
            kind_value = int(kinds[seed_y, seed_x])
            if kind_value == 0 or visited[seed_y, seed_x]:
                continue

            queue = deque([(seed_x, seed_y)])
            visited[seed_y, seed_x] = True
            pixels: list[int] = []
            touches_image_edge = False
            touches_selection_edge = False
            while queue:
                x, y = queue.popleft()
                pixels.append(y * width + x)
                if x == 0 or y == 0 or x + 1 == width or y + 1 == height:
                    touches_image_edge = True
                for dx, dy in offsets:
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < width and 0 <= ny < height):
                        if policy.selection_policy == "selected":
                            touches_selection_edge = True
                        continue
                    if policy.selection_policy == "selected" and selection[ny, nx] == 0:
                        touches_selection_edge = True
                    if visited[ny, nx] or int(kinds[ny, nx]) != kind_value:
                        continue
                    visited[ny, nx] = True
                    queue.append((nx, ny))

            size_ok = len(pixels) <= threshold
            if policy.threshold_policy == "strict":
                size_ok = len(pixels) < threshold
            elif policy.threshold_policy != "inclusive":
                raise ValueError(
                    f"Unsupported threshold policy: {policy.threshold_policy}"
                )
            if not size_ok:
                continue
            if policy.edge_policy == "reject" and touches_image_edge:
                continue
            if policy.edge_policy not in ("allow", "reject"):
                raise ValueError(f"Unsupported edge policy: {policy.edge_policy}")
            if (
                policy.selection_policy == "selected"
                and policy.selection_boundary_policy == "reject"
                and touches_selection_edge
            ):
                continue

            xs = [index % width for index in pixels]
            ys = [index // width for index in pixels]
            components.append(
                {
                    "id": len(components),
                    "kind": "guide" if kind_value == 2 else "transparent",
                    "pixel_indices": sorted(pixels),
                    "pixel_count": len(pixels),
                    "centroid": [sum(xs) // len(xs), sum(ys) // len(ys)],
                    "bbox": [
                        min(xs),
                        min(ys),
                        max(xs) - min(xs) + 1,
                        max(ys) - min(ys) + 1,
                    ],
                    "touches_image_edge": touches_image_edge,
                    "touches_selection_edge": touches_selection_edge,
                }
            )
    return components


def region_centroid(pixel_indices: Sequence[int], width: int) -> tuple[int, int]:
    if not pixel_indices:
        raise ValueError("A region centroid requires at least one pixel.")
    xs = [index % width for index in pixel_indices]
    ys = [index // width for index in pixel_indices]
    return sum(xs) // len(xs), sum(ys) // len(ys)


def centered_patch_bounds(
    width: int, height: int, center: tuple[int, int], size: int = 32
) -> dict:
    virtual_x = int(center[0]) - size // 2
    virtual_y = int(center[1]) - size // 2
    source_x = max(0, virtual_x)
    source_y = max(0, virtual_y)
    source_end_x = min(width, virtual_x + size)
    source_end_y = min(height, virtual_y + size)
    return {
        "virtual_x": virtual_x,
        "virtual_y": virtual_y,
        "source_x": source_x,
        "source_y": source_y,
        "source_width": max(0, source_end_x - source_x),
        "source_height": max(0, source_end_y - source_y),
        "destination_x": source_x - virtual_x,
        "destination_y": source_y - virtual_y,
    }


def project_indices_to_patch(
    indices: Iterable[int], width: int, bounds: dict, size: int = 32
) -> list[int]:
    projected: list[int] = []
    for index in indices:
        source_x = int(index) % width
        source_y = int(index) // width
        patch_x = source_x - int(bounds["virtual_x"])
        patch_y = source_y - int(bounds["virtual_y"])
        if 0 <= patch_x < size and 0 <= patch_y < size:
            projected.append(patch_y * size + patch_x)
    return sorted(projected)


def make_patch_expectation(case: dict, guide_policy: str) -> dict:
    source = case["source"]
    width = int(source["width"])
    height = int(source["height"])
    gap_indices = [int(value) for value in source["gap_indices"]]
    center = region_centroid(gap_indices, width)
    bounds = centered_patch_bounds(width, height, center, 32)
    line = set(int(value) for value in source["line_active_indices"])
    guides = set(int(value) for value in source["guide_active_indices"])
    gap = set(gap_indices)
    if guide_policy == "line_only":
        boundary = line
    elif guide_policy == "line_plus_guide":
        boundary = line | guides
    elif guide_policy == "line_plus_guide_suppress_target":
        boundary = line | (guides - gap)
    else:
        raise ValueError(f"Unsupported patch guide policy: {guide_policy}")
    return {
        "centroid": list(center),
        "bounds": bounds,
        "tensor": {
            "dtype": "float32",
            "shape": [1, 2, 32, 32],
            "zero_fill": 0.0,
            "channel_0_active_indices": project_indices_to_patch(
                boundary, width, bounds
            ),
            "channel_1_active_indices": project_indices_to_patch(gap, width, bounds),
        },
    }


def tensor_from_sparse(case: dict) -> np.ndarray:
    tensor = np.zeros((1, 2, 32, 32), dtype=np.float32)
    flat = tensor.reshape(1, 2, -1)
    for index in case["tensor"]["channel_0_active_indices"]:
        flat[0, 0, int(index)] = 1.0
    for index in case["tensor"]["channel_1_active_indices"]:
        flat[0, 1, int(index)] = 1.0
    return tensor


def connected_labels(mask: np.ndarray, connectivity: int = 4) -> np.ndarray:
    """Label nonzero pixels in row-major order; zero remains background."""

    foreground = np.asarray(mask, dtype=bool)
    if foreground.ndim != 2:
        raise ValueError("Label input must be a two-dimensional mask.")
    height, width = foreground.shape
    labels = np.zeros((height, width), dtype=np.int32)
    offsets = _neighbor_offsets(connectivity)
    next_label = 0
    for seed_y in range(height):
        for seed_x in range(width):
            if not foreground[seed_y, seed_x] or labels[seed_y, seed_x] != 0:
                continue
            next_label += 1
            labels[seed_y, seed_x] = next_label
            queue = deque([(seed_x, seed_y)])
            while queue:
                x, y = queue.popleft()
                for dx, dy in offsets:
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    if not foreground[ny, nx] or labels[ny, nx] != 0:
                        continue
                    labels[ny, nx] = next_label
                    queue.append((nx, ny))
    return labels


def segment_colored_components(
    rgba: np.ndarray,
    blocked: np.ndarray,
    tolerance: int = 30,
    similarity: str = "seed_relative",
) -> np.ndarray:
    """Reference the two observed color-component similarity variants."""

    image = np.asarray(rgba, dtype=np.uint8)
    blocked_mask = np.asarray(blocked, dtype=bool) | (image[..., 3] == 0)
    height, width = blocked_mask.shape
    labels = np.zeros((height, width), dtype=np.int32)
    next_label = 0
    for seed_y in range(height):
        for seed_x in range(width):
            if blocked_mask[seed_y, seed_x] or labels[seed_y, seed_x] != 0:
                continue
            next_label += 1
            seed_rgb = image[seed_y, seed_x, :3].astype(np.int16)
            labels[seed_y, seed_x] = next_label
            queue = deque([(seed_x, seed_y)])
            while queue:
                x, y = queue.popleft()
                current_rgb = image[y, x, :3].astype(np.int16)
                for dx, dy in _neighbor_offsets(4):
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    if blocked_mask[ny, nx] or labels[ny, nx] != 0:
                        continue
                    target = seed_rgb if similarity == "seed_relative" else current_rgb
                    if similarity not in ("seed_relative", "neighbor_transitive"):
                        raise ValueError(f"Unsupported color similarity: {similarity}")
                    difference = int(
                        np.abs(image[ny, nx, :3].astype(np.int16) - target).sum()
                    )
                    if difference > tolerance:
                        continue
                    labels[ny, nx] = next_label
                    queue.append((nx, ny))
    return labels


def modal_rgb(values: np.ndarray, tie_policy: str = "first_encountered") -> list[int]:
    """Return the RGB mode; input order is deterministic image scan order.

    Callers pass only in-bounds, nontransparent Coloring pixels assigned to the
    selected semantic region. Alpha is not part of the key and does not weight
    a participating pixel.
    """
    pixels = np.asarray(values, dtype=np.uint8)
    if pixels.ndim != 2 or pixels.shape[1] < 3 or pixels.shape[0] == 0:
        raise ValueError("Modal RGB requires at least one RGB(A) pixel.")
    colors = [tuple(int(channel) for channel in pixel[:3]) for pixel in pixels]
    counts = Counter(colors)
    highest = max(counts.values())
    tied = [color for color, count in counts.items() if count == highest]
    if tie_policy == "first_encountered":
        selected = tied[0]
    elif tie_policy == "lowest_rgb":
        selected = min(tied)
    else:
        raise ValueError(f"Unsupported modal tie policy: {tie_policy}")
    return list(selected)


def score_regions(
    rgba: np.ndarray,
    labels: np.ndarray,
    probabilities: np.ndarray,
    *,
    include_label_zero: bool,
    tie_policy: str = "first_encountered",
) -> dict:
    image = np.asarray(rgba, dtype=np.uint8)
    label_map = np.asarray(labels, dtype=np.int32)
    probability_map = np.asarray(probabilities, dtype=np.float32)
    if image.shape[:2] != label_map.shape or label_map.shape != probability_map.shape:
        raise ValueError("Postprocessing arrays must have matching dimensions.")
    label_values = sorted(int(value) for value in np.unique(label_map))
    if not include_label_zero:
        label_values = [value for value in label_values if value != 0]
    means: dict[str, float] = {}
    best_label: int | None = None
    best_mean = float("-inf")
    for label in label_values:
        mask = label_map == label
        if not mask.any():
            continue
        mean = float(np.asarray(probability_map[mask], dtype=np.float64).mean())
        means[str(label)] = mean
        if mean > best_mean:
            best_mean = mean
            best_label = label
    if best_label is None:
        return {"selected_region_id": None, "region_means": means, "rgb": None}
    selected_pixels = image[label_map == best_label]
    return {
        "selected_region_id": best_label,
        "selected_pixel_indices": np.flatnonzero(label_map.reshape(-1) == best_label)
        .astype(int)
        .tolist(),
        "region_means": means,
        "rgb": modal_rgb(selected_pixels, tie_policy),
    }


def evaluate_selection_scope(contract_input: dict) -> dict:
    """Apply canonical D-04 without treating the selection as geometry.

    The caller supplies the result of full-image enclosure analysis when that
    geometry is available.  A clipped acquisition boundary can only make the
    result indeterminate; it can never manufacture an enclosure.
    """

    component = sorted(int(value) for value in contract_input["component_pixel_indices"])
    selected = {int(value) for value in contract_input["selection_pixel_indices"]}
    full_geometry_accessible = bool(contract_input["full_geometry_accessible"])
    touches_boundary = bool(contract_input["touches_acquisition_boundary"])

    if not full_geometry_accessible:
        if not touches_boundary:
            raise ValueError(
                "A clipped-domain contract must identify the acquisition boundary."
            )
        return {
            "geometry_status": "indeterminate",
            "component_pixel_indices": component,
            "eligible": False,
            "application_pixel_indices": [],
            "selection_created_enclosure": False,
        }

    enclosed = contract_input["component_enclosed_in_full_geometry"]
    if not isinstance(enclosed, bool):
        raise ValueError("Full geometry requires an explicit enclosure result.")
    application = [index for index in component if index in selected] if enclosed else []
    return {
        "geometry_status": "enclosed" if enclosed else "open",
        "component_pixel_indices": component,
        "eligible": bool(application),
        "application_pixel_indices": application,
        "selection_created_enclosure": False,
    }


def evaluate_prediction_application(contract_input: dict) -> dict:
    """Apply canonical D-07 to learned/fallback prediction metadata."""

    source = contract_input["prediction_source"]
    if source not in ("learned", "fallback"):
        raise ValueError(f"Unsupported prediction source: {source}")
    learned_succeeded = bool(contract_input["learned_inference_succeeded"])
    confidence = contract_input["reported_confidence_band"]
    confirmed = bool(contract_input["explicit_user_confirmation"])

    if source == "learned":
        if not learned_succeeded:
            raise ValueError("A learned prediction requires successful inference.")
        return {
            "prediction_provenance": "learned",
            "effective_confidence_band": confidence,
            "apply_high_eligible": confidence == "high",
            "requires_explicit_confirmation": False,
            "manual_apply_eligible": True,
        }

    return {
        "prediction_provenance": "fallback",
        "effective_confidence_band": None,
        "apply_high_eligible": False,
        "requires_explicit_confirmation": True,
        "manual_apply_eligible": confirmed,
    }


def evaluate_modal_color(contract_input: dict) -> dict:
    """Apply canonical D-06 participation and deterministic scan ordering."""

    width = int(contract_input["width"])
    height = int(contract_input["height"])
    raw_pixels = contract_input["coloring_rgba_row_major"]
    if len(raw_pixels) != width * height:
        raise ValueError("Modal-color raster dimensions do not match its pixels.")
    if any(
        len(pixel) != 4
        or any(not isinstance(channel, int) or not 0 <= channel <= 255 for channel in pixel)
        for pixel in raw_pixels
    ):
        raise ValueError("Modal-color pixels must be RGBA8 values.")
    pixels = np.asarray(raw_pixels, dtype=np.uint8)
    region = [int(value) for value in contract_input["semantic_region_pixel_indices"]]
    if len(region) != len(set(region)) or any(
        index < 0 or index >= width * height for index in region
    ):
        raise ValueError("Semantic-region indices must be unique and in bounds.")
    excluded = {int(value) for value in contract_input["excluded_pixel_indices"]}
    if any(index < 0 or index >= width * height for index in excluded):
        raise ValueError("Excluded indices must be in bounds.")

    participating = sorted(
        index
        for index in region
        if index not in excluded and int(pixels[index, 3]) > 0
    )
    if not participating:
        raise ValueError("A representative color requires a painted participant.")
    return {
        "participating_pixel_indices": participating,
        "rgb": modal_rgb(pixels[participating], tie_policy="first_encountered"),
    }
