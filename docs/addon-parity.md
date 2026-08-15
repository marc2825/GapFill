# GapFill Phase 2 characterization and Phase 5 learned parity

Current phase: 5

Golden-corpus freeze: 2026-08-13 (Asia/Tokyo)

Phase 5 resolution: 2026-08-14 (Asia/Tokyo)

Phase 5 production baseline: `c52affd4816df7eeeea53985c3b39ba0c4e83b86`

## Phase 5 current learned-prediction result

The reviewed current contract is Line-only NCHW float32 input, canonical
straight-alpha RGBA-to-grayscale conversion, full-image four-connected Line
regions, positive painted-label eligibility, mean likelihood over all valid
region pixels, and exact modal RGB with first-row-major tie resolution. Guides
remain Phase 4 detection boundaries but do not enter the trained model tensor.

| Stage | Neutral | ML evidence | Web | Krita | CSP pure core |
| --- | --- | --- | --- | --- | --- |
| Boundary conversion | byte-exact 8-value oracle | inclusive grayscale 128 training rule | exact | exact | exact |
| Patch/tensor | 13 Line-only cases | 13/13 exact | 13/13 exact | 13/13 exact | M001 exact plus shared construction tests |
| ONNX artifact | 7/7 CPU, max delta 0 | frozen artifact | 7/7 WASM within unchanged tolerance | 7/7 CPU, max delta 0 | 7/7 CPU outputs drive C++ backend, max delta 0 |
| Region/color | 8 fixed maps | Line labels support the choice; historical label-0 bug retained as evidence | 8/8 exact | 8/8 exact | fixed maps/unit coverage plus integrated M001 exact |
| Integrated M001 | region 2, RGB `[20,20,240]`, mean `0.8431808595754662` | artifact output | same | same | same |
| D-07 | policy oracle | no product policy | explicit learned/fallback | explicit learned/fallback | `Learned`/`HeuristicFallback`; heuristic excluded from Apply-High |

The CSP row does not claim a shipping ONNX Runtime adapter. A local Python ONNX
Runtime 1.28.0 CPU path executes the pinned artifact and feeds the tested C++
backend boundary; native cross-platform runtime packaging remains a later gate.
Real Krita and CELSYS hosts remain unverified.

The Phase 2 tables below are preserved as the historical disagreement record.
Where they say “current,” read that as the Phase 2 snapshot unless a Phase 5
resolution explicitly supersedes it.

## Historical Phase 2 purpose and interpretation

This record compares the paper/manual interpretation, ML Python pipeline, web
reference, Krita pure engine, and CSP pure core on independently controlled
fixtures. It is a characterization report, not a majority vote. A passing
parity test means that an implementation still exhibits its audited behavior;
it does not make that behavior canonical.

The detailed canonical contract and remaining empirical decisions are in
`docs/addon-spec.md`.
Exact inputs and observations are in
`tests/fixtures/gapfill/parity/characterization.json`. Statuses mean:

- `AGREES`: all implementations that implement the stage agree with a stable
  expectation.
- `DELIBERATE_PLATFORM_DIFFERENCE`: a documented platform capability or scope
  difference explains the mismatch.
- `UNRESOLVED_SPECIFICATION`: evidence supports multiple plausible rules, so a
  product or empirical decision is still required.
- `CONFIRMED_IMPLEMENTATION_DIVERGENCE`: behavior conflicts with a stable rule
  or an implementation omits inputs required by that rule.

In this Phase 2 snapshot, “Unavailable” is not a pass and CSP had no learned
inference/postprocessing stage. None of these pure tests verifies a real Krita
or Clip Studio Paint host.

| Stage | Cases | Agrees | Platform difference | Unresolved | Confirmed divergence |
| --- | ---: | ---: | ---: | ---: | ---: |
| Detection | 19 | 5 | 1 | 5 | 8 |
| Patch/tensor construction | 13 | 11 | 0 | 2 | 0 |
| Exact ONNX artifact | 7 | 0 | 0 | 7 | 0 |
| Region/color postprocessing | 8 | 2 | 0 | 5 | 1 |

Canonical expectations are explicitly marked `STABLE` and `canonical: true`.
Historical or experimental alternatives such as strict threshold, edge allow,
and eight-connectivity remain explicitly named `NONCANONICAL_REFERENCE`
variants. Empirical alternatives remain unresolved; neither current majority
behavior nor a passing reader promotes them to truth.

## Frozen decision impact

| Decision | Canonical result | Current result and classification | Audit risk |
| --- | --- | --- | --- |
| `D-01` | accept sizes `<= T` | ML/Web/Krita/CSP agree | G-03 |
| `D-02` | reject image-edge components | ML/Web retain D003: confirmed divergence; Krita/CSP agree | G-03 |
| `D-03` | only Coloring alpha 0 is a gap | Phase 4 Krita/CSP normalized detectors agree; ML stage does not implement RGBA membership and the CSP compatibility setting no longer broadens detector membership | G-03 |
| `D-04` | analyze full geometry, then restrict application; clipped-only boundary is indeterminate/rejected | Phase 4 Krita/CSP pure detectors expose full component geometry plus an application subset; real CSP acquisition remains an unverified host limitation; ML/Web have no selection stage | G-03, C-10 |
| `D-05` | four-neighbor only | all defaults agree; optional CSP eight-neighbor mode is an intentional noncanonical extension | — |
| `D-06` | exact RGB mode; tie uses first row-major encounter | Phase 5 neutral/Web/Krita/CSP pure paths return red in R006; the former Krita sorted-lowest result is retained only as historical characterization | K-14 closed in pure path |
| `D-07` | explicit learned/fallback provenance; fallback confidence cleared, confirmation required, Apply-High excluded | Phase 5 Web/Krita/CSP carry provenance; CSP heuristic keeps only a diagnostic score and is excluded from every automatic/Apply-High path; ML has no product policy | K-11/C-02/C-03 pure-policy portions closed |

## Detection matrix

Abbreviations: `ML` is the checked-in Python pipeline; `Web` is the browser
reference; `Krita` is its pure engine; `CSP-W` is whole-image CSP; `CSP-S` is
selection-scoped CSP. Counts below are candidate component sizes, not colors.

| Case | ML | Web | Krita normalized | CSP normalized W / S | Status | Interpretation |
| --- | --- | --- | --- | --- | --- | --- |
| D001 enclosed 1 px | 1 | 1 | 1 | 1 / 1 | `AGREES` | Basic enclosed transparent component agrees. |
| D002 sizes T-1/T/T+1 | 2,3 | 2,3 | 2,3 | 2,3 / 2,3 | `AGREES` | D-01 freezes inclusive `<= T`; all current code agrees. |
| D003 image-edge 1 px | 1 | 1 | none | none / none | `CONFIRMED_IMPLEMENTATION_DIVERGENCE` | D-02 rejects the exterior-touching component; ML/Web retain it. |
| D004 exterior plus inner | inner 1 | inner 1 | inner 1 | inner 1 / inner 1 | `AGREES` | Large exterior is excluded by size; inner gap agrees. |
| D005 diagonal pair | 1,1 | 1,1 | 1,1 | 1,1 / 1,1 | `AGREES` | D-05 four-neighbor default agrees; optional CSP eight-neighbor mode is noncanonical. |
| D006 Line Art enclosure | 1 | 1 | 1 | 1 / 1 | `PURE_CORE_AGREES` | Both add-on cores now accept normalized Line boundaries; the shipping CSP host path still supplies no Line mask. |
| D007 Guide enclosure | none | 1 | 1 | 1 / 1 | `PHASE4_DETECTION_PROFILE` | By explicit Phase 4 direction, add-on detection selects the frozen `guide_as_boundary` variant. The manifest and ONNX Guide policy remain empirical. |
| D008 lone Guide in open area | none | Guide 1 | none | none / none | `ADDON_DETECTION_CORRECTED` | Guide is a boundary, not a one-pixel paintable component. Web remains divergent. |
| D009 Guide stroke to exterior | none | Guide 3 | none | none / none | `ADDON_DETECTION_CORRECTED` | Boundary composition leaves only open exterior geometry; Web's typed candidate remains divergent. |
| D010 mixed Line/Guide enclosure | none | 1 | 1 | 1 / 1 | `PHASE4_DETECTION_PROFILE` | Add-on detection uses combined normalized boundaries; ML training still does not settle model-input semantics. |
| D011 alpha 0/1/127/254/255 | all five | only 0 | only 0 | only 0 / only 0 | `ADDON_PURE_CORE_AGREES` | D-03 accepts only alpha 0. ML receives a prepared mask rather than implementing RGBA membership. |
| D012 gray 0/127/128 | 1 | 1 | legacy RGBA: 1 | normalized input required | `RASTERIZATION_UNRESOLVED` | The detector consumes a binary boundary; ML grayscale and current Krita any-alpha conversions remain separate empirical policies. |
| D012 gray 129/254 | none | 1 | legacy RGBA: 1 | normalized input required | `RASTERIZATION_UNRESOLVED` | Phase 4 deliberately does not promote either faint-line conversion to canonical. |
| D012 gray 255 | none | none | none | normalized input required | `RASTERIZATION_UNRESOLVED` | An absent normalized boundary agrees; host conversion remains outside detector semantics. |
| D013 selection clips gap | whole: 3 | whole: 3 | geometry: 3 / apply: 1 | geometry: 3 / apply: 1 | `ADDON_PURE_CORE_AGREES` | D-04 now finds `[11,12,13]` before restricting application to `[12]`; a clipped-only host must still reject as indeterminate. |
| D014 selection contains gap | whole: 1 | whole: 1 | geometry/apply: 1 | geometry/apply: 1 | `ADDON_PURE_CORE_AGREES` | Full geometry and selection application agree. |

The current ML detector is an executable preprocessing reference, not a full
paper implementation: it is given a prepared binary mask and does not itself
distinguish Coloring, Line Art, and Guide layers. Phase 4 gives Krita and CSP the
same normalized pure geometry contract and exact candidate sets for the tested
profile. The current CSP CLI/private adapter still supplies Coloring only, so the
pure-core Line/Guide results are not a real-host support claim.

## Patch and tensor matrix (Phase 2 snapshot, superseded for prediction)

| Fixture family | ML | Web | Krita | CSP | Status |
| --- | --- | --- | --- | --- | --- |
| P001/P002 floor centroid | exact match | exact match | exact match | unavailable | `AGREES` |
| P003 all 8 edges/corners | exact 32x32 side-specific zero padding | exact match | exact match | unavailable | `AGREES` |
| P004 target gap channel | exact sparse target pixels | exact match | exact match | unavailable | `AGREES` |
| P005 one Guide pixel | Line Art only | Line Art OR Guide | Line Art OR Guide | unavailable | `UNRESOLVED_SPECIFICATION` |
| P006 Guide on target | target remains in channel 1 | target Guide pixel suppressed | target Guide pixel suppressed | unavailable | `UNRESOLVED_SPECIFICATION` |

The stable tensor shape is NCHW float32 `[1,2,32,32]`, with the centered target
at patch `(16,16)` and output `[1,1,32,32]`. Phase 5 resolves P005/P006 for
runtime prediction in favor of the `training_line_only` variant: Guides are not
ORed into channel 0 and no target-Guide suppression is performed. The table
retains the former implementations as historical evidence.

## Exact ONNX artifact parity

Seven fixed tensors freeze meaningful model behavior: no Guide, a one-pixel
Guide delta, symmetric and asymmetric geometry, boundary-near geometry, and a
target Guide pixel both present and suppressed. Each fixture stores all 1024
float32 output values plus a byte-level float32 SHA-256. The pinned artifact is
`web/public/models/unet32.onnx`, SHA-256
`8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`.

Python ONNX Runtime 1.28.0 CPU reproduced the stored outputs exactly. Web
`onnxruntime-web` 1.22.0 WASM reproduced them at `atol=1e-6`, `rtol=1e-5`; the
largest observed absolute difference was `1.2516975402832031e-6`. Phase 5 adds
direct seven-output checks through Krita's validated wrapper and the local CSP
parity runner. The C++ learned path receives the exact output through its small
backend interface; its shipping `OnnxPredictorStub` now fails explicitly rather
than silently invoking the rule predictor.

The numeric values remain artifact characterization, not accuracy truth.
Line-only cases are canonical runtime inputs; Guide-composed cases remain
out-of-distribution sensitivity evidence. Sensitivity is confirmed:

- adding one Guide pixel changes all 1024 values (max delta
  `0.2567824125`, mean delta `0.0444267020`);
- suppressing a target-overlapping Guide pixel changes all 1024 values (max
  delta `0.2577674389`, mean delta `0.0613388440`).

The extended A-G characterization also observes maximum pairwise deltas of
`0.6486428082` for Guide closure, `0.6038002372` for isolated Guide geometry,
and `0.8656817973` for mixed Line/Guide closure. The mixed case changes the
fixed red/blue winner. None of that establishes Guide inputs as trained.

## Region and color postprocessing matrix (Phase 2 snapshot)

All probabilities below are fixed, human-readable fixture values. CSP's owner
segmentation observations are recorded where useful, but CSP has no equivalent
learned region-likelihood stage.

| Case | ML | Web | Krita | CSP | Status |
| --- | --- | --- | --- | --- | --- |
| R001 manual mean winner | region 2, blue | same | same | unavailable | `AGREES` |
| R002 label 0 high | label 0, black | label 1, green | label 1, green | unavailable | `UNRESOLVED_SPECIFICATION` |
| R003 disconnected same RGB | line region 1, red | colored region 2, red | same as Web | unavailable | `UNRESOLVED_SPECIFICATION` |
| R004 tolerance 29/30/31 | line region 1, black | colored region 2, red 31 | same as Web | one transitive owner | `UNRESOLVED_SPECIFICATION` |
| R005 0/20/40 color chain | line region 1, red 0 | colored region 2, red 40 | same as Web | one transitive owner | `UNRESOLVED_SPECIFICATION` |
| R006 modal tie | first encounter, red | first encounter, red | sorted-lowest, blue | unavailable | `CONFIRMED_IMPLEMENTATION_DIVERGENCE` |
| R007 anti-aliased modal | `[100,120,140]` | same | same | unavailable | `AGREES` |
| R008 line vs colored regions | line region, red | colored region, blue | same as Web | unavailable | `UNRESOLVED_SPECIFICATION` |

Phase 5 selects Line-derived full-image labels and excludes label 0. Positive
labels need at least one painted pixel; all valid labeled pixels, including
alpha-zero gaps, participate in the mean; only alpha-positive pixels vote for
the RGB mode. Equal means and equal modal counts retain first row-major
encounter. Under that contract R001-R008 select respectively: `2/blue`,
`1/green`, `1/red`, `1/black`, `1/red-0`, `1/red`, `1/[100,120,140]`, and
`1/red`. Neutral, Web, and Krita match all eight; CSP independently covers the
same scoring/tie invariants and its integrated M001 result matches exactly.
Color tolerance and CSP owner transitivity are no longer learned-region
semantics; they remain properties of the explicitly labeled heuristic.

## Selection and fallback policy contracts

These rules use small hand-reviewed contracts instead of artificial image
oracles. Exact inputs and outputs are in `policy/cases.json`.

| Case | Canonical result | Current implementation status |
| --- | --- | --- |
| MP001 modal participation | pixels `[1,2,4]` vote once; alpha-zero, explicit exclusion, and out-of-region pixels do not; RGB is blue | contract coverage for D-06 participation; current tie mismatch remains isolated in R006. |
| S001 full geometry then selection | component `[11,12,13]` is enclosed; only `[12]` is eligible for application | Phase 4 Krita/CSP normalized pure detectors agree exactly; ML/Web do not implement selection scope. |
| S002 clipped acquisition boundary | geometry is indeterminate; reject; selection did not create enclosure | CSP's conservative rejection agrees for this conditional host limitation; real CSP acquisition remains unverified. |
| S003 selection excludes enclosed gap | geometry remains enclosed, but application set is empty | Phase 4 add-on detectors omit it from processing/output without changing the geometry verdict. |
| F001 learned High | provenance `learned`; remains Apply-High eligible | Phase 5 Web/Krita/CSP result contracts carry learned provenance; CSP classifies and auto-applies only this source. |
| F002 fallback High-like, unconfirmed | provenance `fallback`; effective learned confidence is null; Apply-High false; manual apply false | Phase 5 Web/Krita tag it and clear learned confidence; CSP keeps the heuristic score separately and leaves it Unreviewed. |
| F003 fallback High-like, confirmed | manual apply true after explicit confirmation; learned confidence stays null and Apply-High stays false | CSP permits an explicit per-gap decision without admitting the fallback to bulk High logic; Web/Krita application gestures are explicit user actions. |

## End-to-end review material

The corpus includes three synthetic artworks and two crops from the repository's
Ex2 material. The real crops pin source hashes and rectangles:

- `E101_ex2_ordinary_crop`, crop `[426,84,458,116]`;
- `E102_ex2_guide_crop`, crop `[521,384,553,416]`.

Their annotations identify the visible target and supporting layers. They do
not contain automatically inferred canonical masks or colors. The completed
Coloring images are review evidence, not a truth oracle.

## Phase 2 verification record

The following checks were run on 2026-08-13 against baseline commit
`30c7f02b698e8a9d61bc1a4e866fa5d8d7e8bfe5` plus the Phase 2 documentation,
fixtures, and read-only test infrastructure:

- the generator was run twice; `manifest.json` remained
  `6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`;
- neutral validation passed, including fixture hashes/provenance, independent
  detection/patch/postprocess/policy recomputation, frozen characterization
  status checks, and seven exact ONNX runs;
- nine neutral reference unit tests passed, including direct D-01 through D-07
  contract checks;
- the Python characterizer matched 19 ML/Krita detection observations, all 13
  patch cases, all eight postprocess cases, and seven model outputs with maximum
  absolute delta 0;
- the full web suite passed 14/14 files with no skips; ESLint, preset-asset and
  metadata checks, TypeScript, and the production Vite build also passed;
- the Krita pure suite plus shared reader passed 16/16; Ruff passed for the
  plugin, neutral scripts, and shared reader; compile-only syntax validation and
  a 23-entry source ZIP build/integrity/content check also passed;
- Make passed the 25/25 CSP core tests, 38 explicitly non-golden CSP detection
  scope/case rows across all 19 cases, and PNG CLI end-to-end verification;
- Release CMake configure/build and CTest passed 5/5, including the shared CSP
  reader and PNG chain;
- ASan/UBSan Debug CTest passed 5/5 with no diagnostics. Leak detection was
  disabled because the audit environment runs under ptrace, so LSan remains
  unverified;
- `git diff --exit-code 30c7f02 -- web/src/utils ml/src
  krita-plugin/pykrita csp-plugin/src` passed, confirming no production
  implementation subtree changed.

The exact reproduction commands and dependency versions are recorded in
`docs/addon-spec.md`; CI now runs the neutral validator/characterizer as well as
the Web, Krita, and CSP readers.

## Gaps deliberately left open after Phase 5

- Guide detection is fixed as a Phase 4 boundary rule, while the canonical
  model input is Line-only. Whether a future retrained model should consume
  Guides remains a model-research question; current Guide-composed outputs are
  sensitivity evidence only.
- The normalized RGBA-to-boundary conversion is fixed, but real host rendering,
  profiles, masks, blend modes, premultiplication, and layer visibility remain
  unsettled host inputs.
- Exact ONNX outputs and pure region/RGB parity are frozen. They do not establish
  model accuracy, confidence calibration, or acceptable behavior on real art.
- No real Krita canvas, color-management, selection/undo, overlay, transform,
  cancellation, or packaging behavior is verified here.
- No real CSP SDK adapter, preview, selection, cancellation, writeback, or Undo
  behavior is verified here.
- No accuracy/calibration claim is made from seven fixed model tensors.
- No heuristic score is accepted as learned confidence or Apply-High input.
- No unresolved fixture has been converted into a canonical expectation merely
  to make all implementations pass.

The Phase 5 pure learned-prediction entry criteria are satisfied by the current
validation record in `docs/addon-phase5.md`. Phase 6 remains separately scoped
host work and was not started here.

## Phase 6 Krita host status

Phase 6 preserves every pure result above. Its immutable snapshot boundary and
fake/Qt tests establish testable acquisition, staleness, generation, conversion,
mutation-readback, and fail-closed overlay contracts, but no real Krita
installation was available. Consequently pure-to-adapter tests are PASS while
host acquisition, canvas/UI, profile conversion, native mutation, selection,
and Undo parity are all UNTESTED. The exact A–V matrix and generated `.kra`
recipes are under `krita-plugin/host_tests`; the full record is
`docs/addon-phase6.md`.

For E102, Phase 6 host parity remains the frozen near-white prediction
`[243,242,239]`; the completed-art yellow is a separate accuracy observation.
No host-layer change altered a semantic golden or the ONNX artifact.
