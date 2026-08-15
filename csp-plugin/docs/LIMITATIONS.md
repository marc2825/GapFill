# Known limitations

## CELSYS SDK boundary

CELSYS [publicly describes a filter plug-in SDK](https://www.clipstudio.net/ja/sdk/)
for CLIP STUDIO PAINT EX, but its
headers, samples, and detailed API documentation are distributed after accepting
separate SDK terms. They are not bundled here. Consequently this repository does
not pretend to provide an installable `.cpm`/native CSP binary without those
materials; it provides the tested engine and the exact host contract to connect.

The 2021-08-27 SDK has now been evaluated. Its surface includes one filter
source/destination raster, selection, the standard property/Preview flow, and
progress/cancellation. It does not expose independent sibling Coloring, Line,
and Guide sources, arbitrary/named/typed layers, or a layer tree. It also lacks
document-layer creation and the dynamic list/thumbnail UI needed for Review
List and One-by-One. Phase 7 therefore classifies native input feasibility as
`C. INSUFFICIENT_FOR_GAPFILL_PARITY`.

The current private adapter compiled with MSVC, but compilation is not real-host
qualification. It has neither independent Line/Guide acquisition nor a packaged
ONNX Runtime backend; heuristic fallback cannot be auto-applied. Its
single-layer/rule-based path is not GapFill and could continue only as a clearly
differentiated heuristic feature with explicit confirmation. Exact real CSP
pixel, profile, selection, Preview, cancellation, write, one-step Undo and Redo
behavior remains `UNTESTED`.

The full review workflow remains the safe PNG route: export the coloring layer,
run the CLI, and import `*.gap-corrections.png` as a new layer. The Windows CSP
4.0.10 executable was found, but the private artifact was not installed after
the input-feasibility failure. All manual rows remain untested.

CELSYS states that filter plug-ins target desktop CSP EX and that plug-ins cannot
be added to the iPad version. CELSYS also requires a separate submission/review
process for distributing SDK-based plug-ins. Follow the
[current official terms](https://www.clipstudio.net/ja/dl/cspsdk_term/),
not assumptions in this repository.

## Current functional scope

- The public pure core accepts normalized Coloring, Line, and Guide detection
  masks. The current CLI and 2021-SDK adapter acquire only one Coloring-like
  raster, so their Line/Guide masks are empty. The SDK does not expose the
  independent sources needed for canonical host parity.
- The canonical learned pure path consumes Coloring plus Line Art; Guides stay
  detection-only. Current CLI/native acquisition supplies neither a separate
  Line image nor a native ONNX backend, so it cannot invoke that learned path.
- The public C++ distribution contains a tested `InferenceBackend` boundary and
  canonical semantic pipeline, but its ONNX adapter is still an explicit
  unavailable stub. Selecting ONNX fails visibly and never falls back silently.
  Local parity uses Python ONNX Runtime 1.28.0 CPU; no image is uploaded.
- The CLI contact sheet is a static review artifact, not a native interactive CSP UI.
- The compiled private 2021-SDK plug-in is not a qualified GapFill product;
  Correction/Highlight layer creation and Review List/One-by-One remain
  companion capabilities.
- Owner color grouping and the Rule-Based predictor remain an explicitly named
  heuristic. Their score is not learned confidence, cannot receive a High band,
  and requires an explicit per-gap Apply decision.
- RGBA8 PNG is the interchange format; document color depth/profile conversion is
  the responsibility of the eventual SDK adapter or CSP export/import.
- Processing is linear and cancellable but currently single-threaded to keep host
  integration deterministic. Detection uses adjacent-row run state and
  threshold-bounded retained component pixels, while the three normalized masks
  and returned candidates remain proportional to image size. Host cancellation
  delivery still requires real CSP qualification.
- The PNG companion validates source/output identity and stages encoded artifacts
  beside their destinations. Its rollback protects ordinary reported write and
  rename failures, but it is not an OS-level multi-file transaction. Abrupt
  process/OS loss can leave a hidden recovery backup, and directory entries are
  not explicitly synchronized to stable storage. Real Windows filesystem and
  antivirus/interruption behavior remains part of platform qualification.
- Candidate application is bound to the pure engine's source, selection, image
  geometry, and candidate-producing settings snapshot. The future CSP host
  adapter must still ensure that its document/layer snapshot remains unchanged
  between host read and final host commit.

## Not planned for this CSP MVP

No event interception, process injection, UI automation, paint-bucket replacement,
hover UI, drag color picking, sweep gestures, or Undo hooks are used.
