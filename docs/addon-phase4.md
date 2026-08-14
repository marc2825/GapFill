# Add-on Phase 4 — detection and raster geometry

Date: 2026-08-14 (Asia/Tokyo)  
Branch: `fix/addon-detection-semantics`  
Baseline: `5cdb19962dfed459c63633fc268f2e9c8194d499`

This phase corrects only pure add-on detection, normalized raster geometry,
selection scope, and detector traversal/cancellation. It does not begin Phase 5
and does not change Web/ML production algorithms, ONNX/model artifacts,
prediction/color algorithms, host mutation, private SDK acquisition, UI, or
packaging behavior.

## Frozen baseline and fail-first record

The starting worktree was clean on the branch above and `git diff --check`
passed. The frozen fixture manifest was
`6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`.
Before production edits:

- neutral validation and 9/9 reference tests passed;
- Krita had 16 passing tests including its Phase 2 reader, and Ruff passed;
- CSP Make/core/safety/E2E passed with 35/35 unit tests; fresh Release CTest
  passed 6/6; ASan/UBSan passed 6/6 with leak detection disabled.

The new shared tests were then installed before their APIs existed. Krita failed
collection because `DetectionGeometry` did not exist; the CSP probe failed to
compile because `core/detection_geometry.hpp` did not exist. Those were the
expected Phase 4 fail-first conditions. Expected values came from the unchanged
frozen fixture JSON, not from either add-on implementation.

## Normalized contract and implemented rules

Both pure cores now expose the same smallest useful contract:

- equal-width/height, top-left-origin, row-major binary masks;
- `coloring_gap=true` means canonical Coloring alpha was exactly zero;
- `line_boundary=true` and `guide_boundary=true` mean impassable geometry;
- optional selection is a separate application scope, not geometry.

Krita calls this `DetectionGeometry`; CSP calls it `DetectionGeometry` with
`BinaryMask` members. Existing RGBA entry points explicitly normalize before
detection. Krita's named legacy conversion preserves its prior any-nonzero-alpha
Line/Guide acquisition rule. The normalized detector does not choose a faint or
anti-aliased raster threshold.

The implemented frozen decisions are:

| Decision | Phase 4 result |
| --- | --- |
| D-01 | inclusive `component_size <= threshold` |
| D-02 | reject every component touching the image boundary |
| D-03 | exact-zero Coloring membership only |
| D-04 | find full component/enclosure first; then intersect application with selection |
| D-05 | four-neighbor canonical/default connectivity |

CSP's explicit eight-neighbor option remains available as a named noncanonical
compatibility extension and is excluded from canonical fixture runs.

## Krita correction

The former two-class candidate map treated Guide-covered transparent pixels as
paintable `GapKind.GUIDE` components. Detection now subtracts both Line and Guide
boundaries from exact-zero Coloring membership and emits only ordinary
transparent components. Thus a lone Guide in open transparency is not a gap;
Guide-only and mixed Line/Guide rings can enclose a gap.

`GapKind.GUIDE` remains temporarily available only for existing manually-built
patch/model fixtures, preserving the unresolved ONNX target-Guide suppression
behavior for Phase 5. Patch extraction, inference, and postprocessing code were
not changed. `GapRegion.indices` remains full geometry and
`application_indices`/`target_indices` represents the optional selected subset.

## CSP correction and safety binding

The public detector, `SmartGapPropagation`, and `QuickFixPipeline` can now receive
normalized multi-layer geometry. The existing active-layer entry points delegate
through exact-zero Coloring normalization with empty Line/Guide masks. This makes
the pure architecture canonical without pretending that the current private
CELSYS adapter can acquire separate layers.

`GapCandidate.pixels` is full geometry; `applicationPixels` is the selected
subset (empty means the full set in whole-layer compatibility calls). Bounding
box, area, centroid, prediction, and review identity use full geometry, while
correction writes use only the application set. Candidate provenance now hashes
all three normalized masks in addition to the Phase 3 source, selection, and
settings binding. Output validation checks application uniqueness/subset/scope
without weakening opaque/stale/overlap checks.

The retained CSP alpha setting no longer broadens detector membership. It is
kept for settings/CLI compatibility and unchanged owner/prediction sampling.

## Traversal and cancellation

Both detectors use streaming row-run connected-component labeling. They retain
only previous/current row runs, active component summaries, and at most the
configured threshold of indices for a still-eligible component. Once a component
exceeds the threshold its indices are discarded, but its connectivity state is
continued until finalization, so an oversized component cannot be subdivided
into false small candidates. There is no image-sized flood-fill frontier.

Scanning and joins are linear in image pixels/runs. Retained lists merge by size,
bounding retained-index movement by O(emitted pixels log threshold); normalized
masks and returned candidates remain O(image pixels) in the worst case.
Cancellation is polled every row in both implementations, every 4096 C++
scan/join/aggregation operations, and every 4096 Krita run/join/aggregation
operations (plus the existing progress paths). Tests cover a completed and
interrupted 4096×4096 open transparent image and an adversarial checkerboard. In
this Linux environment the standalone Krita 4096×4096 completion took about 0.26 seconds
with 76,644 KiB maximum RSS. The complete Release C++ unit binary, including its
4096×4096 completion/cancellation and checkerboard cases, took 0.17 seconds with
118,272 KiB maximum RSS. These are pure Linux test-environment observations, not
Krita/CSP-host performance claims.

## Parity and prediction preservation

Neutral validation recomputes every stored detection variant. For 13 applicable
normalized cases, Krita and CSP independently match the exact frozen component
pixels, application pixels, bounds, floor centroids, ordering, and IDs. The
Phase 4 detection profile uses the already-frozen Guide-boundary variants by
explicit maintainer direction. The Phase 2 manifest still labels Guide detection
composition empirical, and ONNX Guide composition/suppression remains unresolved.

Prediction preservation is separated from intended candidate-set corrections:

- the neutral validator loaded ONNX Runtime 1.28.0 and reproduced the frozen
  model cases; the model hash remains unchanged;
- Krita's Phase 2 patch/tensor and postprocessing readers still pass, including
  the legacy manually-created target-Guide case;
- a CSP unit test feeds an unchanged one-pixel candidate through legacy and
  normalized paths and compares suggested color, confidence/band, owner, and
  diagnostics exactly;
- no prediction, rule-confidence, region, modal-color, or fallback-provenance
  production file changed.

## Final verification

All commands below completed successfully unless explicitly marked unavailable:

- Neutral: fixture validator; 9/9 reference tests.
- Web: 14/14 Node tests; ESLint; 30 preset-asset checks; 51 PNG plus 17
  documentation-image metadata checks; TypeScript/Vite production build; Task C
  exclusion checks.
- Krita: 21/21 pure/shared tests; Ruff; `compileall`; source ZIP build;
  `unzip -t`; 23-entry content listing including `unet32.onnx`.
- CSP Make: clean build; 41/41 unit/safety tests; all 38 Phase 2 historical rows
  accounted for (37 unchanged, D013 selected changed exactly to full geometry
  `[11,12,13]` and application `[12]`); 13/13 normalized parity cases; Phase 3
  CLI safety script; PNG E2E.
- CSP CMake: fresh Release configure/build; CTest 7/7; install; installed CLI
  help smoke.
- Sanitizers: fresh ASan/UBSan build and CTest 7/7 with
  `ASAN_OPTIONS=detect_leaks=0`; no sanitizer diagnostics.
- `git diff --check`: passed.

LeakSanitizer remains unverified: its `detect_leaks=1` run aborts with the known
“LeakSanitizer does not work under ptrace” environment error. Real Krita, real
CSP/CELSYS, Windows/MSVC, host layer acquisition, Preview/Undo, and host
cancellation were not available and are not marked passed.

## Frozen artifacts and remaining limits

- Fixture manifest SHA-256:
  `6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`.
- ONNX artifact SHA-256:
  `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`.
- No fixture expected value or model byte changed.

Known mismatches intentionally remain visible: Web/ML image-edge behavior,
Web's typed Guide candidates, ML's line-only Guide behavior, faint boundary
rasterization, ONNX Guide composition, semantic-region correspondence,
label-zero eligibility, modal tie behavior, CSP heuristic prediction/confidence,
and all real-host limitations from the audit. The current CSP shipping paths
still provide only the active Coloring raster to the new pure geometry API.

Phase 4's pure-core entry criteria for later Phase 5 work are satisfied. No
Phase 5 implementation was started, and this Phase 4 work was not committed.
