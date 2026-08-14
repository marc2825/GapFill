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

## Extension points

`GapColorPredictor` may be implemented by a local ONNX backend without changing
detection, review, or output. Optional reference, line, and guide images remain
separate prediction inputs. Phase 4's binary Line/Guide detection boundaries do
not settle the unresolved ONNX Guide-channel composition policy.

`HostFilterContext` isolates proprietary SDK types for a future richer host API.
The evaluated 2021 filter SDK instead uses the narrower `QuickFixPipeline`, since
it cannot create layers or present the full review dialog. The core remains
independently buildable and testable without CSP installed.

The public core exposes normalized multi-layer detection and a corresponding
`SmartGapPropagation`/`QuickFixPipeline` overload. The current CLI and private
2021 adapter still normalize only the active Coloring raster with empty Line and
Guide masks because acquiring those layers is a later host-integration problem.
