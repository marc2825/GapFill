# Add-on Phase 7: CELSYS host-adapter feasibility

Date: 2026-08-15 (Asia/Tokyo)

Public baseline: `3a2e0e91ef6458c1c2ed1a11740d8106d5d3d8ff`

Branch: `qualify/csp-host-adapter`

## Decision

Phase 7 reached a capability decision without changing the frozen GapFill
algorithm:

- input feasibility: **C. `INSUFFICIENT_FOR_GAPFILL_PARITY`**;
- host qualification: **5. `NOT_APPLICABLE_BECAUSE_INPUT_INFEASIBLE`**;
- public SDK-independent host contract: implemented and tested;
- permitted private adapter: compiled, but not parity-qualified;
- real CSP host qualification: not executed; every manual host row remains
  `UNTESTED`;
- native CSP artifact advertised as GapFill: **not permitted by this evidence**;
- Phase 8 entry for a native CSP GapFill release: **permanently ineligible for
  the evaluated SDK/adapter combination**.

The evaluated filter SDK supplies one filter source raster and a selection. Its
permitted interface does not supply arbitrary sibling layers, a layer tree,
named or typed Line/Guide sources, or independent document projections from
which canonical Coloring, Line, and Guide planes could be recovered. A visual
composite cannot restore the lost source identity. This is a capability failure,
not a reason to weaken Phase 4/5 semantics.

The result is final for this evaluated API/adapter combination: it is not an
unfinished native implementation, a blocked real-host qualification, or a
Phase 8 TODO. Host/core GapFill parity testing is intentionally not applicable
because the adapter cannot first construct the canonical input. Reopening a
native CSP GapFill route requires new capability evidence from a supported CSP
integration mechanism; another build of the same adapter is not new evidence.

The existing single-layer/rule-based path can only be considered as a separately
differentiated heuristic quick-fix concept. It is not GapFill parity, lacks the
canonical multi-layer inputs, uses heuristic prediction where applicable, and
must retain explicit confirmation for heuristic output. This record does not
choose a final product name or begin that product/release work.

Phase 6.5 subsequently closed independently for its recorded Krita host matrix;
nothing in this CSP decision supplied that evidence, and the later Krita result
does not change this CSP capability failure.

| Product gate | Final state |
| --- | --- |
| Krita Phase 6 implementation | `COMPLETE` |
| Krita Phase 6.5 real-host qualification | `CLOSED`: A–P and R–V PASS; Q host condition unavailable |
| Krita release qualification | Phase 6.5 host gate satisfied for the recorded matrix; separate Phase 8 packaging/release work remains |
| CSP Phase 7 input feasibility | `C. INSUFFICIENT_FOR_GAPFILL_PARITY` |
| CSP Phase 7 host qualification | `5. NOT_APPLICABLE_BECAUSE_INPUT_INFEASIBLE` |
| CSP canonical GapFill Phase 8 eligibility | `INELIGIBLE` for the evaluated SDK/adapter combination |

## Frozen baseline

The repository started clean at the public baseline above. The pre-change CSP
core reported 48/48 tests. A Windows MSVC baseline build and safe temporary-prefix
installation passed; its installed CLI help smoke passed, and CTest passed 8/8.
The Phase 5 CTest was explicitly not registered because the available Windows
Python lacked NumPy and ONNX Runtime.

Frozen hashes before and after Phase 7 are:

| Artifact | SHA-256 |
| --- | --- |
| `tests/fixtures/gapfill/manifest.json` | `6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c` |
| `web/public/models/unet32.onnx` | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78` |
| `web/public/models/model_info.json` | `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5` |

D-01 through D-07, normalized geometry, detector connectivity, Line/Guide
semantics, Line-only model input, threshold, tensor construction, model,
semantic regions, scoring, modal RGB, provenance, and Phase 3 safety policy are
unchanged. No fixture, golden value, model byte, predictor, detector, or
correction algorithm was edited.

## Environment inventory

| Dependency | Availability | Evidence and limit |
| --- | --- | --- |
| Linux environment | `AVAILABLE` | Ubuntu 24.04.1 under WSL2 x86-64; kernel `6.6.87.2-microsoft-standard-WSL2`. |
| Windows MSVC | `AVAILABLE` | Visual Studio Community 2026 18.7.1; MSVC 19.51.36248.0, x64. The requested historical v142 toolset is absent, so the installed default 14.51 toolset was used. |
| Windows SDK | `AVAILABLE` | 10.0.26100.0 selected by CMake. |
| Windows CMake | `AVAILABLE` | Visual Studio-bundled CMake 4.3.1-msvc1. Linux CMake was unavailable. |
| Permitted CELSYS SDK | `ACCESS-RESTRICTED` and locally available | Evaluated 2021-08-27 filter SDK in the ignored local SDK workspace. No restricted file entered the public diff. |
| CSP executable | `AVAILABLE` | Windows `CLIPStudioPaint.exe`, file/product version 4.0.10.0/4.0.10. The executable/registry evidence did not independently prove the EX edition, although the SDK target documentation is EX. |
| Private adapter | `ACCESS-RESTRICTED` and locally available | First-party files exist only under the ignored SDK workspace. They are not a Git worktree and have no private commit ID. Stable content-manifest aggregate SHA-256: `db2470f6a181243cd14bef63e789ad434cc827be3676de419ddce7f3e4576311`. |
| Private credentials/config | `UNAVAILABLE` | None were required or found for the local build. No distribution credentials were used. |
| Existing installed `.cpm` | `UNAVAILABLE` | No existing plug-in installation was found. Phase 7 did not install the newly built artifact. |
| Python parity environment | `UNAVAILABLE` | System/Windows Python lacked NumPy/ONNX Runtime/Pytest/Ruff. Isolated dependency installation was not approved in this environment, so the affected gates remain unavailable rather than passed. |

Windows/WSL process bridging was intermittent and sometimes returned a socket
error. Retrying the same read/build operation later succeeded; no result was
inferred from the failed bridge attempts.

## Public/private boundary

The public repository now describes only host-neutral requirements:

- document-coordinate raster and mask tiles;
- normalized straight RGBA8 sRGB input declaration;
- independent Coloring, Line, and Guide planes;
- exact soft-selection values;
- stable document/target/revision identity;
- cancellation, replaceable Preview, freshness, two-phase final mutation,
  abort, and Undo/Redo evidence.

The contract contains no CELSYS SDK types, constants, headers, sample code, or
call sequence. The SDK-specific implementation, SDK files, build products, and
`.cpm` remain ignored and private.

## Minimum host capability matrix

All entries marked Required are necessary for the canonical native product.
“Fail closed” means no Preview or document mutation. A “product downgrade” is a
separately disclosed non-GapFill feature, never an implicit algorithm fallback.

| ID | Exact information/behavior | Frozen dependency | Need | Safe response if absent |
| --- | --- | --- | --- | --- |
| A | Positive document width/height and stable document identity | Bounds for D-02, patches, output | Required | Fail closed |
| B | Target Coloring RGBA after documented profile conversion, including exact alpha | D-03, source colors, final pixels | Required | Fail closed |
| C | Independent Line raster/projection, not a visual composite | Line detection boundary, Line-only tensor/regions | Required | Fail closed; a single-layer heuristic is a product downgrade |
| D | Independent Guide raster/projection | Guide detection boundary | Required | Fail closed; no inference from Coloring/composite |
| E | Selection presence plus full document-coordinate 0–255 mask | D-04 application scope | Required when host supports selection | Fail closed if an existing selection cannot be read; absence is explicit |
| F | Stable target layer/node identity | Stale-target prevention | Required | Fail closed |
| G | Document/layer origins, extents, crop and coordinate mapping | Exact masks, tensors, writes | Required | Fail closed |
| H | Channel offsets, alpha representation, row/pixel stride, profile/encoding evidence | D-03, luma conversion, RGB output | Required | Convert explicitly or fail closed |
| I | Complete safe reads with detectable partial/overlapping coverage | Every pure-core input | Required | Reject snapshot |
| J | Temporary, replaceable Preview and restart over the committed source | Non-accumulating review | Required for native filter UX | Fail closed; offline companion is an optional product route |
| K | Cancellation observable during acquisition and every bounded core/write phase | Phase 3 atomicity | Required | Abort/discard |
| L | Exact final write to the intended target and coordinates | Accepted correction only | Required | Abort |
| M | Two-phase final mutation with failure abort/no partial commit | Phase 3 safety | Required | Abort; no direct write fallback |
| N | One accepted operation is one coherent Undo; Redo restores it | Release safety contract | Required | Release blocker |
| O | Revision/freshness validation before Preview and before commit | No stale scan/write | Required | Reject stale snapshot |

Optional UX capabilities include native review lists/thumbnails, creating
Correction/Highlight layers, layer placement, and custom review dialogs. Their
absence limits UX but does not repair missing required input C or D.

## Actual SDK acquisition finding

Permitted inspection covered the locally accepted SDK headers, samples, public
adapter, and first-party private adapter without copying their contents. The
surface provides the conventional filter target/source/destination, selection,
canvas-related metadata, property/Preview flow, and progress/cancellation. No
permitted surface for arbitrary sibling layers, layer tree enumeration, named
Line/Guide layers, reference/guide layer types, or independent document
projection was found.

The current private adapter correspondingly reads one filter source raster and
an optional selection and calls the compatibility Quick Fix overload with empty
Line and Guide inputs. It also lacks a packaged native ONNX backend. Its
heuristic fallback is correctly excluded from automatic application, which
means the current native build applies no canonical learned correction.

The requested asymmetric real-document cases A–G were not executed. They remain
`UNTESTED`, not passed. Static interface inspection is nevertheless sufficient
for classification C: none of those pixel experiments can provide an adapter
with an absent independent-source interface, and a composite cannot be inverted
reliably. The experiments would characterize active/composite raster details,
but cannot change canonical input feasibility for this SDK.

| Asymmetric acquisition case | Real-host result |
| --- | --- |
| A: Coloring only | `UNTESTED` |
| B: Line only | `UNTESTED` |
| C: Guide only | `UNTESTED` |
| D: Coloring + Line | `UNTESTED` |
| E: Coloring + Guide | `UNTESTED` |
| F: Line + Guide | `UNTESTED` |
| G: Coloring + Line + Guide | `UNTESTED` |

Observed acquisition capability summary:

| Source/metadata | Result |
| --- | --- |
| One filter source raster | Surface available; runtime pixel semantics `UNTESTED` |
| Independent Coloring + Line + Guide | Not exposed; not recoverable without information loss |
| Arbitrary/named/typed sibling layers or layer tree | Not exposed |
| Independent document projection | Not exposed |
| Selection | Surface available; origin/soft-mask runtime behavior `UNTESTED` |
| Coordinates/strides/channel/alpha/profile | Relevant fields/conversion responsibility exist; exact real-host behavior `UNTESTED` |

## Public adapter contract and conformance

`native_host_contract` was implemented tests-first. The initial test build
failed on the intentionally missing header. After implementation, 59/59 checks
passed with GCC and the same executable passed under MSVC/CTest.

The suite covers:

- nonzero and negative document origins, cropped and differently sized planes,
  out-of-order tiles, row/pixel padding, asymmetric BGRA-to-RGBA offsets, all
  alpha extremes, odd dimensions, 1-pixel, 1-pixel-wide, and 1-pixel-tall data;
- rejection of partial, overlapping, out-of-bounds, truncated, or malformed
  raster/mask input;
- independent Coloring, Line, Guide, Line+Guide, empty Line/Guide, transparent
  outside cropped extents, absent/full/partial/soft selections and differing
  selection/document origins;
- required profile-conversion evidence and dimension/geometry consistency;
- capability preflight, repeated acquisition, acquisition cancel/failure,
  stale identity, initial/replacement Preview, restart, Preview failure cleanup,
  repeated close/dispose cleanup, and Preview cancellation;
- successful two-phase OK, exact staged pixels, pre/mid-write cancellation,
  injected partial-write exception, stale-during-write abort, missing atomic
  capability, and explicit one-step Undo/Redo evidence.

Existing pure-core tests separately cover cancellation during detector traversal
and prediction. The public fake defines required lifecycle behavior only; it is
not evidence that CSP implements Preview, cancellation, transaction, Undo, or
Redo correctly.

## Builds and host qualification

### Public builds

- GCC 13.3/C++20 Make build: passed without project warnings.
- Core: 48/48.
- New native-host contract: 59/59.
- Phase 2 CSP characterization: 37/38 historical rows retained; only approved
  D013 changed under D-04.
- Phase 4 normalized detection: 13/13.
- Phase 3 CLI safety: passed.
- PNG CLI E2E: passed.
- MSVC 19.51 Release x64 public build: passed.
- Safe temporary-prefix install, installed CLI help smoke, and installed CLI
  PNG fixture/apply/verify E2E: passed.
- CTest: 9/9 registered tests passed. Phase 5 Python parity was not registered
  because its dependencies were unavailable.

An earlier diagnostic install target used CMake's default `Program Files`
prefix and failed for lack of administrative permission. It changed no system
installation. The required explicit temporary-prefix installation then passed.

### Private build

The current private first-party adapter was built cleanly in a fresh Windows
temporary directory against the Phase 7 working tree:

| Field | Result |
| --- | --- |
| Configuration | Release, x64, static MSVC runtime |
| Compiler | MSVC 19.51.36248.0 / installed toolset 14.51.36231 |
| Windows SDK | 10.0.26100.0 |
| CELSYS SDK identifier | locally accepted filter SDK, 2021-08-27 |
| Public baseline relationship | public work based on `3a2e0e91ef6458c1c2ed1a11740d8106d5d3d8ff`; build consumed the uncommitted Phase 7 contract |
| Private identity | no private Git commit; aggregate listed in Environment inventory |
| Artifact | Windows x64 `.cpm`, retained outside the public repository |
| Size | 333,312 bytes |
| SHA-256 | `f26105473709654a0446dd0a75598705db974bca806a2914f779c3f495007941` |
| Result | Compiled; no private unit/conformance suite exists; not installed or host-qualified |

MSBuild emitted only warnings about using a temporary build directory and UNC
path case/incremental dependency tracking. No source compiler diagnostic was
reported.

### Real CSP

The Windows CSP 4.0.10 executable is present, but the artifact was deliberately
not installed after classification C. No supported canonical matrix exists to
qualify through this filter SDK. The exact EX edition was not independently
verified, no document was changed, and all 26 manual rows remain `UNTESTED`.

Consequently:

- Preview/restart semantics: `UNTESTED` in CSP;
- cancellation at all host phases: `UNTESTED` in CSP;
- failure/abort/no-partial-commit semantics: `UNTESTED` in CSP;
- final exact write: `UNTESTED` in CSP;
- one-step Undo and Redo: `UNTESTED` in CSP and still release blockers;
- real host/core parity for masks, candidates, tensors, provenance, region and
  final RGB: not run and not claimable.

## Resource observations

No real-host latency, memory, 4K, 8K, many-gap, or cancellation measurement was
run in Phase 7. The earlier public CLI audit observation (4096-square input,
about 1.15 s and 205,096 KiB maximum RSS on that Linux environment) remains a
public-core characterization only and must not be relabeled as CSP performance.

ASan/UBSan builds of both the 48-test core and 59-check host contract passed with
no diagnostics when leak detection was disabled. LeakSanitizer itself was
unavailable because the test process is under ptrace; the initial LSan runs
failed with that environmental diagnostic, not a product leak report.

## Public regression and hygiene

| Gate | Phase 7 result |
| --- | --- |
| Web tests | 15/15, no skips |
| Web lint | Passed |
| Preset assets | 30 verified |
| PNG metadata | 51 preset PNGs and 17 documentation images verified |
| Web TypeScript/Vite build | Passed |
| Neutral Python/ONNX parity | Unavailable; dependencies absent |
| Krita Pytest/Ruff | Unavailable; dependencies absent |
| Krita syntax/compile-independent check | Passed |
| Krita source ZIP build/integrity/required-content check | Passed; 25 entries including model; no vendored runtime tree |
| CSP Make/core/contract/Phase 3/Phase 4/E2E | Passed as listed above |
| CSP Phase 5 Python cross-runtime parity | Unavailable; dependencies absent |
| Public MSVC CMake/build/install/CTest | Passed; 9/9 registered tests |
| Private MSVC build | Passed; compile only |
| ASan/UBSan | Passed with leak detection disabled |
| LSan | Environmentally unavailable under ptrace |
| Real Krita Phase 6.5 | Subsequently `CLOSED` independently: A–P and R–V PASS; Q `ROW_Q_HOST_CONDITION_UNAVAILABLE` |
| Real CSP manual matrix | All rows `UNTESTED` after input infeasibility decision |

Final public-diff checks require `git diff --check`, an ignored/restricted-file
scan, and rechecking the three frozen hashes. The intended public files are
limited to this record, SDK-independent source/tests/build registration, and
public capability/integration/manual/parity/limitations documentation. No
private artifact is intended for staging.

## Remaining CSP blockers and Phase 8 entry

Remaining blockers are:

1. the evaluated filter SDK cannot provide independent canonical Line and Guide
   sources, so native GapFill input parity fails by capability;
2. the private adapter has no packaged native ONNX backend;
3. private adapter conformance tests do not exist;
4. CSP edition, pixel/profile/selection/offset details, Preview/restart,
   cancellation, failure abort, exact writes, one-step Undo and Redo are
   untested;
5. host/core parity and host resource behavior are untested;
6. CELSYS distribution qualification was not attempted.

Therefore no CSP artifact from this work may accurately be called a GapFill
implementation. The evaluated SDK/adapter combination failed the capability
gate and is permanently ineligible for a canonical GapFill Phase 8 release; it
is not merely blocked or waiting. Only new capability evidence from a supported
CSP integration mechanism could establish a new canonical route. A separately
differentiated single-raster/rule-based product would not be GapFill, must
disclose that limitation and its heuristic prediction, must retain D-07
explicit confirmation, and requires its own host/release qualification. No
marketing name is selected and neither route is started here.
