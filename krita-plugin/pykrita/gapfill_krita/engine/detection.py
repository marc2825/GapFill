from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from .types import DetectionGeometry, GapKind, GapRegion, LayerImages

ProgressCallback = Callable[[int, int], None]
_CANCEL_INTERVAL = 4096


@dataclass(frozen=True)
class _Run:
    y: int
    start: int
    end: int
    component: int


@dataclass
class _Component:
    area: int
    sum_x: int
    sum_y: int
    min_x: int
    min_y: int
    max_x: int
    max_y: int
    first_index: int
    touches_edge: bool
    pixels: list[int] = field(default_factory=list)
    application: list[int] = field(default_factory=list)


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value: int) -> int:
        root = value
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[value] != value:
            parent = self.parent[value]
            self.parent[value] = root
            value = parent
        return root

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


def normalize_legacy_rgba_geometry(
    images: LayerImages,
    *,
    selection_scope: Optional[np.ndarray] = None,
) -> DetectionGeometry:
    """Convert current Krita RGBA snapshots to normalized detector masks.

    Coloring uses canonical exact-zero alpha. Line and Guide use the existing
    platform conversion (any nonzero alpha). The latter is deliberately named
    legacy because faint/anti-aliased rasterization remains an empirical host
    question; the pure detector itself consumes only binary boundaries.
    """
    images.validate()
    selection = None
    if selection_scope is not None:
        selection = np.asarray(selection_scope)
        if selection.shape != images.coloring.shape[:2]:
            raise ValueError("Selection dimensions do not match the layer snapshots.")
        selection = selection.astype(np.bool_, copy=False)
    geometry = DetectionGeometry(
        coloring_gap=images.coloring[..., 3] == 0,
        line_boundary=images.line_art[..., 3] > 0,
        guide_boundary=images.guides[..., 3] > 0,
        selection_scope=selection,
    )
    geometry.validate()
    return geometry


def _row_ranges(row: np.ndarray) -> list[tuple[int, int]]:
    padded = np.pad(row.astype(np.int8, copy=False), (1, 1))
    transitions = np.flatnonzero(np.diff(padded))
    return [
        (int(start), int(end))
        for start, end in zip(transitions[::2], transitions[1::2])
    ]


def _run_component(
    y: int,
    start: int,
    end: int,
    width: int,
    height: int,
    max_pixels: int,
    selection: Optional[np.ndarray],
) -> _Component:
    area = end - start
    pixels = list(range(y * width + start, y * width + end)) if area <= max_pixels else []
    application: list[int] = []
    if selection is not None and area <= max_pixels:
        application = [
            y * width + x for x in range(start, end) if bool(selection[y, x])
        ]
    return _Component(
        area=area,
        sum_x=(start + end - 1) * area // 2,
        sum_y=y * area,
        min_x=start,
        min_y=y,
        max_x=end - 1,
        max_y=y,
        first_index=y * width + start,
        touches_edge=y == 0 or y + 1 == height or start == 0 or end == width,
        pixels=pixels,
        application=application,
    )


def _merge_components(left: _Component, right: _Component, max_pixels: int) -> _Component:
    area = left.area + right.area
    if area <= max_pixels:
        if len(left.pixels) < len(right.pixels):
            left, right = right, left
        left.pixels.extend(right.pixels)
        left.application.extend(right.application)
        pixels = left.pixels
        application = left.application
    else:
        pixels = []
        application = []
    return _Component(
        area=area,
        sum_x=left.sum_x + right.sum_x,
        sum_y=left.sum_y + right.sum_y,
        min_x=min(left.min_x, right.min_x),
        min_y=min(left.min_y, right.min_y),
        max_x=max(left.max_x, right.max_x),
        max_y=max(left.max_y, right.max_y),
        first_index=min(left.first_index, right.first_index),
        touches_edge=left.touches_edge or right.touches_edge,
        pixels=pixels,
        application=application,
    )


def _check_cancel(cancel_requested: Optional[Callable[[], bool]]) -> None:
    if cancel_requested and cancel_requested():
        raise InterruptedError("Gap detection was cancelled.")


def _finish_component(
    component: _Component,
    max_pixels: int,
    selection: Optional[np.ndarray],
) -> Optional[GapRegion]:
    if component.touches_edge or component.area > max_pixels:
        return None
    if selection is not None and not component.application:
        return None
    indices = np.asarray(sorted(component.pixels), dtype=np.int64)
    application = (
        np.asarray(sorted(component.application), dtype=np.int64)
        if selection is not None
        else None
    )
    return GapRegion(
        id="",
        indices=indices,
        center=(component.sum_x // component.area, component.sum_y // component.area),
        kind=GapKind.TRANSPARENT,
        metadata={
            "bounds": (
                component.min_x,
                component.min_y,
                component.max_x + 1,
                component.max_y + 1,
            ),
            "first_index": component.first_index,
        },
        application_indices=application,
    )


def detect_gap_regions(
    source: LayerImages | DetectionGeometry,
    max_pixels: int,
    *,
    cancel_requested: Optional[Callable[[], bool]] = None,
    progress: Optional[ProgressCallback] = None,
) -> list[GapRegion]:
    """Detect canonical enclosed gaps using streaming row-run labeling.

    Geometry is four-connected, image-edge components are open, and the size
    cutoff is inclusive. Selection is applied only after a full component's
    enclosure and size are known. Working state contains normalized image masks,
    the previous/current row runs, and at most ``max_pixels`` retained indices
    per still-eligible active component; oversized components remain connected
    but stop retaining pixels.
    """
    geometry = (
        normalize_legacy_rgba_geometry(source)
        if isinstance(source, LayerImages)
        else source
    )
    geometry.validate()
    if max_pixels < 1 or geometry.width == 0 or geometry.height == 0:
        return []

    candidates = geometry.coloring_gap & ~geometry.line_boundary & ~geometry.guide_boundary
    width, height = geometry.width, geometry.height
    selection = geometry.selection_scope
    active: list[_Component] = []
    previous: list[_Run] = []
    completed: list[GapRegion] = []
    operations = 0

    for y in range(height):
        _check_cancel(cancel_requested)
        ranges = _row_ranges(candidates[y])
        current = [
            _Run(y, start, end, len(active) + index)
            for index, (start, end) in enumerate(ranges)
        ]
        nodes = active + [
            _run_component(y, start, end, width, height, max_pixels, selection)
            for start, end in ranges
        ]
        union_find = _UnionFind(len(nodes))

        previous_index = 0
        for run in current:
            while previous_index < len(previous) and previous[previous_index].end <= run.start:
                previous_index += 1
            candidate_index = previous_index
            while candidate_index < len(previous) and previous[candidate_index].start < run.end:
                union_find.union(previous[candidate_index].component, run.component)
                candidate_index += 1
                operations += 1
                if operations % _CANCEL_INTERVAL == 0:
                    _check_cancel(cancel_requested)

        aggregated: dict[int, _Component] = {}
        for index, component in enumerate(nodes):
            root = union_find.find(index)
            aggregated[root] = (
                component
                if root not in aggregated
                else _merge_components(aggregated[root], component, max_pixels)
            )
            operations += 1
            if operations % _CANCEL_INTERVAL == 0:
                _check_cancel(cancel_requested)

        current_roots = {union_find.find(run.component) for run in current}
        for root, component in aggregated.items():
            if root not in current_roots:
                region = _finish_component(component, max_pixels, selection)
                if region is not None:
                    completed.append(region)

        root_to_active: dict[int, int] = {}
        next_active: list[_Component] = []
        next_current: list[_Run] = []
        for run in current:
            root = union_find.find(run.component)
            if root not in root_to_active:
                root_to_active[root] = len(next_active)
                next_active.append(aggregated[root])
            next_current.append(_Run(run.y, run.start, run.end, root_to_active[root]))
        active = next_active
        previous = next_current
        if progress and (y % 32 == 0 or y + 1 == height):
            progress(y + 1, height)

    _check_cancel(cancel_requested)
    for component in active:
        region = _finish_component(component, max_pixels, selection)
        if region is not None:
            completed.append(region)

    completed.sort(key=lambda region: int(region.metadata["first_index"]))
    for index, region in enumerate(completed):
        region.id = f"gap-{index}"
        region.metadata.pop("first_index", None)
    return completed
