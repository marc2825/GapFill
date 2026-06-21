from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .colors import UNASSIGNED_MATERIAL_RGB, predict_color_greedy
from .patches import PATCH_SIZE, build_model_patches
from .postprocessing import segment_colored_regions, select_region_color
from .types import GapRegion, LayerImages, Rgb

EXPECTED_INPUT_SHAPE = (1, 2, PATCH_SIZE, PATCH_SIZE)
EXPECTED_OUTPUT_SHAPE = (1, 1, PATCH_SIZE, PATCH_SIZE)


class ModelUnavailableError(RuntimeError):
    pass


class InvalidModelError(RuntimeError):
    pass


class GapFillPredictor:
    def __init__(self, model_path: Path | str, session_factory: Optional[Callable] = None):
        self.model_path = Path(model_path)
        self._session_factory = session_factory
        self._session = None
        self._input_name = ""
        self._output_name = ""

    @property
    def loaded(self) -> bool:
        return self._session is not None

    def load(self) -> None:
        if self.loaded:
            return
        if not self.model_path.is_file():
            raise ModelUnavailableError(f"ONNX model was not found: {self.model_path}")
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
            raise ModelUnavailableError(f"Failed to load the ONNX model: {error}") from error

        inputs = session.get_inputs()
        outputs = session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise InvalidModelError("GapFill expects exactly one model input and one output.")
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

    def predict(self, images: LayerImages, gap: GapRegion) -> Rgb:
        self.load()
        coloring, line_art, guides, gap_mask = build_model_patches(images, gap)
        boundary_mask = ((line_art.rgba[..., 3] > 0) | (guides.rgba[..., 3] > 0)).astype(np.float32)
        tensor = np.stack((boundary_mask, gap_mask), axis=0)[None, ...]
        if tensor.shape != EXPECTED_INPUT_SHAPE or tensor.dtype != np.float32:
            raise InvalidModelError(
                f"Generated invalid model input: {tensor.shape} / {tensor.dtype}."
            )
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
        if not np.issubdtype(output.dtype, np.floating):
            raise InvalidModelError(
                f"Expected floating-point model output, received {output.dtype}."
            )

        labels, count = segment_colored_regions(coloring.rgba, line_art.rgba, guides.rgba)
        return select_region_color(
            coloring.rgba,
            labels,
            count,
            output[0, 0].astype(np.float32, copy=False),
        )

    def predict_all(
        self,
        images: LayerImages,
        gaps: list[GapRegion],
        *,
        allow_greedy_on_inference_error: bool = True,
        cancel_requested: Optional[Callable[[], bool]] = None,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> list[GapRegion]:
        # Loading is deliberately outside the per-gap fallback: a missing model
        # is a visible setup error, not a reason to silently change algorithms.
        self.load()
        excluded = (images.line_art[..., 3] > 0) | (images.guides[..., 3] > 0)
        for index, gap in enumerate(gaps):
            if cancel_requested and cancel_requested():
                raise InterruptedError("Color prediction was cancelled.")
            try:
                gap.predicted_rgb = self.predict(images, gap)
            except (InvalidModelError, ModelUnavailableError):
                raise
            except Exception:
                if not allow_greedy_on_inference_error:
                    raise
                gap.predicted_rgb = predict_color_greedy(
                    images.coloring,
                    gap.indices,
                    excluded=excluded,
                    fallback=UNASSIGNED_MATERIAL_RGB,
                )
            if progress:
                progress(index + 1, len(gaps))
        return gaps
