# Gap Assist for CLIP STUDIO PAINT — Specification

## Product boundary

Gap Assist is a post-process command run after ordinary coloring. It is not a
replacement for CSP's Paint Bucket and does not depend on hover, tool-switch,
shortcut, canvas-event, Undo/Redo, memory, or process hooks. The full companion
workflow is non-destructive: accepted pixels are emitted as a transparent image
to import as `Gap Assist Corrections`. The restricted native Quick Fix commits
through CSP's ordinary filter flow; duplicate the coloring layer first when an
editable copy is required.

## Modes

### Quick Fix

Detect and predict all candidates, apply only High-confidence **learned**
candidates, and leave Medium/Low or heuristic-fallback candidates untouched or
on the optional highlight layer. The current native distribution has no
packaged ONNX backend, so it does not yet claim usable learned Quick Fix.

### Review List

Use one review session containing summary counts and rows with Apply, ID,
confidence, band, suggested color, preview source, status, and owner ID. The
session supports Apply Selected, Apply High Confidence, Skip Selected, highlight
creation, and Cancel.

### One-by-One

Expose one candidate at a time with Apply, Skip, Mark Only, Next, Back, Apply and
Next, Skip and Next, and Apply All Remaining High Confidence.

## Analysis and output

- Pure detector input: equal-sized binary Coloring-membership, Line-boundary,
  and Guide-boundary masks, plus an optional selection/application mask.
- Canonical Coloring membership is exactly `alpha == 0` at normalization. The
  legacy `alphaThreshold` setting remains serialized for compatibility and for
  existing non-detector sampling code; it does not broaden canonical detection.
- Area presets: Small 3 px, Medium 10 px, Large 30 px, or Custom.
- Connectivity: four neighbors canonically and by default. The optional
  eight-neighbor setting is an explicit noncanonical compatibility extension.
- Components touching the image boundary are excluded. Enclosure and size are
  determined in full accessible geometry before selection intersects the
  component's application pixels; a selection edge cannot create enclosure.
- True Line and Guide mask pixels are impassable boundaries and are not
  paintable candidate pixels.
- Learned channel 0 is the Line-only canonical boundary produced by logical
  straight-alpha RGBA composited over byte white and inclusive grayscale-128
  thresholding. Channel 1 contains exactly the full target-gap pixels. Input is
  NCHW float32 `[1,2,32,32]`; output is float32 `[1,1,32,32]`.
- Full-image four-connected Line fill regions receive positive row-major labels.
  Label 0 is ineligible. Each eligible label needs a painted Coloring pixel and
  is scored by the mean of all valid model-output pixels in that label,
  including transparent gap pixels. Exact score ties keep the first row-major
  label. The chosen region's alpha-positive pixels supply exact modal RGB;
  equal modes keep the first row-major color.
- Learned output must be finite and within `[0,1]`; the winning region mean is
  correspondence confidence, not a calibrated correctness guarantee.
- Opaque owner candidates must contain more pixels than the gap threshold.
- The Rule-Based fallback samples an expanded gap neighborhood, clusters RGB
  into five-bit buckets, weights closer samples more strongly, and records the
  dominant large owner when one exists. Its historical score is diagnostic only.
- Confidence presets are Conservative (.90/.65), Balanced (.85/.55), and
  Aggressive (.75/.45) for learned High/Medium boundaries only. A heuristic
  suggestion has null learned confidence and requires explicit per-gap Apply.
- No-color predictions become Low confidence and Mark Only.

Outputs are correction pixels only, optional red/yellow/cyan confidence markers,
a corrected preview, a review contact sheet, and a machine-readable manifest.
Direct overwrite is opt-in, confirmed, and rejected when a one-step Undo cannot
be guaranteed.

For the PNG companion, output paths must be distinct from the input and one
another. Existing destinations require `--force`; force never bypasses alias
checks. All output content is encoded before same-directory staging and
best-effort set rollback. Explicit per-gap Apply, Skip, or Mark Only decisions
take precedence over bulk helpers, which act only on Unreviewed candidates.
Configuration precedence is defaults, settings file, then CLI overrides; the
last occurrence wins when the same CLI option is repeated.

For the evaluated 2021 CELSYS filter SDK, the native host surface supports the
Quick Fix subset only and commits through CSP's normal filter flow. Full review
and separate correction/highlight outputs are provided by the PNG companion.

## Acceptance matrix

| Requirement | Implementation | Verification |
|---|---|---|
| Detect small enclosed transparent regions | `core/gap_detection` | unit tests 1–6 |
| Exclude large/open regions | `core/gap_detection` | unit tests 2–3 |
| Canonical learned tensor/region/modal color | `predictors/onnx_predictor_stub.*` (`LearnedGapPredictor`) | Phase 5 C++/Python parity + unit tests |
| Validate model backend contract/output | `InferenceBackend`, `LearnedGapPredictor` | malformed contract/output/cancel tests |
| Explicit heuristic fallback/provenance | `gap_color_predictor`, `rule_based_predictor` | D-07 unit/CLI tests |
| Smart owner propagation | `core/owner_regions`, predictor owner weights | high-confidence owner test |
| Review List decisions | `ui/review_session`, `ui/dialog_model` | review-state tests |
| One-by-One controls | `ui/review_session` | navigation test |
| Quick Fix applies learned High only | `ui/review_session` | provenance/mode tests |
| Non-destructive correction output | `core/correction_output` | output/source-integrity tests |
| Highlight skipped/uncertain gaps | `core/correction_output` | highlight test |
| Cancel changes nothing | `plugin_entry/gap_assist_command` | mock-host test |
| Unsafe host capabilities fail closed | `plugin_entry/gap_assist_command` | capability tests |
| PNG input/review/output harness | `io`, `cli` | CTest/`make test-e2e` |
| Persist non-image settings | `core/settings` | settings format + build tests |
| Safe PNG output commit | `io/atomic_output`, `cli` | alias/force/failure-injection tests |
| Candidate snapshot validation | `core/candidate_context`, `core/correction_output` | forged/stale candidate tests |
| Normalized geometry and D-04 binding | `core/image_types`, `core/gap_detection`, `core/candidate_context` | Phase 4 parity/provenance tests |
| No network or telemetry | no network dependency/API in first-party code | source review/CI |

## Deliberately excluded from this version

Real-time overflow fill, bucket replacement, hover-linked highlights, canvas
pop-up magnification, in-circle drag correction, sweep-to-apply, tool lockout,
and canvas-event interception are outside this CSP product boundary.
