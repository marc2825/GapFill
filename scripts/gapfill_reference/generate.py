"""Generate the deterministic, cross-language GapFill Phase 2 fixture corpus."""

from __future__ import annotations

import argparse
import csv
import json
from hashlib import sha256
from pathlib import Path
from typing import Iterable

import numpy as np

from .cases import (
    detection_cases,
    model_cases,
    patch_cases,
    policy_cases,
    postprocess_cases,
    synthetic_end_to_end_cases,
)
from .reference import (
    DetectionPolicy,
    decode_palette_rgba,
    decode_rows_u8,
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

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "gapfill"
MODEL_PATH = REPOSITORY_ROOT / "web" / "public" / "models" / "unet32.onnx"
MODEL_INFO_PATH = REPOSITORY_ROOT / "web" / "public" / "models" / "model_info.json"
PHASE2_BASELINE = "30c7f02b698e8a9d61bc1a4e866fa5d8d7e8bfe5"


PROVENANCE = {
    "PAPER-4.1.1": {
        "kind": "paper",
        "citation": "docs/assets/GapFill_CHI.pdf, Section 4.1.1",
        "claim": "A gap is an enclosed transparent region below a threshold; boundaries may combine Coloring, Line Art, and Guides.",
    },
    "PAPER-4.2": {
        "kind": "paper",
        "citation": "docs/assets/GapFill_CHI.pdf, Sections 4.2.1-4.2.2",
        "claim": "Two binary channels feed a U-Net likelihood map; select the painted region with the highest average likelihood.",
    },
    "PAPER-APPENDIX-A": {
        "kind": "paper",
        "citation": "docs/assets/GapFill_CHI.pdf, Appendix A.2-A.3",
        "claim": "The analysis describes small regions as size <= 10 despite earlier 'under 10' prose.",
    },
    "PAPER-HUMAN-CONTROL": {
        "kind": "paper",
        "citation": "docs/assets/GapFill_CHI.pdf, Sections 3.2 and 4.1.4-4.1.5",
        "claim": "Suggestions remain user-controllable and are corrected or applied explicitly.",
    },
    "MAINTAINER-FREEZE-2026-08-13": {
        "kind": "human_maintainer_decision",
        "citation": "docs/addon-spec.md, Canonical decisions D-01 through D-07",
        "claim": "The maintainer reviewed and approved D-01 through D-07 as the frozen canonical contract on 2026-08-13.",
    },
    "ML-DETECT": {
        "kind": "ml_source",
        "citation": "ml/src/utils/flood_fill/core.py:10-29",
        "claim": "OpenCV threshold 128 followed by SciPy four-connected labeling.",
    },
    "ML-SIZE": {
        "kind": "ml_source",
        "citation": "ml/src/utils/flood_fill/nearest_same_color.py:70-98",
        "claim": "Small regions use size <= threshold; large regions use size > threshold.",
    },
    "ML-PATCH": {
        "kind": "ml_source",
        "citation": "ml/src/utils/patch_utils.py:37-101",
        "claim": "Floor/truncate centroid, centered 32x32 crop, zero padding, line-only channel 0, target region channel 1.",
    },
    "ML-TRAINING": {
        "kind": "ml_source",
        "citation": "ml/src/pipelines/preprocess_data_pipeline.py and ml/src/utils/patch_utils.py",
        "claim": "Training patches contain no Guide input.",
    },
    "ML-POSTPROCESS": {
        "kind": "ml_source",
        "citation": "ml/src/utils/color_utils.py:12-42",
        "claim": "All line-derived labels, including label 0, are scored; first encountered modal ties win.",
    },
    "MODEL-METADATA": {
        "kind": "export_metadata",
        "citation": "web/public/models/model_info.json",
        "claim": "Metadata labels channel 0 as Line Art and Guides despite line-only training code.",
    },
    "EXACT-ONNX-ARTIFACT": {
        "kind": "artifact",
        "citation": "web/public/models/unet32.onnx",
        "claim": "Exact checked-in artifact characterized by checksum and fixed input tensors.",
    },
    "WEB-DETECT": {
        "kind": "current_implementation",
        "citation": "web/src/utils/GapFill/gapRegionDetection.ts",
        "claim": "Exact-alpha transparent candidates, Guide as a separate candidate type, inclusive size, no image-edge rejection.",
    },
    "WEB-PATCH": {
        "kind": "current_implementation",
        "citation": "web/src/utils/GapFill/onnxInference.ts and onnxGapMask.ts",
        "claim": "Line/Guide alpha are ORed and target Guide pixels are removed for Guide-kind gaps.",
    },
    "WEB-POSTPROCESS": {
        "kind": "current_implementation",
        "citation": "web/src/utils/GapFill/onnxPostprocessing.ts",
        "claim": "Opaque colored components use seed-relative Manhattan RGB tolerance 30; first encountered modal ties win.",
    },
    "KRITA-DETECT": {
        "kind": "current_implementation",
        "citation": "krita-plugin/pykrita/gapfill_krita/engine/detection.py",
        "claim": "Guide is a separate candidate type; components are inclusive and image-edge rejecting.",
    },
    "KRITA-PATCH": {
        "kind": "current_implementation",
        "citation": "krita-plugin/pykrita/gapfill_krita/engine/patches.py",
        "claim": "Line/Guide alpha are ORed and target Guide pixels are removed for Guide-kind gaps.",
    },
    "KRITA-POSTPROCESS": {
        "kind": "current_implementation",
        "citation": "krita-plugin/pykrita/gapfill_krita/engine/postprocessing.py and colors.py",
        "claim": "Opaque colored components use seed-relative tolerance 30; sorted-lowest modal ties win.",
    },
    "CSP-CURRENT": {
        "kind": "current_implementation",
        "citation": "experimental/csp-plugin/src/core/gap_detection.cpp",
        "claim": "Only active-image alpha is analyzed; Guide and Line Art are unavailable.",
    },
    "CSP-ALPHA-OPTION": {
        "kind": "current_implementation",
        "citation": "experimental/csp-plugin/src/core/settings.hpp and gap_detection.cpp",
        "claim": "Alpha membership is configurable as alpha <= threshold.",
    },
    "CSP-OPTION": {
        "kind": "current_implementation",
        "citation": "experimental/csp-plugin/src/core/settings.hpp",
        "claim": "Eight-connectivity is an optional CSP-specific mode.",
    },
    "CSP-SELECTION": {
        "kind": "current_implementation",
        "citation": "experimental/csp-plugin/src/core/gap_detection.cpp",
        "claim": "A component touching the selection boundary is open and rejected.",
    },
    "CSP-OWNER": {
        "kind": "current_implementation",
        "citation": "experimental/csp-plugin/src/core/owner_regions.cpp",
        "claim": "Owner colors join by neighbor-relative tolerance and can chain transitively.",
    },
    "WEB-FALLBACK": {
        "kind": "current_implementation",
        "citation": "web/src/utils/GapFill/gapDetection.ts:125-173,248-266 and web/src/types/GapFill/index.ts",
        "claim": "Learned and greedy fallback colors share one untagged predictedColor field.",
    },
    "KRITA-FALLBACK": {
        "kind": "current_implementation",
        "citation": "krita-plugin/pykrita/gapfill_krita/engine/inference.py:113-143 and engine/types.py",
        "claim": "Per-gap greedy fallback writes the same predicted_rgb field without prediction provenance.",
    },
    "CSP-FALLBACK": {
        "kind": "current_implementation",
        "citation": "experimental/csp-plugin/src/core/quick_fix_pipeline.cpp and predictors/gap_color_predictor.cpp",
        "claim": "Rule-based output has no learned/fallback source field and High results default to Apply in Quick Fix.",
    },
    "CURRENT-IMPLEMENTATIONS": {
        "kind": "characterization",
        "citation": "web, Krita, and CSP detector source",
        "claim": "All current implementations use inclusive component thresholds.",
    },
    "CURRENT-DEFAULTS": {
        "kind": "characterization",
        "citation": "ML, web, Krita, and CSP default source",
        "claim": "Four-neighbor connectivity is the shared default.",
    },
    "AUDIT-STABLE-CORE": {
        "kind": "audit",
        "citation": "docs/addon-audit.md, Section 2",
        "claim": "Audit reconstruction of the consistently supported core.",
    },
    "AUDIT-G03": {
        "kind": "audit",
        "citation": "docs/addon-audit.md, G-03",
        "claim": "Image edge, threshold, and alpha policies remain unresolved.",
    },
    "AUDIT-K12": {
        "kind": "audit",
        "citation": "docs/addon-audit.md, K-12",
        "claim": "A lone Guide pixel is misclassified as a gap by typed-candidate behavior.",
    },
    "AUDIT-K11": {
        "kind": "audit",
        "citation": "docs/addon-audit.md, K-11",
        "claim": "Krita fallback predictions are not tagged separately from learned predictions.",
    },
    "AUDIT-K14": {
        "kind": "audit",
        "citation": "docs/addon-audit.md, K-14",
        "claim": "Krita modal ties use numeric sorting while ML/Web use first encounter.",
    },
    "AUDIT-C02": {
        "kind": "audit",
        "citation": "docs/addon-audit.md, C-02",
        "claim": "CSP learned inference is unavailable and ONNX requests fall back to the rule path.",
    },
    "AUDIT-C03": {
        "kind": "audit",
        "citation": "docs/addon-audit.md, C-03",
        "claim": "CSP's heuristic score can be High and auto-applied without learned provenance.",
    },
    "AUDIT-C10": {
        "kind": "audit",
        "citation": "docs/addon-audit.md, C-10",
        "claim": "CSP selection topology and output coverage need an explicit contract.",
    },
    "MANUAL-ARITHMETIC": {
        "kind": "manual_derivation",
        "citation": "tests/fixtures/gapfill/postprocess/cases.json, R001",
        "claim": "Region means are directly hand-checkable from eight listed probabilities.",
    },
    "MANUAL-COUNT": {
        "kind": "manual_derivation",
        "citation": "tests/fixtures/gapfill/postprocess/cases.json, R007",
        "claim": "The flat RGB occurs three times while each anti-aliased RGB occurs once.",
    },
    "MANUAL-TIE": {
        "kind": "manual_derivation",
        "citation": "tests/fixtures/gapfill/postprocess/cases.json, R006",
        "claim": "The two RGB values each occur twice; the red value is first in row-major scan order.",
    },
    "MANUAL-ANNOTATION": {
        "kind": "review_annotation",
        "citation": "tests/fixtures/gapfill/end_to_end/annotations.json",
        "claim": "Human-readable Phase 2 annotation; never generated from a tested implementation.",
    },
    "PRODUCT-POLICY": {
        "kind": "noncanonical_reference",
        "citation": "docs/addon-spec.md",
        "claim": "A rejected or extension variant retained for historical characterization, not canonical truth.",
    },
}


DECISIONS = {
    "DET-ENCLOSED": "STABLE",
    "D-01": "STABLE",
    "D-02": "STABLE",
    "D-03": "STABLE",
    "D-04": "STABLE",
    "D-05": "STABLE",
    "D-06": "STABLE",
    "D-07": "STABLE",
    "BOUNDARY-LINE-TRAINING": "STABLE",
    "PATCH-GEOMETRY": "STABLE",
    "MODEL-CHANNELS": "STABLE",
    "REGION-MEAN": "STABLE",
    "REGION-MODAL-COLOR": "STABLE",
    "GUIDE-DETECTION-COMPOSITION": "EMPIRICAL_DECISION_REQUIRED",
    "GUIDE-MODEL-COMPOSITION": "EMPIRICAL_DECISION_REQUIRED",
    "GUIDE-TARGET-SUPPRESSION": "EMPIRICAL_DECISION_REQUIRED",
    "BOUNDARY-RASTERIZATION": "EMPIRICAL_DECISION_REQUIRED",
    "REGION-CORRESPONDENCE": "EMPIRICAL_DECISION_REQUIRED",
    "REGION-LABEL-ZERO": "EMPIRICAL_DECISION_REQUIRED",
    "REGION-COLOR-TOLERANCE": "EMPIRICAL_DECISION_REQUIRED",
    "MODEL-SEMANTIC-OUTPUT": "EMPIRICAL_DECISION_REQUIRED",
}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _materialize_detection() -> dict:
    cases = detection_cases()
    for case in cases:
        for expectation in case["expectations"]:
            expectation["result"] = {
                "components": detect_components(
                    case, DetectionPolicy(**expectation["policy"])
                )
            }
    return {
        "schema": "gapfill-detection-cases-v1",
        "indexing": "row-major, pixel_index = y * width + x",
        "bbox": "[x, y, width, height]",
        "centroid": "[floor(mean(x)), floor(mean(y))] for nonnegative coordinates",
        "cases": cases,
    }


def _materialize_patch() -> dict:
    cases = patch_cases()
    for case in cases:
        for expectation in case["expectations"]:
            expectation["result"] = make_patch_expectation(
                case, expectation["guide_policy"]
            )
    return {
        "schema": "gapfill-patch-cases-v1",
        "tensor_layout": "NCHW",
        "sparse_binary_encoding": "indices identify 1.0 values in a 32x32 row-major channel; all unlisted values are 0.0",
        "cases": cases,
    }


def _float32_sha(values: np.ndarray) -> str:
    array = np.asarray(values, dtype="<f4")
    return sha256(array.tobytes(order="C")).hexdigest()


def _materialize_model() -> dict:
    import onnx
    import onnxruntime as ort

    model = onnx.load(MODEL_PATH)
    onnx.checker.check_model(model)
    session = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
    cases = model_cases()
    output_arrays: dict[str, np.ndarray] = {}
    for case in cases:
        tensor = tensor_from_sparse(case)
        result = session.run(
            [session.get_outputs()[0].name], {session.get_inputs()[0].name: tensor}
        )[0]
        output = np.asarray(result, dtype=np.float32)
        output_arrays[case["id"]] = output
        case["tensor"]["sha256_f32le"] = _float32_sha(tensor)
        case["characterized_output"] = {
            "role": "artifact_characterization_not_semantic_truth",
            "dtype": "float32",
            "shape": list(output.shape),
            "values_row_major": [float(value) for value in output.reshape(-1)],
            "sha256_f32le": _float32_sha(output),
            "statistics": {
                "minimum": float(output.min()),
                "maximum": float(output.max()),
                "mean": float(output.mean(dtype=np.float64)),
            },
            "provenance": {
                "artifact_sha256": sha256_file(MODEL_PATH),
                "runtime": f"onnxruntime {ort.__version__}",
                "provider": "CPUExecutionProvider",
            },
        }

    base = output_arrays["M001_no_guide"]
    guide = output_arrays["M002_one_guide_delta"]
    delta = np.abs(guide.astype(np.float64) - base.astype(np.float64))
    target_guide = output_arrays["M006_target_guide_present"]
    target_suppressed = output_arrays["M007_target_guide_suppressed"]
    target_delta = np.abs(
        target_suppressed.astype(np.float64) - target_guide.astype(np.float64)
    )
    model_info = json.loads(MODEL_INFO_PATH.read_text(encoding="utf-8"))
    graph_input = session.get_inputs()[0]
    graph_output = session.get_outputs()[0]
    opsets = [
        {"domain": entry.domain, "version": int(entry.version)}
        for entry in model.opset_import
    ]
    return {
        "schema": "gapfill-model-cases-v1",
        "contract": {
            "artifact": "web/public/models/unet32.onnx",
            "sha256": sha256_file(MODEL_PATH),
            "byte_size": MODEL_PATH.stat().st_size,
            "ir_version": int(model.ir_version),
            "producer_name": model.producer_name,
            "producer_version": model.producer_version,
            "opsets": opsets,
            "input": {
                "name": graph_input.name,
                "type": graph_input.type,
                "shape": graph_input.shape,
            },
            "output": {
                "name": graph_output.name,
                "type": graph_output.type,
                "shape": graph_output.shape,
            },
            "embedded_metadata": [
                {"key": item.key, "value": item.value}
                for item in model.metadata_props
            ],
            "sidecar": model_info,
        },
        "comparison_tolerance": {
            "absolute": 1e-6,
            "relative": 1e-5,
            "rationale": "Initial cross-runtime bound for float32 convolution; the Web WASM parity runner records observed maxima and must pass this bound.",
        },
        "controlled_guide_delta": {
            "base_case": "M001_no_guide",
            "guide_case": "M002_one_guide_delta",
            "changed_output_values": int(np.count_nonzero(delta)),
            "maximum_absolute_delta": float(delta.max()),
            "mean_absolute_delta": float(delta.mean()),
        },
        "controlled_target_guide_suppression": {
            "base_case": "M006_target_guide_present",
            "suppressed_case": "M007_target_guide_suppressed",
            "changed_output_values": int(np.count_nonzero(target_delta)),
            "maximum_absolute_delta": float(target_delta.max()),
            "mean_absolute_delta": float(target_delta.mean()),
        },
        "cases": cases,
    }


def _materialize_postprocess() -> dict:
    cases = postprocess_cases()
    for case in cases:
        rgba = decode_palette_rgba(case["coloring_rgba"])
        probabilities = np.asarray(case["probability_map"], dtype=np.float32)
        if case.get("segmentation_variants"):
            blocked = np.zeros((case["height"], case["width"]), dtype=bool)
            for name in case["segmentation_variants"]:
                labels = segment_colored_components(
                    rgba, blocked, tolerance=30, similarity=name
                )
                case.setdefault("label_maps", {})[name] = labels.astype(int).tolist()
                case["expectations"].append(
                    {
                        "variant": name,
                        "classification": "EMPIRICAL_DECISION_REQUIRED",
                        "canonical": False,
                        "decision_ids": case["decision_ids"],
                        "evidence_ids": case["evidence_ids"],
                        "label_map": name,
                        "include_label_zero": False,
                        "tie_policy": "first_encountered",
                    }
                )
        for expectation in case["expectations"]:
            labels = np.asarray(
                case["label_maps"][expectation["label_map"]], dtype=np.int32
            )
            expectation["result"] = score_regions(
                rgba,
                labels,
                probabilities,
                include_label_zero=expectation["include_label_zero"],
                tie_policy=expectation["tie_policy"],
            )
    return {
        "schema": "gapfill-postprocess-cases-v1",
        "probabilities": "float32 values listed in row-major rows",
        "cases": cases,
    }


def _materialize_policy() -> dict:
    data = policy_cases()
    for case in data["modal_color"]:
        actual = evaluate_modal_color(case["input"])
        if actual != case["expected"]:
            raise AssertionError(f"{case['id']}: hand-reviewed modal contract drifted")
    for case in data["selection_scope"]:
        actual = evaluate_selection_scope(case["input"])
        if actual != case["expected"]:
            raise AssertionError(f"{case['id']}: hand-reviewed selection contract drifted")
    for case in data["fallback_application"]:
        actual = evaluate_prediction_application(case["input"])
        if actual != case["expected"]:
            raise AssertionError(f"{case['id']}: hand-reviewed fallback contract drifted")
    return data


def _rgba_image(width: int, height: int, fill: tuple[int, int, int, int]) -> np.ndarray:
    image = np.empty((height, width, 4), dtype=np.uint8)
    image[:] = fill
    return image


def _write_png(path: Path, pixels: np.ndarray) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.asarray(pixels, dtype=np.uint8), mode="RGBA").save(
        path, format="PNG", compress_level=9
    )


def _synthetic_artworks() -> list[dict]:
    records = synthetic_end_to_end_cases()
    by_id = {record["id"]: record for record in records}

    width = height = 5
    coloring = _rgba_image(width, height, (210, 30, 40, 255))
    coloring[2, 2] = (0, 0, 0, 0)
    line = _rgba_image(width, height, (0, 0, 0, 0))
    line[1:4, 1] = (0, 0, 0, 255)
    line[1:4, 3] = (0, 0, 0, 255)
    line[1, 1:4] = (0, 0, 0, 255)
    line[3, 1:4] = (0, 0, 0, 255)
    guide = _rgba_image(width, height, (0, 0, 0, 0))
    _write_artwork("E001_synthetic_unambiguous", coloring, line, guide, by_id)

    width = height = 7
    coloring = _rgba_image(width, height, (0, 0, 0, 0))
    coloring[:, :2] = (30, 190, 70, 255)
    line = _rgba_image(width, height, (0, 0, 0, 0))
    guide = _rgba_image(width, height, (0, 0, 0, 0))
    guide[2:5, 2] = (40, 80, 240, 255)
    guide[2:5, 4] = (40, 80, 240, 255)
    guide[2, 2:5] = (40, 80, 240, 255)
    guide[4, 2:5] = (40, 80, 240, 255)
    _write_artwork("E002_synthetic_guide", coloring, line, guide, by_id)

    width = height = 5
    coloring = _rgba_image(width, height, (220, 30, 30, 255))
    coloring[:, 3:] = (30, 30, 220, 255)
    coloring[2, 2] = (0, 0, 0, 0)
    line = _rgba_image(width, height, (0, 0, 0, 0))
    guide = _rgba_image(width, height, (0, 0, 0, 0))
    _write_artwork("E003_synthetic_ambiguous_color", coloring, line, guide, by_id)
    return records


def _write_artwork(
    case_id: str,
    coloring: np.ndarray,
    line: np.ndarray,
    guide: np.ndarray,
    records: dict[str, dict],
) -> None:
    directory = FIXTURE_ROOT / "end_to_end" / "synthetic" / case_id
    _write_png(directory / "coloring.png", coloring)
    _write_png(directory / "line.png", line)
    _write_png(directory / "guide.png", guide)
    records[case_id]["dimensions"] = [int(coloring.shape[1]), int(coloring.shape[0])]
    records[case_id]["files"] = {
        "coloring": f"end_to_end/synthetic/{case_id}/coloring.png",
        "line": f"end_to_end/synthetic/{case_id}/line.png",
        "guide": f"end_to_end/synthetic/{case_id}/guide.png",
    }


def _typed_preset_candidates(directory: Path, threshold: int = 10) -> list[dict]:
    from PIL import Image

    coloring = np.asarray(Image.open(directory / "coloring.png").convert("RGBA"))
    line = np.asarray(Image.open(directory / "line.png").convert("RGBA"))
    guide = np.asarray(Image.open(directory / "guide.png").convert("RGBA"))
    height, width = coloring.shape[:2]
    kinds = np.zeros((height, width), dtype=np.uint8)
    clear = (coloring[..., 3] == 0) & (line[..., 3] == 0)
    kinds[clear & (guide[..., 3] == 0)] = 1
    kinds[clear & (guide[..., 3] > 0)] = 2
    visited = np.zeros((height, width), dtype=bool)
    results: list[dict] = []
    for seed_y in range(height):
        for seed_x in range(width):
            kind = int(kinds[seed_y, seed_x])
            if kind == 0 or visited[seed_y, seed_x]:
                continue
            stack = [(seed_x, seed_y)]
            visited[seed_y, seed_x] = True
            pixels: list[tuple[int, int]] = []
            while stack:
                x, y = stack.pop()
                pixels.append((x, y))
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    if visited[ny, nx] or int(kinds[ny, nx]) != kind:
                        continue
                    visited[ny, nx] = True
                    stack.append((nx, ny))
            if len(pixels) > threshold:
                continue
            xs = [point[0] for point in pixels]
            ys = [point[1] for point in pixels]
            results.append(
                {
                    "kind": "guide" if kind == 2 else "transparent",
                    "pixel_count": len(pixels),
                    "centroid": [sum(xs) // len(xs), sum(ys) // len(ys)],
                    "bbox": [min(xs), min(ys), max(xs) + 1, max(ys) + 1],
                }
            )
    return results


def _real_art_annotations() -> list[dict]:
    source_directory = (
        REPOSITORY_ROOT / "web" / "public" / "preset-images" / "Ex2"
    )
    records = []
    definitions = [
        {
            "id": "E101_ex2_ordinary_crop",
            "title": "Ex2 ordinary hair-tip gap crop",
            "crop_box_xyxy": [426, 84, 458, 116],
            "annotation": "The coloring crop has a one-column unpainted vertical pixel run at the hair-tip boundary; the checked-in completed coloring fills it yellow. This crop is included for human review, not as an automatically inferred canonical mask or model color.",
            "classification": "UNRESOLVED_SPECIFICATION",
            "decision_ids": ["D-01", "REGION-CORRESPONDENCE"],
        },
        {
            "id": "E102_ex2_guide_crop",
            "title": "Ex2 Guide-associated accessory gap crop",
            "crop_box_xyxy": [521, 384, 553, 416],
            "annotation": "The crop contains a visible Guide stroke adjacent to a single unpainted Coloring pixel; the completed coloring fills the pixel yellow. Whether that Guide belongs in model channel 0 and whether target Guide pixels are suppressed remain empirical decisions.",
            "classification": "UNRESOLVED_SPECIFICATION",
            "decision_ids": [
                "GUIDE-DETECTION-COMPOSITION",
                "GUIDE-MODEL-COMPOSITION",
                "GUIDE-TARGET-SUPPRESSION",
            ],
        },
    ]
    from PIL import Image

    for definition in definitions:
        directory = FIXTURE_ROOT / "end_to_end" / "real" / definition["id"]
        files = {}
        source_hashes = {}
        for role in ("coloring", "coloring_full", "line", "guide"):
            source = source_directory / f"{role}.png"
            output = directory / f"{role}.png"
            output.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(source) as image:
                image.crop(tuple(definition["crop_box_xyxy"])).save(
                    output, format="PNG", compress_level=9
                )
            files[role] = str(output.relative_to(FIXTURE_ROOT))
            source_hashes[role] = sha256_file(source)
        records.append(
            {
                **definition,
                "provenance": {
                    "repository_path": "web/public/preset-images/Ex2",
                    "source_file_sha256": source_hashes,
                    "crop_method": "Pillow RGBA crop using the listed [left, top, right, bottom] box; no resizing or color conversion",
                    "review": "manual visual inspection of coloring, completed coloring, Line Art, and Guide crop at nearest-neighbor magnification",
                },
                "files": files,
                "evidence_ids": ["MANUAL-ANNOTATION"],
                "canonical_expected_output": None,
            }
        )
    return records


def list_real_candidates() -> None:
    directory = REPOSITORY_ROOT / "web" / "public" / "preset-images" / "Ex2"
    print(json.dumps(_typed_preset_candidates(directory), indent=2))


def _write_csp_projection(detection: dict) -> Path:
    path = FIXTURE_ROOT / "parity" / "csp_detection_current.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "role",
                "case_id",
                "scope",
                "width",
                "height",
                "threshold",
                "alpha_hex_row_major",
                "selection_hex_row_major",
                "expected_component_pixel_indices",
            ]
        )
        for case in detection["cases"]:
            rgba = decode_palette_rgba(case["rasters"]["coloring_rgba"])
            alpha_hex = "".join(f"{int(value):02x}" for value in rgba[..., 3].reshape(-1))
            selection = decode_rows_u8(case["rasters"]["selection"])
            selection_hex = "".join(
                f"{int(value):02x}" for value in selection.reshape(-1)
            )
            for scope in ("whole", "selected"):
                policy = DetectionPolicy(
                    line_policy="none",
                    guide_policy="ignored",
                    edge_policy="reject",
                    threshold_policy="inclusive",
                    alpha_policy="exact_zero",
                    selection_policy=scope,
                    selection_boundary_policy="reject",
                )
                components = detect_components(case, policy)
                encoded_components = "|".join(
                    ";".join(str(index) for index in component["pixel_indices"])
                    for component in components
                )
                writer.writerow(
                    [
                        "current_behavior_not_golden",
                        case["id"],
                        scope,
                        case["width"],
                        case["height"],
                        case["threshold"],
                        alpha_hex,
                        selection_hex,
                        encoded_components,
                    ]
                )
    return path


def _detection_observation(case: dict, policy: DetectionPolicy) -> list[dict]:
    return detect_components(case, policy)


def _materialize_characterization(
    detection: dict, patch: dict, model: dict, postprocess: dict, policy: dict
) -> dict:
    detection_status = {
        "D001_one_pixel_enclosed": "AGREES",
        "D002_threshold_triplet": "AGREES",
        "D003_edge_touching_small": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
        "D004_exterior_and_interior": "AGREES",
        "D005_diagonal_connectivity": "AGREES",
        "D006_line_art_enclosure": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
        "D007_guide_enclosure": "UNRESOLVED_SPECIFICATION",
        "D008_isolated_guide_pixel_open": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
        "D009_guide_stroke_to_exterior": "UNRESOLVED_SPECIFICATION",
        "D010_mixed_line_guide_enclosure": "UNRESOLVED_SPECIFICATION",
        "D011_alpha_sweep": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
        "D012_faint_line_000": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
        "D012_faint_line_127": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
        "D012_faint_line_128": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
        "D012_faint_line_129": "UNRESOLVED_SPECIFICATION",
        "D012_faint_line_254": "UNRESOLVED_SPECIFICATION",
        "D012_faint_line_255": "AGREES",
        "D013_selection_boundary": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
        "D014_selection_contains_gap": "DELIBERATE_PLATFORM_DIFFERENCE",
    }
    decision_metadata = {
        "D002_threshold_triplet": {
            "decision_ids": ["D-01"],
            "audit_risk_ids": ["G-03"],
            "implementation_assessments": {
                "ml_python_current": "agrees",
                "web_current": "agrees",
                "krita_current": "agrees",
                "csp_current": "agrees",
            },
        },
        "D003_edge_touching_small": {
            "decision_ids": ["D-02"],
            "audit_risk_ids": ["G-03"],
            "implementation_assessments": {
                "ml_python_current": "confirmed_bug_or_divergence",
                "web_current": "confirmed_bug_or_divergence",
                "krita_current": "agrees",
                "csp_current": "agrees",
            },
        },
        "D005_diagonal_connectivity": {
            "decision_ids": ["D-05"],
            "audit_risk_ids": [],
            "implementation_assessments": {
                "ml_python_current": "agrees",
                "web_current": "agrees",
                "krita_current": "agrees",
                "csp_default": "agrees",
                "csp_optional_eight": "intentional_noncanonical_extension",
            },
        },
        "D011_alpha_sweep": {
            "decision_ids": ["D-03"],
            "audit_risk_ids": ["G-03"],
            "implementation_assessments": {
                "ml_python_current": "not_implemented_at_this_stage_and_observed_result_diverges",
                "web_current": "agrees",
                "krita_current": "agrees",
                "csp_default": "agrees",
                "csp_configurable_partial_alpha": "intentional_noncanonical_extension_if_retained",
            },
        },
        "D013_selection_boundary": {
            "decision_ids": ["D-04"],
            "audit_risk_ids": ["G-03", "C-10"],
            "implementation_assessments": {
                "ml_python_current": "selection_scope_not_implemented",
                "web_current": "selection_scope_not_implemented",
                "krita_current": "selection_scope_not_implemented",
                "csp_core_current": "confirmed_bug_or_divergence_when_full_image_is_available",
                "csp_host_acquisition": "host_limitation_unverified",
            },
        },
        "D014_selection_contains_gap": {
            "decision_ids": ["D-04"],
            "audit_risk_ids": ["G-03", "C-10"],
            "implementation_assessments": {
                "ml_python_current": "selection_scope_not_implemented",
                "web_current": "selection_scope_not_implemented",
                "krita_current": "selection_scope_not_implemented",
                "csp_core_current": "agrees_for_fully_contained_component",
            },
        },
    }
    detection_rows = []
    for case in detection["cases"]:
        paper_variants = {
            expectation["variant"]: expectation["result"]["components"]
            for expectation in case["expectations"]
        }
        ml_case = json.loads(json.dumps(case))
        ml_case["rasters"]["coloring_rgba"] = {
            "encoding": "palette_rgba8",
            "palette": {".": [0, 0, 0, 0]},
            "rows": ["." * case["width"] for _ in range(case["height"])],
        }
        observations = {
            "paper_or_spec_variants": paper_variants,
            "ml_python_current": _detection_observation(
                ml_case,
                DetectionPolicy(
                    threshold_policy="inclusive",
                    edge_policy="allow",
                    connectivity=4,
                    alpha_policy="exact_zero",
                    line_policy="training_gray_128",
                    guide_policy="ignored",
                ),
            ),
            "web_current": _detection_observation(
                case,
                DetectionPolicy(
                    threshold_policy="inclusive",
                    edge_policy="allow",
                    connectivity=4,
                    alpha_policy="exact_zero",
                    line_policy="any_alpha",
                    guide_policy="typed_candidate",
                ),
            ),
            "krita_current": _detection_observation(
                case,
                DetectionPolicy(
                    threshold_policy="inclusive",
                    edge_policy="reject",
                    connectivity=4,
                    alpha_policy="exact_zero",
                    line_policy="any_alpha",
                    guide_policy="typed_candidate",
                ),
            ),
            "csp_current_whole": _detection_observation(
                case,
                DetectionPolicy(
                    threshold_policy="inclusive",
                    edge_policy="reject",
                    connectivity=4,
                    alpha_policy="at_most",
                    alpha_threshold=0,
                    line_policy="none",
                    guide_policy="ignored",
                ),
            ),
            "csp_current_selection": _detection_observation(
                case,
                DetectionPolicy(
                    threshold_policy="inclusive",
                    edge_policy="reject",
                    connectivity=4,
                    alpha_policy="at_most",
                    alpha_threshold=0,
                    line_policy="none",
                    guide_policy="ignored",
                    selection_policy="selected",
                    selection_boundary_policy="reject",
                ),
            ),
        }
        detection_rows.append(
            {
                "case_id": case["id"],
                "status": detection_status[case["id"]],
                "canonical_expectations": {
                    expectation["variant"]: expectation["result"]["components"]
                    for expectation in case["expectations"]
                    if expectation.get("canonical")
                },
                "observations": observations,
                **decision_metadata.get(case["id"], {}),
            }
        )

    patch_rows = []
    for case in patch["cases"]:
        variants = {
            item["variant"]: item["result"] for item in case["expectations"]
        }
        guide_case = case["id"] in ("P005_guide_delta", "P006_target_guide_suppression")
        patch_rows.append(
            {
                "case_id": case["id"],
                "status": "UNRESOLVED_SPECIFICATION" if guide_case else "AGREES",
                "observations": {
                    "ml_python_current_variant": "training_line_only",
                    "web_current_variant": (
                        "suppress_target_guide"
                        if case["id"] == "P006_target_guide_suppression"
                        else "line_plus_guide"
                        if case["id"] == "P005_guide_delta"
                        else "training_line_only"
                    ),
                    "krita_current_variant": (
                        "suppress_target_guide"
                        if case["id"] == "P006_target_guide_suppression"
                        else "line_plus_guide"
                        if case["id"] == "P005_guide_delta"
                        else "training_line_only"
                    ),
                    "csp_current": "STAGE_UNAVAILABLE",
                    "variants": variants,
                },
            }
        )

    postprocess_status = {
        "R001_manual_mean_winner": "AGREES",
        "R002_label_zero": "UNRESOLVED_SPECIFICATION",
        "R003_disconnected_same_rgb": "UNRESOLVED_SPECIFICATION",
        "R004_tolerance_30_boundary": "UNRESOLVED_SPECIFICATION",
        "R005_transitive_color_chain": "UNRESOLVED_SPECIFICATION",
        "R006_modal_tie": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
        "R007_antialiased_colors": "AGREES",
        "R008_line_vs_colored_regions": "UNRESOLVED_SPECIFICATION",
    }
    postprocess_rows = []
    for case in postprocess["cases"]:
        rgba = decode_palette_rgba(case["coloring_rgba"])
        probabilities = np.asarray(case["probability_map"], dtype=np.float32)
        label_maps = case["label_maps"]
        first_label_map = next(iter(label_maps))
        ml_label_map = "line_labels" if "line_labels" in label_maps else first_label_map
        colored_label_map = (
            "colored_components"
            if "colored_components" in label_maps
            else "seed_relative"
            if "seed_relative" in label_maps
            else first_label_map
        )
        ml_result = score_regions(
            rgba,
            np.asarray(label_maps[ml_label_map], dtype=np.int32),
            probabilities,
            include_label_zero=True,
            tie_policy="first_encountered",
        )
        web_result = score_regions(
            rgba,
            np.asarray(label_maps[colored_label_map], dtype=np.int32),
            probabilities,
            include_label_zero=False,
            tie_policy="first_encountered",
        )
        krita_result = score_regions(
            rgba,
            np.asarray(label_maps[colored_label_map], dtype=np.int32),
            probabilities,
            include_label_zero=False,
            tie_policy="lowest_rgb",
        )
        csp_observation: object = "LEARNED_STAGE_UNAVAILABLE"
        if "neighbor_transitive" in label_maps:
            csp_observation = {
                "owner_style_labels": label_maps["neighbor_transitive"],
                "note": "CSP does not score the fixed ONNX map; only its transitive owner segmentation is comparable here.",
            }
        postprocess_rows.append(
            {
                "case_id": case["id"],
                "status": postprocess_status[case["id"]],
                "canonical_expectations": {
                    expectation["variant"]: expectation["result"]
                    for expectation in case["expectations"]
                    if expectation.get("canonical")
                },
                **(
                    {
                        "decision_ids": ["D-06"],
                        "audit_risk_ids": ["K-14"],
                        "implementation_assessments": {
                            "ml_python_current": "agrees",
                            "web_current": "agrees",
                            "krita_current": "confirmed_bug_or_divergence",
                            "csp_current": "not_yet_implemented",
                        },
                    }
                    if case["id"] == "R006_modal_tie"
                    else {}
                ),
                "observations": {
                    "ml_python_current": ml_result,
                    "web_current": web_result,
                    "krita_current": krita_result,
                    "csp_current": csp_observation,
                },
            }
        )

    model_rows = [
        {
            "case_id": case["id"],
            "status": "UNRESOLVED_SPECIFICATION",
            "python_onnxruntime_sha256_f32le": case["characterized_output"][
                "sha256_f32le"
            ],
            "web_onnxruntime_wasm": "RUN_BY_WEB_PARITY_TEST",
            "krita_current": "The wrapper uses the same artifact/runtime; Phase 2 checks its tensor construction and postprocessing separately.",
            "csp_current": "STAGE_UNAVAILABLE",
        }
        for case in model["cases"]
    ]
    policy_rows = {
        "selection_scope": [
            {
                "case_id": case["id"],
                "decision_ids": ["D-04"],
                "audit_risk_ids": ["G-03", "C-10"],
                "canonical_result": case["expected"],
                "status": (
                    "CONFIRMED_IMPLEMENTATION_DIVERGENCE"
                    if case["id"] == "S001_full_geometry_then_selection"
                    else "AGREES"
                ),
                "current_implementation_notes": {
                    "ml_python": "selection scope not implemented",
                    "web": "selection scope not implemented",
                    "krita": "selection scope not implemented in the pure detector",
                    "csp_core": (
                        "clips before geometry and rejects; divergence because the core has the full Image"
                        if case["id"] == "S001_full_geometry_then_selection"
                        else "matches the conservative result for the controlled condition"
                    ),
                    "real_csp_host": "host acquisition limitation unverified",
                },
            }
            for case in policy["selection_scope"]
        ],
        "fallback_application": {
            "decision_ids": ["D-07"],
            "audit_risk_ids": ["K-11", "C-02", "C-03"],
            "canonical_cases": {
                case["id"]: case["expected"]
                for case in policy["fallback_application"]
            },
            "status": "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
            "current_implementation_notes": {
                "ml_python": "no product fallback/auto-apply policy at this stage",
                "web": "greedy fallback and learned results share untagged predictedColor and ordinary application behavior",
                "krita": "greedy fallback and learned results share untagged predicted_rgb and ordinary Apply All behavior",
                "csp": "rule output lacks source provenance and High heuristic results default to Apply in Quick Fix",
            },
        },
    }
    return {
        "schema": "gapfill-characterization-v2",
        "warning": "Current implementation observations are evidence only. They are not promoted to canonical truth by this file.",
        "detection": detection_rows,
        "patch": patch_rows,
        "model": model_rows,
        "postprocess": postprocess_rows,
        "policy": policy_rows,
    }


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            yield path


def generate() -> None:
    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    detection = _materialize_detection()
    patch = _materialize_patch()
    model = _materialize_model()
    postprocess = _materialize_postprocess()
    policy = _materialize_policy()
    _write_json(FIXTURE_ROOT / "detection" / "cases.json", detection)
    _write_json(FIXTURE_ROOT / "patch" / "cases.json", patch)
    _write_json(FIXTURE_ROOT / "model" / "cases.json", model)
    _write_json(FIXTURE_ROOT / "postprocess" / "cases.json", postprocess)
    _write_json(FIXTURE_ROOT / "policy" / "cases.json", policy)
    annotations = {
        "schema": "gapfill-end-to-end-annotations-v1",
        "warning": "Real-art annotations are human-reviewable observations, not outputs inferred from web, Krita, ML, or CSP.",
        "synthetic": _synthetic_artworks(),
        "real": _real_art_annotations(),
    }
    _write_json(FIXTURE_ROOT / "end_to_end" / "annotations.json", annotations)
    _write_json(
        FIXTURE_ROOT / "parity" / "characterization.json",
        _materialize_characterization(detection, patch, model, postprocess, policy),
    )
    _write_csp_projection(detection)

    manifest = {
        "schema": "gapfill-fixture-manifest-v2",
        "phase": 2,
        "date": "2026-08-13",
        "baseline_commit": PHASE2_BASELINE,
        "evidence_hierarchy": [
            "checked-in paper",
            "ML source and exact ONNX artifact",
            "web executable reference",
            "host API evidence",
            "add-on behavior and tests",
        ],
        "classification_values": [
            "STABLE",
            "EMPIRICAL_DECISION_REQUIRED",
            "NONCANONICAL_REFERENCE",
        ],
        "characterization_status_values": [
            "AGREES",
            "DELIBERATE_PLATFORM_DIFFERENCE",
            "UNRESOLVED_SPECIFICATION",
            "CONFIRMED_IMPLEMENTATION_DIVERGENCE",
        ],
        "decisions": DECISIONS,
        "provenance": PROVENANCE,
        "model_contract": model["contract"],
        "files": [
            {
                "path": str(path.relative_to(FIXTURE_ROOT)),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in _iter_files(FIXTURE_ROOT)
        ],
        "reproduction": {
            "generate": "/tmp/gapfill-phase2-venv/bin/python -m scripts.gapfill_reference.generate --write",
            "validate": "/tmp/gapfill-phase2-venv/bin/python -m scripts.gapfill_reference.validate",
            "dependencies": [
                "numpy==2.5.2",
                "onnx==1.22.0",
                "onnxruntime==1.28.0",
                "pillow==12.3.0",
            ],
        },
    }
    _write_json(FIXTURE_ROOT / "manifest.json", manifest)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write the corpus")
    parser.add_argument(
        "--list-real-candidates",
        action="store_true",
        help="Print current typed-candidate observations for Ex2 without assigning truth",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.list_real_candidates:
        list_real_candidates()
        return
    if not args.write:
        raise SystemExit("Pass --write to generate fixtures.")
    generate()


if __name__ == "__main__":
    main()
