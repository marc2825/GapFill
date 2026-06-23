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
High-confidence corrected pixels                       ReviewSession + CorrectionOutputGenerator
        |                                                                   |
CSP Preview / OK / Cancel / Undo                        correction / highlight / manifest / preview
```

The same core is driven by `gap_assist_cli`, which replaces host pixels and UI
with PNG I/O, a contact sheet, a JSON manifest, and a decisions file.

`QuickFixPipeline` is the restricted-host path used by conventional filter APIs.
It returns a corrected in-memory copy containing High-confidence fills only; the
host owns Preview, OK/Cancel, committing the destination, and Undo.

## Core invariants

- `Image` owns checked, tightly packed RGBA8 pixels.
- Detection is linear in pixel count. Gap traversal stores at most the configured
  threshold worth of output pixels for rejected large components.
- Owner traversal uses one signed 32-bit label per pixel and one reusable component
  queue, avoiding per-label statistics sized to a pathological checkerboard. Owner
  labels are released immediately after prediction.
- Analysis receives a const source image and never mutates it.
- Candidate state is the only source of truth for Apply/Skip/Mark Only.
- Output is generated only after review acceptance.
- Host mutation begins after all analysis and confirmation steps.
- Overwrite is unavailable without both explicit confirmation and an Undo transaction.

## Extension points

`GapColorPredictor` may be implemented by a local ONNX backend without changing
detection, review, or output. Optional reference, line, and guide images can be
added to `PredictInput`; they must not change the active-layer definition of a
gap unless a future specification explicitly does so.

`HostFilterContext` isolates proprietary SDK types for a future richer host API.
The evaluated 2021 filter SDK instead uses the narrower `QuickFixPipeline`, since
it cannot create layers or present the full review dialog. The core remains
independently buildable and testable without CSP installed.
