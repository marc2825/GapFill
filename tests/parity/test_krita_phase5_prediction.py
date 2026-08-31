from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from gapfill_krita.engine.inference import (
    GapFillPredictor,
    InvalidModelError,
)
from gapfill_krita.engine.patches import (
    build_model_tensor,
    canonical_boundary_from_rgba,
)
from gapfill_krita.engine.postprocessing import (
    build_line_region_labels,
    select_region_prediction,
)
from gapfill_krita.engine.types import (
    GapKind,
    GapRegion,
    LayerImages,
    ModelBoundaryMode,
    PredictionProvenance,
)


class _Metadata:
    def __init__(self, name: str, shape: list[int], data_type: str = "tensor(float)"):
        self.name = name
        self.shape = shape
        self.type = data_type


class _Session:
    def __init__(self, _path: str, providers: list[str]):
        self.providers = providers
        self.output = np.full((1, 1, 32, 32), 0.5, dtype=np.float32)
        self.raise_on_run = False
        self.run_calls = 0
        self.last_input: np.ndarray | None = None

    def get_inputs(self) -> list[_Metadata]:
        return [_Metadata("input_mask", [1, 2, 32, 32])]

    def get_outputs(self) -> list[_Metadata]:
        return [_Metadata("nearest_region_mask", [1, 1, 32, 32])]

    def run(self, names: list[str], inputs: dict[str, np.ndarray]) -> list[np.ndarray]:
        self.run_calls += 1
        if self.raise_on_run:
            raise RuntimeError("controlled inference failure")
        self.last_input = inputs["input_mask"].copy()
        return [self.output.copy()]


def _images(width: int = 7, height: int = 7) -> LayerImages:
    coloring = np.zeros((height, width, 4), dtype=np.uint8)
    coloring[:, :3] = (220, 30, 30, 255)
    coloring[:, 4:] = (30, 30, 220, 255)
    line = np.zeros_like(coloring)
    guides = np.zeros_like(coloring)
    return LayerImages(coloring, line, guides)


def _gap(identifier: str = "gap-0", x: int = 3, y: int = 3) -> GapRegion:
    return GapRegion(
        identifier,
        np.asarray([y * 7 + x], dtype=np.int64),
        (x, y),
        GapKind.TRANSPARENT,
    )


class KritaPhase5PredictionTests(unittest.TestCase):
    def test_training_faithful_boundary_threshold(self) -> None:
        rgba = np.asarray(
            [[
                [0, 0, 0, 0],
                [0, 0, 0, 1],
                [127, 127, 127, 255],
                [128, 128, 128, 255],
                [129, 129, 129, 255],
                [0, 0, 0, 255],
                [0, 0, 0, 126],
                [0, 0, 0, 127],
            ]],
            dtype=np.uint8,
        )
        self.assertEqual(
            canonical_boundary_from_rgba(rgba).tolist(),
            [[False, False, True, True, False, True, False, True]],
        )

    def test_tensor_is_nchw_float32_line_only(self) -> None:
        images = _images()
        images.line_art[3, 2] = (0, 0, 0, 255)
        images.guides[3, 4] = (0, 0, 0, 255)
        tensor, _ = build_model_tensor(images, _gap())
        self.assertEqual(tensor.shape, (1, 2, 32, 32))
        self.assertEqual(tensor.dtype, np.float32)
        self.assertEqual(np.flatnonzero(tensor[0, 0]).tolist(), [16 * 32 + 15])
        self.assertEqual(np.flatnonzero(tensor[0, 1]).tolist(), [16 * 32 + 16])

    def test_line_regions_and_modal_tie_are_canonical(self) -> None:
        line = np.zeros((2, 3, 4), dtype=np.uint8)
        line[:, 1] = (0, 0, 0, 255)
        self.assertEqual(
            build_line_region_labels(line).tolist(),
            [[1, 0, 2], [1, 0, 2]],
        )

        coloring = np.asarray(
            [
                [[240, 20, 20, 255], [20, 20, 240, 255]],
                [[20, 20, 240, 255], [240, 20, 20, 255]],
            ],
            dtype=np.uint8,
        )
        selection = select_region_prediction(
            coloring,
            np.ones((2, 2), dtype=np.int32),
            np.full((2, 2), 0.8, dtype=np.float32),
        )
        self.assertEqual(selection.rgb, (240, 20, 20))
        self.assertEqual(selection.label, 1)

    def test_no_gaps_does_not_load_model(self) -> None:
        calls = 0

        def factory(path: str, providers: list[str]) -> _Session:
            nonlocal calls
            calls += 1
            return _Session(path, providers)

        predictor = GapFillPredictor(
            "missing-is-irrelevant.onnx",
            session_factory=factory,
            expected_model_sha256=None,
        )
        self.assertEqual(predictor.predict_all(_images(), []), [])
        self.assertEqual(calls, 0)

    def test_learned_and_fallback_provenance_are_explicit(self) -> None:
        sessions: list[_Session] = []

        def factory(path: str, providers: list[str]) -> _Session:
            session = _Session(path, providers)
            sessions.append(session)
            return session

        with tempfile.NamedTemporaryFile(suffix=".onnx") as model:
            predictor = GapFillPredictor(
                model.name,
                session_factory=factory,
                expected_model_sha256=None,
            )
            images = _images()
            first = _gap("gap-0", 3, 3)
            second = _gap("gap-1", 2, 3)

            original_predict = predictor.predict_details
            calls = 0

            def controlled_predict(
                images: LayerImages,
                gap: GapRegion,
                model_boundary_mode: ModelBoundaryMode,
            ):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("controlled one-gap failure")
                return original_predict(images, gap, model_boundary_mode)

            predictor.predict_details = controlled_predict  # type: ignore[method-assign]
            predictor.predict_all(images, [first, second])

        self.assertEqual(first.prediction_provenance, PredictionProvenance.LEARNED)
        self.assertIsNotNone(first.learned_confidence)
        self.assertEqual(second.prediction_provenance, PredictionProvenance.FALLBACK)
        self.assertIsNone(second.learned_confidence)
        self.assertIn("controlled one-gap failure", second.metadata["fallback_reason"])

    def test_invalid_output_fails_batch_without_partial_labels(self) -> None:
        session: _Session | None = None

        def factory(path: str, providers: list[str]) -> _Session:
            nonlocal session
            session = _Session(path, providers)
            session.output[0, 0, 0, 0] = np.nan
            return session

        with tempfile.NamedTemporaryFile(suffix=".onnx") as model:
            predictor = GapFillPredictor(
                model.name,
                session_factory=factory,
                expected_model_sha256=None,
            )
            gaps = [_gap("gap-0", 3, 3), _gap("gap-1", 2, 3)]
            with self.assertRaises(InvalidModelError):
                predictor.predict_all(_images(), gaps)

        self.assertTrue(all(gap.predicted_rgb is None for gap in gaps))
        self.assertTrue(all(gap.prediction_provenance is None for gap in gaps))

    def test_cancellation_after_inference_does_not_commit_partial_batch(self) -> None:
        session: _Session | None = None

        def factory(path: str, providers: list[str]) -> _Session:
            nonlocal session
            session = _Session(path, providers)
            return session

        polls = 0

        def cancelled() -> bool:
            nonlocal polls
            polls += 1
            return polls >= 4

        with tempfile.NamedTemporaryFile(suffix=".onnx") as model:
            predictor = GapFillPredictor(
                model.name,
                session_factory=factory,
                expected_model_sha256=None,
            )
            gaps = [_gap("gap-0", 3, 3), _gap("gap-1", 2, 3)]
            with self.assertRaises(InterruptedError):
                predictor.predict_all(_images(), gaps, cancel_requested=cancelled)

        self.assertIsNotNone(session)
        self.assertEqual(session.run_calls, 1)
        self.assertTrue(all(gap.predicted_rgb is None for gap in gaps))
        self.assertTrue(all(gap.prediction_provenance is None for gap in gaps))

    def test_exact_model_names_are_required(self) -> None:
        class WrongNameSession(_Session):
            def get_inputs(self) -> list[_Metadata]:
                return [_Metadata("wrong_input", [1, 2, 32, 32])]

        with tempfile.NamedTemporaryFile(suffix=".onnx") as model:
            predictor = GapFillPredictor(
                model.name,
                session_factory=WrongNameSession,
                expected_model_sha256=None,
            )
            with self.assertRaises(InvalidModelError):
                predictor.load()

    def test_released_model_hash_and_all_frozen_outputs_match(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        model = repository / "web" / "public" / "models" / "unet32.onnx"
        cases_path = (
            repository / "tests" / "fixtures" / "gapfill" / "model" / "cases.json"
        )
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
        predictor = GapFillPredictor(model)
        predictor.load()
        self.assertEqual(
            predictor.model_sha256,
            "8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78",
        )
        absolute = float(cases["comparison_tolerance"]["absolute"])
        relative = float(cases["comparison_tolerance"]["relative"])
        for case in cases["cases"]:
            tensor = np.zeros((1, 2, 32, 32), dtype=np.float32)
            flat = tensor.reshape((1, 2, -1))
            flat[0, 0, case["tensor"]["channel_0_active_indices"]] = 1.0
            flat[0, 1, case["tensor"]["channel_1_active_indices"]] = 1.0
            actual = predictor.run_tensor(tensor)
            expected = np.asarray(
                case["characterized_output"]["values_row_major"], dtype=np.float32
            ).reshape((1, 1, 32, 32))
            np.testing.assert_allclose(
                actual,
                expected,
                atol=absolute,
                rtol=relative,
                err_msg=case["id"],
            )

    def test_released_model_selects_canonical_m001_region_and_rgb(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        model = repository / "web" / "public" / "models" / "unet32.onnx"
        cases_path = (
            repository / "tests" / "fixtures" / "gapfill" / "model" / "cases.json"
        )
        case = next(
            item
            for item in json.loads(cases_path.read_text(encoding="utf-8"))["cases"]
            if item["id"] == "M001_no_guide"
        )
        line = np.zeros((32, 32, 4), dtype=np.uint8)
        line.reshape((-1, 4))[case["tensor"]["channel_0_active_indices"]] = (
            0,
            0,
            0,
            255,
        )
        labels = build_line_region_labels(line)
        coloring = np.zeros((32, 32, 4), dtype=np.uint8)
        coloring[labels == 1] = (240, 20, 20, 255)
        coloring[labels > 1] = (20, 20, 240, 255)
        target = case["tensor"]["channel_1_active_indices"]
        coloring.reshape((-1, 4))[target] = 0
        gap = GapRegion(
            "gap-0",
            np.asarray(target, dtype=np.int64),
            (16, 16),
            GapKind.TRANSPARENT,
        )

        prediction = GapFillPredictor(model).predict_details(
            LayerImages(coloring, line, np.zeros_like(line)),
            gap,
        )
        self.assertEqual(prediction.provenance, PredictionProvenance.LEARNED)
        self.assertEqual(prediction.rgb, (20, 20, 240))
        self.assertAlmostEqual(prediction.learned_confidence, 0.8431808595754662)


if __name__ == "__main__":
    unittest.main()
