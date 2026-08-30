#!/usr/bin/env python3
"""Cross-runtime Phase 5 parity for the CSP backend boundary and pure core."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import onnxruntime as ort

REPOSITORY = Path(__file__).resolve().parents[2]
FIXTURES = REPOSITORY / "tests" / "fixtures" / "gapfill"
sys.path.insert(0, str(REPOSITORY / "scripts"))

from gapfill_reference.reference import (
    canonical_line_labels,
    score_canonical_regions,
    tensor_from_sparse,
)

MODEL_SHA256 = "8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78"


def parse_probe(output: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in output.splitlines():
        key, value = line.split("=", 1)
        result[key] = value
    return result


def indices(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item]


def run(probe: Path, *arguments: object) -> dict[str, str]:
    result = subprocess.run(
        [str(probe), *(str(argument) for argument in arguments)],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_probe(result.stdout)


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: test_csp_phase5_prediction.py PROBE MODEL")
    probe = Path(sys.argv[1])
    model = Path(sys.argv[2])
    if hashlib.sha256(model.read_bytes()).hexdigest() != MODEL_SHA256:
        raise AssertionError("CSP parity received the wrong ONNX artifact")

    data = json.loads((FIXTURES / "model" / "cases.json").read_text())
    session = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    if [item.name for item in session.get_inputs()] != ["input_mask"]:
        raise AssertionError("unexpected ONNX input contract")
    if [item.name for item in session.get_outputs()] != ["nearest_region_mask"]:
        raise AssertionError("unexpected ONNX output contract")

    absolute = float(data["comparison_tolerance"]["absolute"])
    relative = float(data["comparison_tolerance"]["relative"])
    actual_outputs: dict[str, np.ndarray] = {}
    maximum_delta = 0.0
    for case in data["cases"]:
        tensor = tensor_from_sparse(case)
        actual = np.asarray(
            session.run(["nearest_region_mask"], {"input_mask": tensor})[0],
            dtype=np.float32,
        )
        expected = np.asarray(
            case["characterized_output"]["values_row_major"], dtype=np.float32
        ).reshape((1, 1, 32, 32))
        maximum_delta = max(
            maximum_delta,
            float(np.max(np.abs(actual.astype(np.float64) - expected))),
        )
        np.testing.assert_allclose(
            actual, expected, atol=absolute, rtol=relative, err_msg=case["id"]
        )
        actual_outputs[case["id"]] = actual

    no_guide = next(case for case in data["cases"] if case["id"] == "M001_no_guide")
    emitted = run(probe, "tensor")
    if indices(emitted["boundary"]) != no_guide["tensor"][
        "channel_0_active_indices"
    ]:
        raise AssertionError("CSP canonical boundary tensor differs from M001")
    if indices(emitted["target"]) != no_guide["tensor"][
        "channel_1_active_indices"
    ]:
        raise AssertionError("CSP canonical target tensor differs from M001")

    output = actual_outputs["M001_no_guide"].reshape(-1)
    with tempfile.TemporaryDirectory(prefix="gapfill-csp-phase5-") as temporary:
        output_path = Path(temporary) / "output.txt"
        output_path.write_text(
            "\n".join(format(float(value), ".9g") for value in output) + "\n",
            encoding="utf-8",
        )
        predicted = run(probe, "predict", output_path)

    if indices(predicted["boundary"]) != no_guide["tensor"][
        "channel_0_active_indices"
    ] or indices(predicted["target"]) != no_guide["tensor"][
        "channel_1_active_indices"
    ]:
        raise AssertionError("CSP predictor backend received a noncanonical tensor")

    line = np.zeros((32, 32, 4), dtype=np.uint8)
    line.reshape((-1, 4))[no_guide["tensor"]["channel_0_active_indices"]] = (
        0,
        0,
        0,
        255,
    )
    labels = canonical_line_labels(line)
    coloring = np.zeros((32, 32, 4), dtype=np.uint8)
    coloring[labels == 1] = (240, 20, 20, 255)
    coloring[labels > 1] = (20, 20, 240, 255)
    coloring.reshape((-1, 4))[no_guide["tensor"]["channel_1_active_indices"]] = 0
    expected_selection = score_canonical_regions(
        coloring, labels, output.reshape((32, 32))
    )
    if int(predicted["region"]) != expected_selection["selected_region_id"]:
        raise AssertionError("CSP semantic-region winner differs from neutral reference")
    if tuple(int(value) for value in predicted["rgb"].split(",")) != tuple(
        expected_selection["rgb"]
    ):
        raise AssertionError("CSP modal RGB differs from neutral reference")
    if not np.isclose(
        float(predicted["confidence"]),
        expected_selection["confidence"],
        atol=1e-12,
        rtol=1e-12,
    ):
        raise AssertionError("CSP semantic-region mean differs from neutral reference")
    if predicted["provenance"] != "learned":
        raise AssertionError("CSP learned result lost its provenance")

    print(
        "CSP Phase 5 parity: 7/7 ONNX outputs and canonical "
        f"tensor/region/RGB passed; max delta={maximum_delta}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
