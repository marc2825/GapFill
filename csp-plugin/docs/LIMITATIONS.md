# Known limitations

## CELSYS SDK boundary

CELSYS [publicly describes a filter plug-in SDK](https://www.clipstudio.net/ja/sdk/)
for CLIP STUDIO PAINT EX, but its
headers, samples, and detailed API documentation are distributed after accepting
separate SDK terms. They are not bundled here. Consequently this repository does
not pretend to provide an installable `.cpm`/native CSP binary without those
materials; it provides the tested engine and the exact host contract to connect.

The 2021-08-27 SDK has now been evaluated. It can read source/destination raster
pixels and selections, use CSP's standard filter property dialog, update Preview,
report progress/cancellation, and participate in CSP's normal filter commit/Undo
flow. It does not expose document-layer creation or the dynamic list/thumbnail UI
needed for Review List and One-by-One. The native implementation is therefore a
Quick Fix filter that applies High-confidence corrections only. For a reversible
editable copy, duplicate the coloring layer before running it.

The full review workflow remains the safe PNG route: export the coloring layer,
run the CLI, and import `*.gap-corrections.png` as a new layer. Runtime
compatibility with CSP EX 4.0.10 remains pending until the first MSVC-built `.cpm`
passes the manual host test plan.

CELSYS states that filter plug-ins target desktop CSP EX and that plug-ins cannot
be added to the iPad version. CELSYS also requires a separate submission/review
process for distributing SDK-based plug-ins. Follow the
[current official terms](https://www.clipstudio.net/ja/dl/cspsdk_term/),
not assumptions in this repository.

## Current functional scope

- The public pure core accepts normalized Coloring, Line, and Guide detection
  masks. The current CLI and 2021-SDK Quick Fix adapter can still acquire only
  the active Coloring raster, so their Line/Guide masks are empty. Real host
  multi-layer acquisition remains unverified and is not claimed by Phase 4.
- Reference composites, Line Art, and Guides remain unused by the rule predictor;
  detector geometry does not change its inference semantics.
- The ONNX class is a local-only stub. Selecting ONNX visibly falls back to the
  rule predictor; no image is uploaded.
- The CLI contact sheet is a static review artifact, not a native interactive CSP UI.
- The native 2021-SDK plug-in offers Quick Fix only; Correction/Highlight layer
  creation and Review List/One-by-One are companion features.
- Owner color grouping uses a configurable adjacent RGB Manhattan tolerance. It
  is intentionally conservative and not equivalent to the research U-Net.
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
