from __future__ import annotations

import importlib
import sys
from dataclasses import replace
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest
from gapfill_krita.engine.types import (
    GapKind,
    GapRegion,
    LayerImages,
    PredictionProvenance,
)
from gapfill_krita.host_contract import (
    HostObservation,
    HostSnapshot,
    NodeState,
    ScanContext,
    StaleScanError,
)


class _Docker:
    def __init__(self):
        self.regions = []
        self.status = ""
        self.errors = []

    def set_regions(self, gaps):
        self.regions = list(gaps)

    def set_status(self, message):
        self.status = message

    def show_error(self, message):
        self.errors.append(message)

    def set_busy(self, _busy, _message=""):
        pass


def _node(identifier: str) -> NodeState:
    return NodeState(
        unique_id=identifier,
        node_type="paintlayer",
        position=(0, 0),
        bounds=(0, 0, 4, 4),
        color_model="RGBA",
        color_depth="U8",
        color_profile="sRGB-elle-V2-srgbtrc.icc",
        locked=False,
        alpha_locked=False,
        animated=False,
        visible=True,
        opacity=255,
        blending_mode="normal",
        inherit_alpha=False,
        layer_style="",
        child_signature=(),
        ancestor_signature=(),
    )


def _snapshot(generation: int = 1) -> HostSnapshot:
    rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    observation = HostObservation(
        document_key=11,
        view_key=22,
        image_root_id="root",
        document_geometry=(0, 0, 4, 4),
        source_space=("RGBA", "U8", "sRGB-elle-V2-srgbtrc.icc"),
        target=_node("target"),
        line=_node("line"),
        guides=None,
        active_node_id="target",
        selection_present=False,
        selection_sha256=None,
        coloring_sha256="H0",
        line_sha256="line",
        guides_sha256="guides",
        composite_sha256="composite-H0",
    )
    return HostSnapshot.create(
        LayerImages(rgba, rgba.copy(), rgba.copy(), rgba.copy()),
        None,
        ScanContext(generation, observation),
    )


def _gap(identifier: str, index: int, color) -> GapRegion:
    return GapRegion(
        identifier,
        np.asarray([index], dtype=np.int64),
        (index % 4, index // 4),
        GapKind.TRANSPARENT,
        predicted_rgb=color,
        prediction_provenance=PredictionProvenance.LEARNED,
        learned_confidence=0.75 + index / 100,
        metadata={"bounds": (index % 4, index // 4, index % 4 + 1, index // 4 + 1)},
        application_indices=np.asarray([index], dtype=np.int64),
    )


@pytest.fixture
def controller_module(monkeypatch):
    fake_krita = ModuleType("krita")

    class Krita:
        @staticmethod
        def instance():
            return None

    fake_krita.Krita = Krita
    fake_krita.ManagedColor = object
    monkeypatch.setitem(sys.modules, "krita", fake_krita)
    monkeypatch.delitem(sys.modules, "gapfill_krita.controller", raising=False)
    module = importlib.import_module("gapfill_krita.controller")
    yield module
    sys.modules.pop("gapfill_krita.controller", None)


def _active_controller(module, gaps):
    docker = _Docker()
    controller = module.GapFillController(docker)
    generation = controller._gate.start()
    controller._published_generation = generation
    controller.document = object()
    controller.view = object()
    controller.snapshot = _snapshot(generation)
    controller.gaps = list(gaps)
    controller._context_is_current = lambda value: value == generation
    refreshes = []
    controller._refresh_overlay_images = lambda: refreshes.append(tuple(controller.gaps))
    return controller, docker, generation, refreshes


def test_owned_applies_preserve_frozen_remaining_analysis_without_rescan(
    controller_module, monkeypatch
) -> None:
    gaps = [
        _gap("A", 1, (11, 12, 13)),
        _gap("B", 6, (21, 22, 23)),
        _gap("C", 11, (31, 32, 33)),
    ]
    controller, docker, generation, refreshes = _active_controller(
        controller_module, gaps
    )
    frozen_images = controller.snapshot.images
    frozen_b = gaps[1]
    frozen_c = gaps[2]
    frozen_b_state = (
        frozen_b.predicted_rgb,
        frozen_b.prediction_provenance,
        frozen_b.learned_confidence,
        frozen_b.center,
        frozen_b.indices.copy(),
        dict(frozen_b.metadata),
    )
    frozen_c_state = (
        frozen_c.predicted_rgb,
        frozen_c.prediction_provenance,
        frozen_c.learned_confidence,
        frozen_c.center,
        frozen_c.indices.copy(),
        dict(frozen_c.metadata),
    )

    calls = []

    def apply(_document, _view, context, selected):
        calls.append((context, tuple(gap.id for gap in selected)))
        number = len(calls)
        observation = replace(
            context.observation,
            coloring_sha256=f"H{number}",
            composite_sha256=f"composite-H{number}",
        )
        return SimpleNamespace(
            changed_pixels=sum(gap.target_indices.size for gap in selected),
            context=ScanContext(context.generation, observation),
        )

    monkeypatch.setattr(controller_module, "apply_gap_colors", apply)
    monkeypatch.setattr(
        controller_module,
        "GapFillWorker",
        lambda *_args, **_kwargs: pytest.fail("no scan/prediction worker may be built"),
    )
    scan_calls = []
    controller.scan = lambda *_args, **_kwargs: scan_calls.append(True)

    controller.apply_ids(["A"])

    assert controller._gate.accepts(generation)
    assert controller.resolved_ids == {"A"}
    assert [gap.id for gap in controller.gaps] == ["B", "C"]
    assert docker.regions == [frozen_b, frozen_c]
    assert controller.snapshot.images is frozen_images
    assert controller.snapshot.context.observation.coloring_sha256 == "H1"
    assert calls == [(calls[0][0], ("A",))]
    assert not scan_calls
    assert refreshes == [(frozen_b, frozen_c)]

    assert controller.gaps[0] is frozen_b
    assert controller.gaps[1] is frozen_c
    assert (
        frozen_b.predicted_rgb,
        frozen_b.prediction_provenance,
        frozen_b.learned_confidence,
        frozen_b.center,
        frozen_b.metadata,
    ) == frozen_b_state[:4] + (frozen_b_state[5],)
    assert np.array_equal(frozen_b.indices, frozen_b_state[4])
    assert (
        frozen_c.predicted_rgb,
        frozen_c.prediction_provenance,
        frozen_c.learned_confidence,
        frozen_c.center,
        frozen_c.metadata,
    ) == frozen_c_state[:4] + (frozen_c_state[5],)
    assert np.array_equal(frozen_c.indices, frozen_c_state[4])

    controller._scan_completed(generation, [_gap("stale", 2, (1, 2, 3))])
    assert [gap.id for gap in controller.gaps] == ["B", "C"]

    controller.apply_ids(["B"])
    assert controller._gate.accepts(generation)
    assert controller.resolved_ids == {"A", "B"}
    assert controller.gaps == [frozen_c]
    assert controller.snapshot.images is frozen_images
    assert controller.snapshot.context.observation.coloring_sha256 == "H2"
    assert [selected for _context, selected in calls] == [("A",), ("B",)]
    assert not scan_calls

    controller.apply_ids(["A"])
    assert len(calls) == 2
    assert "cannot be applied twice" in docker.errors[-1]

    controller.apply_ids(["C"])
    assert len(calls) == 3
    assert controller._gate.active is None
    assert controller.resolved_ids == {"A", "B", "C"}
    assert controller.gaps == []
    assert controller.snapshot is None
    assert "All candidates" in docker.status
    assert not scan_calls


def test_external_mutation_and_document_replacement_invalidate_session(
    controller_module, monkeypatch
) -> None:
    controller, docker, generation, _refreshes = _active_controller(
        controller_module,
        [_gap("A", 1, (11, 12, 13)), _gap("B", 2, (21, 22, 23))],
    )

    def owned_apply(_document, _view, context, _selected):
        return SimpleNamespace(
            changed_pixels=1,
            context=ScanContext(
                context.generation,
                replace(
                    context.observation,
                    coloring_sha256="H1",
                    composite_sha256="composite-H1",
                ),
            ),
        )

    monkeypatch.setattr(controller_module, "apply_gap_colors", owned_apply)
    controller.apply_ids(["A"])
    assert controller.snapshot.context.observation.coloring_sha256 == "H1"

    def stale(*_args, **_kwargs):
        raise StaleScanError("Coloring pixels changed after scanning.")

    monkeypatch.setattr(controller_module, "apply_gap_colors", stale)
    controller.apply_ids(["B"])
    assert controller._gate.active is None
    assert controller.snapshot is None
    assert controller.gaps == []
    assert "invalidated" in docker.errors[-1]

    controller._scan_completed(generation, [_gap("stale", 2, (1, 2, 3))])
    assert controller.gaps == []

    controller, docker, _generation, _refreshes = _active_controller(
        controller_module, [_gap("A", 1, (11, 12, 13))]
    )
    controller._context_is_current = lambda _value: False
    controller.apply_ids(["A"])
    assert controller._gate.active is None
    assert controller.snapshot is None
    assert "document/view changed" in docker.errors[-1]


def test_overlapping_unresolved_candidate_is_invalidated_without_rescan(
    controller_module, monkeypatch
) -> None:
    first = _gap("A", 1, (11, 12, 13))
    conflict = _gap("B", 2, (21, 22, 23))
    conflict.indices = np.asarray([1, 2], dtype=np.int64)
    remaining = _gap("C", 11, (31, 32, 33))
    controller, docker, generation, _refreshes = _active_controller(
        controller_module, [first, conflict, remaining]
    )

    def apply(_document, _view, context, selected):
        return SimpleNamespace(
            changed_pixels=1,
            context=ScanContext(
                context.generation,
                replace(
                    context.observation,
                    coloring_sha256="H1",
                    composite_sha256="composite-H1",
                ),
            ),
        )

    monkeypatch.setattr(controller_module, "apply_gap_colors", apply)
    controller.apply_ids(["A"])

    assert controller._gate.accepts(generation)
    assert controller.resolved_ids == {"A"}
    assert controller.invalidated_ids == {"B"}
    assert controller.gaps == [remaining]
    assert "without rescanning" in docker.status


def test_uncertain_native_failure_invalidates_session(
    controller_module, monkeypatch
) -> None:
    controller, docker, _generation, _refreshes = _active_controller(
        controller_module, [_gap("A", 1, (11, 12, 13))]
    )

    def native_failure(*_args, **_kwargs):
        raise controller_module.NativeHostError("controlled uncertain native failure")

    monkeypatch.setattr(controller_module, "apply_gap_colors", native_failure)
    controller.apply_ids(["A"])

    assert controller._gate.active is None
    assert controller.snapshot is None
    assert controller.gaps == []
    assert "could not be preserved" in docker.errors[-1]
