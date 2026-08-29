# OFFF Development Handoff

> **NEW THREAD START**
>
> Repository: `/home/marc2825/GapFill`
> Frozen GapFill release: `0c30afce131f330b4f0cc10ac0cf54c21b1c72b2`
> Frozen tag: `krita-v1.0.0` (do not move or amend)
> Published release: `https://github.com/marc2825/GapFill/releases/tag/krita-v1.0.0`
> GapFill 1.0.0 is frozen; do not opportunistically change it for OFFF.
> OFFF history is on `feature/overflow-floodfill` at `0caa23c658e6c589b8ff1ea0ed4a1ae9fa2a5043`.
> Inspect that branch read-only; do not merge, rebase, or cherry-pick it yet.
> Read its spec with `git show feature/overflow-floodfill:web/docs/OVERFLOW_FLOOD_FILL_SPEC.md`.
> Existing OFFF code is a web prototype, not a qualified Krita implementation.
> Frozen GapFill model channel 0 is Line-only; Guides affect detection topology only.
> Historical OFFF specifies model channel 0 as Line Art / Guides.
> `SEMANTIC DECISION REQUIRED BEFORE SHARING MODEL INPUT INFRASTRUCTURE`.
> First task: read-only OFFF spec-vs-code gap analysis and OFFF v1 semantic freeze.
> Prefer a new branch from the frozen release and selective reconstruction after that freeze.
> Keep GapFill and OFFF independently testable; later qualify coexistence in a real host.
> Do not begin implementation until the semantic and integration plans are reviewed.

## 1. Why this document exists

This is the durable boundary between the completed GapFill 1.0.0 release and
future Overflow Flood Fill (OFFF) development. It records enough repository
evidence to restart in a new thread without relying on prior conversation or
temporary qualification files.

This document is not an OFFF specification freeze, an integration approval, or
evidence that OFFF is release-ready. It describes the historical prototype,
marks unresolved decisions, and defines a safe restart sequence.

## 2. Frozen GapFill 1.0.0 baseline

| Item | Frozen identity |
| --- | --- |
| Release commit | `0c30afce131f330b4f0cc10ac0cf54c21b1c72b2` |
| Commit subject | `ci(krita): publish frozen GapFill 1.0.0 artifact` |
| Annotated tag | `krita-v1.0.0` |
| Tag object | `4e119534e1fc0e9a9ccd9702458098c0e55b8bdc` |
| Tag target | `0c30afce131f330b4f0cc10ac0cf54c21b1c72b2` |
| GitHub Release | [GapFill 1.0.0](https://github.com/marc2825/GapFill/releases/tag/krita-v1.0.0), ID `379020840` |
| Production asset | `gapfill-krita-windows-x86_64.zip`, asset ID `535364662` |
| Asset SHA-256 | `7001c1bf92aa7abb5840baf52fe07457ab06cb80074297488e67ded212ab74e2` |
| Qualified platform | Windows x86_64 only |

The published asset was verified byte-for-byte against the frozen repository
artifact. Linux and macOS are not qualified GapFill 1.0.0 release artifacts.
Documentation commits after the release do not move the tag or alter this
baseline.

**Freeze boundary:** GapFill 1.0.0 is frozen. OFFF development must not
opportunistically modify its production behavior. Any future GapFill production
change requires an explicit reason, a separate regression analysis, a Phase 6.5
and release-impact review, and coexistence testing. Prefer an independent OFFF
mode, adapters, and genuinely neutral shared infrastructure.

## 3. GapFill frozen semantics

The canonical GapFill contract remains defined by `docs/addon-spec.md`. The
following distinctions are especially important for OFFF work:

- Model input channel 0 is **Line-only**.
- Guides affect **detection topology only**; Guides are not part of the trained
  GapFill model input.
- Detection uses canonical four-neighbor connectivity.
- An eligible gap is enclosed, has `component_size <= threshold`, does not touch
  the image edge, and is transparent in Coloring (`alpha == 0`).
- The model input is the frozen two-channel 32×32 tensor; channel 1 identifies
  the target gap.
- Learned prediction, fallback provenance, Line-derived semantic regions,
  label-zero exclusion, region scoring, and representative modal RGB/tie rules
  are frozen GapFill semantics.

Do not reinterpret these rules, import obsolete branch-era GapFill wording, or
change GapFill to make OFFF integration easier.

## 4. GapFill qualification and release limitations

Phase 6.5 is **CLOSED** with authoritative host status:

```text
A-P PASS
Q   ROW_Q_HOST_CONDITION_UNAVAILABLE
R-V PASS
```

Qualification boundaries that must remain accurately stated:

- Row Q did not obtain a real HiDPI host condition.
- Row V qualified the worker-active path
  `docker.close() -> closeEvent() -> controller.shutdown()`; full Krita
  application close with an active worker was not formally qualified.
- Row T's alternate-profile case was governed RGBA/U8 ACEScg. It does not imply
  arbitrary ICC, mixed-profile, HDR, or non-U8 qualification.
- The evaluated native canonical CSP track is
  `INSUFFICIENT_FOR_GAPFILL_PARITY`.
- Documented opening-like cases such as clothing sleeves remain outside intended
  GapFill capability.

These are GapFill release limits. They become OFFF limits only if OFFF actually
shares the corresponding boundary; that must be established, not assumed.

## 5. OFFF current branch and commit state

The historical OFFF work lives on `feature/overflow-floodfill` and its remote
counterpart. The branch was inspected without checkout or mutation.

| Item | Evidence |
| --- | --- |
| OFFF branch HEAD | `0caa23c658e6c589b8ff1ea0ed4a1ae9fa2a5043` |
| Subject | `prototype for overflow floodfill` |
| Merge base with frozen release | `2044d8f163367b25ed6cb81f2c0c86949d9fdf0f` |
| Divergence from release | OFFF: 1 unique commit; release: 23 unique commits |
| Commit scope | 27 files, 2,296 insertions, 173 deletions |

The one OFFF commit mixes specification, web UI, pure algorithm modules, tests,
and edits to shared branch-era GapFill files. Directly overlapping files also
changed on the release line include `README.md`, `web/README.md`,
`web/src/utils/GapFill/gapDetection.ts`, and
`web/src/utils/GapFill/onnxInference.ts`.

The authoritative historical OFFF specification is stored on that branch at:

```text
web/docs/OVERFLOW_FLOOD_FILL_SPEC.md
```

From the frozen line, inspect it without switching branches:

```bash
git show feature/overflow-floodfill:web/docs/OVERFLOW_FLOOD_FILL_SPEC.md
```

The OFFF branch is historical evidence, not an integration-ready branch.

## 6. OFFF current specification

The historical specification describes an experimental extension for clean,
binary line art. Anti-aliased input is deferred. Its intended behavior is:

- anticipate small Coloring gaps while the bucket tool is active, instead of
  running a separate repair pass;
- define a small gap as a connected transparent Coloring region whose area is at
  most a user threshold;
- recognize a Guide-associated gap when visible Guide geometry lies below it;
- form large owner regions from topology separated by Line Art and Guides,
  independently of whether those regions are already painted;
- precompute a gap-to-owner assignment using model probabilities;
- score each candidate owner by mean model probability over its pixels within
  the 32×32 patch, then retain the best owner;
- expose an independent OFFF mode tied to bucket-fill interaction, precompute
  assignments, preview linked gaps on hover, and propagate on click;
- use the clicked pixel's color for an already painted owner, or the current
  brush color for an unpainted owner;
- apply the owner and linked gaps as one history operation when appropriate;
- fall back to standard bucket behavior outside an owner;
- suppress one immediate retry after undo for the last owner.

The specification's model input is a two-channel 32×32 tensor: channel 1 is the
target small gap, while channel 0 is stated exactly as **“binary Line Art /
Guides mask.”** The output is used to select an owner, not directly as a color.

Specified limitations include binary input, four-connected owner regions,
owner candidates restricted to those overlapping the patch, and sensitivity to
the model and likelihood threshold. Planned but unimplemented topics include an
anti-alias topology proxy, anti-alias fringe handling, and debug overlays.

## 7. OFFF implementation status

The implementation on `feature/overflow-floodfill` is **web-only prototype
code**. No Krita OFFF production adapter or host qualification exists.

| Area | Status | Repository evidence and boundary |
| --- | --- | --- |
| OFFF problem and interaction model | **SPECIFIED** | `web/docs/OVERFLOW_FLOOD_FILL_SPEC.md` |
| Owner-region construction | **IMPLEMENTED** | `web/src/overflow/ownerRegions.ts`; full-image four-neighbor components of pixels not blocked by Line/Guide alpha, filtered by minimum area |
| Gap-to-owner precompute | **IMPLEMENTED** | `web/src/overflow/precompute.ts`; target-mask canvas, ONNX probability map, mean owner score inside the patch, progress yielding and abort checks |
| Owner/gap painting | **IMPLEMENTED** | `web/src/overflow/paint.ts`; clicked RGBA or selected hex color and one `putImageData` operation |
| Web mode state and interaction | **PARTIALLY IMPLEMENTED** | `web/src/overflow/useOverflowFill.ts` plus App/Workspace/Canvas/Toolbar hooks; delayed precompute, cancellation, stale request suppression, hover, click, fallback and undo-retry state exist |
| Web controls and rendering | **IMPLEMENTED** | `OverflowFillControl.tsx`, `rendering.ts`, and related CSS/integration edits |
| OFFF-specific tests | **PARTIALLY IMPLEMENTED** | Two test files: three owner-region cases and two paint cases; historical branch `npm test` passes |
| Web TypeScript/build integrity | **IMPLEMENTED, HISTORICALLY CHECKED** | Historical branch `npm run build` passes; this is not OFFF qualification |
| Precompute/model/tensor tests | **TODO** | No dedicated OFFF tests found for assignment scores, tensors, ONNX output, tie behavior, cancellation, or stale publication |
| Interaction/lifecycle tests | **TODO** | No dedicated tests found for hover, fallback bucket, undo suppression, atomic history, invalidation, or mode/tool lifecycle |
| Krita OFFF implementation | **TODO** | No Krita OFFF production code found on the branch |
| Krita real-host qualification | **TODO** | No OFFF host matrix or formal host evidence exists |
| Anti-aliased topology/fringe | **TODO** | Explicit future work in the spec |
| Debug overlays | **TODO** | Explicit future work in the spec |
| Vectorization | **UNKNOWN / REQUIRES FRESH-THREAD INVESTIGATION** | No vectorization implementation or governing contract was found |

Important implementation details requiring scrutiny during the spec freeze:

- owner labels are assigned in row-major discovery order;
- a strict greater-than comparison makes the first encountered label win equal
  scores implicitly, but the spec does not freeze that tie rule;
- no explicit exclusion of edge-touching/exterior owner components was found;
- `precompute.ts` substitutes Line for a missing Guides canvas and the branch-era
  inference path composes Line **OR** Guides into channel 0;
- painting uses a single canvas update, but exact host transaction, Undo/Redo,
  restoration, and failure behavior are not implemented for Krita;
- the prototype's tool restoration, cache invalidation breadth, and performance
  contract are not frozen.

## 8. GapFill vs OFFF semantic differences

### Mandatory unresolved model-input decision

```text
Frozen GapFill:
  model channel 0 = Line-only
  Guides = detection topology only

Historical OFFF specification and prototype:
  model channel 0 = Line Art / Guides
  prototype composition = Line OR effective Guides

SEMANTIC DECISION REQUIRED BEFORE SHARING MODEL INPUT INFRASTRUCTURE
```

This is not a wording cleanup. The frozen model was qualified with GapFill's
Line-only input. Feeding Guide-composed tensors to that model is a characterized
out-of-distribution extension unless new evidence establishes otherwise. OFFF
may deliberately choose different semantics, a different model, or another
decision, but it must do so in its own specification and tests. GapFill remains
unchanged.

Other distinctions requiring an explicit OFFF v1 decision include:

- GapFill detects correction candidates and predicts representative colors;
  OFFF assigns small gaps to owner regions and propagates a clicked/current color.
- GapFill excludes edge-touching candidate components; OFFF owner exterior
  eligibility is not specified clearly enough.
- GapFill representative color, region scoring, and tie rules are frozen; OFFF
  owner color and score/tie semantics are separate and not fully frozen.
- GapFill selection/application semantics are qualified; OFFF selection behavior
  is unknown.
- GapFill's UI is a scan/preview/apply workflow; OFFF is intended as an
  interactive bucket-fill mode with precomputation and hover feedback.

## 9. Safe shared infrastructure

“Safe to share” means host-neutral mechanisms or patterns, not automatic OFFF
qualification. Extract or name-neutralize them where appropriate, and give OFFF
its own tests.

### A. Safe to reuse or share

- generation-token gating and stale-result publication suppression patterns;
- worker/QThread cancellation, bounded shutdown, and lifecycle patterns;
- stable node lookup by UUID;
- immutable observation, exact raw-byte hashing, and freshness primitives;
- non-overlapping patch-run packing and versioned native-helper loading
  mechanisms, separated from a product-specific application plan;
- unique canvas resolution and fail-closed transform guard patterns;
- ManagedColor/canvas conversion mechanics, separated from the rule that chooses
  an OFFF color.

These mechanisms were qualified in a GapFill context. OFFF must test their use
under its own data flow and lifecycle.

### B. Reuse only through an adapter or semantic boundary

- Krita document/layer snapshot and raster normalization: OFFF must define its
  required nodes, coordinate system, inputs, and observation identity;
- Line/Guide acquisition: acquisition may be shared, composition may not;
- model loading, session creation, and 32×32 extraction: loading mechanics may be
  shared only after OFFF freezes tensor composition and model validity;
- native transaction helper and raw target read/write: OFFF must produce its own
  exact mutation plan and atomic application contract;
- selection, foreground, active-node, tool, and editor-state restoration: the
  mechanism can be adapted after OFFF defines which actions may change state;
- canvas/overlay infrastructure: coordinate safety can be shared, but OFFF hover,
  hit testing, preview, and interaction semantics differ;
- color conversion bridge: conversion is neutral, while clicked/current color
  selection, alpha handling, and profile expectations are OFFF semantics;
- standard bucket fallback and tool integration: host-facing adapters must
  preserve OFFF's independently frozen interaction contract.

## 10. GapFill-specific infrastructure and semantics that must remain isolated

### C. Do not share as generic behavior

- the frozen GapFill detector and candidate eligibility rules;
- GapFill's Guide-as-detection-only and Line-only model-input composition;
- GapFill learned color prediction, fallback provenance, semantic labels, region
  scoring, modal RGB, and tie rules;
- GapFill correction/preview/sweep logic and Apply Selected/Apply All behavior;
- GapFill setting names and threshold meanings unless an explicit adapter maps a
  separately defined OFFF concept;
- GapFill overlay magnifier and correction interaction semantics;
- GapFill release artifacts, frozen hashes, tag workflow, and qualification
  metadata as though they qualified OFFF.

OFFF may independently adopt a similar concept after it is specified and tested.
It must not import GapFill-specific code in a way that changes the frozen product
or silently inherits an incompatible rule.

### D. Unknown: investigate before sharing or implementing

- whether the first supported OFFF product is web-only, Krita, or both;
- whether the existing ONNX model is valid for OFFF's eventual input semantics;
- exterior and edge-touching owner eligibility;
- exact score tie-breaking and owner/color/alpha representation;
- selection and partial-application behavior;
- tool restoration and coexistence with other modes;
- precompute cache keys, invalidation, cancellation granularity, and performance;
- supported Krita coordinates, profiles, color models, transforms, and HiDPI;
- anti-aliased topology, fringe behavior, and any proposed vectorization;
- exact atomic application, Undo/Redo, no-op, and failure contracts;
- GapFill/OFFF coexistence behavior in one installed plugin.

## 11. Branch integration analysis

Do not naive-merge `feature/overflow-floodfill`. Its one mixed commit is based on
an old common ancestor and edits shared GapFill files that later changed during
GapFill hardening and qualification.

| Category | Integration risk |
| --- | --- |
| Production code | Mixed web prototype changes can import obsolete shared GapFill behavior or bypass current boundaries. |
| Host integration | Historical OFFF contains no Krita adapter; the current release's qualified host infrastructure must be approached through explicit adapters. |
| UI | Prototype mode integration touches central App, canvas, toolbar, renderer, navigation, and interaction hooks; coexistence and state restoration are unqualified. |
| Model semantics | Branch edits compose Line/Guides and conflict with frozen GapFill channel 0. Shared inference files must not be transplanted wholesale. |
| Tests | Pure owner/paint tests are useful seeds, but broad semantic, lifecycle, and host coverage is absent. |
| Documentation | The OFFF spec is valuable historical input. Branch-era GapFill docs are not canonical and must not replace current release docs. |
| Release infrastructure | OFFF has no qualified release pipeline; do not import or reinterpret GapFill release evidence. |

Recommended strategy:

1. Preserve `feature/overflow-floodfill` unchanged as historical reference.
2. Complete the read-only gap analysis and freeze OFFF v1 semantics.
3. Create a new OFFF development branch from `krita-v1.0.0` (commit
   `0c30afce131f330b4f0cc10ac0cf54c21b1c72b2`), or from a reviewed
   documentation-only descendant whose production tree is identical.
4. Recreate/port the OFFF spec first.
5. Selectively reconstruct pure OFFF modules and tests one at a time, preserving
   provenance and comparing each result to the historical branch.
6. Add explicit adapters to neutral current infrastructure only after the
   corresponding OFFF boundary is frozen.
7. Do **not** transplant the historical branch versions of
   `gapDetection.ts` or `onnxInference.ts`.

A rebase or whole-commit cherry-pick is not recommended. Selective reconstruction
is safer than resolving a mixed semantic conflict inside a mechanical history
operation.

## 12. Recommended OFFF restart sequence

1. Perform a read-only branch/spec/code inventory.
2. Produce an OFFF spec-vs-implementation gap table using the five statuses in
   this document.
3. Resolve or explicitly defer every semantic decision, especially channel 0,
   owner eligibility, scoring/ties, color source, selection, fallback, atomic
   history, and supported product/host.
4. Freeze and review an OFFF v1 semantic contract without changing GapFill.
5. Define neutral interfaces and product adapters; record what is deliberately
   shared and what remains isolated.
6. Approve a file-by-file reconstruction plan from a new release-based branch.
7. Port pure algorithms and deterministic tests before host/UI integration.
8. Add web and/or Krita integration only for the supported target selected by the
   frozen spec.
9. Establish OFFF-specific qualification and GapFill coexistence regression.

## 13. First fresh-thread task

The first task is **OFFF SPEC FREEZE / GAP ANALYSIS**, not coding.

The new thread must read the historical spec and implementation, compare them
line-by-line at each semantic boundary, compare OFFF against frozen GapFill,
classify each behavior as `SPECIFIED`, `IMPLEMENTED`, `PARTIALLY IMPLEMENTED`,
`TODO`, or `AMBIGUOUS`, and propose a reviewed OFFF v1 contract. It must resolve
or explicitly defer the Line/Guide model-input conflict before any shared model
input infrastructure is planned.

The output should include a proposed semantic decision register, an updated
reuse matrix, and a file-by-file integration plan. It should not modify
production code or perform a branch integration.

## 14. Files to read first

Frozen release and qualification records:

1. `docs/OFFF_HANDOFF.md`
2. `docs/addon-spec.md`
3. `docs/addon-release.md`
4. `docs/addon-phase6.5.md`
5. `krita-plugin/release/freeze.json`
6. `krita-plugin/host_tests/matrix.json`
7. `krita-plugin/pykrita/gapfill_krita/host_contract.py`
8. `krita-plugin/pykrita/gapfill_krita/controller.py`
9. `krita-plugin/pykrita/gapfill_krita/canvas_boundary.py`
10. `krita-plugin/pykrita/gapfill_krita/native_backend.py`

`docs/addon-release.md` is the release/freeze **preparation** record and therefore
speaks prospectively about tagging/publication. The published state and remote
identities in sections 2 and 17 of this handoff are later facts, independently
verified against the tag and GitHub Release.

Historical OFFF files, read without checkout using
`git show feature/overflow-floodfill:<path>`:

1. `web/docs/OVERFLOW_FLOOD_FILL_SPEC.md`
2. `web/src/overflow/types.ts`
3. `web/src/overflow/ownerRegions.ts`
4. `web/src/overflow/precompute.ts`
5. `web/src/overflow/paint.ts`
6. `web/src/overflow/useOverflowFill.ts`
7. `web/src/overflow/rendering.ts`
8. `web/src/overflow/OverflowFillControl.tsx`
9. `web/src/tests/overflow/ownerRegions.test.mjs`
10. `web/src/tests/overflow/paint.test.mjs`
11. `web/src/utils/GapFill/gapDetection.ts`
12. `web/src/utils/GapFill/onnxInference.ts`

Also inspect the OFFF commit diff and all UI integration files before making an
integration plan:

```bash
git show --stat --summary 0caa23c658e6c589b8ff1ea0ed4a1ae9fa2a5043
git diff --name-status 2044d8f163367b25ed6cb81f2c0c86949d9fdf0f..feature/overflow-floodfill
```

## 15. Do-not-do list

- Do not move, amend, recreate, or retag `krita-v1.0.0`.
- Do not modify frozen GapFill semantics to accommodate OFFF.
- Do not merge, rebase, or cherry-pick the historical OFFF commit before the spec
  freeze and file-level plan.
- Do not import branch-era GapFill docs or shared inference/detection files as
  canonical.
- Do not infer implementation from filenames or count pure/web tests as Krita
  qualification.
- Do not claim the existing ONNX model is valid for Guide-composed OFFF input
  without new evidence.
- Do not invent historical semantics where the code and spec are ambiguous.
- Do not patch production opportunistically during a formal qualification run.
- Do not treat consumed qualification attempts as rerunnable evidence.
- Do not claim OFFF release readiness from GapFill's release artifacts or matrix.
- Do not use transient `/tmp`, Windows Temp, shell, or workflow-download paths as
  durable architecture evidence.
- Do not implement OFFF as part of this handoff.

Current local hygiene only: if `krita-plugin/:memory:.ses` is present, leave it
untouched, untracked, unstaged, unpackaged, and uncommitted. It is not OFFF
architecture.

## 16. Validation and checkpoint rules

Governance for future OFFF work:

- correctness over speed;
- freeze semantics before integration;
- distinguish pure algorithm correctness from Krita-host integration;
- preserve consumed formal evidence and exact failure boundaries;
- once a versioned formal qualification attempt starts, that version is consumed;
- diagnose and preserve a real-host failure before proposing a production repair;
- production changes require explicit regression scope;
- keep GapFill and OFFF independently testable;
- eventually qualify their coexistence in a real host.

OFFF will require its own deterministic fixtures, algorithm tests, host-boundary
tests, relevant worker/lifecycle tests, apply/Undo/Redo tests, state-restoration
tests, regression against frozen GapFill, and a real-host qualification matrix.
The matrix must be designed only after the OFFF v1 contract and supported host
surface are frozen.

At each future checkpoint, record the base and branch commits, semantic decisions,
changed files, exact tests, frozen identities affected or confirmed unchanged,
and qualification state. Never update an expected result merely to match a host
bug.

## 17. Release references and frozen hashes

The authoritative machine-readable release freeze is
`krita-plugin/release/freeze.json`.

| Frozen item | SHA-256 |
| --- | --- |
| Production semantic identity | `b3812c8a00aa359097d9395b13d27e55433b311584a00e6906de0f426f5acc38` |
| Lifecycle identity | `94b42368efc0df7c37333fe864f57593254557c2b181676106efd0a45e535e5f` |
| Display Oracle V2 identity | `a0d6a02bcc678ed316a18e26da17a693293e0ac22d4579d992de6eeb21844f35` |
| Native helper | `ad2fa7463d59dca74a92dc867734b38eb7aa49821b163547da442147348f8746` |
| ONNX model | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78` |
| Model sidecar | `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5` |
| Published Windows x86_64 ZIP | `7001c1bf92aa7abb5840baf52fe07457ab06cb80074297488e67ded212ab74e2` |

These identities freeze GapFill evidence. They do not freeze or qualify OFFF.
