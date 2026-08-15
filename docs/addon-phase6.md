# Add-on Phase 6 — Krita host integration

Date: 2026-08-15 (Asia/Tokyo)

Branch: `fix/krita-host-integration`

Phase 5 baseline: `0d1c099def9119a523f21812c927229d4d1a66d4`

Status: **Phase 6 implementation complete for the deliberately
restricted/fail-closed host boundary; Phase 6.5 real-Krita qualification OPEN
and BLOCKED because no executable real Krita host is available**. This external
block is not a real-host PASS. No commit was created. Phase 7 was not started.

## Scope and baseline

This phase changed only the Krita acquisition/mutation/UI boundary, focused
host-independent tests, the real-host qualification kit, and documentation. It
did not change the pure detector/predictor, Web, ML, CSP, model, or frozen
semantic corpus.

The clean starting state was the Phase 5 commit above on
`fix/krita-host-integration`; `git diff --check` passed. Baseline and final
integrity values are identical:

| Artifact | SHA-256 |
| --- | --- |
| Frozen fixture manifest | `6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c` |
| `unet32.onnx` | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78` |
| Model sidecar | `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5` |

The baseline source ZIP was 23 entries at
`d0f0b3b4c4979520fa4a29964ee85c5b7dc678c799d1c90abdc8f2ba68ec45e7`.
The final source ZIP is 25 entries because it adds the two host-boundary
modules; it is `8ec6e03856d358b313f68e6bf905d8e1b5eb713c3b59df387fc2267204c970c3`.
ZIP timestamps are not normalized, so that archive hash is a record of this
build, not a reproducible-build claim.

The known pure real-art observations remained:

- E101 ordinary: application indices `[496,528,560]`, RGB `[251,98,115]`,
  learned score `0.913528784`;
- E102 Guide-associated: application index `[729]`, RGB `[243,242,239]`,
  learned score `0.829399342`.

E102's completed-art target is yellow `[251,239,153]`. Phase 6 preserves the
near-white pure prediction as the host-parity expectation and does not treat
the completed art as permission to alter the learned algorithm.

## Authority and actual host availability

The implementation was checked against the official LibKis APIs for
[Document](https://api.kde.org/legacy/krita/html/classDocument.html),
[Node](https://api.kde.org/legacy/krita/html/classNode.html),
[View](https://api.kde.org/legacy/krita/html/classView.html),
[Canvas](https://api.kde.org/legacy/krita/html/classCanvas.html), and
[ManagedColor](https://api.kde.org/legacy/krita/html/classManagedColor.html),
plus upstream implementation source for selection commands and raw pixel
writeback.

Actual host discovery found no Krita executable, package, embedded `krita`
module, or runnable Windows Krita bridge. The environment was Ubuntu 24.04 on
WSL2 x86-64 with Python 3.12.3. PyQt6 6.11.0 was installed only into the
isolated test venv and ran with the offscreen Qt platform. PyQt5 and every real
Krita/Python/Qt combination were unavailable.

Therefore:

- tested real Krita distributions: **none**;
- Krita 6 is an implementation candidate, not verified support;
- Krita 5.3 remains untested, and deterministic Apply is currently unsupported
  because its public `View` API does not expose all required state controls;
- a PyQt import shim is not considered compatibility evidence.

## Host boundary and coordinate contract

`HostSnapshot` owns immutable copies/owned arrays for Coloring raw pixels, Line
projection, Guide projection, root projection, and exact byte selection
coverage. `ScanContext` binds them to document/view identity, document
rectangle, node UUIDs/state/geometry/profile, active node, source hashes, and a
generation. The pure engine receives only NumPy data and never calls LibKis.

Every raster read uses the document rectangle `(xOffset, yOffset, width,
height)`. Coloring is read with `Node.pixelData`; Line, Guides, and root use
`projectionPixelData`. Application indices are row-major within that same
rectangle. Correct mapping back to changed/moved/effected raw target storage is
not guessed.

The current admitted target contract is deliberately narrow:

- RGBA/U8 Paint Layer at the document origin;
- unlocked, alpha unlocked, non-animated, visible, opacity 255, Normal blend,
  inherit alpha off;
- no child mask/effect, layer style, or non-neutral ancestor;
- root, Coloring, Line, and Guide use the same RGBA/U8 profile;
- Line/Guide projections are visible under neutral ancestors;
- document area is at most `16,777,216` pixels.

Moved Coloring layers, target masks/transform masks/styles, animation,
translucent/blended/inherit-alpha ancestry, mixed profiles, and larger documents
fail before preview. Line/Guide projection effects are still subject to the
same-profile/neutral-parent restriction and require real-host qualification.

## K finding results

### K-01 — color/profile conversion

Implemented, **real-host unverified**. Frozen pure RGB is defined as logical
source/root-profile byte components. Display uses a source-profile
`ManagedColor.colorForCanvas(canvas)`. QColor/dialog input converts through
`ManagedColor.fromQColor(qcolor, canvas)` back to the frozen source space.
Commit converts the same displayed QColor into the Coloring profile before the
selection-fill action. Preview and magnifier QColors use this bridge rather
than unmanaged raw profile bytes.

Interactive color sampling admits only fully opaque composite pixels. A
semi-transparent raw pixel is not converted into an opaque fill because its
perceived color depends on an unspecified canvas backdrop.

The fake boundary preserves asymmetric RGB exactly in identity space. sRGB and
a materially different RGBA/U8 profile, display roundtrip, and perceived
sample/preview/commit equality remain A–V host tests. No pure RGB value changed.

### K-02 — stale apply

Implemented, **real-host unverified**. Before preview and again immediately
before mutation, the adapter resolves every original node by UUID and re-reads
all relevant pixels/projections and selection bytes. It rejects changed
document/view/geometry, active node, target UUID/state/position/bounds/content,
Line/Guide state/content, root projection, or selection. Application also
checks unique/in-range canonical target indices and requires them to remain
alpha zero.

Deterministic tests cover Coloring edits; target move, transform/child effect,
delete, replace, lock and alpha-lock changes; resize; selection change; active
node switch; and document/view switch. After a successful Apply all suggestions
are discarded and the user must rescan.

### K-03 — generation/cancellation races

Implemented, **real-host unverified**. Each worker signal carries an immutable
generation. A `GenerationGate` rejects callbacks after cancel, supersession,
deactivate, missing document/view, or shutdown. Old workers are cooperatively
cancelled and retained until their thread finishes; no retired signal may
install UI or state.

Real Qt event-loop tests cover cancellation before model initialization,
queued delivery, cancellation immediately before completion, deactivate before
delivery, B superseding A, missing context, and shutdown. ONNX Runtime remains a
synchronous call and is not claimed interruptible: cancellation is observed
before detection/model construction, at detector/predictor polls, after each
inference, and before completion delivery. Synchronous UI-thread snapshot and
freshness reads are also not interruptible.

### K-04 — view mapping

Fail-closed implementation, **real-host unverified**. Pan/zoom continues to use
the official flake image/canvas transforms and is isolated in overlay mapping;
an offscreen Qt test verifies asymmetric center mapping, hit testing, sampling,
and preview alignment. Because the official transforms omit rotation and
mirroring, either state disables and hides the overlay. DPR other than 1 is
also disabled until qualified. No compensating constants were invented.

Arbitrary rotation, horizontal mirror, vertical mirror where a host provides
it, real pan/zoom, window resize, tab/split/multiwindow ownership, and display
scales remain UNTESTED. Apply from the docker can remain available even when
interactive overlay creation fails.

### K-05 — raw/projection geometry

Implemented as the restricted contract above, **real-host unverified**.
Origin-aligned plain Coloring plus document-coordinate projected boundaries and
composite are the only admitted configuration. Moved/effected targets fail
before preview. Fake tests verify rejection, but only generated `.kra` and
real-host pixel assertions can establish LibKis row order, offsets, profiles,
mask projection, and group behavior.

### K-06 — selection and Undo

Selection restoration is implemented and fake-tested; **Undo remains an open
release blocker and all real-host behavior is unverified**. The adapter records
semantic presence, duplicates the selection, captures full byte coverage,
restores the duplicate, and passes `None` when no selection existed. Tests cover
null and arbitrary soft selection bytes. Foreground and active node are also
restored and checked.

Public `Document.setSelection` creates selection Undo commands and public LibKis
does not expose a transaction/macro around the native fill plus those commands.
`Node.setPixelData` is deterministic but upstream implements it as a direct
paint-device write without a supported Undo command. This phase therefore keeps
the native selection-fill action, does not claim a one-step atomic operation,
and keeps the release gate open. Real rectangular/arbitrary/soft/inverted
selection, Apply one/selected/all, and exact Undo/redo command-stack tests are
all UNTESTED.

### K-07 — resource/cancel behavior

Partially implemented and bounded, **real-host unverified**. The adapter rejects
more than 16,777,216 pixels before any LibKis pixel read. Newly acquired arrays
are frozen by ownership instead of being copied a second time. The magnifier
converts only its 64×64 source window instead of allocating a second
profile-converted document image.

Host-neutral allocation measurements (not LibKis snapshot or analysis timing):

| Shape/data | Wall time | Peak RSS |
| --- | ---: | ---: |
| 1920×1080, four RGBA arrays + byte selection + ownership freeze | 0.32 s | 75,748 KiB |
| 4096×4096, same | 0.58 s | 319,552 KiB |
| 7680×4320 preflight rejection, no image allocation | 0.17 s including Python startup | 31,200 KiB |

Real snapshot time, complete analysis peak, UI event latency, cancel latency,
transparent-exterior/many-gap behavior, and moved/small targets are UNTESTED.
The limit is a safety boundary, not an arbitrary-size or 4K-host performance
claim.

### K-08 — canvas QWidget ownership

Implemented fail-closed, **real-host unverified**. Widget discovery is isolated
in `canvas_boundary.py`, scoped to the active main window, accepts exactly one
visible class structurally named as a canvas, and excludes controller/docker
classes. The unsafe largest-area fallback is gone. The overlay is a child of
that widget; Qt destruction tests show parent deletion owns the overlay. Hidden,
ambiguous, rotated, mirrored, or unqualified HiDPI states disable interaction.

One tab, split views, two windows, canvas-only mode, dock rearrangement,
view/document close, deactivate/reactivate, and application close remain the
real-host A–V matrix.

### K-13 — deterministic mutation

Implemented for the guarded route, **real-host unverified**. Apply requires the
native action to exist and remain enabled, saves eraser/global-alpha-lock/current
blend/painting opacity/flow, normalizes them to paint/Normal/1.0, activates the
resolved target before each color, and restores exact prior state afterward.
Krita builds missing those public controls fail before mutation.

The adapter constructs full-coverage internal masks only for canonical
application indices, converts each source color through the canvas into target
profile components, waits for the action, and compares the complete raw target
against the exact expected image. Failure keeps suggestions. If a postcondition
fails after mutation, it performs an exact full-target raw recovery and verifies
that recovery; this is emergency data restoration, not claimed Undo integration.
The fake action suite covers hostile ambient state, multiple colors,
missing/disabled/no-op actions, exact state restoration, readback failure, and
recovery. Actual action behavior and quantization are UNTESTED.

## Real-host corpus and matrix

`krita-plugin/host_tests/generate_fixtures.py` is intended to run from Krita's
Scripter and reproducibly generates ordinary/Guide gaps, E101/E102 crops,
multiple colors, moved target, masks, soft selection, asymmetric corner
landmarks, and an alternate profile when installed. The generator itself could
not be executed without Krita. `host_tests/matrix.json` records exact host and
artifact metadata and starts with every required row untested:

| Rows | Result |
| --- | --- |
| A loading through E known near-white parity | UNTESTED |
| F apply one through L stale rejection | UNTESTED |
| M cancellation through Q HiDPI | UNTESTED |
| R moved target through V shutdown | UNTESTED |

No screenshot, offscreen Qt result, fake adapter result, or pure PNG parity has
been promoted to a real-host PASS.

## Deterministic test and regression record

Final commands/results:

- Neutral: `python -m scripts.gapfill_reference.validate` passed; independent
  reference `unittest` passed 15/15; `characterize_python --phase5` reproduced
  seven model outputs at maximum delta 0 and all frozen boundary/patch/
  postprocess/Guide comparisons.
- Web: `npm test` passed all 15 files with no skips; ESLint, 30 preset assets,
  51 preset PNG and 17 documentation metadata checks passed; the CI-equivalent
  `GAPFILL_INCLUDE_TASK_C=false npm run build` passed and excluded Task C and
  `coloring_full.png`. An earlier local build intentionally lacked that CI
  environment flag and the exclusion assertion correctly failed; it is not
  counted as the final gate.
- Krita: the complete plugin plus shared Phase 2/4/5 command passed 57 tests;
  the new subset uses a real PyQt6 offscreen event loop and narrow official-
  contract fakes. Ruff and `compileall` passed.
- Krita package: `/tmp/gapfill-krita-phase6-final3.zip` passed `unzip -t`, contained
  25 source entries including `host_contract.py`, `canvas_boundary.py`, model,
  and sidecar, and passed an extracted-package import of the host contract and
  worker under the isolated dependency environment.
- CSP Make: warning-enabled build passed, core tests passed 48/48, Phase 2
  retained 37/38 historical rows with only D013's approved Phase 4 change,
  Phase 4 passed 13/13, Phase 3 safety passed, and PNG CLI E2E passed.
- CSP CMake: CMake 4.1.0/GNU 13.3 Release configure/build passed with the
  isolated Python/ONNX runtime; CTest passed 9/9 including Phase 5; install
  passed. A first configure used host Python without ONNX Runtime and correctly
  registered only 8 tests; it was reconfigured with the required interpreter
  before the recorded 9/9 result.
- Sanitizers: Debug ASan/UBSan CTest passed 9/9 with
  `ASAN_OPTIONS=detect_leaks=0`; no diagnostics. LSan remains unverified under
  the ptrace environment.
- Integrity: frozen hashes above are unchanged; no diff exists in the Krita
  pure engine, CSP, ML, Web algorithm, model, or semantic fixture tree;
  `git diff --check` passed.

## Production diff classification

- Host snapshot/acquisition and bounded resources: new `host_contract.py` and
  adapter snapshot code.
- Stale-generation safety and cancellation/lifetime: controller, worker, docker
  shutdown, and generation tests.
- Geometry mapping and overlay/view integration: new `canvas_boundary.py` and
  overlay/controller changes.
- Profile/color conversion: `CanvasColorBridge` plus preview/sample/apply edge
  conversion.
- Selection/user-state preservation and deterministic mutation/Undo: guarded
  adapter application, readback, recovery, and fake-host tests.
- Mechanically necessary adapter change: worker accepts immutable snapshots and
  signal generation tokens; Qt compatibility exposes `QUuid`.
- Qualification only: host fixture generator, A–V matrix, README/manual, and
  this record.

No production change altered D-01 through D-07, normalized detection geometry,
Line-only trained input, threshold `<=128`, 32×32 tensors, ONNX bytes,
Line-derived regions, label-0 exclusion, scoring/modal rules, provenance,
Phase 3 CSP safety, CSP/ML/Web algorithms, or any frozen expected value.

## Remaining release blockers and independent host-qualification gates

The following are not resolved by implementation tests:

- no supported real Krita distribution has loaded the plug-in or executed A–V;
- profile/pixel acquisition, canvas conversion, native action output, selection
  semantics, Undo/redo, and shutdown behavior are not host-verified;
- public LibKis cannot provide the desired single atomic Undo for this action
  route, and actual user-visible command consequences are unknown;
- overlay QWidget discovery remains a private, conservative heuristic; real
  pan/zoom/lifetime behavior is unknown and rotation/mirror/HiDPI/split ambiguity
  are deliberately disabled;
- Krita 5 deterministic apply is unsupported with its public view-state API;
- full host performance/cancel latency is unmeasured;
- package action/license/vendor cleanup and platform wheels remain Phase 8 work.

Phase 6 implementation is therefore **complete**. Phase 6.5 real-Krita
qualification remains **OPEN and BLOCKED** solely because this environment has
no executable real Krita host. Absence of a host is not a PASS: every A–V
real-host row remains **UNTESTED**, the one-step Undo issue remains a Krita
release blocker, and Phase 6.5 must pass for the tested support matrix before
any Krita artifact is considered release-qualified.

Phase 7 CSP/CELSYS feasibility is technically independent of the unavailable
Krita host and may proceed in parallel when separately authorized. Allowing
Phase 7 to start does not mean that Phase 6.5 passed and does not establish
Krita release readiness. Phase 7 was not started in this phase.

Phase 8/release qualification must preserve two separate host gates:

- Krita requires successful Phase 6.5 real-host qualification for its tested
  support matrix;
- CSP requires successful Phase 7 qualification for its tested support matrix.

One host's successful gate must not be used as evidence that the other host or
artifact is release-qualified.
