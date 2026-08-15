# GapFill for Krita

GapFill for Krita ports the paper's gap-detection and region-correspondence color-prediction workflow into a native Python docker. The code has PyQt5/PyQt6 import shims, but **no real Krita distribution has completed the Phase 6 host matrix yet**. Deterministic apply now requires the public view-state controls exposed by Krita 6; older builds fail closed if those controls are absent.

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
- Applies fills through Krita's native selection-fill action, verifies exact target pixels, and restores user state. Public LibKis does not provide an undo macro for the internal selection actions, so one-step atomic Undo is not yet guaranteed.
- Performs detection and inference off the UI thread and supports cancellation.

## Install a Release Bundle

Use the bundle matching your operating system. The platform bundle contains NumPy, ONNX Runtime, and `unet32.onnx`; a plain source ZIP does not contain binary Python dependencies.

1. In Krita, choose **Tools → Scripts → Import Python Plugin From File…** and select `gapfill-krita-<platform>.zip`.
2. Restart Krita.
3. Open **Settings → Configure Krita… → Python Plugin Manager**, enable **GapFill**, and restart Krita again.
4. Show the docker with **Settings → Dockers → GapFill**. If hidden, use **Tools → Scripts → Show GapFill Docker**.

Python plugins are disabled by default in Krita, so the enable-and-restart step is required.

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

Apply saves and normalizes foreground color, eraser mode, global alpha lock,
blending mode, opacity, flow, active node, and the exact global selection. It
restores semantic no-selection with `None`, reads back the entire Coloring layer,
and keeps suggestions on failure. A successful apply invalidates every remaining
suggestion and requires a rescan. The public selection-fill route creates host
Undo commands that cannot be grouped by LibKis; exact command order and Undo/redo
remain a real-host release gate.

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
  --output krita-plugin/dist/gapfill-krita-platform.zip
```

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
- Confirm applied pixels land only on Coloring, the exact original selection
  presence/bytes and foreground/tool state return, and record every visible Undo
  and redo step. One-step atomic Undo is not currently claimed.
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
│       ├── overlay.py       # Canvas preview and pointer interactions
│       ├── docker.py        # User interface
│       └── worker.py        # Cancellable background work
├── actions/                 # Krita action metadata
├── scripts/                 # Packaging and development installation
└── tests/                   # Krita-independent regression tests
```

## License

The plugin source is released under the repository's [MIT License](../LICENSE). The trained model is subject to the repository's release terms. No preset or third-party anime images are packaged with this plugin.
