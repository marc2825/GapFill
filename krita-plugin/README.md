# GapFill for Krita

GapFill for Krita ports the paper's gap-detection and region-correspondence color-prediction workflow into a Python docker with a narrowly version-pinned native mutation helper. **No real Krita distribution has completed the Phase 6.5 host matrix yet.** The only Apply host currently admitted by the implementation is Windows x64, Krita 5.3.3 git `858d352`, Qt 5.15.7, and CPython 3.13.5; every other host fails closed before loading the helper.

## Features

- Detects small, enclosed, fully transparent components on the selected Coloring layer.
- Treats Line Art and Guide pixels as detection boundaries; only enclosed,
  uncovered Coloring transparency is paintable gap geometry.
- Excludes Line Art pixels and open components touching the document boundary.
- Runs the pinned 2-channel, 32×32 U-Net with a Line-only boundary channel,
  validates its hash/interface/output, scores full-image Line-derived semantic
  regions, and returns their deterministic modal RGB.
- Shows temporary suggested fills, circular highlights, and a fixed 5× hover magnifier.
- Supports in-circle drag-to-correct, out-circle sweep-to-apply, list-based correction, Apply Selected, and Apply All.
- Converts every selected correction through `CanvasColorBridge`, sends the complete exact BGRA/U8 patch in one native transaction, and validates the full Coloring layer byte-for-byte. Formal production Row I passed exact one-step Undo/Redo in the admitted Windows/Krita host cell; the remaining Phase 6.5 matrix is still incomplete.
- Performs detection and inference off the UI thread and supports cancellation.

## Install a Release Bundle

Use only a qualification bundle built for the exact supported host cell. It contains NumPy, ONNX Runtime, `unet32.onnx`, and the hash-pinned native helper. A plain source ZIP does not contain binary Python dependencies or the helper and therefore cannot perform Apply.

1. In Krita, choose **Tools → Scripts → Import Python Plugin From File…** and select `gapfill-krita-<platform>.zip`.
2. Restart Krita.
3. Open **Settings → Configure Krita… → Python Plugin Manager**, enable **GapFill**, and restart Krita again.
4. Show the docker with **Settings → Dockers → GapFill**. If hidden, use **Tools → Scripts → Show GapFill Docker**.

Python plugins are disabled by default in Krita, so the enable-and-restart step is required.
Exit Krita completely before replacing or removing a bundle: Windows keeps a loaded `.pyd` locked until the process exits.

## Install from This Checkout

The model is reused from `web/public/models/unet32.onnx` and copied into the installed plugin:

```bash
python3.13 -m pip install -r krita-plugin/requirements-runtime.txt \
  --target krita-plugin/pykrita/gapfill_krita/_vendor
python3 krita-plugin/scripts/install_dev.py --dry-run
python3 krita-plugin/scripts/install_dev.py
```

Restart Krita, enable GapFill in Python Plugin Manager, and restart again. Use `--resource-dir PATH` if Krita uses a nonstandard resource directory. The default locations are:

- Linux: `~/.local/share/krita`
- Windows: `%APPDATA%\krita`
- macOS: `~/Library/Application Support/krita`

## Layer Setup

Choose layers in the GapFill docker before scanning:

- **Coloring** must be an unlocked, origin-aligned, non-animated RGBA/U8 paint layer with no child masks/effects or layer style. It and its parents must be visible, fully opaque, Normal-blended, and not use inherit alpha. Unpainted pixels must be fully transparent.
- **Line Art** must have a transparent background; its nonzero alpha pixels are boundaries and never gaps.
- **Guides** are optional and must also have a transparent background. Their
  nonzero-alpha pixels are detection boundaries, not paintable Guide-gap pixels.
  A Guide-only or mixed Line/Guide enclosure may bound an ordinary transparent
  Coloring gap; an isolated Guide in open transparency does not create a gap.
- A white Background layer may remain visible below the other layers, but do not select it as Coloring, Line Art, or Guides. It is only visual backing and does not change the Coloring layer's transparency.

The selected nodes are read over the document rectangle. Line/Guide projections
must be visible RGBA/U8 nodes under neutral parents and currently must share the
document profile. Moved Coloring layers, Coloring masks/effects/styles, mixed
profiles, and documents larger than 16,777,216 pixels are rejected before
preview. Any document/node/selection/projection change after scanning makes the
result stale and prevents apply.

The pure detector first converts these RGBA snapshots into separate binary
Coloring-membership, Line-boundary, and Guide-boundary masks. Coloring membership
is exactly alpha zero. Detection preserves its Phase 4 any-nonzero-alpha
Line/Guide normalization. Learned prediction is deliberately separate: channel
0 contains Line Art only after logical straight-alpha RGBA is composited over
byte white and thresholded at inclusive grayscale 128. Guides remain detection
boundaries but are excluded from the trained model tensor. Real Krita
profile/render conversion into those logical bytes remains a host test.

## Interaction

1. Set the maximum gap size and select **Scan / Activate**.
2. Hover a circular marker to inspect its fixed 5× magnifier.
3. Drag from inside a circle to sample a replacement color from the visible composite. Hover the magnifier's **×** to cancel correction.
4. Drag from outside the circles to sweep over several suggestions, then release to apply them.
5. Alternatively, correct colors in the docker and use **Apply Selected** or **Apply All**.

Interactive overlays currently support only an unrotated, unmirrored, device
pixel ratio 1 canvas whose internal QWidget can be identified uniquely inside
the active window. Rotation, mirror, unqualified HiDPI, and ambiguous split-view
layouts disable the overlay instead of guessing at pointer coordinates.
Sampling accepts only fully opaque composite pixels; semi-transparent samples
are ignored because converting them into an opaque fill has no backdrop-stable
perceived color.

The ONNX model must load successfully before suggestions are shown. A missing,
wrong-hash, malformed, or incompatible model/runtime is displayed as an error
instead of silently replacing all predictions with the greedy heuristic. An
isolated per-gap failure may use the optional greedy fallback only when at least
one learned prediction succeeded; its provenance is `fallback` and its learned
confidence is null. If every gap fails, the batch fails without committing
partial prediction metadata. A no-gap scan does not load the model.

ONNX Runtime calls are synchronous and cannot be interrupted mid-call. Stop is
checked before and after load and each inference; results are attached only
after the complete batch reaches a cancellation boundary.

Apply does not create or replace a selection and does not change foreground
color, active node, eraser mode, alpha lock, blending mode, opacity, or flow.
Python retains the frozen application plan and profile conversion, then sends
all colors and pixels in one call to the exact-host native helper. The helper
resolves the scanned document by image-root UUID and the Coloring layer by node
UUID, validates expected-before bytes, and writes sorted horizontal runs inside
one Krita transaction. Native failure reverts and verifies the touched bytes;
success must pass a full-layer exact raw-byte readback. There is no fallback to
`fill_selection_foreground_color` or direct Python writeback. A successful apply
invalidates every remaining suggestion and requires a rescan. Formal one-step
Undo/Redo passed in the admitted Windows/Krita host cell; remaining Phase 6.5
rows still gate overall release qualification.

## Build and Test

Create a standard importable ZIP (model included, binary dependencies excluded):

```bash
python3 krita-plugin/scripts/build_plugin.py
```

Create a platform-specific self-contained ZIP after installing matching Python 3.13 wheels into a staging directory:

```bash
python3.13 -m pip install -r krita-plugin/requirements-runtime.txt \
  --target krita-plugin/vendor
python3 krita-plugin/scripts/build_plugin.py \
  --vendor krita-plugin/vendor \
  --native-helper /path/to/gapfill_krita_native_5_3_3.cp313-win_amd64.pyd \
  --output krita-plugin/dist/gapfill-krita-platform.zip
```

The builder accepts only the exact helper filename and SHA-256 recorded in
`scripts/build_plugin.py`. The reproducible helper source/build recipe is under
`native/krita_5_3_3/`; the compiler, Krita headers/import libraries, and build
workspace are not distributed in the plug-in ZIP.

Run the engine tests and lint checks:

```bash
python3.13 -m pip install -r krita-plugin/requirements-dev.txt
cd krita-plugin
pytest
ruff check .
```

The pure, Qt, and fake-adapter suites run without Krita. They do not establish
host compatibility. A release must execute `host_tests/matrix.json` in every
advertised real Krita distribution.

## Release Smoke Test

- Import and enable the clean release ZIP on a machine without development packages.
- Scan a document with normal gaps, Guide gaps, a white Background, and an open transparent exterior.
- Confirm that only enclosed gaps below the threshold are listed.
- Confirm previews, pan/zoom markers, 5× magnifier, correction cancellation,
  color sampling, sweep, Apply Selected, and Apply All at DPR 1. Confirm
  rotation, mirror, HiDPI, and ambiguous split views fail closed until qualified.
- Confirm Stop cancels a large scan and the canvas remains responsive.
- Confirm missing/corrupt model errors are visible.
- Confirm applied pixels land only on Coloring, selection and foreground/tool
  state remain exact, and record every visible Undo and redo step. Row I is
  qualified only for the admitted host cell and must be repeated for any future
  supported host matrix.
- Run every A–V row in `host_tests/matrix.json`; leave unavailable rows UNTESTED.

## Architecture

```text
krita-plugin/
├── pykrita/
│   ├── gapfill_krita.desktop
│   └── gapfill_krita/
│       ├── engine/          # NumPy detection, patching, inference, postprocessing
│       ├── controller.py    # Application state and orchestration
│       ├── host_contract.py # Immutable provenance and host-independent invariants
│       ├── krita_adapter.py # LibKis acquisition, conversion, apply/readback
│       ├── native_backend.py # Exact-host guard and hash/ABI-checked helper loader
│       ├── _native/         # Packaged version-pinned Windows helper location
│       ├── overlay.py       # Canvas preview and pointer interactions
│       ├── docker.py        # User interface
│       └── worker.py        # Cancellable background work
├── actions/                 # Krita action metadata
├── native/krita_5_3_3/      # Reproducible pinned helper source/build definition
├── scripts/                 # Packaging and development installation
└── tests/                   # Krita-independent regression tests
```

## License

The plugin source is released under the repository's [MIT License](../LICENSE). The trained model is subject to the repository's release terms. No preset or third-party anime images are packaged with this plugin.
