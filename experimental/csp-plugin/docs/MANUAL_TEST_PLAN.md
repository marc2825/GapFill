# Windows CSP EX 4.0.10 manual test plan

Run this only after the CELSYS SDK adapter compiles. Use disposable documents and
copies of source artwork. Record the CSP version, SDK release, OS, architecture,
plug-in hash, and test date.

## Phase 7 status

The private adapter compiled on 2026-08-15, but Phase 7 classified the evaluated
filter SDK input as `C. INSUFFICIENT_FOR_GAPFILL_PARITY`: it cannot expose
independent canonical Coloring, Line, and Guide sources. The artifact was not
installed. Compilation is not host qualification, and all rows below remain
`UNTESTED`. Do not change a row to `PASS` without recorded real-host evidence.

The exact private artifact used for the compile-only gate was Windows x64
Release, 333,312 bytes, SHA-256
`f26105473709654a0446dd0a75598705db974bca806a2914f779c3f495007941`.
The available executable reported CSP 4.0.10; the EX edition was not
independently verified.

| # | Required real-host row | Phase 7 result |
| ---: | --- | --- |
| 1 | Plug-in discovery/loading | `UNTESTED` |
| 2 | Ordinary canonical gap | `UNTESTED` |
| 3 | Line-enclosed gap | `UNTESTED` |
| 4 | Guide-enclosed gap | `UNTESTED` |
| 5 | Mixed Line + Guide closure | `UNTESTED` |
| 6 | Known no-gap/open-Guide negative | `UNTESTED` |
| 7 | Alpha/channel asymmetric input | `UNTESTED` |
| 8 | Selection | `UNTESTED` |
| 9 | Layer offset | `UNTESTED` |
| 10 | Profile behavior | `UNTESTED` |
| 11 | Preview | `UNTESTED` |
| 12 | Preview replacement/restart | `UNTESTED` |
| 13 | Cancel during acquisition | `UNTESTED` |
| 14 | Cancel during detection | `UNTESTED` |
| 15 | Cancel around inference | `UNTESTED` |
| 16 | Cancel during write | `UNTESTED` |
| 17 | Injected acquisition failure | `UNTESTED` |
| 18 | Injected mutation failure where possible | `UNTESTED` |
| 19 | OK | `UNTESTED` |
| 20 | Exact written pixels | `UNTESTED` |
| 21 | Undo | `UNTESTED` |
| 22 | Redo | `UNTESTED` |
| 23 | Repeated invocation | `UNTESTED` |
| 24 | Document close/cancellation | `UNTESTED` |
| 25 | Supported large document | `UNTESTED` |
| 26 | Unsupported configuration fail-closed behavior | `UNTESTED` |

The asymmetric source-acquisition cases (Coloring only, Line only, Guide only,
each pair, and all three) are also `UNTESTED`. Static permitted SDK inspection
established that the independent Line/Guide source interface required to run
them canonically is absent. They must not be simulated with a composite or by
relabelling the one filter source.

## Installation and host boundary

- [ ] The plug-in installs through the supported CSP mechanism without modifying
      application files manually.
- [ ] It appears only where the SDK documentation says a filter plug-in should.
- [ ] It rejects empty, vector, text, reference, or otherwise unsupported active layers.
- [ ] The UI states clearly when only the active raster layer is analyzed.
- [ ] Restarting CSP preserves only non-image settings.

## Detection

- [ ] A 1 px enclosed transparent gap is detected with Small.
- [ ] A 4–10 px gap is excluded by Small and detected by Medium.
- [ ] A 30 px gap is detected by Large; a 31 px gap is excluded.
- [ ] A custom threshold is honored.
- [ ] A transparent region connected to the canvas edge is excluded.
- [ ] Canonical detection includes alpha 0 and excludes alpha 1/127/254/255,
      regardless of the retained legacy alpha setting.
- [ ] Four- and eight-neighbor diagonal behavior matches the unit tests.
- [ ] Selection Only finds enclosure from full canvas geometry and writes only
      the selected intersection; selection clipping does not create enclosure.

## Review behavior

- [ ] Changing a native property updates CSP Preview without committing pixels.
- [ ] A runtime-enabled build labels learned predictions and Quick Fix applies
      only High-confidence learned candidates.
- [ ] Apply High Confidence leaves Medium/Low and every heuristic fallback unchanged.
- [ ] Re-preview replaces stale output rather than accumulating corrections.
- [ ] Cancel leaves document pixels and history unchanged.

## Output and Undo

- [ ] Native OK changes only High-confidence learned gap pixels on the active layer.
- [ ] Duplicating the coloring layer first provides an editable non-destructive copy.
- [ ] One CSP Undo restores the exact pre-filter pixel data.
- [ ] Cancelling progress creates no partial pixel change or Undo entry.

## PNG companion review and layer output

- [ ] Review List manifest/contact sheet contains summary, IDs, confidence,
      suggested color, owner ID, and status.
- [ ] Excluding Apply, Skip, and Mark Only produce no correction pixels.
- [ ] One-by-One decision files support Apply, Skip, Mark Only, and applying all
      remaining High-confidence learned candidates; heuristic suggestions move
      only after explicit per-gap Apply.
- [ ] Importing `*.gap-corrections.png` creates a transparent correction layer
      above the coloring layer without modifying the source.
- [ ] Optional highlights mark unresolved Medium/Low candidates and omit applied gaps.

## Pixel correctness

- [ ] RGBA channel order is correct (test red, green, blue, black, white, alpha).
- [ ] Top/bottom row orientation is correct using an asymmetric test image.
- [ ] Transparent RGB values do not create visible fringes.
- [ ] Premultiplied/unpremultiplied alpha conversion is verified.
- [ ] Behavior is recorded for non-sRGB profiles and higher-bit-depth documents.

## Performance and privacy

- [ ] 4096×4096 RGBA input completes with responsive progress/cancel behavior.
- [ ] Approximately 100 candidates can be reviewed without UI stalls.
- [ ] No image or pixel data is sent over the network.
- [ ] No image content appears in logs, settings, crash text, or undeleted temp files.

## Failure cases

- [ ] Missing/invalid settings fall back safely or produce a clear error.
- [ ] Unsupported host capabilities fail closed without pixel mutation.
- [ ] ONNX selected without a local adapter fails visibly without running or
      relabeling Rule-Based output.
- [ ] A wrong-hash/malformed/incompatible model fails before host mutation.
- [ ] Cancel before or between model calls publishes no partial prediction batch;
      record that one synchronous ONNX Runtime call cannot be interrupted.
- [ ] Exceptions close progress UI and CSP does not commit the filter destination.
