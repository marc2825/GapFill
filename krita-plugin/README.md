# GapFill for Krita

GapFill for Krita ports the paper's gap-detection and region-correspondence color-prediction workflow into a native Python docker. It is intended for **Krita 5.3 or Krita 6 on 64-bit desktop platforms** and supports both PyQt5 and PyQt6.

## Features

- Detects small, enclosed, fully transparent components on the selected Coloring layer.
- Treats Line Art and Guide pixels as detection boundaries; only enclosed,
  uncovered Coloring transparency is paintable gap geometry.
- Excludes Line Art pixels and open components touching the document boundary.
- Runs the same 2-channel, 32×32 U-Net model used by the web application and validates its full input/output contract.
- Shows temporary suggested fills, circular highlights, and a fixed 5× hover magnifier.
- Supports in-circle drag-to-correct, out-circle sweep-to-apply, list-based correction, Apply Selected, and Apply All.
- Applies fills through Krita's native selection-fill action so edits participate in Krita's undo history.
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

- **Coloring** must be an unlocked RGBA/U8 paint layer. Unpainted pixels must be fully transparent.
- **Line Art** must have a transparent background; its nonzero alpha pixels are boundaries and never gaps.
- **Guides** are optional and must also have a transparent background. Their
  nonzero-alpha pixels are detection boundaries, not paintable Guide-gap pixels.
  A Guide-only or mixed Line/Guide enclosure may bound an ordinary transparent
  Coloring gap; an isolated Guide in open transparency does not create a gap.
- A white Background layer may remain visible below the other layers, but do not select it as Coloring, Line Art, or Guides. It is only visual backing and does not change the Coloring layer's transparency.

The selected nodes are read in document coordinates. If layers are moved or transformed after scanning, rescan before applying suggestions.

The pure detector first converts these RGBA snapshots into separate binary
Coloring-membership, Line-boundary, and Guide-boundary masks. Coloring membership
is exactly alpha zero. The current Krita conversion preserves the existing
any-nonzero-alpha Line/Guide rule; the correct faint/anti-aliased host
rasterization threshold remains an empirical question and is not an ONNX policy.

## Interaction

1. Set the maximum gap size and select **Scan / Activate**.
2. Hover a circular marker to inspect its fixed 5× magnifier.
3. Drag from inside a circle to sample a replacement color from the visible composite. Hover the magnifier's **×** to cancel correction.
4. Drag from outside the circles to sweep over several suggestions, then release to apply them.
5. Alternatively, correct colors in the docker and use **Apply Selected** or **Apply All**.

The ONNX model must load successfully before suggestions are shown. A missing model or runtime is displayed as an error in the docker instead of silently replacing all predictions with the greedy heuristic. The optional greedy fallback is limited to an isolated inference failure after the model has loaded.

Krita creates one undoable fill operation per distinct color in an applied batch. Undo repeatedly if a batch contained multiple colors.

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

The engine suite runs without Krita or Qt. A final release must also complete the manual smoke test below in both Krita 5.3 and Krita 6 because the canvas widget is an internal Qt widget rather than part of LibKis's public API.

## Release Smoke Test

- Import and enable the clean release ZIP on a machine without development packages.
- Scan a document with normal gaps, Guide gaps, a white Background, and an open transparent exterior.
- Confirm that only enclosed gaps below the threshold are listed.
- Confirm previews, transformed/rotated canvas markers, 5× magnifier, correction cancellation, color sampling, sweep, Apply Selected, and Apply All.
- Confirm Stop cancels a large scan and the canvas remains responsive.
- Confirm missing/corrupt model errors are visible.
- Confirm applied pixels land only on Coloring and undo restores them.
- Repeat with a pre-existing Krita selection and foreground color and confirm both are restored.

## Architecture

```text
krita-plugin/
├── pykrita/
│   ├── gapfill_krita.desktop
│   └── gapfill_krita/
│       ├── engine/          # NumPy detection, patching, inference, postprocessing
│       ├── controller.py    # Application state and orchestration
│       ├── krita_adapter.py # LibKis layer snapshots and undoable application
│       ├── overlay.py       # Canvas preview and pointer interactions
│       ├── docker.py        # User interface
│       └── worker.py        # Cancellable background work
├── actions/                 # Krita action metadata
├── scripts/                 # Packaging and development installation
└── tests/                   # Krita-independent regression tests
```

## License

The plugin source is released under the repository's [MIT License](../LICENSE). The trained model is subject to the repository's release terms. No preset or third-party anime images are packaged with this plugin.
