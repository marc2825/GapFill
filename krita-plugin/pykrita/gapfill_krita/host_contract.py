"""Krita-independent snapshot, staleness, and application invariants."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Optional

import numpy as np

from .engine.detection import normalize_legacy_rgba_geometry
from .engine.types import DetectionGeometry, GapRegion, LayerImages, Rgb

# Four RGBA snapshots plus selection and pure-analysis working memory make 8K
# unsafe in the audited host design. 4K-class documents remain admitted while
# 7680x4320 is rejected before the first LibKis pixel allocation.
MAX_SNAPSHOT_PIXELS = 4096 * 4096


class StaleScanError(RuntimeError):
    """The host no longer matches the immutable scan provenance."""


class GenerationGate:
    """Small host-neutral token gate for queued Qt callbacks."""

    def __init__(self) -> None:
        self._counter = 0
        self._active: Optional[int] = None
        self._closed = False

    @property
    def active(self) -> Optional[int]:
        return self._active

    def start(self) -> int:
        if self._closed:
            raise RuntimeError("GapFill is shutting down.")
        self._counter += 1
        self._active = self._counter
        return self._counter

    def accepts(self, generation: int) -> bool:
        return not self._closed and self._active == generation

    def retire(self, generation: Optional[int] = None) -> None:
        if generation is None or self._active == generation:
            self._active = None
            self._counter += 1

    def close(self) -> None:
        self._closed = True
        self._active = None
        self._counter += 1


@dataclass(frozen=True)
class NodeState:
    unique_id: str
    node_type: str
    position: tuple[int, int]
    bounds: tuple[int, int, int, int]
    color_model: str
    color_depth: str
    color_profile: str
    locked: bool
    alpha_locked: bool
    animated: bool
    visible: bool
    opacity: int
    blending_mode: str
    inherit_alpha: bool
    layer_style: str
    child_signature: tuple[tuple[str, str], ...]
    ancestor_signature: tuple[tuple[object, ...], ...]


@dataclass(frozen=True)
class HostObservation:
    document_key: int
    view_key: int
    image_root_id: str
    document_geometry: tuple[int, int, int, int]
    source_space: tuple[str, str, str]
    target: Optional[NodeState]
    line: Optional[NodeState]
    guides: Optional[NodeState]
    active_node_id: Optional[str]
    selection_present: bool
    selection_sha256: Optional[str]
    coloring_sha256: str
    line_sha256: str
    guides_sha256: str
    composite_sha256: str


@dataclass(frozen=True)
class ScanContext:
    generation: int
    observation: HostObservation


@dataclass(frozen=True)
class HostSnapshot:
    images: LayerImages
    selection_mask: Optional[np.ndarray]
    context: ScanContext

    @classmethod
    def create(
        cls,
        images: LayerImages,
        selection_mask: Optional[np.ndarray],
        context: ScanContext,
        *,
        take_ownership: bool = False,
    ) -> "HostSnapshot":
        images.validate()
        frozen_images = LayerImages(
            _frozen_copy(images.coloring, copy=not take_ownership),
            _frozen_copy(images.line_art, copy=not take_ownership),
            _frozen_copy(images.guides, copy=not take_ownership),
            _frozen_copy(images.composite, copy=not take_ownership)
            if images.composite is not None
            else None,
        )
        frozen_selection = None
        if selection_mask is not None:
            selection = np.asarray(selection_mask)
            if selection.shape != frozen_images.coloring.shape[:2]:
                raise ValueError("Selection dimensions do not match the host snapshot.")
            if selection.dtype != np.uint8:
                raise ValueError("The host selection must use byte coverage values.")
            frozen_selection = _frozen_copy(selection, copy=not take_ownership)
        return cls(frozen_images, frozen_selection, context)

    @property
    def detection_geometry(self) -> DetectionGeometry:
        selection = self.selection_mask > 0 if self.selection_mask is not None else None
        return normalize_legacy_rgba_geometry(
            self.images,
            selection_scope=selection,
        )


@dataclass(frozen=True)
class ApplicationPlan:
    indices: np.ndarray
    expected_rgba: np.ndarray
    groups: tuple[tuple[Rgb, np.ndarray], ...]


def _frozen_copy(array: Optional[np.ndarray], *, copy: bool = True) -> np.ndarray:
    if array is None:
        raise ValueError("Cannot freeze an absent array.")
    result = np.asarray(array).copy() if copy else np.asarray(array)
    result.flags.writeable = False
    return result


def image_sha256(image: np.ndarray) -> str:
    array = np.ascontiguousarray(image)
    digest = hashlib.sha256()
    digest.update(str(array.shape).encode("ascii"))
    digest.update(b"\0")
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(array.tobytes())
    return digest.hexdigest()


def require_supported_size(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise RuntimeError("GapFill requires a non-empty document.")
    pixels = width * height
    if pixels > MAX_SNAPSHOT_PIXELS:
        raise RuntimeError(
            "The document exceeds GapFill's supported snapshot limit of "
            f"{MAX_SNAPSHOT_PIXELS:,} pixels (received {width}x{height})."
        )


def require_fresh(context: ScanContext, current: HostObservation) -> None:
    expected = context.observation
    if current.document_key != expected.document_key:
        raise StaleScanError("The active document switched after scanning.")
    if current.view_key != expected.view_key:
        raise StaleScanError("The active view switched after scanning.")
    if current.image_root_id != expected.image_root_id:
        raise StaleScanError("The document image identity changed after scanning.")
    if current.document_geometry != expected.document_geometry:
        raise StaleScanError("The document resized or moved after scanning.")
    if current.source_space != expected.source_space:
        raise StaleScanError("The document color space changed after scanning.")
    if current.target is None:
        raise StaleScanError("The target deleted after scanning.")
    if expected.target is None or current.target.unique_id != expected.target.unique_id:
        raise StaleScanError("The target replaced after scanning.")
    if current.active_node_id != expected.active_node_id:
        raise StaleScanError("The active node switched after scanning.")
    if current.target.position != expected.target.position:
        raise StaleScanError("The target moved after scanning.")
    if current.target.child_signature != expected.target.child_signature:
        raise StaleScanError("The target transformed or gained an effect after scanning.")
    if current.target.locked != expected.target.locked:
        raise StaleScanError("The target locked state changed after scanning.")
    if current.target.alpha_locked != expected.target.alpha_locked:
        raise StaleScanError("The alpha lock changed after scanning.")
    if current.target != expected.target:
        raise StaleScanError("The target node state changed after scanning.")
    if current.line != expected.line or current.guides != expected.guides:
        raise StaleScanError("A Line Art or Guide node changed after scanning.")
    if (
        current.selection_present != expected.selection_present
        or current.selection_sha256 != expected.selection_sha256
    ):
        raise StaleScanError("The selection changed after scanning.")
    if current.coloring_sha256 != expected.coloring_sha256:
        raise StaleScanError("Coloring pixels changed after scanning.")
    if current.line_sha256 != expected.line_sha256:
        raise StaleScanError("Line Art pixels changed after scanning.")
    if current.guides_sha256 != expected.guides_sha256:
        raise StaleScanError("Guide pixels changed after scanning.")
    if current.composite_sha256 != expected.composite_sha256:
        raise StaleScanError("The document projection changed after scanning.")


def advance_context_after_owned_mutation(
    context: ScanContext,
    current: HostObservation,
    *,
    expected_coloring_sha256: str,
) -> ScanContext:
    """Advance only the host checkpoint after one verified GapFill transaction.

    The frozen analysis arrays and candidate results are intentionally not inputs
    here. Applying transparent pixels may change the target bounds, Coloring
    bytes, and composite projection; every other observed host property must
    still match the scan checkpoint exactly.
    """
    expected = context.observation
    if expected.target is None or current.target is None:
        raise StaleScanError("The target deleted while advancing the GapFill session.")
    if current.coloring_sha256 != expected_coloring_sha256:
        raise StaleScanError(
            "Coloring pixels changed after the verified GapFill transaction."
        )

    allowed_target = replace(expected.target, bounds=current.target.bounds)
    allowed_observation = replace(
        expected,
        target=allowed_target,
        coloring_sha256=expected_coloring_sha256,
        composite_sha256=current.composite_sha256,
    )
    require_fresh(ScanContext(context.generation, allowed_observation), current)
    return ScanContext(context.generation, current)


def build_application_plan(gaps: list[GapRegion], coloring: np.ndarray) -> ApplicationPlan:
    if coloring.dtype != np.uint8 or coloring.ndim != 3 or coloring.shape[2] != 4:
        raise ValueError("Application validation requires uint8 RGBA Coloring pixels.")
    flat = coloring.reshape((-1, 4))
    grouped: dict[Rgb, list[np.ndarray]] = {}
    all_indices: list[np.ndarray] = []
    seen: set[int] = set()
    for gap in gaps:
        color = gap.color
        if color is None:
            raise RuntimeError(f"{gap.id} has no predicted color.")
        indices = np.asarray(gap.target_indices, dtype=np.int64)
        if indices.ndim != 1 or indices.size == 0:
            raise StaleScanError(f"{gap.id} has no application pixels.")
        for value in indices.tolist():
            index = int(value)
            if index < 0 or index >= flat.shape[0]:
                raise StaleScanError(f"{gap.id} contains an out-of-range application pixel.")
            if index in seen:
                raise StaleScanError("Gap application pixels overlap.")
            seen.add(index)
        if np.any(flat[indices, 3] != 0):
            raise StaleScanError(
                f"{gap.id} is no longer fully transparent at every application pixel."
            )
        grouped.setdefault(color, []).append(indices)
        all_indices.append(indices)

    indices = (
        np.sort(np.concatenate(all_indices)).astype(np.int64, copy=False)
        if all_indices
        else np.asarray([], dtype=np.int64)
    )
    expected = coloring.copy()
    expected_flat = expected.reshape((-1, 4))
    groups: list[tuple[Rgb, np.ndarray]] = []
    for color, parts in grouped.items():
        group_indices = np.sort(np.concatenate(parts)).astype(np.int64, copy=False)
        expected_flat[group_indices, :3] = color
        expected_flat[group_indices, 3] = 255
        groups.append((color, group_indices))
    return ApplicationPlan(indices, expected, tuple(groups))
