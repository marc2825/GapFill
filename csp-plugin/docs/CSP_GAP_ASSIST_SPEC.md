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

Detect and predict all candidates, apply only High-confidence candidates, and
leave Medium/Low candidates untouched or on the optional highlight layer.

### Review List

Use one review session containing summary counts and rows with Apply, ID,
confidence, band, suggested color, preview source, status, and owner ID. The
session supports Apply Selected, Apply High Confidence, Skip Selected, highlight
creation, and Cancel.

### One-by-One

Expose one candidate at a time with Apply, Skip, Mark Only, Next, Back, Apply and
Next, Skip and Next, and Apply All Remaining High Confidence.

## Analysis and output

- Input: RGBA active-raster-layer pixels and, when supported, a selection mask.
- Transparent test: `alpha <= alphaThreshold` (default 0).
- Area presets: Small 3 px, Medium 10 px, Large 30 px, or Custom.
- Connectivity: four neighbors by default, optionally eight.
- Open components touching an image or selection boundary are excluded.
- Opaque owner candidates must contain more pixels than the gap threshold.
- The rule predictor samples an expanded gap neighborhood, clusters RGB into
  five-bit buckets, weights closer samples more strongly, and records the
  dominant large owner when one exists.
- Confidence presets are Conservative (.90/.65), Balanced (.85/.55), and
  Aggressive (.75/.45) for High/Medium boundaries.
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
| Suggest color and confidence | `predictors/rule_based_predictor` | prediction tests |
| Swappable predictor/ONNX fallback | `gap_color_predictor`, ONNX stub, command/CLI fallback | compile + CLI |
| Smart owner propagation | `core/owner_regions`, predictor owner weights | high-confidence owner test |
| Review List decisions | `ui/review_session`, `ui/dialog_model` | review-state tests |
| One-by-One controls | `ui/review_session` | navigation test |
| Quick Fix applies High only | `ui/review_session` | mode test |
| Non-destructive correction output | `core/correction_output` | output/source-integrity tests |
| Highlight skipped/uncertain gaps | `core/correction_output` | highlight test |
| Cancel changes nothing | `plugin_entry/gap_assist_command` | mock-host test |
| Unsafe host capabilities fail closed | `plugin_entry/gap_assist_command` | capability tests |
| PNG input/review/output harness | `io`, `cli` | CTest/`make test-e2e` |
| Persist non-image settings | `core/settings` | settings format + build tests |
| Safe PNG output commit | `io/atomic_output`, `cli` | alias/force/failure-injection tests |
| Candidate snapshot validation | `core/candidate_context`, `core/correction_output` | forged/stale candidate tests |
| No network or telemetry | no network dependency/API in first-party code | source review/CI |

## Deliberately excluded from this version

Real-time overflow fill, bucket replacement, hover-linked highlights, canvas
pop-up magnification, in-circle drag correction, sweep-to-apply, tool lockout,
and canvas-event interception are outside this CSP product boundary.
