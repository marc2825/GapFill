import tempfile
import unittest

import numpy as np
from gapfill_krita.engine.inference import GapFillPredictor, InvalidModelError
from gapfill_krita.engine.types import (
    GapKind,
    GapRegion,
    LayerImages,
    LearnedPrediction,
    ModelBoundaryMode,
    PredictionProvenance,
)


class Metadata:
    def __init__(self, name, shape, data_type="tensor(float)"):
        self.name = name
        self.shape = shape
        self.type = data_type


class Session:
    def __init__(self, _path, providers, output_shape=(1, 1, 32, 32)):
        self.providers = providers
        self.output_shape = output_shape

    def get_inputs(self):
        return [Metadata("input_mask", [1, 2, 32, 32])]

    def get_outputs(self):
        return [Metadata("nearest_region_mask", list(self.output_shape))]

    def run(self, names, inputs):
        return [np.zeros(self.output_shape, dtype=np.float32)]


class InferenceTests(unittest.TestCase):
    def test_predict_all_freezes_the_explicit_mode_into_prediction_metadata(self):
        predictor = GapFillPredictor("unused.onnx", expected_model_sha256=None)
        predictor.load = lambda: None
        observed = []

        def predict_details(_images, _gap, mode, **_kwargs):
            observed.append(mode)
            return LearnedPrediction((12, 34, 56), PredictionProvenance.LEARNED)

        predictor.predict_details = predict_details
        images = np.zeros((3, 3, 4), dtype=np.uint8)
        gap = GapRegion(
            "gap-0", np.asarray([4], dtype=np.int64), (1, 1), GapKind.TRANSPARENT
        )
        predictor.predict_all(
            LayerImages(images, images.copy(), images.copy()),
            [gap],
            model_boundary_mode=ModelBoundaryMode.LINE_OR_GUIDES,
        )

        self.assertEqual(observed, [ModelBoundaryMode.LINE_OR_GUIDES])
        self.assertEqual(gap.metadata["model_boundary_mode"], "line_or_guides")

    def test_predict_all_labels_line_regions_once_per_batch(self):
        from unittest import mock

        from gapfill_krita.engine import inference

        width = height = 8
        coloring = np.zeros((height, width, 4), dtype=np.uint8)
        coloring[:, :4] = (220, 30, 30, 255)
        coloring[:, 4:] = (30, 30, 220, 255)
        line = np.zeros_like(coloring)
        line[:, 3] = (0, 0, 0, 255)
        images = LayerImages(coloring, line, np.zeros_like(coloring))
        gaps = [
            GapRegion(
                f"gap-{index}",
                np.asarray([y * width + x], dtype=np.int64),
                (x, y),
                GapKind.TRANSPARENT,
            )
            for index, (x, y) in enumerate(((1, 1), (6, 2), (5, 6)))
        ]
        with tempfile.NamedTemporaryFile(suffix=".onnx") as model:
            predictor = GapFillPredictor(
                model.name, session_factory=Session, expected_model_sha256=None
            )
            with mock.patch.object(
                inference,
                "build_line_region_labels",
                wraps=inference.build_line_region_labels,
            ) as labeler:
                predictor.predict_all(images, gaps, allow_greedy_on_inference_error=False)

        self.assertEqual(labeler.call_count, 1)
        self.assertTrue(
            all(gap.prediction_provenance is PredictionProvenance.LEARNED for gap in gaps)
        )

    def test_precomputed_labels_match_per_gap_labeling(self):
        width = height = 8
        coloring = np.zeros((height, width, 4), dtype=np.uint8)
        coloring[:, :4] = (220, 30, 30, 255)
        coloring[:, 4:] = (30, 30, 220, 255)
        line = np.zeros_like(coloring)
        line[:, 3] = (0, 0, 0, 255)
        images = LayerImages(coloring, line, np.zeros_like(coloring))
        gap = GapRegion(
            "gap-0", np.asarray([2 * width + 6], dtype=np.int64), (6, 2), GapKind.TRANSPARENT
        )
        with tempfile.NamedTemporaryFile(suffix=".onnx") as model:
            predictor = GapFillPredictor(
                model.name, session_factory=Session, expected_model_sha256=None
            )
            from gapfill_krita.engine.postprocessing import build_line_region_labels

            labels = build_line_region_labels(line)
            self.assertEqual(
                predictor.predict_details(images, gap),
                predictor.predict_details(images, gap, line_region_labels=labels),
            )
            with self.assertRaises(ValueError):
                predictor.predict_details(
                    images, gap, line_region_labels=labels[:-1]
                )

    def test_accepts_exact_model_contract(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx") as model:
            predictor = GapFillPredictor(
                model.name, session_factory=Session, expected_model_sha256=None
            )
            predictor.load()
            self.assertTrue(predictor.loaded)

    def test_rejects_incorrect_output_shape(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx") as model:

            def factory(path, providers):
                return Session(path, providers, (1, 32, 32))

            predictor = GapFillPredictor(
                model.name, session_factory=factory, expected_model_sha256=None
            )
            with self.assertRaises(InvalidModelError):
                predictor.load()

    def test_rejects_dynamic_metadata_shape(self):
        class DynamicSession(Session):
            def get_inputs(self):
                return [Metadata("input_mask", [1, 2, "height", "width"])]

        with tempfile.NamedTemporaryFile(suffix=".onnx") as model:
            predictor = GapFillPredictor(
                model.name,
                session_factory=DynamicSession,
                expected_model_sha256=None,
            )
            with self.assertRaises(InvalidModelError):
                predictor.load()

    def test_released_model_loads_and_runs(self):
        from pathlib import Path

        repository = Path(__file__).resolve().parents[2]
        model = repository / "web" / "public" / "models" / "unet32.onnx"
        if not model.is_file():
            self.skipTest("Released model is not present in this checkout.")
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            self.skipTest("ONNX Runtime is unavailable.")

        width = height = 64
        coloring = np.zeros((height, width, 4), dtype=np.uint8)
        coloring[:, :20] = (220, 60, 40, 255)
        coloring[:, 44:] = (40, 80, 220, 255)
        line = np.zeros_like(coloring)
        guides = np.zeros_like(coloring)
        indices = np.array(
            [y * width + x for y in range(30, 33) for x in range(30, 33)],
            dtype=np.int64,
        )
        gap = GapRegion("gap-0", indices, (31, 31), GapKind.TRANSPARENT)

        result = GapFillPredictor(model).predict(LayerImages(coloring, line, guides), gap)

        self.assertEqual(len(result), 3)
        self.assertTrue(all(0 <= channel <= 255 for channel in result))


if __name__ == "__main__":
    unittest.main()
