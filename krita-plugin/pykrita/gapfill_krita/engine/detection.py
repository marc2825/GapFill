from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from .types import GapKind, GapRegion, LayerImages

ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class _Run:
    y: int
    start: int
    end: int
    kind: int
    label: int


class _UnionFind:
    def __init__(self) -> None:
        self.parent: list[int] = []
        self.rank: list[int] = []

    def add(self) -> int:
        label = len(self.parent)
        self.parent.append(label)
        self.rank.append(0)
        return label

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


def _candidate_map(images: LayerImages) -> np.ndarray:
    coloring_transparent = images.coloring[..., 3] == 0
    line_clear = images.line_art[..., 3] == 0
    guide_present = images.guides[..., 3] > 0
    candidates = np.zeros(images.coloring.shape[:2], dtype=np.uint8)
    candidates[coloring_transparent & line_clear & ~guide_present] = 1
    # A visible Guide over transparent coloring is its own candidate component.
    candidates[coloring_transparent & line_clear & guide_present] = 2
    return candidates


def _row_runs(row: np.ndarray, y: int, union_find: _UnionFind) -> list[_Run]:
    if row.size == 0:
        return []
    boundaries = np.flatnonzero(
        np.concatenate((np.array([True]), row[1:] != row[:-1], np.array([True])))
    )
    runs: list[_Run] = []
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        kind = int(row[start])
        if kind:
            runs.append(_Run(y, int(start), int(end), kind, union_find.add()))
    return runs


def _connect_rows(previous: list[_Run], current: list[_Run], uf: _UnionFind) -> None:
    previous_index = 0
    for run in current:
        while previous_index < len(previous) and previous[previous_index].end <= run.start:
            previous_index += 1
        candidate_index = previous_index
        while candidate_index < len(previous) and previous[candidate_index].start < run.end:
            candidate = previous[candidate_index]
            if candidate.kind == run.kind:
                uf.union(candidate.label, run.label)
            candidate_index += 1


def detect_gap_regions(
    images: LayerImages,
    max_pixels: int,
    *,
    cancel_requested: Optional[Callable[[], bool]] = None,
    progress: Optional[ProgressCallback] = None,
) -> list[GapRegion]:
    """Detect enclosed 4-connected gaps using row-run component labeling.

    Normal transparent gaps and transparent pixels covered by Guides are kept as
    separate component classes. Components touching the document edge are open,
    not enclosed, and therefore are not gaps.
    """
    images.validate()
    if max_pixels < 1:
        return []

    candidates = _candidate_map(images)
    height, width = candidates.shape
    uf = _UnionFind()
    all_runs: list[_Run] = []
    previous: list[_Run] = []

    for y in range(height):
        if cancel_requested and cancel_requested():
            raise InterruptedError("Gap detection was cancelled.")
        current = _row_runs(candidates[y], y, uf)
        _connect_rows(previous, current, uf)
        all_runs.extend(current)
        previous = current
        if progress and (y % 32 == 0 or y + 1 == height):
            progress(y + 1, height)

    grouped: dict[int, list[_Run]] = {}
    for run in all_runs:
        grouped.setdefault(uf.find(run.label), []).append(run)

    regions: list[GapRegion] = []
    for runs in grouped.values():
        pixel_count = sum(run.end - run.start for run in runs)
        if pixel_count > max_pixels:
            continue
        touches_edge = any(
            run.y == 0 or run.y == height - 1 or run.start == 0 or run.end == width for run in runs
        )
        if touches_edge:
            continue

        indices = np.concatenate(
            [run.y * width + np.arange(run.start, run.end, dtype=np.int64) for run in runs]
        )
        ys, xs = np.divmod(indices, width)
        center = (int(np.floor(xs.mean())), int(np.floor(ys.mean())))
        bounds = (
            int(xs.min()),
            int(ys.min()),
            int(xs.max()) + 1,
            int(ys.max()) + 1,
        )
        kind = GapKind.GUIDE if runs[0].kind == 2 else GapKind.TRANSPARENT
        regions.append(
            GapRegion(
                id=f"gap-{len(regions)}",
                indices=indices,
                center=center,
                kind=kind,
                metadata={"bounds": bounds},
            )
        )

    regions.sort(key=lambda region: (region.center[1], region.center[0]))
    for index, region in enumerate(regions):
        region.id = f"gap-{index}"
    return regions
