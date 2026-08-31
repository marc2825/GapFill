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
    ModelBoundaryMode,
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


class _Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def disconnect(self, callback):
        self.callbacks.remove(callback)

    def emit(self):
        for callback in list(self.callbacks):
            callback(False)


def _actions():
    return {
        "edit_undo": SimpleNamespace(triggered=_Signal()),
        "edit_redo": SimpleNamespace(triggered=_Signal()),
    }


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


def _active_controller(
    module, gaps, mode: ModelBoundaryMode = ModelBoundaryMode.LINE_ONLY
):
    docker = _Docker()
    controller = module.GapFillController(docker)
    generation = controller._gate.start()
    controller._published_generation = generation
    controller.document = object()
    controller.view = object()
    controller.snapshot = _snapshot(generation)
    controller.gaps = list(gaps)
    controller._analysis_model_boundary_mode = mode
    controller._start_session_history(controller.gaps)
    overlay = SimpleNamespace(
        closed=False,
        deleted=False,
        close=lambda: setattr(overlay, "closed", True),
        deleteLater=lambda: setattr(overlay, "deleted", True),
    )
    controller.overlay = overlay
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
    assert controller._gate.accepts(generation)
    assert controller.resolved_ids == {"A", "B", "C"}
    assert controller.gaps == []
    assert controller.snapshot is not None
    assert "All candidates" in docker.status
    assert not scan_calls


def _install_owned_apply(controller_module, monkeypatch):
    calls = []

    def apply(_document, _view, context, selected):
        calls.append(tuple(gap.id for gap in selected))
        number = len(calls)
        return SimpleNamespace(
            changed_pixels=sum(gap.target_indices.size for gap in selected),
            context=ScanContext(
                context.generation,
                replace(
                    context.observation,
                    coloring_sha256=f"H{number}",
                    composite_sha256=f"composite-H{number}",
                ),
            ),
        )

    monkeypatch.setattr(controller_module, "apply_gap_colors", apply)
    return calls


def _observe_hash(controller, coloring_hash: str):
    number = coloring_hash.removeprefix("H")
    current = controller.snapshot.context.observation
    return replace(
        current,
        coloring_sha256=coloring_hash,
        composite_sha256=f"composite-H{number}",
    )


@pytest.mark.parametrize("model_mode", list(ModelBoundaryMode))
def test_verified_undo_restores_original_frozen_candidates_without_inference(
    controller_module, monkeypatch, model_mode
) -> None:
    gaps = [
        _gap("A", 1, (11, 12, 13)),
        _gap("B", 6, (21, 22, 23)),
        _gap("C", 11, (31, 32, 33)),
    ]
    controller, docker, generation, _refreshes = _active_controller(
        controller_module, gaps, model_mode
    )
    gaps[0].preview_rgb = (101, 102, 103)
    frozen_metadata = [dict(gap.metadata) for gap in gaps]
    _install_owned_apply(controller_module, monkeypatch)
    controller.apply_ids(["A"])
    controller._observe_current_context = lambda: _observe_hash(controller, "H0")

    controller._reconcile_history("undo")

    assert controller._gate.accepts(generation)
    assert controller.gaps == gaps
    assert all(actual is frozen for actual, frozen in zip(controller.gaps, gaps))
    assert gaps[0].preview_rgb is None
    assert gaps[0].color == gaps[0].predicted_rgb
    assert [gap.metadata for gap in gaps] == frozen_metadata
    assert controller.resolved_ids == set()
    assert controller.invalidated_ids == set()
    assert controller.snapshot.context.observation.coloring_sha256 == "H0"
    assert docker.regions == gaps
    assert "Restored frozen GapFill checkpoint 1/2" in docker.status
    assert all(
        checkpoint.model_boundary_mode is model_mode
        for checkpoint in controller._session_checkpoints
    )


def test_model_mode_change_invalidates_active_analysis_without_rescan(
    controller_module, monkeypatch
) -> None:
    controller, docker, _generation, _refreshes = _active_controller(
        controller_module, [_gap("A", 1, (11, 12, 13))]
    )
    constructed_workers = []
    monkeypatch.setattr(
        controller_module,
        "GapFillWorker",
        lambda *_args, **_kwargs: constructed_workers.append(True),
    )

    controller.model_boundary_mode_changed(ModelBoundaryMode.LINE_OR_GUIDES)

    assert constructed_workers == []
    assert controller.snapshot is None
    assert controller.gaps == []
    assert controller.overlay is None
    assert controller._session_checkpoints == []
    assert controller._analysis_model_boundary_mode is None
    assert docker.regions == []
    assert "Run Scan / Activate" in docker.status


def test_checkpoint_cannot_restore_into_a_different_model_mode(
    controller_module
) -> None:
    controller, _docker, _generation, _refreshes = _active_controller(
        controller_module,
        [_gap("A", 1, (11, 12, 13))],
        ModelBoundaryMode.LINE_ONLY,
    )
    controller._analysis_model_boundary_mode = ModelBoundaryMode.LINE_OR_GUIDES

    with pytest.raises(StaleScanError, match="different model input mode"):
        controller._restore_session_checkpoint(0)


def test_scan_time_binding_uses_current_actions_not_initial_action_environment(
    controller_module, monkeypatch
) -> None:
    initial_actions = _actions()
    current_actions = _actions()
    active_actions = initial_actions
    requested = []
    app = SimpleNamespace(
        action=lambda identifier: (
            requested.append(identifier),
            active_actions[identifier],
        )[1]
    )
    monkeypatch.setattr(
        controller_module,
        "Krita",
        SimpleNamespace(instance=lambda: app),
    )
    controller = controller_module.GapFillController(_Docker())
    directions = []
    controller.history_action_triggered = directions.append
    assert requested == []

    active_actions = current_actions
    controller._bind_history_actions(app)

    initial_actions["edit_undo"].triggered.emit()
    initial_actions["edit_redo"].triggered.emit()
    assert directions == []
    current_actions["edit_undo"].triggered.emit()
    current_actions["edit_redo"].triggered.emit()

    assert requested == ["edit_undo", "edit_redo"]
    assert directions == ["undo", "redo"]
    assert len(controller._history_action_connections) == 2
    controller._disconnect_history_actions()
    assert not current_actions["edit_undo"].triggered.callbacks
    assert not current_actions["edit_redo"].triggered.callbacks


def test_rebinding_same_or_replaced_actions_never_duplicates_callbacks(
    controller_module, monkeypatch
) -> None:
    first = _actions()
    second = _actions()
    active_actions = first
    app = SimpleNamespace(action=lambda identifier: active_actions[identifier])
    monkeypatch.setattr(
        controller_module,
        "Krita",
        SimpleNamespace(instance=lambda: app),
    )
    controller = controller_module.GapFillController(_Docker())
    directions = []
    controller.history_action_triggered = directions.append

    controller._bind_history_actions(app)
    controller._bind_history_actions(app)
    controller._bind_history_actions(app)
    assert len(first["edit_undo"].triggered.callbacks) == 1
    assert len(first["edit_redo"].triggered.callbacks) == 1
    first["edit_undo"].triggered.emit()
    assert directions == ["undo"]

    active_actions = second
    controller._bind_history_actions(app)
    assert not first["edit_undo"].triggered.callbacks
    assert not first["edit_redo"].triggered.callbacks
    first["edit_undo"].triggered.emit()
    assert directions == ["undo"]
    second["edit_undo"].triggered.emit()
    second["edit_redo"].triggered.emit()
    assert directions == ["undo", "undo", "redo"]


def test_scan_invokes_current_window_action_binding_after_host_resolution(
    controller_module, monkeypatch
) -> None:
    document = object()
    view = object()
    window = SimpleNamespace(activeView=lambda: view)
    app = SimpleNamespace(
        activeDocument=lambda: document,
        activeWindow=lambda: window,
    )
    monkeypatch.setattr(
        controller_module,
        "Krita",
        SimpleNamespace(instance=lambda: app),
    )
    controller = controller_module.GapFillController(_Docker())
    bound = []
    controller._bind_history_actions = bound.append
    monkeypatch.setattr(
        controller_module,
        "snapshot_host",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("stop after binding")),
    )

    controller.scan(object(), object(), None, 100, False)

    assert bound == [app]


def test_current_undo_action_runs_real_host_ordered_reconciliation_once(
    controller_module, monkeypatch
) -> None:
    gaps = [
        _gap("A", 1, (11, 12, 13)),
        _gap("B", 6, (21, 22, 23)),
        _gap("C", 11, (31, 32, 33)),
    ]
    controller, docker, generation, _refreshes = _active_controller(
        controller_module, gaps
    )
    actions = _actions()
    app = SimpleNamespace(action=lambda identifier: actions[identifier])
    controller._bind_history_actions(app)
    _install_owned_apply(controller_module, monkeypatch)
    frozen_state = (
        gaps[0].id,
        gaps[0].predicted_rgb,
        gaps[0].learned_confidence,
        gaps[0].prediction_provenance,
        gaps[0].center,
        gaps[0].indices.copy(),
        dict(gaps[0].metadata),
    )
    gaps[0].preview_rgb = (0, 0, 255)
    gaps[2].preview_rgb = (240, 200, 10)
    controller._preview_changed("A", gaps[0].preview_rgb)
    rendered = []
    controller._refresh_overlay_images = lambda: rendered.append(
        tuple((gap.id, gap.color) for gap in controller.gaps)
    )
    monkeypatch.setattr(
        controller_module,
        "GapFillWorker",
        lambda *_args, **_kwargs: pytest.fail("Undo must not construct a worker"),
    )
    queued = []
    monkeypatch.setattr(
        controller_module,
        "QTimer",
        SimpleNamespace(singleShot=lambda _delay, callback: queued.append(callback)),
    )
    controller.apply_ids(["A"])
    controller._observe_current_context = lambda: _observe_hash(controller, "H0")

    actions["edit_undo"].triggered.emit()

    assert len(queued) == 1
    assert controller._pending_history_direction == "undo"
    assert controller._checkpoint_index == 1
    queued.pop()()
    assert controller._gate.accepts(generation)
    assert controller._checkpoint_index == 0
    assert controller.gaps == gaps
    assert controller.resolved_ids == set()
    assert docker.regions == gaps
    assert gaps[0].predicted_rgb == (11, 12, 13)
    assert gaps[0].preview_rgb is None
    assert gaps[0].color == (11, 12, 13)
    assert gaps[2].preview_rgb == (240, 200, 10)
    assert rendered[-1] == (
        ("A", (11, 12, 13)),
        ("B", (21, 22, 23)),
        ("C", (240, 200, 10)),
    )
    assert (
        gaps[0].id,
        gaps[0].predicted_rgb,
        gaps[0].learned_confidence,
        gaps[0].prediction_provenance,
        gaps[0].center,
        gaps[0].metadata,
    ) == frozen_state[:5] + (frozen_state[6],)
    assert np.array_equal(gaps[0].indices, frozen_state[5])
    assert not queued


def test_shutdown_disconnects_current_action_objects(
    controller_module, monkeypatch
) -> None:
    controller, _docker, _generation, _refreshes = _active_controller(
        controller_module, [_gap("A", 1, (11, 12, 13))]
    )
    actions = _actions()
    app = SimpleNamespace(action=lambda identifier: actions[identifier])
    controller._bind_history_actions(app)
    directions = []
    controller.history_action_triggered = directions.append

    controller.shutdown()
    actions["edit_undo"].triggered.emit()
    actions["edit_redo"].triggered.emit()

    assert directions == []
    assert controller._history_action_connections == {}
    assert controller._history_binding_diagnostic == "History actions are not bound."


def test_missing_current_history_action_is_diagnostic_and_nonfatal(
    controller_module, monkeypatch
) -> None:
    undo = SimpleNamespace(triggered=_Signal())
    app = SimpleNamespace(
        action=lambda identifier: undo if identifier == "edit_undo" else None
    )
    monkeypatch.setattr(
        controller_module,
        "Krita",
        SimpleNamespace(instance=lambda: app),
    )
    controller = controller_module.GapFillController(_Docker())

    controller._bind_history_actions(app)

    assert set(controller._history_action_connections) == {"undo"}
    assert controller._history_binding_diagnostic == (
        "Unavailable current-window history action(s): edit_redo"
    )


def test_two_level_undo_and_redo_restore_only_adjacent_exact_checkpoints(
    controller_module, monkeypatch
) -> None:
    gaps = [
        _gap("A", 1, (11, 12, 13)),
        _gap("B", 6, (21, 22, 23)),
        _gap("C", 11, (31, 32, 33)),
    ]
    controller, _docker, _generation, _refreshes = _active_controller(
        controller_module, gaps
    )
    _install_owned_apply(controller_module, monkeypatch)
    gaps[0].preview_rgb = (0, 0, 255)
    controller._preview_changed("A", gaps[0].preview_rgb)
    controller.apply_ids(["A"])
    gaps[1].preview_rgb = (128, 0, 128)
    controller._preview_changed("B", gaps[1].preview_rgb)
    controller.apply_ids(["B"])

    controller._observe_current_context = lambda: _observe_hash(controller, "H1")
    controller._reconcile_history("undo")
    assert controller.gaps == [gaps[1], gaps[2]]
    assert controller.resolved_ids == {"A"}
    assert gaps[1].preview_rgb is None
    assert gaps[1].color == gaps[1].predicted_rgb

    controller._observe_current_context = lambda: _observe_hash(controller, "H0")
    controller._reconcile_history("undo")
    assert controller.gaps == gaps
    assert controller.resolved_ids == set()
    assert gaps[0].preview_rgb is None
    assert gaps[0].color == gaps[0].predicted_rgb

    controller._observe_current_context = lambda: _observe_hash(controller, "H1")
    controller._reconcile_history("redo")
    assert controller.gaps == [gaps[1], gaps[2]]
    assert controller.resolved_ids == {"A"}

    controller._observe_current_context = lambda: _observe_hash(controller, "H2")
    controller._reconcile_history("redo")
    assert controller.gaps == [gaps[2]]
    assert controller.resolved_ids == {"A", "B"}

    controller._observe_current_context = lambda: _observe_hash(controller, "H1")
    controller._reconcile_history("undo")
    assert controller.gaps == [gaps[1], gaps[2]]
    assert gaps[1].preview_rgb is None
    controller._observe_current_context = lambda: _observe_hash(controller, "H0")
    controller._reconcile_history("undo")
    assert controller.gaps == gaps
    assert gaps[0].preview_rgb is None


def test_exhausted_session_undo_reinstalls_overlay_and_candidate(
    controller_module, monkeypatch
) -> None:
    gap = _gap("A", 1, (11, 12, 13))
    controller, docker, generation, _refreshes = _active_controller(
        controller_module, [gap]
    )
    _install_owned_apply(controller_module, monkeypatch)
    installed = []

    def install_overlay():
        installed.append(True)
        controller.overlay = object()

    controller._install_overlay = install_overlay
    gap.preview_rgb = (0, 0, 255)
    controller._preview_changed("A", gap.preview_rgb)
    controller.apply_ids(["A"])
    assert controller.gaps == []
    assert controller.snapshot is not None
    assert controller._gate.accepts(generation)

    controller._observe_current_context = lambda: _observe_hash(controller, "H0")
    controller._reconcile_history("undo")

    assert controller.gaps == [gap]
    assert controller.gaps[0] is gap
    assert gap.preview_rgb is None
    assert gap.color == gap.predicted_rgb
    assert docker.regions == [gap]
    assert installed == [True]


def test_unknown_history_or_external_state_invalidates_fail_closed(
    controller_module, monkeypatch
) -> None:
    controller, docker, _generation, _refreshes = _active_controller(
        controller_module, [_gap("A", 1, (11, 12, 13))]
    )
    _install_owned_apply(controller_module, monkeypatch)
    controller.apply_ids(["A"])
    controller._observe_current_context = lambda: replace(
        controller.snapshot.context.observation,
        coloring_sha256="external",
        composite_sha256="external-composite",
    )

    controller._reconcile_history("undo")

    assert controller.snapshot is None
    assert controller.gaps == []
    assert controller._gate.active is None
    assert "did not match" in docker.errors[-1]


def test_history_branch_discards_stale_forward_checkpoint(
    controller_module, monkeypatch
) -> None:
    gaps = [_gap("A", 1, (11, 12, 13)), _gap("B", 6, (21, 22, 23))]
    controller, docker, _generation, _refreshes = _active_controller(
        controller_module, gaps
    )
    calls = _install_owned_apply(controller_module, monkeypatch)
    controller.apply_ids(["A"])
    old_forward = controller._session_checkpoints[1]
    controller._observe_current_context = lambda: _observe_hash(controller, "H0")
    controller._reconcile_history("undo")

    controller.apply_ids(["B"])

    assert calls == [("A",), ("B",)]
    assert len(controller._session_checkpoints) == 2
    assert controller._session_checkpoints[1] is not old_forward
    assert controller.resolved_ids == {"B"}
    assert controller.gaps == [gaps[0]]

    controller._observe_current_context = lambda: old_forward.context.observation
    controller._reconcile_history("redo")
    assert controller.snapshot is None
    assert "not an adjacent known GapFill transaction" in docker.errors[-1]


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
    overlay = SimpleNamespace(
        closed=False,
        deleted=False,
        close=lambda: setattr(overlay, "closed", True),
        deleteLater=lambda: setattr(overlay, "deleted", True),
    )
    controller.overlay = overlay
    controller.apply_ids(["B"])
    assert controller._gate.active is None
    assert controller.snapshot is None
    assert controller.gaps == []
    assert overlay.closed
    assert overlay.deleted
    assert controller.overlay is None
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
