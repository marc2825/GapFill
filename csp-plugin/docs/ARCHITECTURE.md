# Architecture

```text
                                  detection + prediction
                                           |
        +----------------------------------+--------------------------------+
        |                                                                   |
2021 CSP filter callback                                           PNG companion / future host
        |                                                                   |
 QuickFixPipeline                                             HostFilterContext + GapAssistCommand
        |                                                                   |
single-raster compatibility path                       ReviewSession + CorrectionOutputGenerator
        |                                                                   |
input-infeasible for GapFill parity                     correction / highlight / manifest / preview
```

The same core is driven by `gap_assist_cli`, which replaces host pixels and UI
with PNG I/O, a contact sheet, a JSON manifest, and a decisions file.

`QuickFixPipeline` is the restricted-host path used by conventional filter APIs.
It returns a corrected in-memory copy containing High-confidence **learned**
fills only; heuristic fallback never qualifies. The host owns Preview,
OK/Cancel, committing the destination, and Undo.

## Core invariants

- `Image` owns checked, tightly packed RGBA8 pixels.
- Pure detection consumes `DetectionGeometry`: three equal-sized, row-major,
  top-left-origin binary masks for exact-alpha-zero Coloring membership, Line
  boundaries, and Guide boundaries. Selection is a separate application scope
  and never changes connectivity or enclosure.
- Detection uses streaming row-run component labeling. Scanning/union work is
  linear in image pixels and row runs; retained component lists merge by size,
  so retained-index movement is bounded by O(emitted pixels log threshold). It
  retains only previous/current-row runs,
  active component summaries, and at most the configured threshold of pixel
  indices per still-eligible component. An oversized open component is traversed
  once without an image-sized flood-fill queue.
- Cancellation is checked at every row and every 4096 scan/union/aggregation
  operations. Progress is reported at most every 64 rows.
- Owner traversal uses one signed 32-bit label per pixel and one reusable component
  queue, avoiding per-label statistics sized to a pathological checkerboard. Owner
  labels are released immediately after prediction.
- Analysis receives a const source image and never mutates it.
- Candidate state is the only source of truth for Apply/Skip/Mark Only.
- Output is generated only after review acceptance.
- Host mutation begins after all analysis and confirmation steps.
- Overwrite is unavailable without both explicit confirmation and an Undo transaction.
- Learned prediction uses a Line-only NCHW float32 `[1,2,32,32]` tensor. The
  target gap is channel 1; Guides are detection boundaries but never enter the
  trained model input.
- Semantic regions are full-image four-connected fillable Line components.
  Positive painted labels are scored by mean model probability in the cropped
  patch; label 0 is excluded; the selected region contributes exact modal RGB
  with a first-row-major tie break.
- `PredictionProvenance` separates learned confidence from the uncalibrated
  heuristic score. Only `Learned` can receive a confidence band or automatic
  Apply state.

## Extension points

`LearnedGapPredictor` implements canonical patching, output interpretation,
region scoring, and modal color around a small `InferenceBackend`. The backend
must report the frozen model SHA-256, one exact input/output name, float32 type,
and fixed shapes before its synchronous `run` is accepted. Phase 5 tests this
boundary with actual local ONNX Runtime output. `OnnxPredictorStub` remains an
explicit unavailable distribution adapter until native runtime packaging is
implemented; it never substitutes the rule predictor.

Optional reference and Guide images remain separate inputs for future products,
but the current learned contract consumes only Coloring and Line Art. Phase 4's
Guide detection boundary does not imply Guide composition in the model.

`HostFilterContext` isolates proprietary SDK types for a future richer host API.
The evaluated 2021 filter SDK instead uses the narrower `QuickFixPipeline`, since
it cannot create layers or present the full review dialog. The core remains
independently buildable and testable without CSP installed.

`NativeHostAdapter`/`NativeHostSession` define the smaller SDK-independent
canonical input and lifecycle requirement: independent document-coordinate
Coloring, Line, Guide and Selection, explicit layout/profile normalization,
stable snapshot identity, replaceable Preview, cancellation, atomic mutation,
abort and Undo/Redo evidence. Fake-host conformance defines these requirements;
it is not CSP host evidence.

The public core exposes normalized multi-layer detection and a corresponding
`SmartGapPropagation`/`QuickFixPipeline` overload. The current CLI and private
2021 adapter normalize only one Coloring-like raster with empty Line and Guide
masks. Phase 7 established that the evaluated filter SDK does not expose those
independent sources, so this path is not a canonical GapFill implementation.

Model calls are synchronous and cannot be interrupted. Cancellation is polled
before contract validation, before and after each backend call, between gaps,
and before returning. Results are accumulated privately and published only when
the whole batch reaches the final cancellation boundary.
