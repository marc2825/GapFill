"""Validate the checked-in GapFill Phase 2 fixture corpus."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256

import numpy as np

from .generate import DECISIONS, FIXTURE_ROOT, MODEL_PATH, PROVENANCE
from .reference import (
    DetectionPolicy,
    decode_palette_rgba,
    detect_components,
    evaluate_modal_color,
    evaluate_prediction_application,
    evaluate_selection_scope,
    make_patch_expectation,
    score_regions,
    segment_colored_components,
    sha256_file,
    tensor_from_sparse,
)

VALID_CLASSIFICATIONS = {
    "STABLE",
    "EMPIRICAL_DECISION_REQUIRED",
    "NONCANONICAL_REFERENCE",
}


def _load(relative: str) -> dict:
    return json.loads((FIXTURE_ROOT / relative).read_text(encoding="utf-8"))


def _validate_provenance(expectation: dict, location: str) -> None:
    classification = expectation["classification"]
    if classification not in VALID_CLASSIFICATIONS:
        raise AssertionError(f"{location}: invalid classification {classification}")
    evidence_ids = expectation.get("evidence_ids", [])
    decision_ids = expectation.get("decision_ids", [])
    if not evidence_ids or not decision_ids:
        raise AssertionError(f"{location}: missing evidence or decision IDs")
    for evidence_id in evidence_ids:
        if evidence_id not in PROVENANCE:
            raise AssertionError(f"{location}: unknown evidence {evidence_id}")
    for decision_id in decision_ids:
        if decision_id not in DECISIONS:
            raise AssertionError(f"{location}: unknown decision {decision_id}")
    if expectation.get("canonical") and classification != "STABLE":
        raise AssertionError(f"{location}: only STABLE values may be canonical")


def validate_manifest() -> None:
    manifest = _load("manifest.json")
    if manifest["schema"] != "gapfill-fixture-manifest-v2":
        raise AssertionError("Unexpected manifest schema")
    if manifest["provenance"] != PROVENANCE:
        raise AssertionError("Manifest provenance catalog drifted")
    if manifest["decisions"] != DECISIONS:
        raise AssertionError("Manifest decision catalog drifted")
    for decision_id in ("D-01", "D-02", "D-03", "D-04", "D-05", "D-06", "D-07"):
        if manifest["decisions"].get(decision_id) != "STABLE":
            raise AssertionError(f"{decision_id}: maintainer decision is not frozen STABLE")
    if "HUMAN_PRODUCT_DECISION_REQUIRED" in manifest["decisions"].values():
        raise AssertionError("A human product decision remains unresolved")
    listed = {entry["path"]: entry for entry in manifest["files"]}
    actual = {
        str(path.relative_to(FIXTURE_ROOT)): path
        for path in FIXTURE_ROOT.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if set(listed) != set(actual):
        raise AssertionError(
            f"Manifest file set mismatch: missing={set(actual)-set(listed)}, extra={set(listed)-set(actual)}"
        )
    for relative, path in actual.items():
        entry = listed[relative]
        if entry["sha256"] != sha256_file(path) or entry["bytes"] != path.stat().st_size:
            raise AssertionError(f"Manifest checksum/size mismatch: {relative}")
    if manifest["model_contract"]["sha256"] != sha256_file(MODEL_PATH):
        raise AssertionError("Pinned ONNX checksum mismatch")


def validate_detection() -> None:
    data = _load("detection/cases.json")
    for case in data["cases"]:
        if len(case["rasters"]["coloring_rgba"]["rows"]) != case["height"]:
            raise AssertionError(f"{case['id']}: coloring height mismatch")
        for expectation in case["expectations"]:
            location = f"{case['id']}/{expectation['variant']}"
            _validate_provenance(expectation, location)
            actual = {
                "components": detect_components(
                    case, DetectionPolicy(**expectation["policy"])
                )
            }
            if actual != expectation["result"]:
                raise AssertionError(f"Detection expectation drifted: {location}")


def validate_patch() -> None:
    data = _load("patch/cases.json")
    for case in data["cases"]:
        for expectation in case["expectations"]:
            location = f"{case['id']}/{expectation['variant']}"
            _validate_provenance(expectation, location)
            actual = make_patch_expectation(case, expectation["guide_policy"])
            if actual != expectation["result"]:
                raise AssertionError(f"Patch expectation drifted: {location}")
            tensor = tensor_from_sparse(actual)
            if tensor.shape != (1, 2, 32, 32) or tensor.dtype != np.float32:
                raise AssertionError(f"Invalid tensor contract: {location}")


def validate_model(*, run_model: bool) -> None:
    data = _load("model/cases.json")
    contract = data["contract"]
    if contract["sha256"] != sha256_file(MODEL_PATH):
        raise AssertionError("Model artifact hash differs from fixture contract")
    if contract["input"] != {
        "name": "input_mask",
        "shape": [1, 2, 32, 32],
        "type": "tensor(float)",
    }:
        raise AssertionError("Unexpected pinned model input contract")
    if contract["output"] != {
        "name": "nearest_region_mask",
        "shape": [1, 1, 32, 32],
        "type": "tensor(float)",
    }:
        raise AssertionError("Unexpected pinned model output contract")
    tolerance = data["comparison_tolerance"]
    if not tolerance.get("rationale") or tolerance["absolute"] <= 0 or tolerance["relative"] <= 0:
        raise AssertionError("Model tolerance must be positive and justified")
    for case in data["cases"]:
        _validate_provenance(case, case["id"])
        tensor = tensor_from_sparse(case)
        if tensor.shape != tuple(case["tensor"]["shape"]):
            raise AssertionError(f"{case['id']}: input shape mismatch")
        characterized = case["characterized_output"]
        expected = np.asarray(characterized["values_row_major"], dtype="<f4")
        if expected.size != 32 * 32 or tuple(characterized["shape"]) != (1, 1, 32, 32):
            raise AssertionError(f"{case['id']}: stored output shape/value count mismatch")
        if characterized["dtype"] != "float32" or not np.isfinite(expected).all():
            raise AssertionError(f"{case['id']}: stored output dtype/finite contract mismatch")
        if sha256(expected.tobytes(order="C")).hexdigest() != characterized["sha256_f32le"]:
            raise AssertionError(f"{case['id']}: stored output float32 checksum mismatch")
    if not run_model:
        return

    import onnxruntime as ort

    session = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
    model_input = session.get_inputs()[0]
    model_output = session.get_outputs()[0]
    if {
        "name": model_input.name,
        "shape": list(model_input.shape),
        "type": model_input.type,
    } != contract["input"]:
        raise AssertionError("Runtime model input metadata differs from the pinned contract")
    if {
        "name": model_output.name,
        "shape": list(model_output.shape),
        "type": model_output.type,
    } != contract["output"]:
        raise AssertionError("Runtime model output metadata differs from the pinned contract")
    absolute = float(data["comparison_tolerance"]["absolute"])
    relative = float(data["comparison_tolerance"]["relative"])
    for case in data["cases"]:
        tensor = tensor_from_sparse(case)
        actual = np.asarray(
            session.run(
                [session.get_outputs()[0].name],
                {session.get_inputs()[0].name: tensor},
            )[0],
            dtype=np.float32,
        )
        expected = np.asarray(
            case["characterized_output"]["values_row_major"], dtype=np.float32
        ).reshape(case["characterized_output"]["shape"])
        if not np.allclose(actual, expected, atol=absolute, rtol=relative):
            delta = float(np.max(np.abs(actual.astype(np.float64) - expected)))
            raise AssertionError(f"{case['id']}: model output delta {delta}")


def validate_postprocess() -> None:
    data = _load("postprocess/cases.json")
    for case in data["cases"]:
        rgba = decode_palette_rgba(case["coloring_rgba"])
        probabilities = np.asarray(case["probability_map"], dtype=np.float32)
        for name in case.get("segmentation_variants", []):
            actual_labels = segment_colored_components(
                rgba,
                np.zeros((case["height"], case["width"]), dtype=bool),
                tolerance=30,
                similarity=name,
            ).astype(int).tolist()
            if actual_labels != case["label_maps"][name]:
                raise AssertionError(f"{case['id']}: segmentation drifted for {name}")
        for expectation in case["expectations"]:
            location = f"{case['id']}/{expectation['variant']}"
            _validate_provenance(expectation, location)
            labels = np.asarray(
                case["label_maps"][expectation["label_map"]], dtype=np.int32
            )
            actual = score_regions(
                rgba,
                labels,
                probabilities,
                include_label_zero=expectation["include_label_zero"],
                tie_policy=expectation["tie_policy"],
            )
            if actual != expectation["result"]:
                raise AssertionError(f"Postprocess expectation drifted: {location}")


def validate_policy() -> None:
    data = _load("policy/cases.json")
    if data["schema"] != "gapfill-policy-cases-v1":
        raise AssertionError("Unexpected policy fixture schema")
    for case in data["modal_color"]:
        _validate_provenance(case, case["id"])
        if evaluate_modal_color(case["input"]) != case["expected"]:
            raise AssertionError(f"{case['id']}: modal-color policy contract drifted")
    for case in data["selection_scope"]:
        _validate_provenance(case, case["id"])
        if evaluate_selection_scope(case["input"]) != case["expected"]:
            raise AssertionError(f"{case['id']}: selection policy contract drifted")
    for case in data["fallback_application"]:
        _validate_provenance(case, case["id"])
        if evaluate_prediction_application(case["input"]) != case["expected"]:
            raise AssertionError(f"{case['id']}: fallback policy contract drifted")


def validate_characterization() -> None:
    data = _load("parity/characterization.json")
    if data["schema"] != "gapfill-characterization-v2":
        raise AssertionError("Unexpected characterization schema")
    expected_statuses = {
        "D002_threshold_triplet": "AGREES",
        "D003_edge_touching_small": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
        "D005_diagonal_connectivity": "AGREES",
        "D011_alpha_sweep": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
        "D013_selection_boundary": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
    }
    actual_statuses = {row["case_id"]: row["status"] for row in data["detection"]}
    for case_id, status in expected_statuses.items():
        if actual_statuses.get(case_id) != status:
            raise AssertionError(f"{case_id}: frozen characterization status drifted")
    postprocess_statuses = {
        row["case_id"]: row["status"] for row in data["postprocess"]
    }
    if postprocess_statuses.get("R006_modal_tie") != "CONFIRMED_IMPLEMENTATION_DIVERGENCE":
        raise AssertionError("D-06 Krita divergence is no longer visible")
    selection_statuses = {
        row["case_id"]: row["status"] for row in data["policy"]["selection_scope"]
    }
    if (
        selection_statuses.get("S001_full_geometry_then_selection")
        != "CONFIRMED_IMPLEMENTATION_DIVERGENCE"
    ):
        raise AssertionError("D-04 CSP core divergence is no longer visible")
    if data["policy"]["fallback_application"]["status"] != "CONFIRMED_IMPLEMENTATION_DIVERGENCE":
        raise AssertionError("D-07 fallback divergence is no longer visible")


def validate_end_to_end() -> None:
    from PIL import Image

    data = _load("end_to_end/annotations.json")
    for section in ("synthetic", "real"):
        for case in data[section]:
            evidence_ids = case.get("evidence_ids", [])
            for evidence_id in evidence_ids:
                if evidence_id not in PROVENANCE:
                    raise AssertionError(f"{case['id']}: unknown evidence {evidence_id}")
            for decision_id in case.get("decision_ids", []):
                if decision_id not in DECISIONS:
                    raise AssertionError(f"{case['id']}: unknown decision {decision_id}")
            dimensions = None
            for relative in case["files"].values():
                path = FIXTURE_ROOT / relative
                with Image.open(path) as image:
                    if image.mode != "RGBA":
                        raise AssertionError(f"{relative}: expected RGBA")
                    dimensions = dimensions or image.size
                    if image.size != dimensions:
                        raise AssertionError(f"{case['id']}: image dimensions differ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-model-run",
        action="store_true",
        help="Validate stored model fixture structure without loading ONNX Runtime",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    validate_manifest()
    validate_detection()
    validate_patch()
    validate_model(run_model=not args.skip_model_run)
    validate_postprocess()
    validate_policy()
    validate_characterization()
    validate_end_to_end()
    print("GapFill Phase 2 fixtures: validation passed")


if __name__ == "__main__":
    main()
