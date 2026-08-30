from dataclasses import replace

import numpy as np
import pytest
from gapfill_krita.engine.types import GapKind, GapRegion, LayerImages
from gapfill_krita.host_contract import (
    MAX_SNAPSHOT_PIXELS,
    GenerationGate,
    HostObservation,
    HostSnapshot,
    NodeState,
    ScanContext,
    StaleScanError,
    advance_context_after_owned_mutation,
    build_application_plan,
    image_sha256,
    require_fresh,
    require_supported_size,
)


def _node(identifier: str = "target") -> NodeState:
    return NodeState(
        unique_id=identifier,
        node_type="paintlayer",
        position=(0, 0),
        bounds=(0, 0, 5, 5),
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


def _observation() -> HostObservation:
    return HostObservation(
        document_key=11,
        view_key=22,
        image_root_id="{00000000-0000-0000-0000-000000000010}",
        document_geometry=(0, 0, 5, 5),
        source_space=("RGBA", "U8", "sRGB-elle-V2-srgbtrc.icc"),
        target=_node(),
        line=_node("line"),
        guides=None,
        active_node_id="target",
        selection_present=False,
        selection_sha256=None,
        coloring_sha256="coloring",
        line_sha256="line",
        guides_sha256="empty-guides",
        composite_sha256="composite",
    )


def test_stale_context_rejects_every_relevant_mutation() -> None:
    original = _observation()
    context = ScanContext(7, original)
    variants = {
        "Coloring pixels": replace(original, coloring_sha256="edited"),
        "target moved": replace(original, target=replace(original.target, position=(3, 4))),
        "target transformed": replace(
            original, target=replace(original.target, child_signature=(("transform", "transformmask"),))
        ),
        "target deleted": replace(original, target=None),
        "target replaced": replace(original, target=_node("replacement")),
        "target locked": replace(original, target=replace(original.target, locked=True)),
        "alpha lock": replace(original, target=replace(original.target, alpha_locked=True)),
        "document resized": replace(original, document_geometry=(0, 0, 6, 5)),
        "color space changed": replace(
            original, source_space=("RGBA", "U8", "another.icc")
        ),
        "selection changed": replace(
            original,
            selection_present=True,
            selection_sha256="selection",
        ),
        "active node switched": replace(original, active_node_id="line"),
        "active document switched": replace(original, document_key=12),
        "active view switched": replace(original, view_key=23),
        "document image identity changed": replace(original, image_root_id="replacement"),
    }
    for reason, current in variants.items():
        with pytest.raises(StaleScanError, match=reason):
            require_fresh(context, current)

    require_fresh(context, original)


def test_owned_mutation_advances_only_target_pixels_bounds_and_composite() -> None:
    original = _observation()
    context = ScanContext(7, original)
    current = replace(
        original,
        target=replace(original.target, bounds=(0, 0, 6, 5)),
        coloring_sha256="verified-h1",
        composite_sha256="projection-h1",
    )
    advanced = advance_context_after_owned_mutation(
        context, current, expected_coloring_sha256="verified-h1"
    )
    assert advanced.generation == context.generation
    assert advanced.observation == current
    require_fresh(advanced, current)

    external = replace(current, line_sha256="external-line-edit")
    with pytest.raises(StaleScanError, match="Line Art pixels"):
        advance_context_after_owned_mutation(
            context, external, expected_coloring_sha256="verified-h1"
        )

    wrong_coloring = replace(current, coloring_sha256="external-coloring-edit")
    with pytest.raises(StaleScanError, match="Coloring pixels changed"):
        advance_context_after_owned_mutation(
            context, wrong_coloring, expected_coloring_sha256="verified-h1"
        )


def test_host_snapshot_freezes_arrays_and_preserves_soft_selection() -> None:
    rgba = np.zeros((5, 5, 4), dtype=np.uint8)
    selection = np.zeros((5, 5), dtype=np.uint8)
    selection[2, 2] = 1
    snapshot = HostSnapshot.create(
        LayerImages(rgba, rgba.copy(), rgba.copy(), rgba.copy()),
        selection,
        ScanContext(1, _observation()),
    )
    assert snapshot.selection_mask[2, 2] == 1
    assert snapshot.detection_geometry.selection_scope[2, 2]
    assert not snapshot.images.coloring.flags.writeable
    with pytest.raises(ValueError):
        snapshot.images.coloring[0, 0, 0] = 1


def test_application_plan_uses_selected_targets_and_fails_on_stale_pixels() -> None:
    coloring = np.zeros((3, 3, 4), dtype=np.uint8)
    first = GapRegion(
        "gap-0",
        np.asarray([4, 5], dtype=np.int64),
        (1, 1),
        GapKind.TRANSPARENT,
        predicted_rgb=(20, 30, 40),
        application_indices=np.asarray([4], dtype=np.int64),
    )
    plan = build_application_plan([first], coloring)
    assert plan.indices.tolist() == [4]
    assert plan.expected_rgba.reshape((-1, 4))[4].tolist() == [20, 30, 40, 255]

    coloring.reshape((-1, 4))[4] = (1, 2, 3, 255)
    with pytest.raises(StaleScanError, match="no longer fully transparent"):
        build_application_plan([first], coloring)


def test_snapshot_limit_fails_before_allocation() -> None:
    require_supported_size(4096, 4096)
    assert MAX_SNAPSHOT_PIXELS == 4096 * 4096
    with pytest.raises(RuntimeError, match="supported snapshot limit"):
        require_supported_size(7680, 4320)


def test_image_digest_binds_shape_dtype_and_bytes() -> None:
    first = np.zeros((2, 2, 4), dtype=np.uint8)
    second = first.copy()
    second[1, 1, 0] = 1
    assert image_sha256(first) != image_sha256(second)


def test_generation_gate_rejects_cancelled_superseded_and_shutdown_callbacks() -> None:
    gate = GenerationGate()
    scan_a = gate.start()
    assert gate.accepts(scan_a)
    gate.retire(scan_a)  # Deactivate just before queued completion delivery.
    assert not gate.accepts(scan_a)

    scan_b = gate.start()  # B supersedes all delayed A signals.
    assert scan_b != scan_a
    assert gate.accepts(scan_b)
    assert not gate.accepts(scan_a)

    gate.close()  # Plug-in shutdown while B is still active.
    assert not gate.accepts(scan_b)
    with pytest.raises(RuntimeError, match="shutting down"):
        gate.start()
