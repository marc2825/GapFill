from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .colors import UNASSIGNED_MATERIAL_RGB, predict_color_greedy
from .patches import PATCH_SIZE, build_model_tensor, extract_patch
from .postprocessing import (
    build_line_region_labels,
    extract_label_patch,
    select_region_prediction,
)
from .types import (
    GapRegion,
    LayerImages,
    LearnedPrediction,
    ModelBoundaryMode,
    PredictionProvenance,
    Rgb,
)

EXPECTED_INPUT_SHAPE = (1, 2, PATCH_SIZE, PATCH_SIZE)
EXPECTED_OUTPUT_SHAPE = (1, 1, PATCH_SIZE, PATCH_SIZE)
EXPECTED_INPUT_NAME = "input_mask"
EXPECTED_OUTPUT_NAME = "nearest_region_mask"
EXPECTED_MODEL_SHA256 = "8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78"


class ModelUnavailableError(RuntimeError):
    pass


class InvalidModelError(RuntimeError):
    pass


class GapFillPredictor:
    def __init__(
        self,
        model_path: Path | str,
        session_factory: Optional[Callable] = None,
        expected_model_sha256: Optional[str] = EXPECTED_MODEL_SHA256,
    ):
        self.model_path = Path(model_path)
        self._session_factory = session_factory
        self._expected_model_sha256 = expected_model_sha256
        self._session = None
        self._input_name = ""
        self._output_name = ""
        self._model_sha256 = ""

    @property
    def loaded(self) -> bool:
        return self._session is not None

    @property
    def model_sha256(self) -> str:
        return self._model_sha256

    def load(self) -> None:
        if self.loaded:
            return
        if not self.model_path.is_file():
            raise ModelUnavailableError(f"ONNX model was not found: {self.model_path}")
        try:
            self._model_sha256 = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
        except OSError as error:
            raise ModelUnavailableError(f"Failed to read the ONNX model: {error}") from error
        if (
            self._expected_model_sha256 is not None
            and self._model_sha256 != self._expected_model_sha256
        ):
            raise InvalidModelError(
                "GapFill model SHA-256 mismatch: "
                f"expected {self._expected_model_sha256}, received {self._model_sha256}."
            )
        try:
            if self._session_factory is None:
                import onnxruntime as ort

                factory = ort.InferenceSession
            else:
                factory = self._session_factory
            session = factory(str(self.model_path), providers=["CPUExecutionProvider"])
        except ImportError as error:
            raise ModelUnavailableError(
                "ONNX Runtime is not installed for Krita's Python environment."
            ) from error
        except Exception as error:
            raise InvalidModelError(f"Failed to load the ONNX model: {error}") from error

        inputs = session.get_inputs()
        outputs = session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise InvalidModelError("GapFill expects exactly one model input and one output.")
        if inputs[0].name != EXPECTED_INPUT_NAME or outputs[0].name != EXPECTED_OUTPUT_NAME:
            raise InvalidModelError(
                "GapFill expects model names input_mask and nearest_region_mask."
            )
        self._validate_metadata_shape("input", inputs[0].shape, EXPECTED_INPUT_SHAPE)
        self._validate_metadata_shape("output", outputs[0].shape, EXPECTED_OUTPUT_SHAPE)
        if inputs[0].type != "tensor(float)" or outputs[0].type != "tensor(float)":
            raise InvalidModelError("GapFill model input and output must be float32 tensors.")
        self._session = session
        self._input_name = inputs[0].name
        self._output_name = outputs[0].name

    @staticmethod
    def _validate_metadata_shape(name: str, actual: object, expected: tuple[int, ...]) -> None:
        try:
            values = tuple(actual)  # type: ignore[arg-type]
        except TypeError as error:
            raise InvalidModelError(f"Invalid {name} shape metadata: {actual!r}") from error
        if values != expected:
            raise InvalidModelError(f"Expected {name} shape {expected}, received {values}.")

    def predict_details(
        self,
        images: LayerImages,
        gap: GapRegion,
        model_boundary_mode: ModelBoundaryMode = ModelBoundaryMode.LINE_ONLY,
    ) -> LearnedPrediction:
        tensor, bounds = build_model_tensor(
            images, gap, mode=model_boundary_mode
        )
        output = self.run_tensor(tensor)

        full_labels = build_line_region_labels(images.line_art)
        labels = extract_label_patch(full_labels, bounds)
        coloring = extract_patch(images.coloring, bounds)
        selection = select_region_prediction(
            coloring.rgba,
            labels,
            output[0, 0],
        )
        return LearnedPrediction(
            rgb=selection.rgb,
            provenance=PredictionProvenance.LEARNED,
            learned_confidence=selection.mean_probability,
        )

    def run_tensor(self, tensor: np.ndarray) -> np.ndarray:
        """Run and validate one canonical tensor against the frozen model contract."""

        self.load()
        if tensor.shape != EXPECTED_INPUT_SHAPE or tensor.dtype != np.float32:
            raise InvalidModelError(
                f"Generated invalid model input: {tensor.shape} / {tensor.dtype}."
            )
        if not np.isfinite(tensor).all() or not np.logical_or(
            tensor == 0.0, tensor == 1.0
        ).all():
            raise InvalidModelError("GapFill model input must be finite and binary.")
        try:
            outputs = self._session.run(  # type: ignore[union-attr]
                [self._output_name], {self._input_name: tensor}
            )
        except Exception as error:
            raise RuntimeError(f"ONNX inference failed: {error}") from error
        if len(outputs) != 1:
            raise InvalidModelError("GapFill model returned an unexpected output count.")
        output = np.asarray(outputs[0])
        if output.shape != EXPECTED_OUTPUT_SHAPE:
            raise InvalidModelError(
                f"Expected model output shape {EXPECTED_OUTPUT_SHAPE}, received {output.shape}."
            )
        if output.dtype != np.float32:
            raise InvalidModelError(
                f"Expected float32 model output, received {output.dtype}."
            )
        if not np.isfinite(output).all():
            raise InvalidModelError("GapFill model output contains a nonfinite value.")
        if np.any(output < 0.0) or np.any(output > 1.0):
            raise InvalidModelError("GapFill model output contains a value outside [0, 1].")
        return output

    def predict(
        self,
        images: LayerImages,
        gap: GapRegion,
        model_boundary_mode: ModelBoundaryMode = ModelBoundaryMode.LINE_ONLY,
    ) -> Rgb:
        return self.predict_details(images, gap, model_boundary_mode).rgb

    def predict_all(
        self,
        images: LayerImages,
        gaps: list[GapRegion],
        *,
        model_boundary_mode: ModelBoundaryMode = ModelBoundaryMode.LINE_ONLY,
        allow_greedy_on_inference_error: bool = True,
        cancel_requested: Optional[Callable[[], bool]] = None,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> list[GapRegion]:
        if not gaps:
            return gaps
        if cancel_requested and cancel_requested():
            raise InterruptedError("Color prediction was cancelled.")
        # Loading is deliberately outside per-gap fallback: missing, corrupt,
        # or incompatible models are visible batch errors.
        self.load()
        if cancel_requested and cancel_requested():
            raise InterruptedError("Color prediction was cancelled.")
        excluded = (images.line_art[..., 3] > 0) | (images.guides[..., 3] > 0)
        pending: list[LearnedPrediction] = []
        learned_count = 0
        fallback_errors: list[Exception] = []
        for index, gap in enumerate(gaps):
            if cancel_requested and cancel_requested():
                raise InterruptedError("Color prediction was cancelled.")
            try:
                prediction = self.predict_details(
                    images, gap, model_boundary_mode
                )
                learned_count += 1
            except (InvalidModelError, ModelUnavailableError):
                raise
            except Exception as error:
                if not allow_greedy_on_inference_error:
                    raise
                fallback_errors.append(error)
                prediction = LearnedPrediction(
                    rgb=predict_color_greedy(
                        images.coloring,
                        gap.indices,
                        excluded=excluded,
                        fallback=UNASSIGNED_MATERIAL_RGB,
                    ),
                    provenance=PredictionProvenance.FALLBACK,
                    learned_confidence=None,
                    fallback_reason=str(error),
                )
            if cancel_requested and cancel_requested():
                raise InterruptedError("Color prediction was cancelled.")
            pending.append(prediction)
            if progress:
                progress(index + 1, len(gaps))
        if fallback_errors and learned_count == 0:
            raise RuntimeError(
                "ONNX inference failed for every gap; heuristic fallback was not "
                f"substituted for the batch: {fallback_errors[0]}"
            ) from fallback_errors[0]
        if cancel_requested and cancel_requested():
            raise InterruptedError("Color prediction was cancelled.")

        # Commit prediction metadata only after the complete batch succeeds.
        for gap, prediction in zip(gaps, pending):
            gap.predicted_rgb = prediction.rgb
            gap.prediction_provenance = prediction.provenance
            gap.learned_confidence = prediction.learned_confidence
            gap.metadata["model_boundary_mode"] = model_boundary_mode.value
            if prediction.fallback_reason is None:
                gap.metadata.pop("fallback_reason", None)
            else:
                gap.metadata["fallback_reason"] = prediction.fallback_reason
        return gaps
