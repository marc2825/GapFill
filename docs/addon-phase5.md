# Add-on Phase 5 — learned prediction and region/color correspondence

Date: 2026-08-14 (Asia/Tokyo)

Branch: `fix/addon-learned-prediction`

Baseline: `c52affd4816df7eeeea53985c3b39ba0c4e83b86`

This phase resolves G-01, G-02, G-04, G-05 and implements the prediction parts
of frozen D-06/D-07. It does not change Phase 4 detection decisions D-01 through
D-05, Phase 3 data-safety policy, host mutation/Undo, overlay/view mapping,
stale-scan lifecycle, color-profile handling, the private CELSYS adapter, native
Preview/Undo, release packaging, broad UI, broad performance, model weights, or
training data. Phase 6 was not started. No commit was created.

## Baseline and fail-first record

The starting worktree was clean on the branch and baseline above; `git
diff --check` passed. The frozen fixture manifest was
`6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`.
The ONNX artifact was 24,697,438 bytes with SHA-256
`8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`.

Before production changes, the established gates passed as follows:

- neutral validation and 9/9 reference tests passed; the stage-specific 13
  patch, seven model, and eight postprocess characterizations passed. The old
  all-stage Phase 2 characterizer retained its known post-Phase-4 D008 mismatch
  because that file freezes the former Krita detection snapshot;
- Web passed 14 test files, ESLint, 30 preset-asset checks, 51 PNG plus 17 docs
  metadata checks, and the production build/Task-C exclusion checks;
- Krita passed 21 pure/shared tests, Ruff, compile-only syntax checks, and the
  23-entry source ZIP build/integrity/content check;
- CSP passed its 41-test Make/core/safety set, the Phase 3 CLI safety suite,
  Phase 4 13/13 normalized parity, PNG E2E, Release CMake/CTest 7/7, install, and
  installed-CLI help smoke;
- ASan/UBSan CTest passed 7/7 with leak detection disabled. LSan remained
  unavailable because the environment runs under ptrace.

New tests were then placed before their production APIs. Web could not import
the canonical boundary/tensor/Line-region functions, Krita could not import its
canonical learned helpers, and the CSP probe could not compile because the
backend/learned-predictor types did not exist. Provenance tests also exposed the
existing untagged CSP rule score and automatic High application. These were the
expected Phase 5 fail-first conditions; no frozen expected value was edited.

## Reconstructed pipeline

| Stage | ML training/inference evidence | Former Web/Krita/CSP behavior | Phase 5 canonical behavior |
| --- | --- | --- | --- |
| Source raster | grayscale Line Art plus painted image/Line labels | Web/Krita logical RGBA; CSP active Coloring only | logical byte RGBA Coloring and Line snapshots; host conversion remains separate |
| Boundary | OpenCV inverse binary threshold at 128 | Web/Krita any alpha; CSP learned stage absent | fixed luma, straight-alpha over white, inclusive `<=128` |
| Guides | absent from `create_region_patches` | Web/Krita ORed Guides and could suppress target Guide; CSP absent | excluded from model; retained as Phase 4 detection boundaries |
| Target mask | exact selected region label | exact gap pixels, with former Guide special case | exact full canonical gap pixels, no Guide special case |
| Center/crop | floor mean; virtual origin `center-16`; side-specific zero padding | Web/Krita already matched; CSP absent | same in all pure paths |
| Tensor | HWC two-channel then float32 NCHW `[1,2,32,32]` | Web/Krita same layout with different channel 0; CSP absent | channel 0 Line boundary, channel 1 target, binary float32 NCHW |
| Model interface | `input_mask` -> `nearest_region_mask` | incomplete validation; CSP stub | exact count/name/type/shape/hash checks and output validation |
| Region identity | full-image Line-derived labels cropped to patch | opaque Coloring RGB-tolerance components; CSP owners | full-image four-connected Line fill labels, cropped with zero padding |
| Eligibility | helper accidentally included label 0 | Web/Krita positive painted components | positive label with at least one alpha-positive Coloring pixel |
| Score | arithmetic mean of likelihood in label | arithmetic mean in colored component | float64 mean over every valid pixel in eligible label, including gap pixels |
| Winner tie | first iteration | implementation-dependent across paths | first label encountered row-major |
| Color | exact modal region color | Krita used sorted `np.unique`; CSP heuristic averaged buckets | exact RGB among alpha-positive pixels; D-06 first row-major tie |
| Failure | research script logs/skips | partial/unmarked fallback possible | explicit provenance, systematic failure, and atomic batch/cancel rules |

The ML postprocessing helper's label-0 inclusion is a real implementation bug:
label 0 is the Line/padding background, not a painted semantic region. The
historical helper stays in the Phase 2 characterizer; the Phase 5 reference path
corrects it without changing training or model bytes.

## G-02 — Guide experiment and policy

All comparisons use the exact checked-in model, the same target channel, and
inputs differing only at the stated channel-0 geometry. Fixed Line-derived left
red/right blue labels make region/RGB changes visible.

| Controlled comparison | Changed outputs | Maximum delta | Mean delta | Left -> right winner |
| --- | ---: | ---: | ---: | --- |
| A no Guide vs B ordinary Guide pixel | 1024/1024 | `0.2567824125` | `0.0444267020` | blue -> blue |
| C target Guide retained vs D suppressed | 1024/1024 | `0.2577674389` | `0.0613388440` | blue -> blue |
| E open Line ring vs Guide-completed closure | 1024/1024 | `0.6486428082` | `0.0777805308` | blue -> blue |
| F no geometry vs isolated/open Guide pixel | 1024/1024 | `0.6038002372` | `0.0943574822` | blue -> blue |
| G partial Line vs mixed Line/Guide closure | 1024/1024 | `0.8656817973` | `0.3938044994` | red -> blue |

The artifact is sensitive to Guide pixels, but sensitivity is not evidence that
they were present in training. The training patch code supplies Line Art only.
The canonical model policy is therefore Line-only, with no target-Guide
suppression. Guide-composed tensors are documented as characterized
out-of-distribution extensions. Retraining was not needed because the artifact
is usable under its actual training contract. This decision does not weaken the
separate Phase 4 rule that Guides are detection boundaries.

## G-05 — normalized boundary conversion

For logical straight-alpha byte RGBA, every runtime uses:

```text
luma = (4899*R + 9617*G + 1868*B + 8192) >> 14
over_white = (luma*A + 255*(255-A) + 127) // 255
boundary = over_white <= 128
```

The controlled sequence absent, alpha-1 black, opaque gray 127, 128, 129,
opaque black, alpha-126 black, and alpha-127 black yields
`0,0,1,1,0,1,0,1`. This matches the training threshold in normalized byte
space and replaces model-time `alpha > 0`. It does not change Phase 4 detector
masks. Krita/Web profile conversion, layer rendering, masks, blend modes, and
premultiplication remain real-host Phase 6 questions.

## G-01 — canonical regions, scoring, and D-06

The model was trained to predict a Line-derived nearest-region mask. Phase 5
therefore labels the full fillable inverse of the canonical Line boundary with
four-connectivity, assigning positive IDs at first row-major encounter. Labels
are cropped into the same virtual 32x32 window; Line and padding remain 0.

Label 0 is excluded. A positive label is eligible only if at least one valid
pixel has Coloring alpha `1..255`. Its score is the float64 arithmetic mean of
all valid output values assigned to the label; transparent gap pixels
participate because the learned target is the complete semantic-region mask.
Nonfinite or out-of-range model output rejects the complete result. Empty or
unpainted-only labels are skipped. Equal scores preserve first-row-major label
order.

A fillable component connected to the image exterior receives an ordinary
positive Line-region label and follows the same painted eligibility rule. That
postprocessing identity is separate from D-02's rejection of an open target gap.

Only alpha-positive pixels in the winning region vote for color. Each votes
once using exact RGB; equal maximum counts select the first tied RGB encountered
in row-major image order. No RGB sorting, tolerance, transitive chain, or
unordered-container order participates. Neutral, Web, Krita, and C++ tests agree
on all eight fixed maps and the explicit 2x2 red/blue tie.

## G-04 — artifact and semantic parity

The frozen artifact contract is:

| Field | Value |
| --- | --- |
| SHA-256 / bytes | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78` / 24,697,438 |
| Producer / IR / opset | PyTorch `2.12.0+cu130`; IR 10; default-domain opset 18 |
| Input | `input_mask`, `tensor(float)`, `[1,2,32,32]` |
| Output | `nearest_region_mask`, `tensor(float)`, `[1,1,32,32]` |
| Reviewed runtime | ONNX Runtime 1.28.0 CPU on Linux/WSL2 x86-64 |
| Tolerance | frozen `atol=1e-6`, `rtol=1e-5` |

The model sidecar now accurately says Line-only; its SHA-256 is
`2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5`.
It also records the model SHA-256, and the exporter reproduces the same policy
and integrity field. Model bytes and all frozen semantic files remain unchanged.

| Fixture | Frozen float32 output SHA-256 |
| --- | --- |
| M001 | `f6803fa3410932809e07332311c2c467789a01a8f7cf83a82018ba15be936dc1` |
| M002 | `873e4fae797e2717002bdc15c25dec22b1ec59631528072f0f000016e8c8d0fa` |
| M003 | `be36bb97c83a2591b96aa6d55461f671c9f583a0c9a7df194c4b8265a9c17d01` |
| M004 | `368002c4d1c960646bad70be1a8fcb4f7f1c020251904f237f0defad13eca398` |
| M005 | `d74d60858f443a7c7fbb7d965e43c784fae51e0a255c4ca6774c9378aa9d9d1b` |
| M006 | `b8087455928ac3687b914a6792d25203cf94cd77a398208898d9b195d3caa7f8` |
| M007 | `f6803fa3410932809e07332311c2c467789a01a8f7cf83a82018ba15be936dc1` |

Python/Krita CPU reproduces all seven at maximum delta 0; Web WASM stays within
the unchanged tolerance. The CSP parity runner executes the same artifact with
local Python ONNX Runtime, passes its output through the C++ backend, and matches
the C++ tensor, M001 region 2, RGB `[20,20,240]`, learned provenance, and mean
`0.8431808595754662`.

## Krita result and D-07 behavior

The pure engine now builds canonical Line-only tensors, validates the model
hash/count/names/types/shapes and output count/type/shape/finite/range, uses
full-image Line labels, and implements the canonical score/modal rules. A
zero-gap batch returns before model load. Missing, corrupt, or incompatible
models fail the batch. Isolated per-gap exceptions may use greedy fallback only
after at least one learned result succeeds. Every result carries provenance and
nullable learned confidence; an all-fallback batch fails. Prediction fields are
attached only after the complete batch succeeds.

ONNX Runtime inference is synchronous and is not claimed cancellable mid-call.
Cancellation is checked before/after load, before/after each inference, between
gaps, and before the final atomic metadata attachment. No Krita worker,
controller, overlay, or mutation code changed.

## CSP learned architecture and D-07 behavior

`LearnedGapPredictor` is a host-independent semantic pipeline around
`InferenceBackend`. The backend reports artifact hash, one input/output,
names, shapes, and types and synchronously accepts/returns float arrays. The
predictor constructs Line-only patches, validates outputs, scores full-image
Line labels, and returns `Learned` provenance, region label, modal color, and
winning mean. Results accumulate privately and are returned only after a final
cancellation poll.

The public `OnnxPredictorStub` remains an explicit unavailable distribution
adapter. CLI/host ONNX requests now fail clearly instead of silently switching
algorithms. Local Python ONNX Runtime plus a reference backend provides real
Phase 5 artifact execution and semantic parity; cross-platform native ONNX
Runtime packaging remains Phase 8 work.

The former rule predictor remains `HeuristicFallback`. Its existing bucketed
color and score are intentionally unchanged, but the score is stored only as
`heuristicScore`. Learned confidence is null, effective confidence/band is
cleared to Low, default Apply is false, and ReviewSession/Quick Fix/Apply-High
exclude it. It can be applied only by an explicit per-gap decision. Manifests and
dialog data expose provenance, learned confidence, heuristic score, and semantic
region label separately.

## Failure and cancellation contract

- No gaps: do not initialize/load a model or do owner/region work.
- Missing/load/hash/interface failure: fail visibly; do not substitute a batch
  of heuristic results.
- Invalid shape/type/count, nonfinite, or out-of-range output: reject the batch.
- One isolated gap failure: Krita may use visibly tagged fallback only when the
  batch also contains a learned success; CSP's pure learned predictor is atomic
  and fails the batch.
- Cancel before load, between gaps, immediately before/after inference, or
  before return: publish no partially labeled batch.
- A synchronous runtime call cannot be interrupted; the next poll is the first
  cancellation boundary.

## Production diff classification

At handoff the uncommitted Phase 5 worktree contains 52 modified tracked paths
and five new paths. They are confined to the neutral/ML model contract,
Web/Krita/CSP pure prediction and provenance paths, focused tests/probes,
test/CI registration, and the documentation named in this record.

- Canonical model-input/boundary conversion: neutral reference, Web ONNX
  utilities, Krita patches, and CSP learned predictor.
- Canonical region correspondence/scoring/modal color: neutral, Web, Krita, and
  CSP pure prediction paths.
- Learned backend/model integrity: Krita validation, CSP backend boundary, model
  sidecar/export metadata, and parity runners.
- Provenance/fallback: Web/Krita result data and CSP prediction/review/manifest
  data; CLI/host explicit unavailable errors.
- Mechanically necessary adaptation: CSP pipeline optional Line/Guide pointers,
  explicit-decision E2E fixture, build/test/CI registration.

No canonical detection source, Phase 3 path/snapshot/rollback policy, Krita host
mutation/Undo, Krita overlay/view/profile/controller code, CELSYS adapter source,
CSP Preview/Undo, release workflow/package builder, model weights, or frozen
fixture expected value changed.

## Final verification

The final local matrix passed unless explicitly marked unavailable:

- Neutral/reference: fixture/provenance validator; 15/15 unit tests; Phase 5
  characterization with eight boundary values, 13 Line-only patch cases, eight
  postprocess cases, five A-G Guide comparisons, and seven ONNX outputs at
  maximum delta `0.0`. A temporary exporter run reproduced the checked-in
  sidecar byte-for-byte at SHA-256
  `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5`.
- Web: all 15 Node test files passed with no skips, including seven WASM model
  outputs, 13 canonical tensors, eight canonical fixed maps, and integrated
  M001 region/RGB; ESLint passed; 30 preset assets, 51 preset PNG metadata
  records, and 17 documentation images passed; TypeScript/Vite production build
  passed; Task C and its forbidden asset reference were absent; built model was
  present.
- Krita: all 31 pure/shared tests passed, including Phase 2 history, Phase 4
  detection, Phase 5 model/tensor/region/RGB/fallback/cancel coverage; Ruff and
  `compileall` passed. The source ZIP built at
  `/tmp/gapfill-krita-phase5.zip`, contained exactly 23 entries including the
  pinned model/sidecar, and passed `unzip -t`; its final SHA-256 was
  `d0f0b3b4c4979520fa4a29964ee85c5b7dc678c799d1c90abdc8f2ba68ec45e7`.
- CSP Make: clean warning-enabled C++20 build passed; 48/48 unit tests passed;
  37/38 Phase 2 historical rows were retained with only the already-approved
  Phase 4 D013 change; Phase 4 normalized detection passed 13/13; Phase 3 CLI
  safety passed; Phase 5 passed 7/7 ONNX outputs plus exact C++ tensor,
  region/RGB/provenance at maximum delta `0.0`; PNG E2E passed with an explicit
  per-gap Apply decision.
- CSP CMake: fresh Release configure/build passed with GNU 13.3 and CMake
  4.4.2; CTest passed 9/9, including Phase 3, Phase 4, and Phase 5; install
  passed; the installed CLI help advertised learned-only Apply-High and an
  unavailable native ONNX adapter; an installed-CLI PNG create/apply/verify
  smoke passed.
- Sanitizers: fresh ASan/UBSan Debug build and CTest passed 9/9 with
  `ASAN_OPTIONS=detect_leaks=0` and no diagnostics. LeakSanitizer remains
  unverified: `detect_leaks=1` aborted before a usable result with
  “LeakSanitizer does not work under ptrace.”
- Integrity/diff: model SHA, frozen manifest SHA, and every frozen fixture/model
  byte remained unchanged; canonical Krita/CSP detector sources have no diff;
  `git diff --check` passed.

The local commands mirror the updated CI matrix, but no remote GitHub Actions
run was triggered. Real Krita, real CSP/CELSYS, Windows/MSVC, host
mutation/Preview/Undo, profile management, native CSP model packaging, and host
cancellation were not available and are not marked passed.

## Remaining questions and Phase 6 gate

The seven tensors prove artifact and runtime parity, not accuracy or confidence
calibration. Guide-composed inference remains out-of-distribution. Real-art
semantic accuracy, a learned-confidence reliability study, host-specific
render/profile bytes, and native runtime availability remain open.

An audit-only run of the final pure Krita pipeline over the five end-to-end PNG
cases produced one detected/predicted gap per case. E001 selected its reviewed
red `[210,30,40]` at mean `0.860601157`; the intentionally unresolved E002 and
E003 cases selected green `[30,190,70]` at `0.536231834` and red `[220,30,30]`
at `0.524894037`. E101 selected `[251,98,115]` at `0.913528784`, exactly matching
the completed Coloring pixels at all three detected indices (and exposing a
conflict with the older annotation's word "yellow"). E102 selected
`[243,242,239]` at `0.829399342`, while its completed Coloring pixel is
`[251,239,153]`. These observations are deliberately not promoted to frozen
model-accuracy oracles; E102, Guide-associated correspondence, the E101 prose
annotation, and whether winning-region means are reliable confidence signals
need human/art-set review.

The Phase 6 entry criteria are satisfied: the pure learned contract is reviewed,
implemented, documented, and green without model/golden drift. This is only
permission to begin a separately authorized host phase, not a release-readiness
claim. Phase 6 is still required before a Krita host claim; native CSP
additionally needs later layer acquisition, SDK qualification, and runtime
packaging. Phase 6 was not started.
