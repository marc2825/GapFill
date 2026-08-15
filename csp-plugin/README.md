# Gap Assist for CLIP STUDIO PAINT

Gap Assist is a post-process gap detector and reviewer for anime-style coloring.
It analyzes a raster after normal bucket/brush work, predicts a color for small
enclosed transparent regions, and produces reviewed corrections. It does not
intercept CLIP STUDIO PAINT tools or canvas events. The public pure core now
contains canonical learned preprocessing/postprocessing; a distributable CSP
ONNX Runtime adapter is not yet included.

This directory currently provides the complete SDK-independent C++20 core, a
PNG review harness, host integration contracts, and automated tests. The final
CELSYS SDK entry point is intentionally not vendored: downloading that SDK
requires the developer to accept CELSYS's terms, and distributable plug-ins are
subject to CELSYS's submission process. See the [official SDK page](https://www.clipstudio.net/ja/sdk/)
and [SDK integration](docs/SDK_INTEGRATION.md).

## Implemented behavior

- Small/Medium/Large/Custom detection over exact-alpha-zero Coloring membership.
- Normalized binary Line/Guide boundary inputs in the public pure core; current
  CLI/native acquisition is single-raster-only and is not GapFill parity.
- Four- or eight-neighbor connectivity and exclusion of open boundary regions.
- Whole-layer and selection-only scopes.
- Canonical Line-only 32×32 learned tensor construction, full-image Line-region
  scoring, deterministic modal RGB, and a small validated inference-backend
  interface independent of CELSYS.
- Explicit Rule-Based heuristic fallback with owner-region IDs and a separate
  diagnostic score; it has no learned confidence and never enters Apply-High.
- Conservative, Balanced, and Aggressive bands for learned confidence only.
- Quick Fix, Review List, and One-by-One review state machines.
- Apply, skip, mark-only, apply-selected, and apply-high-confidence decisions.
- Transparent correction, confidence-highlight, corrected-preview, JSON manifest,
  and before/after contact-sheet outputs.
- Cancellation/progress hooks, settings persistence, and safe host capability checks.
- A replaceable predictor interface; the public distribution stub rejects an
  ONNX request because native ONNX Runtime packaging is still pending.
- No network access, telemetry, or image-content logging.

## Build and test

Requirements are a C++20 compiler and either Make or CMake 3.20+.

```bash
cd csp-plugin
make -j2
make test
make test-phase5 PHASE5_PYTHON=/path/to/python-with-numpy-and-onnxruntime
make test-e2e
```

`test-phase5` executes the pinned model through local Python ONNX Runtime and
feeds its output through the C++ backend contract. It is semantic/runtime parity
coverage, not the distributable native CSP adapter.

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
with `--decisions decisions.txt`. `--apply-high` accepts all remaining
high-confidence Unreviewed **learned** candidates. Rule-Based heuristic
suggestions are never bulk-applied and require an explicit per-gap Apply
decision. Explicit Apply, Skip, and Mark Only decisions always win. Exact
duplicate decisions are accepted idempotently, while
contradictory duplicates fail. Settings precedence is built-in defaults, then
the settings file, then explicit command-line overrides, independent of where
`--settings` appears. Repeated instances of the same CLI option use the last
occurrence. Import the correction PNG into CSP as a new raster layer
above the coloring layer. Import the highlight PNG only when desired.

Use `--help` for every option. A nontransparent selection-mask PNG may be passed
with `--selection`; full-image geometry determines enclosure first, then only
selected pixels of an enclosed component are eligible for correction. Selection
edges never manufacture enclosure.

## CSP integration status

The 2021-08-27 CELSYS Filter Plug-in SDK has been evaluated for the initial
Windows target. Its filter surface exposes one source/destination raster,
selection, property/Preview flow, and progress/cancellation, but not independent
sibling Coloring, Line and Guide sources, arbitrary/named layers, or a layer
tree. Phase 7 therefore classifies it as
`C. INSUFFICIENT_FOR_GAPFILL_PARITY`.

The private adapter compiled with MSVC, but was not installed or real-host
qualified. It has no packaged ONNX backend and supplies empty Line/Guide input;
D-07 also prevents its Rule-Based heuristic from being auto-applied. Compile
success is not a GapFill implementation. Any surviving single-layer/rule-based
feature must be separately differentiated as heuristic, disclose the missing
multi-layer semantics, and retain explicit confirmation. The explicit-decision
PNG companion remains the reviewable path.

The local SDK adapter lives under the ignored `FilterPlugIn20210827` directory.
It is intentionally not part of the public source tree because the SDK agreement
contains separate distribution and confidentiality conditions. See the
[evaluated capability report](docs/CSP_SDK_20210827_CAPABILITIES.md).

The publicly described CSP filter plug-in mechanism targets desktop CLIP STUDIO
PAINT EX. It is not an iPad extension mechanism. Read [known limitations](docs/LIMITATIONS.md)
before attempting an installable build.

## Native CSP release gate

Do not distribute or describe the compiled 2021-SDK artifact as GapFill. A
future native GapFill route must first expose the complete public canonical
input contract and fail closed for unsupported documents, then pass the real
host matrix. A separately scoped heuristic product would need its own product,
qualification, and release decision. Neither route is Phase 8 work here.

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
