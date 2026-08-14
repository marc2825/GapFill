from __future__ import annotations

import json
import unittest

import numpy as np

from .generate import FIXTURE_ROOT, REPOSITORY_ROOT
from .reference import (
    DetectionPolicy,
    build_canonical_model_tensor,
    canonical_boundary_from_rgba,
    canonical_line_labels,
    decode_palette_rgba,
    detect_components,
    evaluate_modal_color,
    evaluate_prediction_application,
    evaluate_selection_scope,
    score_canonical_regions,
    score_regions,
)
from .validate import (
    validate_characterization,
    validate_detection,
    validate_end_to_end,
    validate_manifest,
    validate_model,
    validate_patch,
    validate_policy,
    validate_postprocess,
)


def _load(relative: str) -> dict:
    return json.loads((FIXTURE_ROOT / relative).read_text(encoding="utf-8"))


class ReferenceFixtureTests(unittest.TestCase):
    def test_corpus_integrity_and_provenance(self) -> None:
        validate_manifest()
        validate_detection()
        validate_patch()
        validate_model(run_model=False)
        validate_postprocess()
        validate_policy()
        validate_characterization()
        validate_end_to_end()

    def test_threshold_variants_remain_distinct(self) -> None:
        case = next(
            item
            for item in _load("detection/cases.json")["cases"]
            if item["id"] == "D002_threshold_triplet"
        )
        strict = detect_components(case, DetectionPolicy(threshold_policy="strict"))
        inclusive = detect_components(case, DetectionPolicy(threshold_policy="inclusive"))
        self.assertEqual([component["pixel_count"] for component in strict], [2])
        self.assertEqual(
            [component["pixel_count"] for component in inclusive], [2, 3]
        )

    def test_frozen_detection_decisions_are_canonical(self) -> None:
        cases = {
            item["id"]: item for item in _load("detection/cases.json")["cases"]
        }

        threshold = next(
            expectation
            for expectation in cases["D002_threshold_triplet"]["expectations"]
            if expectation["canonical"]
        )
        self.assertEqual(
            [item["pixel_count"] for item in threshold["result"]["components"]],
            [2, 3],
        )

        edge = next(
            expectation
            for expectation in cases["D003_edge_touching_small"]["expectations"]
            if expectation["canonical"]
        )
        self.assertEqual(edge["result"]["components"], [])

        alpha = next(
            expectation
            for expectation in cases["D011_alpha_sweep"]["expectations"]
            if expectation["canonical"]
        )
        self.assertEqual(
            [item["pixel_indices"] for item in alpha["result"]["components"]],
            [[12]],
        )

        diagonal = next(
            expectation
            for expectation in cases["D005_diagonal_connectivity"]["expectations"]
            if expectation["canonical"]
        )
        self.assertEqual(
            [item["pixel_indices"] for item in diagonal["result"]["components"]],
            [[12], [18]],
        )

    def test_guide_variants_expose_lone_pixel_disagreement(self) -> None:
        case = next(
            item
            for item in _load("detection/cases.json")["cases"]
            if item["id"] == "D008_isolated_guide_pixel_open"
        )
        boundary = detect_components(case, DetectionPolicy(guide_policy="boundary"))
        typed = detect_components(
            case, DetectionPolicy(guide_policy="typed_candidate")
        )
        self.assertEqual(boundary, [])
        self.assertEqual(typed[0]["kind"], "guide")
        self.assertEqual(typed[0]["pixel_indices"], [12])

    def test_manually_derivable_region_mean_winner(self) -> None:
        case = next(
            item
            for item in _load("postprocess/cases.json")["cases"]
            if item["id"] == "R001_manual_mean_winner"
        )
        result = score_regions(
            decode_palette_rgba(case["coloring_rgba"]),
            np.asarray(case["label_maps"]["reviewed_semantic"], dtype=np.int32),
            np.asarray(case["probability_map"], dtype=np.float32),
            include_label_zero=False,
        )
        self.assertAlmostEqual(result["region_means"]["1"], 0.2, places=6)
        self.assertAlmostEqual(result["region_means"]["2"], 0.7, places=6)
        self.assertEqual(result["selected_region_id"], 2)
        self.assertEqual(result["rgb"], [20, 20, 220])

    def test_modal_tie_uses_first_row_major_color(self) -> None:
        case = next(
            item
            for item in _load("postprocess/cases.json")["cases"]
            if item["id"] == "R006_modal_tie"
        )
        canonical = next(
            expectation
            for expectation in case["expectations"]
            if expectation["canonical"]
        )
        self.assertEqual(canonical["variant"], "first_encountered_tie")
        self.assertEqual(canonical["result"]["rgb"], [240, 20, 20])

    def test_modal_participation_excludes_transparent_and_explicit_pixels(self) -> None:
        case = _load("policy/cases.json")["modal_color"][0]
        self.assertEqual(evaluate_modal_color(case["input"]), case["expected"])
        self.assertEqual(case["expected"]["participating_pixel_indices"], [1, 2, 4])

    def test_selection_is_scope_not_synthetic_geometry(self) -> None:
        cases = _load("policy/cases.json")["selection_scope"]
        full = next(
            item
            for item in cases
            if item["id"] == "S001_full_geometry_then_selection"
        )
        clipped = next(
            item
            for item in cases
            if item["id"] == "S002_clipped_domain_boundary_indeterminate"
        )
        self.assertEqual(evaluate_selection_scope(full["input"]), full["expected"])
        self.assertEqual(
            evaluate_selection_scope(clipped["input"]), clipped["expected"]
        )
        self.assertFalse(full["expected"]["selection_created_enclosure"])
        self.assertEqual(clipped["expected"]["geometry_status"], "indeterminate")

    def test_fallback_never_enters_apply_high(self) -> None:
        cases = _load("policy/cases.json")["fallback_application"]
        for case in cases:
            actual = evaluate_prediction_application(case["input"])
            self.assertEqual(actual, case["expected"])
            if actual["prediction_provenance"] == "fallback":
                self.assertIsNone(actual["effective_confidence_band"])
                self.assertFalse(actual["apply_high_eligible"])
                self.assertTrue(actual["requires_explicit_confirmation"])

    def test_phase5_boundary_conversion_is_training_faithful(self) -> None:
        # Transparent byte-RGBA is composited over white before the same
        # inclusive grayscale-128 split used by ML training.
        rgba = np.asarray(
            [[
                [0, 0, 0, 0],       # fully absent
                [0, 0, 0, 1],       # very faint black
                [127, 127, 127, 255],
                [128, 128, 128, 255],
                [129, 129, 129, 255],
                [0, 0, 0, 255],     # fully opaque black
                [0, 0, 0, 126],
                [0, 0, 0, 127],
            ]],
            dtype=np.uint8,
        )
        self.assertEqual(
            canonical_boundary_from_rgba(rgba).tolist(),
            [[False, False, True, True, False, True, False, True]],
        )

    def test_phase5_model_tensor_is_line_only_and_exact(self) -> None:
        line = np.zeros((7, 7, 4), dtype=np.uint8)
        line[3, 2] = (0, 0, 0, 255)
        tensor, bounds = build_canonical_model_tensor(line, [3 * 7 + 3], (3, 3))

        self.assertEqual(tensor.shape, (1, 2, 32, 32))
        self.assertEqual(tensor.dtype, np.float32)
        self.assertEqual((bounds["virtual_x"], bounds["virtual_y"]), (-13, -13))
        self.assertEqual(np.flatnonzero(tensor[0, 0]).tolist(), [16 * 32 + 15])
        self.assertEqual(np.flatnonzero(tensor[0, 1]).tolist(), [16 * 32 + 16])

    def test_phase5_model_sidecar_describes_the_frozen_artifact(self) -> None:
        metadata = json.loads(
            (
                REPOSITORY_ROOT / "web" / "public" / "models" / "model_info.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            metadata["sha256"],
            "8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78",
        )
        self.assertEqual(metadata["opset_version"], 18)
        self.assertEqual(metadata["input_name"], "input_mask")
        self.assertEqual(metadata["input_shape"], [1, 2, 32, 32])
        self.assertEqual(metadata["output_name"], "nearest_region_mask")
        self.assertEqual(metadata["output_shape"], [1, 1, 32, 32])
        self.assertIn("Line Art mask only", metadata["channels"]["0"])
        self.assertIn("Guides are excluded", metadata["channels"]["0"])

    def test_phase5_line_regions_exclude_label_zero_and_color_fragments(self) -> None:
        case = next(
            item
            for item in _load("postprocess/cases.json")["cases"]
            if item["id"] == "R008_line_vs_colored_regions"
        )
        image = decode_palette_rgba(case["coloring_rgba"])
        labels = np.asarray(case["label_maps"]["line_labels"], dtype=np.int32)
        result = score_canonical_regions(
            image,
            labels,
            np.asarray(case["probability_map"], dtype=np.float32),
        )
        self.assertEqual(result["selected_region_id"], 1)
        self.assertEqual(result["selected_pixel_indices"], list(range(10)))
        self.assertEqual(result["rgb"], [200, 20, 20])

        label_zero = next(
            item
            for item in _load("postprocess/cases.json")["cases"]
            if item["id"] == "R002_label_zero"
        )
        result = score_canonical_regions(
            decode_palette_rgba(label_zero["coloring_rgba"]),
            np.asarray(label_zero["label_maps"]["line_labels"], dtype=np.int32),
            np.asarray(label_zero["probability_map"], dtype=np.float32),
        )
        self.assertEqual(result["selected_region_id"], 1)
        self.assertEqual(result["rgb"], [40, 180, 40])

    def test_phase5_scoring_and_modal_ties_are_fully_deterministic(self) -> None:
        coloring = np.asarray(
            [[[250, 0, 0, 0], [240, 20, 20, 255], [20, 20, 240, 255]]],
            dtype=np.uint8,
        )
        labels = np.asarray([[9, 9, 3]], dtype=np.int32)
        probabilities = np.asarray([[1.0, 0.0, 0.5]], dtype=np.float32)
        result = score_canonical_regions(coloring, labels, probabilities)
        # Alpha-zero index 0 participates in the semantic-region mean, matching
        # the model's region-mask objective, but cannot vote for the RGB mode.
        self.assertEqual(result["region_means"], {"9": 0.5, "3": 0.5})
        self.assertEqual(result["selected_region_id"], 9)
        self.assertEqual(result["rgb"], [240, 20, 20])

        with self.assertRaises(ValueError):
            score_canonical_regions(
                coloring,
                labels,
                np.asarray([[0.0, np.nan, 0.5]], dtype=np.float32),
            )

    def test_phase5_full_image_labels_are_row_major_and_four_connected(self) -> None:
        line = np.zeros((3, 3, 4), dtype=np.uint8)
        line[:, 1] = (0, 0, 0, 255)
        self.assertEqual(
            canonical_line_labels(line).tolist(),
            [[1, 0, 2], [1, 0, 2], [1, 0, 2]],
        )


if __name__ == "__main__":
    unittest.main()
