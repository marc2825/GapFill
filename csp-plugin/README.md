# Gap Assist for CLIP STUDIO PAINT

Gap Assist is a post-process gap detector and reviewer for anime-style coloring.
It analyzes an active raster layer after normal bucket/brush work, predicts a
nearby color for small enclosed transparent regions, and either applies a native
Quick Fix or produces a transparent companion correction image. It does not
intercept CLIP STUDIO PAINT tools or canvas events.

This directory currently provides the complete SDK-independent C++20 core, a
PNG review harness, host integration contracts, and automated tests. The final
CELSYS SDK entry point is intentionally not vendored: downloading that SDK
requires the developer to accept CELSYS's terms, and distributable plug-ins are
subject to CELSYS's submission process. See the [official SDK page](https://www.clipstudio.net/ja/sdk/)
and [SDK integration](docs/SDK_INTEGRATION.md).

## Implemented behavior

- Small/Medium/Large/Custom gap detection with configurable alpha threshold.
- Four- or eight-neighbor connectivity and exclusion of open boundary regions.
- Whole-layer and selection-only scopes.
- Rule-based, distance-weighted nearby-color prediction with owner-region IDs.
- Conservative, Balanced, and Aggressive confidence bands.
- Quick Fix, Review List, and One-by-One review state machines.
- Apply, skip, mark-only, apply-selected, and apply-high-confidence decisions.
- Transparent correction, confidence-highlight, corrected-preview, JSON manifest,
  and before/after contact-sheet outputs.
- Cancellation/progress hooks, settings persistence, and safe host capability checks.
- A replaceable predictor interface and an explicit local ONNX stub/fallback.
- No network access, telemetry, or image-content logging.

## Build and test

Requirements are a C++20 compiler and either Make or CMake 3.20+.

```bash
cd csp-plugin
make -j2
make test
make test-e2e
```

Equivalent CMake commands:

```bash
cmake -S csp-plugin -B csp-plugin/build -DCMAKE_BUILD_TYPE=Release
cmake --build csp-plugin/build --config Release
ctest --test-dir csp-plugin/build -C Release --output-on-failure
```

## PNG review workflow

Export the coloring layer from CSP as an RGBA PNG, preserving transparency, then run:

```bash
csp-plugin/build/gap_assist_cli \
  --input coloring.png \
  --mode review \
  --gap-size medium \
  --confidence balanced
```

The source PNG is never overwritten. Default outputs are:

- `coloring.gap-corrections.png` — transparent pixels for accepted corrections.
- `coloring.gap-highlights.png` — medium/low/skipped gap markers.
- `coloring.gap-corrected.png` — flattened preview only.
- `coloring.gap-review.png` — before/after contact sheet.
- `coloring.gap-manifest.json` — IDs, geometry, prediction, confidence, and status.

Every active output must be distinct from the input and from every other output,
including filesystem aliases such as existing symbolic or hard links. Existing
outputs are refused by default; pass `--force` to replace them. `--force` never
permits an alias. Gap Assist encodes every artifact before staging same-directory
temporary files, keeps recoverable backups while installing replacements, and
rolls the set back when a staged write or rename fails. This is process-level
best-effort rollback, not a crash-proof multi-file filesystem transaction; a
process or machine failure can leave a hidden `.gap-assist-backup-*` recovery
file, and directory durability is not guaranteed because directories are not
`fsync`ed.

Edit a decisions file using `examples/review_decisions.example.txt`, then rerun
with `--decisions decisions.txt`. `--apply-high` accepts all remaining high-
confidence Unreviewed candidates; explicit Apply, Skip, and Mark Only decisions
always win. Exact duplicate decisions are accepted idempotently, while
contradictory duplicates fail. Settings precedence is built-in defaults, then
the settings file, then explicit command-line overrides, independent of where
`--settings` appears. Repeated instances of the same CLI option use the last
occurrence. Import the correction PNG into CSP as a new raster layer
above the coloring layer. Import the highlight PNG only when desired.

Use `--help` for every option. A nontransparent selection-mask PNG may be passed
with `--selection`; regions touching the selection boundary are treated as open
and are excluded.

## CSP integration status

The 2021-08-27 CELSYS Filter Plug-in SDK has been evaluated for the initial
Windows target, CLIP STUDIO PAINT EX 4.0.10. It exposes an active RGB raster
layer, destination pixels, selection data, a standard property dialog, Preview,
progress/cancellation, and the normal filter commit/Undo flow. It does not expose
document-layer creation or the dynamic list/thumbnail UI required by the full
Review List and One-by-One designs.

Accordingly, the native Windows plug-in is a conventional **Quick Fix** filter:
it applies High-confidence corrections only, through CSP's standard Preview,
OK, and Cancel flow. Duplicate the coloring layer before running it when an
editable, non-destructive copy is required. The full Review List, One-by-One,
Correction Layer, and Highlight Layer workflow remains available through the PNG
review companion described above.

The local SDK adapter lives under the ignored `FilterPlugIn20210827` directory.
It is intentionally not part of the public source tree because the SDK agreement
contains separate distribution and confidentiality conditions. See the
[evaluated capability report](docs/CSP_SDK_20210827_CAPABILITIES.md).

The publicly described CSP filter plug-in mechanism targets desktop CLIP STUDIO
PAINT EX. It is not an iPad extension mechanism. Read [known limitations](docs/LIMITATIONS.md)
before attempting an installable build.

## Next step for the Windows CSP build

1. Install Visual Studio 2022 with Desktop development with C++, the optional
   MSVC v142 x64/x86 toolset used by this SDK generation, a Windows 10/11 SDK,
   and CMake tools for Windows.
2. Build the private x64 adapter by following
   `FilterPlugIn20210827/GapAssistPrivate/README.md` on the local machine.
3. Test the resulting `.cpm` in a disposable document on CSP EX 4.0.10 using
   [the native manual test plan](docs/MANUAL_TEST_PLAN.md).
4. Before any binary distribution, follow [the release checklist](docs/RELEASE_CHECKLIST.md)
   and CELSYS's required submission/approval route.

## Documentation

- [Product specification and acceptance matrix](docs/CSP_GAP_ASSIST_SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [SDK integration](docs/SDK_INTEGRATION.md)
- [Evaluated 2021 SDK capabilities](docs/CSP_SDK_20210827_CAPABILITIES.md)
- [Known limitations](docs/LIMITATIONS.md)
- [Privacy](docs/PRIVACY.md)
- [Native manual test plan](docs/MANUAL_TEST_PLAN.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

The project source is covered by the repository's MIT license. CELSYS SDK files
and CLIP STUDIO PAINT are not part of this repository or that grant.
