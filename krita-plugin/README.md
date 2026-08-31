# GapFill for Krita

GapFill for Krita is a Python plugin that finds small, enclosed, unpainted gaps
in anime-style coloring and predicts a likely fill color for each gap. It adds
an interactive canvas workflow for reviewing, correcting, and applying those
predictions without leaving Krita.

- **Current published release:** [GapFill for Krita 1.1.0](https://github.com/marc2825/GapFill/releases/tag/krita-v1.1.0)
- **Previous published release:** [GapFill for Krita 1.0.2](https://github.com/marc2825/GapFill/releases/tag/krita-v1.0.2)
- **Download:** `gapfill-for-krita-windows-x86_64.zip`

Version 1.1.0 adds a qualified **Model input** selector with **Line only** and
**Line + Guides** choices. The immutable 1.0.2 artifact and its historical
evidence remain available and unchanged.

## What it does

- Finds small, enclosed, fully transparent gaps on a selected **Coloring**
  layer.
- Uses **Line Art** and optional **Guides** to determine whether a gap is
  enclosed.
- Runs the bundled, hash-pinned model to suggest a color from the surrounding
  artwork.
- Shows candidates as circular markers with a 5× hover magnifier.
- Lets you correct a suggestion by dragging from its marker and sampling a
  visible source color.
- Applies one candidate, a docker selection, all candidates, or candidates
  crossed by a sweep gesture.
- Keeps unapplied candidates in the same frozen scan session. Applying one
  candidate does not silently rescan the document or rerun inference for the
  remaining candidates.
- Reconciles known GapFill-owned Undo/Redo steps with the corresponding frozen
  candidate state.
- Commits each Apply as one atomic native Krita transaction.

## Supported environment

The published 1.1.0 Windows bundle is formally qualified for this exact host
cell:

| Component | Qualified version |
| --- | --- |
| Operating system | Windows 11 Pro x64 |
| Krita | 5.3.3, git revision `858d352` |
| Qt | 5.15.7 |
| Embedded Python | CPython 3.13.5 |
| PyQt | PyQt5 5.15.11 |
| ONNX provider | `CPUExecutionProvider` |

Other operating systems, architectures, Krita revisions, Qt versions, and
embedded Python/PyQt versions are not qualified by this release. The bundled
native Apply helper checks the host and fails closed when it does not match.

## Install the release bundle

The Windows release ZIP is self-contained. It includes the plugin, action
metadata, model, NumPy, ONNX Runtime, and the version-pinned native Apply
helper. Do not install additional Python packages with pip.

1. Download the 1.1.0
   `gapfill-for-krita-windows-x86_64.zip` release asset. Do not extract it.
2. In Krita, choose **Tools → Scripts → Import Python Plugin From File…** and
   select the ZIP.
3. Restart Krita.
4. Open **Settings → Configure Krita… → Python Plugin Manager**, enable
   **GapFill for Krita**, and restart Krita again.
5. Open the docker with **Settings → Dockers → GapFill**. If it is hidden, use
   **Tools → Scripts → Show GapFill Docker**.

Krita disables newly imported Python plugins by default, so the enable step and
second restart are required. Exit Krita completely before replacing or removing
the bundle because Windows may keep the loaded native `.pyd` locked.

A plain source ZIP is not an equivalent release bundle: it does not include the
binary Python dependencies or native helper required for Apply.

## Quick start

1. Choose the paint layer to inspect and modify as **Coloring**.
2. Choose the boundary layer as **Line Art**.
3. Optionally choose a **Guides** layer.
4. Choose **Model input**. **Line only** is the default and matches the trained
   model input semantics; **Line + Guides** is an extended compatibility mode.
5. Set **Maximum gap size**, then click **Scan / Activate**.
6. Inspect the candidate markers and predicted colors.
7. Correct or apply candidates using the canvas or docker controls.
8. Click **Deactivate** when finished.

### Canvas controls

| Gesture | Result |
| --- | --- |
| Hover a marker | Show the 5× magnifier |
| Drag from inside a marker | Pick a replacement color from the visible composite |
| Hover the magnifier's **×** while correcting | Cancel the correction |
| Press outside all markers, sweep across candidates, then release | Apply the crossed candidates |
| Use **Apply Selected** or **Apply All** | Apply candidates chosen in the docker |

The sweep path is shown temporarily in pale yellow-green. Remaining candidates
stay in the frozen session after a successful Apply, with their original
geometry and predictions.

## Layer setup

- **Coloring** must be an unlocked, visible, origin-aligned, non-animated
  RGBA/U8 paint layer using Normal blending and full opacity. It must not use
  inherit alpha or have child masks, effects, or a layer style. Its parent
  groups must also be visible, fully opaque, and neutral. Unpainted pixels must
  be fully transparent.
- **Line Art** must have a transparent background. Every nonzero-alpha pixel is
  a detection boundary and is never treated as a paintable gap.
- **Guides** are optional and must also have a transparent background. Their
  nonzero-alpha pixels can enclose an ordinary Coloring gap, but Guide pixels
  themselves are not paintable “Guide gaps.” An isolated Guide in open
  transparency does not create a gap.
- A white **Background** may remain visible underneath, but do not select it as
  Coloring, Line Art, or Guides. It is visual backing only and does not change
  Coloring transparency.

Line Art and Guides must be visible RGBA/U8 nodes under neutral parents and use
the document profile. Moved Coloring layers, masks/effects/styles, mixed input
profiles, HDR/non-U8 documents, and documents larger than 16,777,216 pixels are
rejected before preview or Apply.

## Detection and prediction semantics

Line Art and Guides have distinct detection and prediction roles:

```text
gap detection boundary = Line Art OR Guides
model channel 0 (Line only)     = canonical Line
model channel 0 (Line + Guides) = canonical Line OR normalized Guides
model channel 1                 = target gap
```

The detector uses four-neighbor connectivity and considers only enclosed,
fully transparent Coloring components at or below the configured size. Open
components touching the document edge are excluded.

For learned prediction, Line Art is composited over byte white and thresholded
at inclusive grayscale 128. In **Line + Guides**, the normalized Guide boundary
(any nonzero alpha, the same binary source used by detection) is ORed with that
Line boundary. For a target Guide gap, only its target pixels are removed from
the Guide contribution before composition. Channel 1 remains the exact target
gap in both modes. The model was trained with Line-only channel 0, so **Line +
Guides** may be out-of-distribution and is not described as more accurate. The
model output remains matched against full-image, Line-derived semantic regions.

The selected mode is frozen when Scan begins. Changing it cancels or invalidates
the current frozen analysis, clears its overlay and checkpoints, and requires
an explicit new Scan; it never runs inference automatically. Known Apply and
Undo/Redo checkpoints can only be restored within their original mode.

The model must load and validate successfully before suggestions are shown. A
missing, malformed, incompatible, or wrong-hash model/runtime produces an error
instead of silently replacing the batch with heuristic output. The optional
fallback is limited to an isolated per-gap prediction failure after at least one
learned prediction has succeeded; fallback suggestions have no learned
confidence and require explicit confirmation.

## Safety and current limits

- Interactive overlays are qualified only on an unrotated, unmirrored,
  device-pixel-ratio-1 canvas whose internal widget can be identified uniquely.
  Rotation, mirroring, unqualified HiDPI, and ambiguous split-view layouts fail
  closed instead of guessing pointer coordinates.
- Color correction accepts only fully opaque composite pixels.
- A document, node, selection, projection, or relevant pixel change after Scan
  makes stale results ineligible for Apply.
- Apply changes only the selected Coloring pixels. It does not intentionally
  alter the selection, foreground color, active node, eraser mode, alpha lock,
  blend mode, opacity, or flow.
- The native helper resolves the scanned document and Coloring layer by UUID,
  validates expected-before bytes, applies sorted runs in one transaction, and
  verifies the complete resulting layer. Failure reverts and verifies touched
  bytes; there is no direct-Python writeback fallback.
- ONNX Runtime calls are synchronous and cannot be interrupted mid-call. Stop
  is checked before and after loading and each inference.
- Opening-like regions such as sleeves are outside GapFill's intended enclosed-
  gap capability.

For the exact qualification scope and exceptions, see
[Phase 6.5 host qualification](../docs/addon-phase6.5.md) and the
[1.0.2 interaction evidence](../docs/addon-interaction-1.0.2.md). The 1.1.0
selector and its completed bounded real-host qualification are recorded in
[Krita model-input modes](../docs/krita-model-input-modes.md).

## Install from a source checkout

This is for development. It does not by itself qualify a host or reproduce the
published Windows bundle.

The model is reused from `web/public/models/unet32.onnx` and copied into the
installed plugin:

```bash
python3.13 -m pip install -r krita-plugin/requirements-runtime.txt \
  --target krita-plugin/pykrita/gapfill_krita/_vendor
python3 krita-plugin/scripts/install_dev.py --dry-run
python3 krita-plugin/scripts/install_dev.py
```

Restart Krita, enable **GapFill for Krita** in Python Plugin Manager, and
restart again. Use `--resource-dir PATH` for a nonstandard resource directory.
Default locations are:

- Linux: `~/.local/share/krita`
- Windows: `%APPDATA%\krita`
- macOS: `~/Library/Application Support/krita`

These paths describe development installation only; they do not imply that the
current release is qualified on Linux or macOS.

## Build and test

Build a standard importable source ZIP, with the model included but binary
dependencies excluded:

```bash
python3 krita-plugin/scripts/build_plugin.py
```

Build a platform-specific self-contained ZIP after staging matching CPython
3.13 wheels:

```bash
python3.13 -m pip install -r krita-plugin/requirements-runtime.txt \
  --target krita-plugin/vendor
python3 krita-plugin/scripts/build_plugin.py \
  --vendor krita-plugin/vendor \
  --native-helper /path/to/gapfill_krita_native_5_3_3.cp313-win_amd64.pyd \
  --output krita-plugin/dist/gapfill-krita-platform.zip
```

The builder accepts only the helper filename and SHA-256 pinned in
`scripts/build_plugin.py`. Reproducible helper source and build instructions are
under `native/krita_5_3_3/`; Krita SDK files and build workspaces are not
distributed in the plugin ZIP.

Run the host-independent tests and lint checks:

```bash
python3.13 -m pip install -r krita-plugin/requirements-dev.txt
cd krita-plugin
pytest
ruff check .
```

The pure, Qt, and fake-adapter suites do not establish real-host compatibility.
Every advertised Krita distribution must execute the matrix in
`host_tests/matrix.json` on that real host.

## Architecture

```text
krita-plugin/
├── pykrita/
│   ├── gapfill_krita.desktop
│   └── gapfill_krita/
│       ├── engine/           # Detection, inference, and postprocessing
│       ├── controller.py     # Session state and orchestration
│       ├── host_contract.py  # Provenance and host-independent invariants
│       ├── krita_adapter.py  # LibKis acquisition and conversion
│       ├── native_backend.py # ABI/hash-checked native helper loader
│       ├── _native/          # Version-pinned Windows helper
│       ├── overlay.py        # Canvas preview and pointer interaction
│       ├── docker.py         # User interface
│       └── worker.py         # Cancellable background work
├── actions/                  # Krita action metadata
├── native/krita_5_3_3/       # Reproducible native-helper source/build
├── scripts/                  # Packaging and development installation
└── tests/                    # Krita-independent regression tests
```

The canonical behavior is documented in the
[GapFill specification](../docs/addon-spec.md). The published artifact and its
frozen identities are recorded in the
[1.1.0 release record](../docs/addon-release-1.1.0.md). Historical
1.0.2 release evidence remains in
[the 1.0.2 record](../docs/addon-release-1.0.2.md).

## Performance roadmap

Current learned prediction creates an ONNX Runtime session with
`CPUExecutionProvider` and evaluates the canonical `1 × 2 × 32 × 32` input once
per gap. Hardware acceleration, batching, caching, and preprocessing changes
are future work. They require measurement, output-parity tests, packaging and
driver analysis, and a new release-qualification matrix; they are not current
plugin behavior.

## License

The plugin source is released under the repository's
[MIT License](../LICENSE). The trained model is subject to the repository's
release terms. No preset or third-party anime images are packaged with this
plugin.
