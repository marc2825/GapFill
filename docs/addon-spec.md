# GapFill behavioral specification and golden-fixture contract

Phase: 2

Evidence freeze: 2026-08-13 (Asia/Tokyo)

Production baseline: `30c7f02b698e8a9d61bc1a4e866fa5d8d7e8bfe5`

## Status and scope

This document establishes the independently reviewable contract that must
precede production corrections. It does not assert that the web, Krita, CSP, or
ML implementation is correct merely because it is executable or tested. Phase 2
does not change production detection, inference, postprocessing, host behavior,
or fallback policy.

Every unresolved or canonical rule is assigned exactly one decision category:

- `STABLE`: evidence is strong enough to make the rule canonical now.
- `EMPIRICAL_DECISION_REQUIRED`: the checked-in artifact or controlled data has
  been characterized, but the evidence does not yet justify one canonical rule.

`NONCANONICAL_REFERENCE` is an expectation role, not an unresolved decision. It
keeps a historical, platform-specific, or experimental behavior executable for
comparison without presenting it as canonical truth. The maintainer reviewed
and resolved all seven former human product decisions as stable `D-01` through
`D-07` on 2026-08-13.

Characterization uses a separate vocabulary:

- `AGREES`
- `DELIBERATE_PLATFORM_DIFFERENCE`
- `UNRESOLVED_SPECIFICATION`
- `CONFIRMED_IMPLEMENTATION_DIVERGENCE`

Those values describe observations, not severity and not canonical truth. The
machine-readable results are in
`tests/fixtures/gapfill/parity/characterization.json`; a readable analysis is in
`docs/addon-parity.md`.

## Evidence hierarchy and pinned sources

Evidence is weighted in this order:

1. checked-in paper;
2. ML training/inference source and the exact ONNX artifact;
3. web implementation as an executable reference, but not an automatic oracle;
4. documented host behavior where platform semantics are involved;
5. add-on implementations/tests as evidence of current behavior only.

Pinned primary evidence:

| Evidence | SHA-256 / identity |
| --- | --- |
| Detailed CHI paper, `docs/assets/GapFill_CHI.pdf` | `5e9919ced3f5e74b6d0f7d6d252600242a2e6c0c3893dbbf3bd2e237c5979751` |
| WISS paper, `docs/assets/GapFill_WISS.pdf` | `c53c3f9039163ee1d9bef833dbe1a0308eeda9b5a8bcbd20f204a423a2bbd666` |
| ONNX model, `web/public/models/unet32.onnx` | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78` |
| ONNX sidecar, `web/public/models/model_info.json` | `70487679d7765f11224e0cffed0f0c002d91a7bcd188fca52502da39ef0c31e5` |
| ML preprocessing | `ml/src/utils/flood_fill/core.py`, `nearest_same_color.py`, `patch_utils.py` |
| ML postprocessing | `ml/src/utils/color_utils.py`, `ml/src/pipelines/inference_pipeline.py` |
| Web executable reference | `web/src/utils/GapFill/` |
| Krita pure engine | `krita-plugin/pykrita/gapfill_krita/engine/` |
| CSP pure core | `csp-plugin/src/core/`, `csp-plugin/src/predictors/` |

The detailed paper states that a gap is an enclosed transparent region on the
active coloring layer and that its boundary may be assembled with Line Art and
Guide layers (Section 4.1.1). It describes a two-channel binary input and a
likelihood-based region correspondence method (Sections 4.2.1-4.2.2). The ML
source is the higher-priority executable evidence for details omitted by the
paper, but its line-only training path does not establish Guide semantics.

## Shared data conventions

These conventions are `STABLE`:

- Coordinates have an upper-left origin; `x` increases right and `y` increases
  down.
- Flat indices are row-major: `pixel_index = y * width + x`.
- Bounding boxes are `[x, y, width, height]` unless explicitly named `xyxy`.
- RGBA fixture channels are 8-bit integers in logical R, G, B, A order.
- Binary tensors contain exactly `0.0` and `1.0` float32 values.
- A canonical expectation is marked `classification: STABLE` and
  `canonical: true`. No empirical or product-decision variant is canonical.

## Stable rules

### Detection topology

`DET-ENCLOSED` — `STABLE`

A candidate gap is conceptually an unpainted/transparent connected region that
is enclosed by the relevant raster boundaries. `D-01` through `D-05` below
freeze size, exterior-edge, alpha, selection, and connectivity semantics. Guide
composition and boundary rasterization remain empirical questions.

`D-05` — `STABLE`

The default connectivity is four orthogonal neighbors. This follows the ML
labeling structure, current default implementations, and the audited core.
Fixture `D005_diagonal_connectivity` therefore yields two one-pixel regions
under the canonical four-neighbor rule. Optional eight-connectivity is not part
of the canonical cross-platform contract.

`BOUNDARY-LINE-TRAINING` — `STABLE` as a training-path fact

The ML path binarizes grayscale Line Art at 128: values at or below 128 become
line/boundary, and values above 128 become fillable. This is a stable statement
about the model pipeline, not yet the chosen host rasterization policy.

### Centroid and patch geometry

`PATCH-GEOMETRY` — `STABLE`

- The centroid is `[floor(mean(x)), floor(mean(y))]`. Coordinates are
  nonnegative, so this equals truncation toward zero in the ML source.
- A 32x32 window begins at `centroid - 16` on each axis. The centroid therefore
  maps to patch coordinate `(16,16)`.
- Pixels outside the source image are exactly zero padded on the side where the
  virtual patch exceeds the image. Source pixels are not recentered within the
  remaining extent.

`P001` and `P002` freeze even and asymmetric centroids. `P003_top_left` through
`P003_bottom_right` cover every edge and corner. `P004` freezes an asymmetric
multi-pixel target mask.

### Model tensor contract

`MODEL-CHANNELS` — `STABLE` except for Guide composition

- Layout: NCHW.
- Input: float32 `[1,2,32,32]`, name `input_mask`.
- Channel 0: binary boundary context derived from Line Art. Whether and how
  Guides join this channel is explicitly unresolved.
- Channel 1: binary mask of exactly the target gap pixels within the patch.
- Output: float32 `[1,1,32,32]`, name `nearest_region_mask`.
- Output meaning: a spatial likelihood map for sharing the target region's
  color, not a direct RGB regression.

### Region score and representative color

`REGION-MEAN` — `STABLE` once semantic regions are defined

For each eligible semantic region, calculate the arithmetic mean of the output
likelihood over that region and select the region with the greatest mean. This
does not define how eligible regions are segmented or whether label 0 is one;
those remain empirical decisions.

`REGION-MODAL-COLOR` — `STABLE` once the winning region is defined

The representative color is the most frequent exact RGB value in the selected
region. `R001_manual_mean_winner` is hand-checkable: region means are 0.2 and
0.7, so region 2 wins and yields RGB `[20,20,220]`. `R007_antialiased_colors`
selects `[100,120,140]` because it occurs three times while each edge color
occurs once. Exact-tie behavior and participation are frozen by `D-06` below.

## Empirical decisions and completed experiments

All rules in this section remain `EMPIRICAL_DECISION_REQUIRED`. Experiments
characterize what exists; none silently promotes a variant to canonical truth.

### Guide composition in detection and model channel 0

Decision IDs: `GUIDE-DETECTION-COMPOSITION`,
`GUIDE-MODEL-COMPOSITION`, `GUIDE-TARGET-SUPPRESSION`.

Evidence conflict:

- Paper Section 4.1.1 permits combined Line Art/Guide boundaries.
- ML training patches contain Line Art only.
- the exported sidecar calls channel 0 “Line Art and Guides.”
- web/Krita OR Line Art and Guide alpha, split Guide-visible transparent pixels
  into a separate candidate type, and suppress target Guide pixels for a
  Guide-kind gap.
- CSP has no separate Line Art or Guide input.

Controlled results:

- `D007-D010` retain Guide-as-boundary, Guide-as-typed-candidate, and
  Guide-ignored variants.
- `D008_isolated_guide_pixel_open` shows a confirmed divergence: the
  Guide-as-boundary interpretation finds no enclosed component, while current
  web/Krita behavior reports the lone Guide pixel as a one-pixel Guide gap.
- `P005_guide_delta` records line-only and line-plus-Guide tensors.
- `P006_target_guide_suppression` records target-present and target-suppressed
  tensors.
- The exact ONNX artifact is sensitive to these one-pixel changes. `M001` versus
  `M002` changes all 1024 output values, with maximum absolute delta
  `0.2567824125` and mean absolute delta `0.0444267020`. `M006` versus `M007`
  (target Guide present versus suppressed) also changes all 1024 values, with
  maximum delta `0.2577674389` and mean delta `0.0613388440`.

The experiment proves sensitivity, not that either Guide variant is
in-distribution or semantically correct. A reviewed labeled Guide corpus or
retraining evidence is required before choosing.

### Faint and anti-aliased boundaries

Decision ID: `BOUNDARY-RASTERIZATION`.

`D012_faint_line_000/127/128/129/254/255` controls one pixel in an otherwise
closed ring. The ML training rule treats grayscale `0`, `127`, and `128` as
boundary and `129`, `254`, and `255` as fillable. Web/Krita use alpha `> 0`; in
the paired raster, that treats every case except fully transparent `255/alpha 0`
as boundary. The ONNX artifact sees only the resulting binary tensor; it cannot
recover grayscale/opacity discarded during rasterization. Real Krita rendering,
profiles, masks, blend modes, and layer visibility remain separate host tests.

### Region correspondence alternatives

Decision IDs: `REGION-CORRESPONDENCE`, `REGION-COLOR-TOLERANCE`.

The competing variants are retained by name:

- `ml_line_labels`: components derived from binarized Line Art;
- `colored_components`: opaque Coloring components, with Line/Guide blocking
  and seed-relative Manhattan RGB tolerance 30;
- `neighbor_transitive`: CSP owner-style neighbor-relative tolerance, which can
  chain across colors farther apart than 30.

`R003` distinguishes disconnected same-RGB areas. `R004` covers differences
29/30/31. `R005` proves the 0 -> 20 -> 40 transitive chain. `R008` makes a
line-derived region span red and blue colored components: ML chooses red while
current web/Krita select blue from the fixed probability map. No majority vote
is used to resolve this conflict.

### Label 0

Decision ID: `REGION-LABEL-ZERO`.

`R002_label_zero` assigns label 0 probability 0.99 and label 1 probability 0.4.
The current ML helper scores label 0 and returns black; web/Krita exclude label 0
and return green. The paper says “painted region” but does not define the label
map's background semantics tightly enough to choose safely.

### Exact model artifact and runtime tolerance

Decision ID: `MODEL-SEMANTIC-OUTPUT`.

The pinned model contract is:

| Field | Value |
| --- | --- |
| Size | 24,697,438 bytes |
| SHA-256 | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78` |
| IR / producer | IR 10; PyTorch `2.12.0+cu130` |
| Opset | default ONNX domain, 18 |
| Input | `input_mask`, `tensor(float)`, `[1,2,32,32]` |
| Output | `nearest_region_mask`, `tensor(float)`, `[1,1,32,32]` |
| Embedded metadata | none |

Seven fixed tensors cover no Guide, one Guide delta, symmetric geometry,
asymmetric geometry, boundary-near geometry, target Guide present, and target
Guide suppressed. Full 1024-value outputs are stored, not just hashes or shape
checks.

| Semantic fixture | SHA-256 of little-endian float32 output |
| --- | --- |
| `M001_no_guide` | `f6803fa3410932809e07332311c2c467789a01a8f7cf83a82018ba15be936dc1` |
| `M002_one_guide_delta` | `873e4fae797e2717002bdc15c25dec22b1ec59631528072f0f000016e8c8d0fa` |
| `M003_symmetric_geometry` | `be36bb97c83a2591b96aa6d55461f671c9f583a0c9a7df194c4b8265a9c17d01` |
| `M004_asymmetric_geometry` | `368002c4d1c960646bad70be1a8fcb4f7f1c020251904f237f0defad13eca398` |
| `M005_boundary_near_geometry` | `d74d60858f443a7c7fbb7d965e43c784fae51e0a255c4ca6774c9378aa9d9d1b` |
| `M006_target_guide_present` | `b8087455928ac3687b914a6792d25203cf94cd77a398208898d9b195d3caa7f8` |
| `M007_target_guide_suppressed` | `f6803fa3410932809e07332311c2c467789a01a8f7cf83a82018ba15be936dc1` |

Reviewed output generation used Python 3.12.3, NumPy 2.5.2, ONNX 1.22.0, and
ONNX Runtime 1.28.0 `CPUExecutionProvider` on Linux/WSL2 x86-64. Web parity used
Node 22.22.1 and `onnxruntime-web` 1.22.0 WASM. All seven outputs passed
`atol=1e-6`, `rtol=1e-5`; the observed maximum absolute WASM/Python delta was
`1.2516975402832031e-6`. The tolerance includes a small absolute floor for values
near zero plus a relative float32 convolution allowance. It is an artifact
parity bound, not an accuracy claim.

## Frozen maintainer decisions

The maintainer approved the following seven rules on 2026-08-13. They are
canonical `STABLE` expectations. Historical and experimental alternatives stay
in the corpus as `NONCANONICAL_REFERENCE`; current implementation mismatches are
not rewritten as passing behavior.

### `D-01` — inclusive gap-size threshold

- **Canonical rule:** accept a candidate exactly when
  `component_size <= threshold`; the threshold is the maximum accepted pixel
  count.
- **Rationale and provenance:** Paper Section 4.1.1 says “below,” Appendix A also
  says “size <= 10,” and ML, Web, Krita, and CSP already use the inclusive form.
  The maintainer resolved the prose ambiguity in favor of the explicit maximum.
- **Type:** core algorithm semantics.
- **Current differences:** all characterized implementations agree. Strict
  `< threshold` remains only as a noncanonical comparison.
- **Coverage:** `D002_threshold_triplet` independently contains components of
  size `T-1`, `T`, and `T+1`; the canonical result accepts the first two.

### `D-02` — image-boundary components are open

- **Canonical rule:** `touches_image_boundary => reject`. A transparent
  component connected to the image exterior is not enclosed.
- **Rationale and provenance:** “enclosed” in Paper Section 4.1.1 and the audited
  GapFill purpose distinguish gaps from transparent exterior regions; the
  maintainer approved conservative exterior rejection.
- **Type:** core algorithm semantics.
- **Current differences:** Krita and CSP agree. The ML preprocessing helper and
  Web retain the controlled one-pixel edge component and therefore diverge.
- **Coverage:** `D003_edge_touching_small` has canonical `reject_open_edge` and a
  retained noncanonical `allow_small_edge_component` characterization.

### `D-03` — only fully transparent Coloring pixels are gaps

- **Canonical rule:** default gap membership is `Coloring.alpha == 0`. Values
  `1..255` are painted and are not canonical unpainted GapFill pixels.
- **Rationale and provenance:** the paper describes transparent/unpainted
  Coloring; Web and Krita use exact zero. Partial-alpha cleanup may be offered
  only as an explicitly named future extension.
- **Type:** core algorithm semantics.
- **Current differences:** Web, Krita, and CSP's default threshold agree. The ML
  fixture reader receives an already prepared binary mask and does not implement
  Coloring-alpha membership at this stage. CSP's configurable `alpha <= N`
  setting is noncanonical when `N > 0`.
- **Coverage:** `D011_alpha_sweep` isolates alpha `0`, `1`, `127`, `254`, and
  `255`; only the alpha-zero pixel is canonical.

### `D-04` — selection is scope, not enclosure geometry

- **Canonical rule:** determine enclosure in the full accessible image geometry
  first, then intersect an enclosed component with the selection for
  eligibility/application. A selection boundary must never create a synthetic
  enclosure. If an API exposes only clipped geometry and a component touches the
  acquisition boundary, its geometry is `indeterminate` and it is rejected.
- **Rationale and provenance:** Paper Section 4.1.1 defines enclosure in image
  geometry; audit risks G-03 and C-10 show that selection topology and output
  coverage must be separated. The maintainer approved conservative behavior
  when outside geometry is unavailable.
- **Type:** core enclosure semantics plus product/platform acquisition and
  application-scope policy.
- **Current differences:** ML, Web, and the Krita pure detector do not implement
  selection scope. CSP core has the full `Image` but clips candidates before
  enclosure analysis, so it rejects `S001` instead of finding the full component
  and applying only its selected pixel. Whether the real CSP SDK exposes full or
  clipped geometry remains a host limitation requiring real-host verification;
  clipped-only rejection agrees with the conservative conditional rule.
- **Coverage:** `D013_selection_boundary` retains separate conditional canonical
  geometry variants. Policy cases `S001` (full geometry then selected subset),
  `S002` (clipped-domain indeterminate), and `S003` (enclosed but outside scope)
  freeze the distinction. `D014` covers a fully contained gap.

### `D-05` — four-neighbor connectivity

- **Canonical rule:** components use only `(x-1,y)`, `(x+1,y)`, `(x,y-1)`, and
  `(x,y+1)` neighbors.
- **Rationale and provenance:** this matches the ML labeling structure and every
  current default; the maintainer rejected diagonal adjacency as canonical
  GapFill connectivity.
- **Type:** core algorithm semantics.
- **Current differences:** all defaults agree. CSP's optional eight-neighbor
  mode is an intentional noncanonical extension if retained and must not become
  the default or be described as parity.
- **Coverage:** `D005_diagonal_connectivity` produces two components under the
  canonical rule and one only under `eight_neighbor_optional`.

### `D-06` — deterministic modal RGB ties

- **Canonical rule:** choose the exact RGB mode of the winning semantic region.
  On an equal maximum count, choose the first tied RGB encountered in row-major,
  top-to-bottom, left-to-right image order.
- **Participation:** each in-bounds Coloring pixel assigned to the winning
  semantic region participates once when its alpha is `1..255`. Alpha is neither
  part of the RGB key nor a weight. Alpha-zero target/gap pixels, pixels outside
  the winning region, Line/Guide-only boundary pixels, explicit exclusions, and
  virtual patch padding do not participate. With full geometry available, an
  application selection does not resample or reorder the semantic region.
- **Rationale and provenance:** the paper specifies a modal region color; ML and
  Web preserve image encounter order. The maintainer selected that deterministic
  lineage rather than numeric sorting or container iteration.
- **Type:** core postprocessing semantics.
- **Current differences:** ML and Web return the first row-major red value in
  `R006`; Krita numerically sorts the tied values and returns blue, a confirmed
  K-14 divergence. CSP has no learned region postprocessing stage.
- **Coverage:** independently reviewed `R006_modal_tie` contains two occurrences
  of each color in a 2x2 `red, blue / blue, red` raster. The canonical result is
  red; the sorted-lowest result is retained as noncanonical evidence.
  `MP001_modal_participation` independently excludes an alpha-zero pixel, an
  explicit exclusion, and an out-of-region pixel while giving alpha-1 and opaque
  in-region pixels one vote each.

### `D-07` — fallback provenance and explicit application

- **Canonical rule:** every prediction records `learned` or `fallback`
  provenance. Inference failure cannot transfer a learned confidence to the
  fallback. A fallback has no effective learned confidence, requires explicit
  user confirmation, and is excluded from Apply-High/high-confidence bulk or
  automatic application even if a heuristic reports a High-like score.
- **Rationale and provenance:** the paper emphasizes user control; audit K-11,
  C-02, and C-03 show untagged fallback paths and an uncalibrated CSP heuristic
  that can report High for a color absent from its input. This is a safety policy,
  not a claim that every fallback is inaccurate.
- **Type:** product safety/application policy.
- **Current differences:** Web and Krita store learned and greedy fallback
  colors in the same untagged result field. CSP lacks provenance, has no learned
  implementation, and Quick Fix can make a High rule result Apply by default.
  The ML pipeline has no product fallback/application policy at this stage.
- **Coverage:** policy contracts `F001` (successful learned High), `F002`
  (unconfirmed fallback with a High-like score), and `F003` (explicitly confirmed
  manual fallback) freeze provenance, confidence clearing, and Apply-High
  exclusion without inventing a raster oracle.

## Fixture contract

The shared hierarchy is:

```text
tests/fixtures/gapfill/
  manifest.json
  README.md
  detection/cases.json
  patch/cases.json
  model/cases.json
  postprocess/cases.json
  policy/cases.json
  end_to_end/annotations.json
  end_to_end/synthetic/.../*.png
  end_to_end/real/.../*.png
  parity/characterization.json
  parity/csp_detection_current.csv
tests/parity/
  test_krita_phase2_fixtures.py
  csp_phase2_fixture_reader.cpp
```

The JSON schema is deliberately limited to objects, arrays, strings, booleans,
integers, and finite decimal values. Python and TypeScript consume it directly.
C++ consumes a deterministic strict CSV projection for the stage it currently
implements; its first column is literally `current_behavior_not_golden` to
prevent accidental promotion. The projection contains whole-layer and
selection-scoped rows for every detection case. The manifest pins every fixture
file by SHA-256 and byte size and resolves every evidence/decision ID.

The reviewed `manifest.json` SHA-256 is
`6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`.
Running the generator twice in the recorded environment produced this same
hash; the manifest intentionally excludes its own checksum from its file list.

Detection has 19 controlled cases, including all required threshold, edge,
connectivity, Line/Guide, alpha, faint-line, and selection families. Patch has
13 cases covering centroid, every edge/corner, padding, target masks, Guide
deltas, and target suppression. Model has seven complete tensors/outputs.
Postprocessing has eight independently readable label/probability cases.
Policy has one modal-participation case, three selection/application cases, and
three fallback/application cases. End-to-end contains three synthetic artworks
and two reviewed Ex2 crops.

The real crops pin their source PNG hashes and exact crop rectangles. They have
human-readable annotations but no automatically inferred canonical mask or
model color. The completed Coloring crop is evidence for review, not a truth
oracle.

## Reproduction and validation

Create the isolated reference environment:

```bash
python3 -m venv /tmp/gapfill-phase2-venv
/tmp/gapfill-phase2-venv/bin/python -m pip install -r scripts/gapfill_reference/requirements.txt
```

The reviewed run used Python 3.12.3, NumPy 2.5.2, ONNX 1.22.0,
ONNX Runtime 1.28.0, OpenCV Headless 5.0.0.93, Pillow 12.3.0, and
SciPy 1.18.0. Web characterization used Node 22.22.1 and
`onnxruntime-web` 1.22.0. CSP fixture readers were compiled with GNU C++
13.3.0 through CMake 4.4.2 and the repository Makefile.

Regenerate the deterministic fixture structure and characterized Python ONNX
outputs from the pinned artifact:

```bash
/tmp/gapfill-phase2-venv/bin/python -m scripts.gapfill_reference.generate --write
```

Regeneration is a review operation: a changed output must be reviewed rather
than accepted solely because the generator emitted it. Read-only validation and
characterization commands are:

```bash
/tmp/gapfill-phase2-venv/bin/python -m scripts.gapfill_reference.validate
/tmp/gapfill-phase2-venv/bin/python -m unittest scripts.gapfill_reference.test_reference -v
/tmp/gapfill-phase2-venv/bin/python -m scripts.gapfill_reference.characterize_python
(cd web && node --experimental-strip-types --test src/tests/GapFill/phase2Fixtures.test.mjs)
(cd krita-plugin && python -m pytest -q tests ../tests/parity/test_krita_phase2_fixtures.py)
make -C csp-plugin test
```

The equivalent CMake/CTest path is:

```bash
cmake -S csp-plugin -B /tmp/gapfill-phase2-cmake -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/gapfill-phase2-cmake --config Release --parallel 2
ctest --test-dir /tmp/gapfill-phase2-cmake -C Release --output-on-failure
```

The `gap_assist_phase2_fixtures` entry receives the shared CSV path from the
source tree.

## Phase 3 entry conditions

Phase 3 may start only when:

1. this specification, manifest, and decisions `D-01` through `D-07` are
   reviewed and frozen;
2. every intended Phase 3 change cites a decision ID and does not depend on an
   unresolved semantic choice;
3. fixture validation, Python ML/Krita characterization, Web/WASM parity, Krita
   shared-fixture tests, and CSP CSV parity are green;
4. any regenerated ONNX value or tolerance change receives explicit review;
5. known mismatches remain reported rather than converted into passing
   canonical expectations;
6. production subtree comparison confirms Phase 2 changed no production
   implementation.

These entry conditions are met by the freeze verification recorded in
`docs/addon-parity.md`. Phase 3 may therefore begin in a later, explicitly
authorized task and remains limited to the already planned CSP output/CLI safety
work. Detection, model, Guide, region-correspondence, host, UI, and packaging
behavior remain out of scope until their later phases and required decisions.
