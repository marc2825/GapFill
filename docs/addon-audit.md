# GapFill add-on baseline and audit

Audit date: 2026-08-12 (Asia/Tokyo)

Scope: `main`, `feature/krita-addon`, and the stacked
`feature/csp-addon`; the original paper, ML pipeline, ONNX artifact, and web
implementation were used as primary behavioral evidence. This audit does not
change either add-on's production behavior.

## Executive conclusion

The branches are buildable and their automated checks are green, but that is
not yet a trustworthy correctness baseline.

- The Krita add-on is recognizably an implementation of the paper's interaction
  and learned-prediction design. Its pure engine closely follows the current web
  code, including several choices that are not established by the paper or the
  training pipeline. The remaining highest risks are at the Krita boundary:
  canvas/profile color conversion, stale scan application, rotation/mirroring,
  cancellation races, selection/undo behavior, color management, and bundled
  binary compatibility.
- The CSP public core is not a port of the learned GapFill algorithm. It detects
  transparent components from one RGBA layer and uses an independently invented
  rule-based color heuristic. On tracked repository artwork, it misses most or
  all candidates found when line art and guides are included. A focused probe
  also made it invent a color absent from the source and assign confidence 1.0.
- The actual CELSYS adapter exists only in a locally ignored SDK directory. It
  is not part of either feature commit, is not built by public CI, and has not
  been exercised in CSP. Public host mocks test a richer future interface, not
  the adapter that would ship.
- The paper, ML code, exported metadata, and web code are not mutually
  consistent. Green tests derived from one implementation cannot resolve those
  disagreements. Cross-implementation golden fixtures are the required next
  step.

One Critical issue was confirmed: the central CSP detector cannot represent the
paper's multi-layer gap geometry and misses all reference candidates on most
tracked presets. There are also multiple High-severity confirmed or strongly
suspected issues that should block calling either add-on release-ready. In
particular, do not publish the CSP build as a GapFill port or ship the Krita
bundle until the Critical/High findings below have been closed.

## Evidence policy

Evidence was weighted in this order:

1. The checked-in [GapFill paper](assets/GapFill_WISS.pdf) and its
   interaction/algorithm descriptions.
2. The training and inference code under `ml/`, plus the exact checked-in ONNX
   model contract.
3. The web implementation as an executable reference, but not as an automatic
   oracle where it conflicts with 1 or 2.
4. Official Krita API documentation and the locally supplied CELSYS SDK
   documentation/adapter boundary.
5. Add-on READMEs and tests as evidence of current intent, not proof that the
   intent is correct.

Confidence labels in the register mean:

- **Confirmed**: directly demonstrated by code, artifact inspection, or a
  reproducible probe.
- **Strong suspicion**: code and API evidence point to a defect, but a real host
  or platform is needed to observe the consequence.
- **Needs verification**: the relevant host/runtime contract is not sufficiently
  documented or available locally.

The private CELSYS SDK and adapter were inspected only at their high-level
boundary. This report contains no SDK header contents and does not propose
moving restricted material into the public tree.

## 1. Baseline

### Live branch graph

Remote heads were refreshed and verified with `git ls-remote` at 2026-08-12
19:51 JST:

| Ref | Exact commit |
| --- | --- |
| `main` | `1341885dbfab562348f5dce4e42824798f5feb6c` |
| `feature/krita-addon` | `52f8c3fa04414e5f5290016e949941369f070f0c` |
| `feature/csp-addon` | `3a7a07e0f384b3cb2c6f5cb0b306bb11558bbaa3` |

```text
                         52f8c3f  Krita add-on
                        /       \
6ae5167  common base --           3a7a07e  CSP-specific commit
        \
         64d5e86 -- 2044d8f -- 466b766 -- 1341885  current main
```

`52f8c3f` is the only Krita commit and its parent is `6ae5167`.
`3a7a07e` is the only CSP-specific commit and its parent is `52f8c3f`.
Consequently, the CSP branch contains both add-ons and Krita is its ancestor.

Commands used:

```bash
git ls-remote --heads origin main feature/krita-addon feature/csp-addon
git merge-base main feature/krita-addon
git merge-base main feature/csp-addon
git merge-base feature/krita-addon feature/csp-addon
git rev-list --left-right --count main...feature/krita-addon
git rev-list --left-right --count main...feature/csp-addon
git rev-list --left-right --count feature/krita-addon...feature/csp-addon
git log --oneline --decorate --graph --all
```

The merge bases are `6ae5167` for `main`/Krita and `main`/CSP, and
`52f8c3f` for Krita/CSP. Left/right counts are respectively `4/1`, `4/2`,
and `0/1`.

### Change inventory

| Range | Files | Insertions/deletions | Meaning |
| --- | ---: | ---: | --- |
| `6ae5167..feature/krita-addon` | 39 | `+2574/-1` | Krita implementation, tests, docs, CI/release definition |
| `feature/krita-addon..feature/csp-addon` | 56 | `+13019/-1` | CSP implementation; 3 vendored LodePNG files account for `+9453` lines |
| `6ae5167..feature/csp-addon` | 92 | `+15592/-1` | Complete stacked add-on work |
| `main..feature/krita-addon` | 40 | `+2577/-14` | Endpoint comparison to current main |
| `main..feature/csp-addon` | 93 | `+15595/-14` | Endpoint comparison to current main |

The private adapter under `FilterPlugIn20210827/GapAssistPrivate/` and the
CELSYS SDK directory are excluded by local Git rules and are not in either
feature commit. Public CSP code contains only SDK-independent core, CLI, a
generic future host abstraction, and documentation.

`git diff --check` passes for the Krita delta. The CSP delta reports only
whitespace in the vendored `experimental/csp-plugin/third_party/lodepng/LICENSE` (line 21 and
final whitespace). `git fsck --full --no-dangling` passes.

### Current-main work to incorporate

The four commits unique to `main` contain no newer add-on, model, test, or CI
logic:

- `64d5e86` is a merge whose tree is identical to `6ae5167`.
- `2044d8f` and `466b766` update SEO metadata in `docs/index.html`.
- `1341885` updates development-branch/citation prose in `README.md` and the
  site.

The net `6ae5167..main` tree change is only `README.md` and
`docs/index.html`, `+13/-3`. Before implementation resumes, transplant/rebase
`52f8c3f` and then `3a7a07e` onto current `main`. Preserve the SEO and branch
status text while retaining the add-on README rows. A legacy `git merge-tree`
probe produced no conflict markers, but the shared README should still be
reviewed manually.

### Automated checks

Checks were run from exact branch snapshots where branch isolation mattered;
the working branch was not switched. No test reported a skip.

Krita's isolated environment was created with:

```bash
python3 -m venv /tmp/gapfill-krita-venv
/tmp/gapfill-krita-venv/bin/python -m pip install -r krita-plugin/requirements-dev.txt
```

| Target | Command/result | Status |
| --- | --- | --- |
| Web reference | `npm test` in `web/`: 13 suites | Pass, 0 skipped |
| Krita tests | `(cd krita-plugin && /tmp/gapfill-krita-venv/bin/python -m pytest -ra)`: 13 tests in 0.79 s | Pass, 0 skipped |
| Krita lint | `(cd krita-plugin && /tmp/gapfill-krita-venv/bin/ruff check .)` | Pass |
| Krita source bundle | `/tmp/gapfill-krita-venv/bin/python krita-plugin/scripts/build_plugin.py --output /tmp/gapfill-krita-audit-final.zip` | Pass |
| Krita package integrity | `unzip -t /tmp/gapfill-krita-audit-final.zip` and content listing | Pass, 23 entries |
| Krita representative vendored bundle | build/extract; `python3 -S` import NumPy/ONNX Runtime; load model contract | Pass on Linux CPython 3.12 only; not a Krita/3.13 result |
| Krita syntax | `python3 -m compileall -q` over plugin scripts/package | Pass |
| CSP Make build | `make -C experimental/csp-plugin -j2 all` | Pass |
| CSP core tests | `make -C experimental/csp-plugin test`: 25 cases | Pass, 0 skipped |
| CSP PNG/CLI E2E | `make -C experimental/csp-plugin test-e2e` | Pass |
| CSP CMake configure/build | isolated CMake 4.4.2, Release, GNU 13.3, parallel 2 | Pass |
| CSP CTest | `ctest --test-dir <audit-build> -C Release --output-on-failure` | Pass, 4/4, 0 skipped |
| CSP CMake install | isolated prefix inventory | Pass; CLI, public docs, LodePNG license only |
| CSP ASan/UBSan | Debug CTest with leak detection disabled | Pass, 4/4, no diagnostics; LSan skipped under ptrace |
| CSP public host probe | `experimental/csp-plugin/build/gap_assist_host_contract_probe` | Pass; explicitly no CELSYS SDK inspected |

The Krita virtual environment used CPython 3.12.3, NumPy 2.5.2, ONNX Runtime
1.28.0, pytest 9.1.1, and Ruff 0.16.2. The exact model was also loaded with
ONNX Runtime: it exposes float input `input_mask` `[1,2,32,32]` and float output
`nearest_region_mask` `[1,1,32,32]`; a zero-input inference returned a finite
`float32` tensor of the declared shape. That is a runtime/contract smoke test,
not a semantic prediction test. The model SHA-256 is
`8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`.

The representative vendored-package commands were:

```bash
/tmp/gapfill-krita-venv/bin/python -m pip install -r krita-plugin/requirements-runtime.txt --target /tmp/gapfill-krita-runtime-vendor
/tmp/gapfill-krita-venv/bin/python krita-plugin/scripts/build_plugin.py --vendor /tmp/gapfill-krita-runtime-vendor --output /tmp/gapfill-krita-platform-audit-final.zip
unzip -t /tmp/gapfill-krita-platform-audit-final.zip
```

The extracted bundle was placed first on `sys.path` under `/usr/bin/python3 -S`;
its NumPy/ONNX Runtime imports and CPU session contract passed. This is only a
Linux CPython 3.12 mechanics check, not evidence for Krita or release Python 3.13.

The CSP checks used GCC 13.3 and C++20 on Linux/WSL2 x86-64. CMake/CTest was not
initially installed, so CMake 4.4.2 was installed only into an isolated
`/tmp` virtual environment. The exact commands were:

```bash
/tmp/gapfill-csp-audit.JMYX4g/cmake-venv/bin/cmake -S experimental/csp-plugin -B /tmp/gapfill-csp-audit.JMYX4g/cmake-build -DCMAKE_BUILD_TYPE=Release
/tmp/gapfill-csp-audit.JMYX4g/cmake-venv/bin/cmake --build /tmp/gapfill-csp-audit.JMYX4g/cmake-build --config Release --parallel 2
/tmp/gapfill-csp-audit.JMYX4g/cmake-venv/bin/ctest --test-dir /tmp/gapfill-csp-audit.JMYX4g/cmake-build -C Release --output-on-failure
/tmp/gapfill-csp-audit.JMYX4g/cmake-venv/bin/cmake --install /tmp/gapfill-csp-audit.JMYX4g/cmake-build --config Release --prefix /tmp/gapfill-csp-audit.JMYX4g/install
```

CTest passed 4/4: aggregate core tests, fixture creation, CLI smoke, and fixture
verification. A separate ASan/UBSan Debug build also passed 4/4 with no
diagnostics when leak detection was disabled. LeakSanitizer could not run under
the environment's ptrace supervision and remains unverified; its first fatal
startup caused dependent CTest cases not to run, rather than exposing a product
leak. A real Windows/MSVC/CELSYS build was not possible locally.

The full `ml/` pytest suite was not established as an add-on gate: its OpenCV,
SciPy, pandas, and PyTorch stack was not installed in the audit environment.
The relevant source was reviewed and the web reference suite passed. This
limitation does not conceal a skipped Krita or CSP add-on check.

### CI and release evidence

- Exact Krita head `52f8c3f`: GitHub Actions run
  [27912623096](https://github.com/marc2825/GapFill/actions/runs/27912623096)
  succeeded, including Web and Krita install/test/lint/build/inspection steps.
- Exact CSP head `3a7a07e`: GitHub Actions run
  [28007926338](https://github.com/marc2825/GapFill/actions/runs/28007926338)
  succeeded, including Web, Krita, and CSP CMake/build/CTest steps.
- Historical raw logs require repository-admin access, so exact historical
  pytest test counts/skips could not be recovered; current local runs had zero
  skips.
- GitHub currently registers only CI and Pages from default `main`. Both bundle
  YAML files exist only on feature branches and their workflow API endpoints
  return 404. There are no `krita-v*` or `csp-v*` tags. Therefore the
  four-platform release matrices are definitions, not demonstrated releases.
- The Krita release definition vendors NumPy/ONNX Runtime but does not import or
  execute the built vendored ZIP. The CSP release definition builds the
  SDK-independent CLI/core only, not a CELSYS plug-in binary.

### Package inspection

The audited source Krita ZIP is approximately 22 MiB compressed (23 entries,
24,766,730 bytes uncompressed) and includes the desktop entry, Python package,
model metadata, and 24,697,438-byte ONNX model. It intentionally
does not include `_vendor` unless `--vendor` is supplied. It also omits
`krita-plugin/actions/gapfill_krita.action`, although development installation
copies that file and Krita expects shortcut action XML under the resource
`actions/` directory, as well as project/model/asset notices. The existing
package test checks the desktop entry, package, model, and cache exclusion only,
so it cannot catch missing release resources or a broken binary dependency
bundle.

## 2. Reconstructed intended specification

### Stable core

The following is supported consistently enough to use as the starting contract:

1. A gap is a small, unpainted/transparent connected region on the coloring
   layer, enclosed by boundaries that may be assembled from line art and a guide
   layer.
2. Connectivity is grid breadth/depth-first search with four orthogonal
   neighbors. Eight-neighbor mode is a CSP invention/option, not the original
   default.
3. For each gap, calculate the integer centroid by taking the mean of its pixel
   coordinates and truncating/flooring nonnegative coordinates.
4. Extract a 32x32 window centered on that centroid and zero-pad outside the
   image.
5. Model input is float32/NCHW `[1,2,32,32]`: channel 0 is a binary boundary
   mask; channel 1 is the binary target-gap mask. Output is float32
   `[1,1,32,32]`, a spatial likelihood map for pixels belonging to the target's
   color region.
6. Select a coherent painted region using the likelihood map, then use a
   representative (modal in the paper/ML/web path) color from that region.
7. Suggestions are previews until the user commits. The original interaction
   offers circular markers, fixed 5x hover magnification, in-circle drag color
   correction, out-of-circle sweep-to-apply, and Apply All.

### Unresolved reference contradictions

These choices must be settled in a written contract before an implementation is
used as an oracle:

| Concern | Paper/training evidence | Executable reference evidence | Audit disposition |
| --- | --- | --- | --- |
| Threshold | Paper prose says “below” a user threshold; appendix and ML classify `size <= 10` as small | Web, Krita, and CSP accept `size <= threshold` | Adopt neither silently; add exact `T-1/T/T+1` goldens and record a product decision. `<=` has the stronger code/appendix support. |
| Image boundary | Paper defines an enclosed region | ML labeling and web detection do not explicitly reject an edge component; size usually filters the exterior | Edge-touching regions should presumptively be open, as Krita/CSP implement, but retain a regression showing the deliberate difference. |
| Guides | Paper allows line art plus guide boundaries | Training patch code uses line art only; exported metadata and web/Krita combine guides and remove the target guide pixel | Characterize the model with controlled guide inputs before asserting this reproduces training. |
| Line threshold | Training binarizes grayscale line art at 128 | Web/Krita treat any nonzero line/guide alpha as boundary | Define behavior for faint/anti-aliased line pixels and test it. |
| Region correspondence | ML inference segments regions from binarized line art and even iterates label 0 | Web/Krita segment opaque colored pixels, block line/guides, and use seed-relative Manhattan RGB tolerance 30 | This is a material algorithm change. Compare both on labeled goldens/model outputs before choosing or repairing either. |
| Final color | Paper/ML use a region representative; ML/web/Krita choose a mode | CSP buckets samples and returns a weighted arithmetic mean | CSP behavior is not equivalent and can create a color absent from the artwork. |
| Gap kinds | Paper describes gaps bounded with optional guides | Web/Krita split ordinary transparent and guide-visible pixels into separate components | The split and removal of the target guide from channel 0 are an approximation requiring evidence. |
| Alpha | “Unpainted transparent” supports alpha 0 | Web/Krita require alpha exactly 0; CSP permits `alpha <= configurable threshold` | Partial-alpha semantics remain a product decision. |

### Comparative algorithm trace

| Stage | Original ML/paper | Krita | CSP public/private path |
| --- | --- | --- | --- |
| Inputs | Coloring plus line art; paper also permits guides | Raw Coloring, projected Line Art, projected optional Guides, root projection | One active RGB-alpha raster source plus optional selection; no separate line/guide input in the shipping quick-fix path |
| Candidate map | Small fillable line-art regions corresponding to transparent coloring | Exact-alpha transparent, line-clear pixels; guide-visible pixels are a second class | Pixels with alpha at/below configurable threshold |
| Components | Four-neighbor; enclosure stated | Four-neighbor RLE/union-find; edge rejected; `<= threshold` | Four or eight; edge and selection-boundary rejected; `<= threshold` |
| Patch/model | Centered/padded 32x32, two binary channels, U-Net | Implemented with ONNX Runtime | Not implemented; ONNX class is a stub |
| Correspondence | Line-art-derived labels, highest mean output likelihood | Color/alpha/tolerance-derived painted regions, highest mean likelihood | Large alpha-opaque owner components only influence heuristic weights |
| Color | Modal color of selected region | Modal RGB of selected region; optional greedy fallback | 5-bit buckets, distance/owner weights, weighted mean, invented confidence |
| Commit | Interactive preview then chosen apply | Overlay plus native foreground selection-fill actions | CLI correction artifacts; private filter auto-applies only invented High-confidence results |

### Krita behavior classification

**Intended reproduction:** four-connected enclosed transparent components,
thresholded detection, centered/padded 32x32 gap patches, two-channel ONNX input,
mean-likelihood region selection, modal color, circular previews, 5x magnifier,
drag correction, sweep, and Apply All.

**Platform-specific:** explicit Coloring/Line Art/Guide node selection; RGBA/U8
restriction; LibKis raw/projection snapshots; a Docker and canvas child widget;
native foreground-selection fill actions; Krita selection, active-node, and
foreground-color save/restore.

**Invented or approximated:** any-alpha boundary semantics; guide-gap component
splitting and target-guide removal; opaque-color connected components with RGB
tolerance 30; radius-5 greedy fallback; document-edge rejection relative to
the current web code; default user threshold 500 rather than the training value
10; per-color native action grouping.

**Not established:** exact model response to guides/anti-aliasing; transformed
or masked node snapshots; ICC/profile correctness; foreground/global action
state; final undo UX; HiDPI transforms; multiwindow widget ownership; Qt thread
teardown; PyQt/Krita binary ABI compatibility. Guide classification, absent
selection restoration, and rotation/mirroring omissions are confirmed defects,
not merely unknowns.

### CSP behavior classification

**Intended reproduction:** detection of small transparent components, default
four-connectivity, edge exclusion, suggesting a nearby color, and committing
only selected corrections.

**Platform-specific:** a conventional CSP filter with active raster source,
optional selection bounds/mask, host-owned Preview/OK/Cancel/Undo, and
high-confidence-only Quick Fix; a companion CLI emits correction/review PNGs
because the 2021 SDK cannot provide the paper's canvas interaction.

The paper's user-study discussion says a custom web app was used because CSP did
not support add-ons. The local work targets a separately supplied, restricted
2021 filter SDK with a much narrower lifecycle. That does not establish that the
paper's interactive tool can be implemented natively; it explains why SDK
feasibility is a separate release gate.

**Invented or approximated:** configurable alpha threshold and
eight-connectivity; size/confidence presets; owner-region flood fill and
transitive color tolerance; 5-bit color buckets; distance and owner weights;
weighted-mean output; confidence formula/bands; auto-apply policy; review modes
and artifact formats; silent ONNX fallback.

**Not established:** whether single-layer transparency can represent useful CSP
artwork without line/guide layers; confidence calibration; soft-selection and
no-selection bounds in the real SDK; progress responsiveness on huge components;
destination mutation/Preview/Undo behavior; the private adapter build and load
on supported CSP/Windows versions.

## 3. Host and implementation audit

### Krita API boundary

Verified from the official API surface:

- Integer RGBA `Node.pixelData()`/`projectionPixelData()` bytes are BGRA, and
  projections include child-layer results. The add-on's byte-to-RGBA conversion
  matches that raw-read contract.
- For an RGBA `ManagedColor`, the documented normalized `components()` access is
  R, G, B, A. The add-on's list assignment therefore is not a red/blue channel
  swap. Color conversion is a separate issue: Krita provides
  `ManagedColor.fromQColor(..., canvas)`/`colorForCanvas(canvas)` for translating
  between display QColor and a canvas color space, and the add-on does not use
  those conversions.
- `flakeToImageTransform()` and `flakeToCanvasTransform()` explicitly omit
  canvas rotation and mirroring. Composing them cannot by itself support those
  view states.
- Krita Python plug-ins place `.desktop`/package resources under `pykrita` and
  shortcut action XML under `actions`.

References: Krita
[Node](https://api.kde.org/legacy/krita/html/classNode.html),
[ManagedColor](https://api.kde.org/legacy/krita/html/classManagedColor.html),
[View](https://api.kde.org/legacy/krita/html/classView.html),
[Selection](https://api.kde.org/legacy/krita/html/classSelection.html), and
[Python plug-in packaging](https://docs.krita.org/en/user_manual/python_scripting/krita_python_plugin_howto.html).

Plausible but still unverified in a real host:

- Document-space reads should handle ordinary paint-layer offsets, but raw
  Coloring pixels intentionally differ from projected Line Art/Guide pixels.
- NumPy/ONNX work occurs after immutable snapshots are handed to a worker, which
  is a reasonable thread boundary; all LibKis/QWidget operations remain on the
  UI thread.
- Foreground and an existing selection are saved and restored in `finally`.
  Whether `foregroundColor()` is an independent value remains a host check.
  Upstream source confirms that a new empty `Selection()` does not restore the
  semantic absence of a global selection; that is K-06, not an unknown.

Fragile behavior:

- The full document is synchronously copied four times before the worker starts.
- The canvas parent is found by private QWidget class-name/area heuristics and
  polled every 100 ms.
- The overlay is a full-canvas mouse-receiving child and therefore owns normal
  canvas pointer interaction while active.
- Document/view identity is checked, but no node revision, geometry, lock, or
  content generation is checked between scan and apply.
- PyQt5/PyQt6 support is only an import shim; neither host generation is tested.

Likely bugs are captured as K-01 through K-14 in the register.

### CSP public/private boundary

The tracked public product has three different surfaces that should not be
conflated:

1. `src/core`, `src/predictors`, and the CLI are real and tested, but implement
   a single-layer heuristic rather than learned GapFill.
2. `HostFilterContext`/`GapAssistCommand` is a generic richer-host design tested
   through mocks. The local CELSYS adapter does not call it.
3. The ignored private adapter calls only `QuickFixPipeline`, reads a cropped
   source/selection through SDK blocks, writes a destination, and leaves
   Preview/OK/Cancel/Undo to the filter lifecycle. It cannot create the public
   design's correction/highlight layers or review UI.

The private code does positively query channel indices, checks alpha lock,
honors block row/pixel strides, blends soft-selection values on output, catches
exceptions, and asks the host to abort. Those are code observations only; none
has been validated against a real CSP host. Its source/selection rectangle
intersection, no-selection behavior, filter destination lifecycle, and polling
cadence remain host-dependent.

### Focused semantic probes

Two temporary audit harnesses were deliberately independent of CSP expected
values:

- On tracked presets, a direct port of the web candidate-map rule at threshold
  10 was compared with the CSP detector over the coloring layer. Results were:
  `Ex2: 12 vs 0`, `B/Easy/L: 10 vs 6`, `B/Easy/R: 10 vs 0`,
  `B/Hard/L: 10 vs 0`, and `B/Hard/R: 10 vs 0`
  (reference vs CSP). Supplemental locally available but Git-ignored `C`
  presets produced `C/1: 116 vs 6`, `C/2: 111 vs 3`,
  `C/3: 101 vs 6`, and `C/4: 112 vs 6`; those counts are useful stress
  evidence but are not reproducible from a clean checkout. `Ex2` contains nine
  ordinary and three guide candidates.
  All six CSP detections in `B/Easy/L` were a subset of the reference set, and
  none of the reference candidates touched the image edge. This isolates
  missing line/guide boundaries rather than edge policy.
- A synthetic neighborhood containing source red values 0 and 7—both in one
  5-bit bucket—made the rule predictor return red 3, a color absent from the
  input, with confidence 1.0. High-confidence Quick Fix would auto-apply it.
- Passing the CLI input path itself as `--correction` changed the source hash
  and replaced it with the correction image, contradicting “source PNG is never
  overwritten.”
- `--selection mask.png --settings settings.ini` allowed the later settings load
  to reset scope to whole-layer and detect outside the mask; reversing the two
  options detected zero. CLI semantics are therefore option-order-dependent.
- Loading an explicit `gap-0=skip` decision and then passing `--apply-high`
  changed the gap back to Apply, despite help text describing remaining
  high-confidence candidates.

These probes establish defects or divergences; they do not choose the final
cross-platform product specification.

## 4. Test audit

Passing tests are classified by whether they could reject a semantically wrong
but internally consistent implementation.

### Krita: 13 tests

| Subsystem | Classification | What the tests can catch | Semantic blind spot |
| --- | --- | --- | --- |
| Detection | Strong regression for current local rules; implementation-coupled as a GapFill oracle | Four-connectivity examples, line enclosure, guide component split, exact threshold, edge rejection | No paper/web fixture, anti-alias/partial alpha, transformed/projection layer, or independent expected candidate map |
| Pixel conversion | Strong regression after independent API review | Raw BGRA byte conversion and shape errors | No real node/profile/offset read |
| Patch extraction | Strong regression for geometry; implementation-coupled for guide policy | Centering, border padding, gap mask, target-guide removal | No byte-for-byte training-pipeline tensor fixture or model characterization |
| ONNX wrapper | Contract regression plus smoke | Input/output count, dtype/shape, fake session call, real artifact can produce an RGB tuple | No known-input/known-output prediction, semantic target-region/color, providers, cancellation during load, or packaged runtime import |
| Postprocessing | Implementation-coupled | One synthetic colored-region segmentation/selection case | Expected labels come from the same invented tolerance assumption; no ML/web comparative golden |
| Package build | Smoke test | Desktop entry, Python entrypoint, model, no cache | Does not require action XML, `_vendor`, shared libraries, importability inside Krita, or supported-platform wheel ABI |
| Adapter/controller/worker/overlay/docker/Qt | Missing | None | No selection, canvas/profile conversion, undo, global action state, lock, mutation, race, transform, HiDPI, multiwindow, Qt5/6, or real-host coverage |

The suite is useful regression protection for pure functions. It is not evidence
that the chosen guide/postprocessing assumptions reproduce the trained model or
that the plug-in can safely edit a Krita document.

### CSP: 25 core tests plus one PNG/CLI fixture

| Subsystem | Classification | What the tests can catch | Semantic blind spot |
| --- | --- | --- | --- |
| Gap detector | Strong regression for declared C++ rules; implementation-coupled as GapFill evidence | Boundary exclusion, threshold, alpha threshold, selection boundary, 4/8 connectivity | No separate line/guide inputs, repository artwork, partial-alpha decision, or comparison with paper/web/ML candidates |
| Owner regions | Implementation-coupled | Current tolerance/area labels on simple colors | Neighbor-to-neighbor color chaining, line-art contamination, mean-vs-mode choice, and correspondence to model regions |
| Rule predictor/confidence | Implementation-coupled | Uniform-neighborhood High result, confidence bands, immediate cancellation | Expected values encode the same bucket/weight formula; no calibrated corpus, absent-color rejection, learned-model comparison, or cancellation inside a large gap window |
| Review/correction output | Strong regression for pure mutation invariants | Apply/skip/mark decisions, transparent correction, unchanged in-memory source | Filesystem path aliasing/overwrite, disk failure/atomicity, real host destination/Undo |
| Settings/CLI parser | Smoke/implementation-coupled | Settings round trip and standard invocation | Option-order dependence, same input/output path, malformed/huge PNGs, settings/output collisions |
| PNG/CLI E2E | Useful smoke | Decodes and re-encodes a 32x32 PNG and fills one transparent center pixel with its uniform surrounding color | The fixture is ideal for the heuristic; no line/guide or ambiguous color decision, no ONNX, no real art |
| Generic host command | Implementation-coupled mock | Pre-cancel and declared transaction/capability branches do not call mock mutation | This interface is not wired to the private CELSYS adapter; no SDK block/selection/Preview/Cancel/Undo behavior |
| Private CELSYS adapter | Missing | None in public CI | Build/load, channel/block layout, no-selection, soft selection, alpha lock, restart, progress, cancellation, destination commit, Undo |
| Scale/performance | Missing | None | Huge transparent component, 4K/8K memory ceiling, allocation failure, responsive host cancel |

The host contract probe is documentation emitted by an executable, not a host
test. The CTest job runs one aggregate 25-case executable plus fixture-create,
CLI-smoke, and fixture-verify tests; it does not make 25 independent CTest host
tests.

## 5. Risk register

Severity reflects user/data/release impact, not implementation effort. “Real
host testing” says whether closing the finding requires Krita or CSP rather than
only a pure/CLI test.

| Severity | Count | Immediate interpretation |
| --- | ---: | --- |
| Critical | 1 | C-01 blocks a CSP GapFill claim/release |
| High | 21 | Semantic, data-safety, host, or package gates that must close before the affected release |
| Medium | 12 | Important correctness, robustness, or process work to schedule explicitly |
| Low | 3 | Hygiene/diagnostic debt that should not be mistaken for host evidence |

### G-01 — Region-correspondence algorithms disagree

- **Component:** Shared model postprocessing (`ml`, web, Krita)
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** ML inference scores regions labeled from the binarized
  line-art segmentation and includes label 0 in its iteration. Web and Krita
  instead construct connected components from opaque coloring pixels, block
  line/guides, and use seed-relative RGB Manhattan tolerance 30.
- **Expected behavior or question:** The probability map must be averaged over
  the same semantic regions the model was trained to identify. It is unresolved
  whether ML label handling is buggy, web/Krita intentionally corrected it, or
  both are wrong for some artwork.
- **Evidence:** `ml/src/utils/flood_fill/core.py:10-29`,
  `ml/src/utils/color_utils.py:12-42`,
  `web/src/utils/GapFill/onnxPostprocessing.ts:20-129`, and
  `krita-plugin/pykrita/gapfill_krita/engine/postprocessing.py:13-72`.
- **Recommended verification:** Check in colored/line label maps and fixed ONNX
  outputs for flat, anti-aliased, disconnected-same-color, label-0, and
  near-tolerance cases; have an independently reviewed oracle state the chosen
  region and color.
- **Recommended eventual fix:** Define one postprocessing contract, fix the
  canonical ML/reference path first if necessary, then port that exact behavior
  and remove competing implicit interpretations.
- **Requires real Krita/CSP testing:** No; close first with pure golden tests,
  then smoke it in hosts.

### G-02 — Guide inputs are claimed but not represented in training patches

- **Component:** Shared model input/model metadata
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** Training patch construction stacks only binarized line
  art and the target region. Exported metadata says channel 0 is “Line Art and
  Guides”; web/Krita OR guide alpha into that channel and erase the target guide
  for guide-kind gaps.
- **Expected behavior or question:** It must be established whether guide pixels
  are in-distribution boundary inputs and exactly which target guide pixels, if
  any, should be suppressed.
- **Evidence:** `ml/src/utils/patch_utils.py:85-101`,
  `ml/src/export_onnx.py:31-47`,
  `web/src/utils/GapFill/onnxPatchExtraction.ts`, and
  `krita-plugin/pykrita/gapfill_krita/engine/patches.py:86-95`.
- **Recommended verification:** Run controlled tensors that differ only in the
  guide mask through the checked-in model; compare with labeled examples from
  the paper/training data and inspect activation/output changes.
- **Recommended eventual fix:** Correct misleading metadata and either document
  guide composition as a characterized runtime extension or retrain/export a
  model whose guide contract is explicit.
- **Requires real Krita/CSP testing:** No for the model decision; yes later for
  host guide-layer acquisition.

### G-03 — Gap membership has unresolved edge, threshold, and alpha rules

- **Component:** Shared gap detector specification
- **Severity:** Medium
- **Confidence:** Confirmed
- **Current behavior:** Paper prose requires enclosure and says “below” a
  threshold; its appendix/ML and all add-ons use `<=`. Web/ML do not explicitly
  reject edge components. Krita/CSP do. Web/Krita require alpha 0; CSP permits a
  configurable partial-alpha threshold.
- **Expected behavior or question:** One explicit rule is needed for `T-1/T/T+1`,
  image/selection edges, and alpha 0/1/127/254/255.
- **Evidence:** Paper §§4.1.1, 4.2.2 and Appendix A; ML
  `nearest_same_color.py:70-98`; web
  `gapRegionDetection.ts:35-83`; Krita `engine/detection.py:93-146`; CSP
  `src/core/gap_detection.cpp:25-113`.
- **Recommended verification:** Add tiny hand-authored truth tables independent
  of every implementation and include one small edge component that threshold
  alone would accept.
- **Recommended eventual fix:** Adopt the reviewed contract in all detectors;
  keep platform selection-boundary behavior separately named.
- **Requires real Krita/CSP testing:** No for core semantics; yes for partial
  alpha and selection acquisition in each host.

### G-04 — Model execution is tested without semantic expected outputs

- **Component:** ONNX artifact and cross-language tests
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** Shape/type validation and finite inference pass, but no
  checked-in input tensor has a reviewed output region/color. Krita fake-session
  expectations and CSP heuristic expectations come from their implementations.
- **Expected behavior or question:** A known tensor/artwork corpus must prove
  patch bytes, model outputs within a pinned tolerance, selected region, and
  final color across Python, browser ONNX, and add-on runtimes.
- **Evidence:** Model smoke described in §1; `krita-plugin/tests/test_inference.py`;
  web ONNX tests; CSP `tests/test_main.cpp` predictor cases. Model hash is pinned
  only in this report, not a golden manifest.
- **Recommended verification:** Export a small, reviewable corpus from the
  primary pipeline with source provenance, raw tensor `.npy`, output `.npy`,
  label map, and expected RGB; review it without add-on code.
- **Recommended eventual fix:** Make that corpus a required parity suite for all
  implementations and release bundles.
- **Requires real Krita/CSP testing:** No for semantic parity; host smoke remains
  separately required.

### G-05 — Anti-aliased boundary semantics do not match training thresholding

- **Component:** Shared line-art/guide rasterization
- **Severity:** Medium
- **Confidence:** Needs verification
- **Current behavior:** Training converts grayscale with threshold 128. Web and
  Krita treat any alpha greater than zero as an impassable boundary, irrespective
  of RGB, opacity, blend mode, or display contribution. CSP has no separate
  boundary layers.
- **Expected behavior or question:** The product must define how opacity,
  grayscale, anti-aliasing, hidden layers, blend modes, and masks become the
  binary model/detection boundary.
- **Evidence:** `ml/src/utils/patch_utils.py:85-100`, web
  `gapRegionDetection.ts:19-30`, Krita `engine/detection.py:54-63` and
  `engine/inference.py:78-83`.
- **Recommended verification:** Render controlled faint/anti-aliased strokes in
  web and real Krita, capture exact masks, and characterize predictions against
  training-style grayscale thresholds.
- **Recommended eventual fix:** Centralize a documented raster-to-boundary
  conversion and expose only settings that the model is known to tolerate.
- **Requires real Krita/CSP testing:** Yes for Krita rendering; CSP would require
  a redesigned multi-layer input.

### K-01 — Preview/sampled colors bypass canvas-profile conversion

- **Component:** Krita color management and mutation adapter
- **Severity:** High
- **Confidence:** Strong suspicion
- **Current behavior:** Raw/projected RGB bytes and QColor samples are treated as
  though they were already numeric components in the target node profile.
  Preview arrays become unmanaged QImages, and apply writes normalized RGB
  directly into a `ManagedColor` constructed with the target profile. The
  documented RGBA component order is correct; the missing conversion between
  canvas/display and target profiles is the risk.
- **Expected behavior or question:** A predicted or drag-sampled displayed color
  must be converted through the active canvas and stored as the same perceived
  color in the target node's profile.
- **Evidence:** `krita_adapter.py:100-113`, `controller.py:173-199`,
  `overlay.py:154-178`, and `qt_compat.py:115-117`; official
  `ManagedColor.fromQColor`/`colorForCanvas` documentation. No test covers a
  non-sRGB profile.
- **Recommended verification:** In real Krita fill one transparent selected
  pixel with asymmetric colors in sRGB and a materially different RGBA/U8 ICC
  profile; inspect perceived QColor and profile-aware round trips after
  Undo/redo.
- **Recommended eventual fix:** Define whether predictions carry source-profile
  or display color, then use Krita's canvas-aware ManagedColor conversion APIs
  for sampling, preview, and commit; add a cross-profile host regression.
- **Requires real Krita/CSP testing:** Yes, Krita.

### K-02 — Apply uses stale pixels and coordinates after document edits

- **Component:** Krita controller/application lifecycle
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** Scan snapshots the document, then apply validates only
  active document/view identity. Editing, moving, transforming, deleting,
  replacing, locking, or changing the scanned coloring node does not invalidate
  gap indices or predictions. After triggering fill, the controller updates its
  cached arrays and removes gaps without verifying resulting pixels.
- **Expected behavior or question:** Apply must be tied to the exact scanned
  node/document revision and revalidate target membership, coordinates, lock,
  and transparency before mutation.
- **Evidence:** `controller.py:32-66,142-150,209-243` and
  `krita_adapter.py:64-120` contain no revision/content token.
- **Recommended verification:** Scan, then edit/move/transform/delete/lock the
  target and switch active nodes before applying; assert no wrong pixel changes
  and no false “Applied” state.
- **Recommended eventual fix:** Introduce a scan generation/context snapshot,
  invalidate it on relevant document/node signals, and re-read/revalidate each
  target just before a single transaction.
- **Requires real Krita/CSP testing:** Yes, Krita.

### K-03 — Late cancellation/deactivation can recreate a closed overlay

- **Component:** Krita controller/worker concurrency
- **Severity:** High
- **Confidence:** Strong suspicion
- **Current behavior:** `deactivate()` sets the worker event and destroys the
  overlay, but it does not invalidate the scan generation or disconnect
  `completed`. If work completes after its last cancellation check, the queued
  `_scan_completed` callback can install a new overlay. Cancellation is not
  checked before model load and model session creation itself is not cancellable.
- **Expected behavior or question:** Once a scan is cancelled, deactivated, or
  superseded, no result from that generation may update UI/state.
- **Evidence:** `controller.py:55-90,98-115`; `worker.py:28-51`;
  `engine/inference.py:113-143`.
- **Recommended verification:** Deterministically pause the worker immediately
  before `completed.emit`, deactivate/change canvas, release it, and assert no
  overlay/regions/status are installed; repeat during model load.
- **Recommended eventual fix:** Give every scan an immutable generation token,
  gate all terminal signals, disconnect/retire old workers, and check cancel
  before expensive model initialization.
- **Requires real Krita/CSP testing:** A Qt event-loop integration test is
  required; final smoke in Krita is also required.

### K-04 — View transforms omit rotation and mirroring

- **Component:** Krita overlay coordinate mapping
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** The overlay composes `flakeToCanvasTransform()` with the
  inverse of `flakeToImageTransform()`. Official View documentation states that
  these transforms do not include canvas rotation or mirroring.
- **Expected behavior or question:** Markers, hit testing, sweep paths,
  magnifier sampling, and preview pixels must coincide with the image under
  pan/zoom/rotation/mirror and HiDPI.
- **Evidence:** `overlay.py:77-121,149-165,260-326` and official Krita View API
  documentation. No overlay test exists.
- **Recommended verification:** Use asymmetric corner gaps at multiple zooms,
  90°/arbitrary rotation, horizontal mirror, and 100%/150%/200% display scale;
  compare marker/hit/sample coordinates to known document pixels.
- **Recommended eventual fix:** Use a supported canvas/document mapping that
  includes view state, or explicitly compose documented rotation/mirror/device
  scaling; isolate it behind a testable adapter.
- **Requires real Krita/CSP testing:** Yes, Krita on at least two display scales.

### K-05 — Raw/projection geometry and mask effects are not validated

- **Component:** Krita layer snapshots and geometry
- **Severity:** High
- **Confidence:** Strong suspicion
- **Current behavior:** Coloring is read raw; line/guides and root composite are
  read projected. Transform masks/layer masks, opacity, and group compositing can
  therefore make the target's editable raw pixels differ from the visible
  boundary/composite geometry. The root is also required to report RGBA/U8,
  effectively narrowing the whole document even though the README describes a
  selected-layer restriction.
- **Expected behavior or question:** Detection, model masks, sampling, preview,
  and final editable indices must refer to a documented common document
  geometry; unsupported transformed/masked target nodes must fail safely.
- **Evidence:** `krita_adapter.py:32-60` and `controller.py:173-235`. Pure tests
  use same-size, origin-aligned NumPy arrays without node effects.
- **Recommended verification:** Build real documents with layer offsets,
  transform/transparency masks, group opacity, and cropped/extended node bounds;
  compare snapshots to visible projection and final editable pixels.
- **Recommended eventual fix:** Define supported node/profile combinations,
  either consistently map projected geometry back to raw editable coordinates
  or reject unsupported node/effect combinations. Address profiles under K-01.
- **Requires real Krita/CSP testing:** Yes, Krita.

### K-06 — Selection restoration and undo history are incorrect

- **Component:** Krita selection and native undo
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** Every per-color gap mask is installed with
  `Document.setSelection`, then the final saved selection is installed the same
  way. Upstream Krita implements each call as a global-selection undo command.
  If there was no original global selection, the code passes a newly constructed
  empty `Selection`, which creates an empty global selection rather than removing
  it. Fill and selection commands are not grouped into one user operation.
- **Expected behavior or question:** Apply must restore the semantic presence or
  absence of the user's selection and produce an intentional, preferably single,
  undo operation without exposing internal gap-mask selections in history.
- **Evidence:** `krita_adapter.py:88-120`; upstream Krita `Document.cpp:355-372`
  (`selection()` null only with no global selection, `setSelection()` pushes
  `KisSetGlobalSelectionCommand`); the Python `Selection()` constructor creates
  a new empty selection.
- **Recommended verification:** Record selection presence/pixels and the undo
  stack for no/existing/inverted/feathered selection and one/multiple predicted
  colors; Undo/redo through every command and compare exact document state.
- **Recommended eventual fix:** Use a host-supported atomic mutation/undo macro,
  avoid changing global selection as an implementation detail where possible,
  and explicitly remove rather than replace an absent original selection.
- **Requires real Krita/CSP testing:** Yes, Krita.

### K-07 — Snapshot and analysis memory/cancellation do not scale safely

- **Component:** Krita performance and responsiveness
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** The UI thread reads Coloring, Line Art, Guides, and root
  composite across the whole document before cancellation can help. Four RGBA
  arrays alone cost about 16 bytes per document pixel, before candidate maps,
  labels, previews, QImages, Python run objects, selections, and ONNX allocations.
  Preview/QImage copies bring the persistent/peak estimate to roughly 28–32
  bytes per pixel before LibKis; a 10,000x10,000 document is therefore roughly
  2.8–3.2 GB for these images alone. Checkerboard data can create millions of
  Python run objects, inference is one session call per gap, and apply allocates
  a full-document selection per distinct color. Scan cancellation begins only
  after synchronous UI-thread snapshots and is cooperative at coarse points.
- **Expected behavior or question:** Large 4K/8K/animation documents need a
  measured memory ceiling, responsive cancel, and no long uninterruptible UI
  freeze.
- **Evidence:** `krita_adapter.py:48-61`, `controller.py:47-58`, detection and
  inference allocations. No scale test exists.
- **Recommended verification:** Measure peak RSS, UI event latency, and cancel
  latency at 4K, 8K, offset small layers, large transparent exterior, and many
  gaps on both supported Krita/Python generations.
- **Recommended eventual fix:** Restrict/tilesize snapshots, avoid duplicate
  composites, permit pre-analysis cancellation, and set explicit supported size
  limits before optimizing the model loop.
- **Requires real Krita/CSP testing:** Yes, Krita for UI latency; pure memory
  benchmarks can begin without it.

### K-08 — Canvas widget discovery and overlay ownership are private/fragile

- **Component:** Krita UI integration
- **Severity:** Medium
- **Confidence:** Needs verification
- **Current behavior:** The controller searches visible descendants of the
  active window, prefers class names containing “canvas,” otherwise chooses the
  largest widget. A full-size child intercepts pointer events and polls geometry
  every 100 ms.
- **Expected behavior or question:** The overlay must bind only to the intended
  view, survive tab/split/multiwindow changes, and neither cover dockers nor
  leave invisible event-capturing widgets.
- **Evidence:** `controller.py:128-160`, `overlay.py:42-87,193-258`. This is not a
  stable documented QWidget acquisition contract and has no Qt test.
- **Recommended verification:** Real-host matrix with two windows, split views,
  tab changes, subwindows, canvas-only mode, dock moves, deactivation, and host
  shutdown under PyQt5 and PyQt6.
- **Recommended eventual fix:** Prefer a documented canvas handle or a narrowly
  validated widget relationship; make overlay lifetime view-owned and remove
  area fallback if it cannot be proven safe.
- **Requires real Krita/CSP testing:** Yes, Krita.

### K-09 — Package omits action and licensing resources

- **Component:** Krita packaging
- **Severity:** Medium
- **Confidence:** Confirmed
- **Current behavior:** Development install copies `actions/gapfill_krita.action`,
  but `build_plugin.py` stages only the desktop file and Python package. The ZIP
  has no `actions/` entry, root MIT `LICENSE`, or clear asset/model notice, and
  its test does not require them.
- **Expected behavior or question:** A release installation should expose the
  same action/shortcut metadata as development installation, in Krita's resource
  layout.
- **Evidence:** `scripts/build_plugin.py:27-51`, `scripts/install_dev.py`,
  `tests/test_build.py:7-25`, ZIP listing, and official plug-in packaging guide.
- **Recommended verification:** Install a clean source and vendored bundle into
  an empty Krita resource directory and confirm menu action, shortcut settings,
  enable/restart, and uninstall behavior.
- **Recommended eventual fix:** Stage the action XML, project/dependency licenses,
  and model/asset notices under reviewed archive paths and assert the complete
  manifest in package tests.
- **Requires real Krita/CSP testing:** Yes for final Krita installation; ZIP
  manifest regression is pure.

### K-10 — Vendored native Python dependencies are not tested inside Krita

- **Component:** Krita release/runtime compatibility
- **Severity:** High
- **Confidence:** Needs verification
- **Current behavior:** Release YAML uses generic CPython to download platform
  wheels for NumPy and ONNX Runtime and inserts `_vendor`; it only builds and
  uploads. No job imports the built ZIP, resolves native shared libraries, loads
  the model, or matches Krita's embedded Python/Qt/architecture. Windows alone
  adds a DLL directory; macOS/Linux loader behavior is assumed. Dependencies use
  version ranges without hashes and `_vendor` is placed at `sys.path[0]`, so it
  can shadow host/other plug-in packages.
- **Expected behavior or question:** Every published bundle must import and run
  under the exact supported Krita distribution on each OS/architecture.
- **Evidence:** `.github/workflows/krita-plugin-bundles.yml`,
  `requirements-runtime.txt`, `__init__.py:9-16`; bundle workflow has no observed
  run and source tests use a normal Python venv. An audit-only CPython 3.12/Linux
  vendored ZIP did import NumPy/ONNX Runtime and load the model, but was about
  63 MiB compressed/155,873,826 bytes uncompressed with 2,181 entries, including
  798 cache/bytecode and about 1,199 test/tool/transformer/bin entries because
  the vendor tree is copied wholesale.
- **Recommended verification:** Build on each target, inspect wheel tags/shared
  libraries, import NumPy/ONNX Runtime from the staged bundle, run a model golden,
  then install into actual Krita 5/6 distributions.
- **Recommended eventual fix:** Pin supported Krita/Python combinations and
  dependency hashes, prune through an allowlisted manifest without dropping
  native libraries/licenses, avoid broad global path shadowing, build/test per
  exact ABI, fail release on staged-bundle import or model mismatch, and document
  unsupported platforms.
- **Requires real Krita/CSP testing:** Yes, Krita on every supported release
  family/platform.

### K-11 — Fallback and zero-gap model behavior can mislead or delay users

- **Component:** Krita inference/error reporting
- **Severity:** Medium
- **Confidence:** Confirmed
- **Current behavior:** `predict_all` loads ONNX even when detection returns no
  gaps. Per-gap generic inference errors default to a greedy color without
  marking which suggestions changed algorithm, counting failures, or stopping a
  systematic failure; every suggestion can silently become greedy despite the
  README's “isolated inference failure” wording.
- **Expected behavior or question:** No-gap scans should not require the model;
  fallback predictions should be opt-in and visibly distinguishable/auditable.
- **Evidence:** `worker.py:31-45`, `engine/inference.py:113-143`, and default
  `settings.py:14,24`.
- **Recommended verification:** Tests for zero gaps with missing runtime and a
  mixed batch where exactly one inference throws; assert status/provenance per
  suggestion.
- **Recommended eventual fix:** Return before model load on no gaps and attach a
  prediction-source/status field rather than silently presenting fallback as
  learned output.
- **Requires real Krita/CSP testing:** No for core behavior; one Krita UI smoke is
  appropriate.

### K-12 — A Guide pixel can be misclassified as an enclosed gap

- **Component:** Krita gap detector/Guide semantics
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** Guide-covered transparent pixels are candidate class 2,
  while surrounding transparent pixels are class 1; components join only equal
  classes. In a fully open transparent 5x5 image, one Guide pixel becomes an
  isolated one-pixel “guide gap” and survives edge rejection even though it is
  physically connected to the exterior. The test suite codifies this result.
- **Expected behavior or question:** Paper §4.1.1 describes Guide layers as part
  of a gap's enclosing boundary, not as paintable gap pixels insulated from the
  exterior by a type distinction.
- **Evidence:** `engine/detection.py:55-63,80-90,100-146`,
  `tests/test_detection.py:29-41`, and an audit probe returning
  `gap-0 / guide / 1 pixel / center (2,2)` for the open 5x5 case.
- **Recommended verification:** Independent candidate masks for a lone Guide
  pixel, Guide stroke crossing exterior, Guide-enclosed hole, mixed Line/Guide
  closure, and target-guide model patch.
- **Recommended eventual fix:** Resolve G-02 first; presumptively treat Guides as
  boundaries in enclosure rather than a separate paintable component, and
  remove the implementation-coupled expectation.
- **Requires real Krita/CSP testing:** No for pure detection; yes to confirm how
  a Krita Guide node projects.

### K-13 — Native fill inherits global action state and success is assumed

- **Component:** Krita native mutation/action state
- **Severity:** High
- **Confidence:** Strong suspicion
- **Current behavior:** The adapter checks target node lock/alpha lock but does
  not save/normalize view eraser mode, global alpha lock, current blending mode,
  or other state influencing `fill_selection_foreground_color`. The action has
  no success result. Controller cache/gap state is nevertheless updated as if
  pixels changed.
- **Expected behavior or question:** Apply must produce the requested opaque
  color on exactly the target pixels regardless of unrelated tool state, or
  fail without removing suggestions/changing user state.
- **Evidence:** `krita_adapter.py:64-78,93-120` and
  `controller.py:209-243`; public View APIs expose the unhandled states, and no
  read-back/postcondition test exists.
- **Recommended verification:** Real-host matrix for eraser on/off, node/global
  alpha lock, normal/non-normal blending, opacity, two views of one document,
  active-node timing, missing/disabled action, and forced failure; read exact
  pixels before updating controller state.
- **Recommended eventual fix:** Prefer a deterministic document mutation API;
  otherwise save, force, synchronize, and restore all relevant action state and
  require a pixel-level postcondition before reporting/removing a gap.
- **Requires real Krita/CSP testing:** Yes, Krita.

### K-14 — Model metadata and small cross-runtime edge cases can drift

- **Component:** Krita model validation/postprocessing parity
- **Severity:** Low
- **Confidence:** Confirmed
- **Current behavior:** Packaged `model_info.json` is not consumed; model names,
  opset, checksum, finite/range expectations, and provenance are not fully
  enforced. Python modal ties choose sorted-lowest RGB via `np.unique` while
  web/ML choose first encountered, and Python/web handle nonfinite probability
  denominators differently. `LayerImages` also does not validate composite dtype.
- **Expected behavior or question:** Released metadata must describe and guard
  the artifact actually used, with deterministic tie/nonfinite/dtype semantics
  shared by all runtimes.
- **Evidence:** `resources/models/model_info.json`, `engine/inference.py`,
  `engine/postprocessing.py`, `engine/types.py:43-44`, corresponding web/ML
  helpers, and source/package metadata comparison.
- **Recommended verification:** Contract tests for wrong name/opset/hash,
  NaN/Inf/range, modal ties/order, composite non-uint8, and package/source
  metadata identity.
- **Recommended eventual fix:** Generate one signed/checksummed model manifest,
  consume its enforced fields, and define cross-language tie/nonfinite behavior
  in Phase 2 fixtures.
- **Requires real Krita/CSP testing:** No.

### C-01 — CSP cannot represent the central multi-layer gap definition

- **Component:** CSP detector and host input contract
- **Severity:** Critical
- **Confidence:** Confirmed
- **Current behavior:** The public/private Quick Fix analyzes only alpha in one
  active raster image. Dormant predictor fields do not feed line art or guides
  into candidate geometry. On tracked presets, reference comparisons find only
  0–6 gaps where the multi-layer rule finds 10–12, including zero of 12 on
  `Ex2`; supplemental Git-ignored `C` assets show the same pattern at 101–116
  reference gaps.
- **Expected behavior or question:** Original GapFill defines an enclosed
  unpainted region whose boundary may combine the coloring, Line Art, and Guide
  layers. A native product must acquire or receive equivalent geometry, or must
  not claim algorithmic equivalence.
- **Evidence:** `src/core/gap_detection.cpp:42-45`,
  `src/core/smart_gap_propagation.cpp:15-21`, paper §4.1.1, web
  `gapDetection.ts:207-213,230-234`, and the preset probe in §3. None of the
  missed reference candidates touched an image edge.
- **Recommended verification:** First preserve expected candidate masks/types
  for the tracked presets. In CSP, determine whether the filter SDK can access
  selected sibling layers or a composite with separately attributable
  boundaries; test the exact raster supplied to the plug-in.
- **Recommended eventual fix:** Add a normalized Coloring/Line/Guide input
  contract and port candidate typing. If the SDK cannot supply it, make the PNG
  companion accept all layers and either withhold native Quick Fix or explicitly
  rename/document it as a different single-layer heuristic.
- **Requires real Krita/CSP testing:** Yes, CSP; SDK feasibility is decisive.

### C-02 — Learned prediction and the 32x32 model pipeline are absent

- **Component:** CSP predictor/model integration
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** The ONNX predictor is a permanent unavailable stub. CLI
  and generic host command reset an ONNX request to rule-based. There is no
  centered patch, two-channel tensor, contract validation, likelihood inference,
  region-mean selection, or modal region color in C++.
- **Expected behavior or question:** A feature presented as GapFill should
  reproduce the pinned model input/output and reviewed postprocessing, unless it
  is explicitly scoped as a non-learned alternative.
- **Evidence:** `src/predictors/onnx_predictor_stub.hpp:9-16`, its implementation
  `:7-11`, `src/cli/main.cpp:186-190`,
  `src/plugin_entry/gap_assist_command.cpp:39-45`, versus paper §4.2 and the
  model contract in §2.
- **Recommended verification:** Before adding a runtime, make C++ emit the exact
  raw 32x32 tensors for shared goldens; feed fixed output maps into independent
  postprocessing tests.
- **Recommended eventual fix:** Port preprocessing/postprocessing exactly, then
  integrate a pinned ONNX backend/model with explicit availability errors and a
  separately named fallback.
- **Requires real Krita/CSP testing:** No for pure parity; yes for native model
  packaging, load time, memory, and CSP compatibility.

### C-03 — Invented heuristic score is unsafe as auto-apply confidence

- **Component:** CSP rule predictor, confidence, Quick Fix
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** Samples are merged into 5-bit RGB buckets; a weighted
  arithmetic mean is returned, and bucket dominance/support/distance becomes a
  hand-thresholded “confidence.” The focused probe returned absent color red 3
  from only red 0/7 samples at confidence 1.0, so Quick Fix would auto-apply it.
- **Expected behavior or question:** Original GapFill selects a real painted
  region by learned likelihood and uses its representative/modal color. Any
  automatic gate needs demonstrated calibration against held-out art.
- **Evidence:** `src/predictors/rule_based_predictor.cpp:24-27,68-83,101-123`,
  `src/core/settings.cpp:44-60`, the probe in §3, and paper §4.2.1.
- **Recommended verification:** Evaluate exact-color accuracy, reliability
  diagrams, false-auto-apply cost, multi-color/line-art neighborhoods, and
  absent-color production on a reviewed corpus.
- **Recommended eventual fix:** Do not call the heuristic score calibrated
  confidence or use it unattended; at minimum select an actual region/modal
  source color, and retain the rule path only as visibly labeled fallback after
  a product decision.
- **Requires real Krita/CSP testing:** Yes for auto-apply UX acceptance; core
  calibration is host-independent.

### C-04 — CLI output paths can overwrite the source

- **Component:** CSP PNG CLI/output safety
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** `--correction` may equal `--input`; output is written
  directly with no path collision/preflight. A probe changed the source hash and
  replaced it with the correction image, contradicting the README's “source PNG
  is never overwritten.” Other output roles may collide too, and pre-existing
  default/explicit output files are replaced without a force policy.
- **Expected behavior or question:** Input must remain byte-for-byte unchanged;
  all outputs must be distinct and committed atomically only after successful
  generation.
- **Evidence:** `experimental/csp-plugin/README.md:62`, `src/cli/main.cpp:212-220`, and the
  source/correction hash probe in §3.
- **Recommended verification:** Tests for identical, normalized-equivalent,
  relative/absolute, case-folded where relevant, hard-link, and symlink paths;
  inject encode/write/rename failures and assert source hash invariance.
- **Recommended eventual fix:** Canonical/equivalent-file collision checks,
  all-output distinctness, temporary files in the target directory, fsync as
  appropriate, atomic rename with cleanup, and an explicit fail/`--force`
  contract for pre-existing outputs.
- **Requires real Krita/CSP testing:** No.

### C-05 — `--apply-high` overrides an explicit Skip

- **Component:** CSP CLI/review decision precedence
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** CLI loads decisions, then `applyHighConfidence()` sets
  every High gap to Apply regardless of prior status. A fixture decision
  `gap-0=skip --apply-high` ended as Apply/applied=1. A separate method correctly
  limits itself to Unreviewed candidates but is not used there.
- **Expected behavior or question:** An explicit user Skip must be terminal
  unless a separately confirmed override operation is requested; “apply
  remaining high” must affect only unreviewed gaps.
- **Evidence:** `src/cli/main.cpp:55,207-210` and
  `src/ui/review_session.cpp:85-97`; focused decision probe.
- **Recommended verification:** Exhaustive decision/state precedence table for
  Apply/Skip/Mark/Unreviewed combined with apply-all/apply-selected/apply-high,
  including option order and duplicate decisions.
- **Recommended eventual fix:** Call the remaining-only operation and encode a
  single documented precedence model shared by CLI and UI.
- **Requires real Krita/CSP testing:** No for the companion CLI; repeat against
  any future native review UI.

### C-06 — CLI settings and options are order-dependent

- **Component:** CSP command-line parser/settings
- **Severity:** Medium
- **Confidence:** Confirmed
- **Current behavior:** `--settings` replaces the complete Settings object at
  parse time while flags such as `--selection` mutate it immediately. Later
  settings therefore erase earlier explicit flags. Selection-before-settings
  processed outside the mask; reversing them detected zero. Mode, size, and
  confidence flags share the pattern.
- **Expected behavior or question:** Configuration-file defaults should load
  once, then explicit command-line overrides should apply with order-independent
  precedence.
- **Evidence:** `src/cli/main.cpp:78-99` and the selection/settings probe in §3.
- **Recommended verification:** Permute every configuration flag around
  `--settings`, compare normalized settings and output hashes, and include
  repeated flags/invalid settings.
- **Recommended eventual fix:** Parse paths and explicit overrides into separate
  structures, load settings once, then apply overrides in one deterministic
  merge.
- **Requires real Krita/CSP testing:** No.

### C-07 — Native cancellation cannot poll during one huge component

- **Component:** CSP detector/output cancellation
- **Severity:** High
- **Confidence:** Strong suspicion
- **Current behavior:** Flood fill reads an atomic flag internally, but the
  single-thread private adapter is the only code that updates that flag and can
  poll CSP only from progress/predictor callbacks. Detector progress fires after
  a completed row, so a component seeded early may traverse millions of pixels
  before CSP is polled. Correction generation has no cancellation hook.
- **Expected behavior or question:** Host Cancel should be observed at a bounded
  work/time interval in detection, owner analysis, prediction, and output, with
  no partial destination commit.
- **Evidence:** `src/core/gap_detection.cpp:70-72,133`,
  `src/core/correction_output.cpp:35-59`, and private adapter callback plumbing
  `GapAssistMain.cpp:438-492`. The path is confirmed; user-visible latency needs
  the real host.
- **Recommended verification:** Inject a mock clock/host poll into a huge single
  component and assert maximum visits/time before cancellation; cancel in every
  native phase in CSP and inspect destination/Undo.
- **Recommended eventual fix:** Pass an explicit bounded host-poll callback into
  all inner loops and output generation, separating it from percentage progress.
- **Requires real Krita/CSP testing:** Yes, CSP for lifecycle/latency.

### C-08 — Oversized components and duplicate images raise peak memory

- **Component:** CSP detector and Quick Fix resource use
- **Severity:** Medium
- **Confidence:** Confirmed
- **Current behavior:** The gap work vector grows to the entire transparent
  component even after it is known to exceed the threshold. Owner labels/queue
  and unconditional correction plus corrected-composite images add copies.
  Detector-only 4096x4096 transparent input used 167,068 KB peak RSS; full CLI
  4096x4096 used 205,096 KB and 1.15 s in this environment.
- **Expected behavior or question:** Oversized-region rejection should have a
  bounded frontier/retention policy, and Quick Fix should allocate only outputs
  it uses under a documented 4K/8K budget.
- **Evidence:** `src/core/gap_detection.cpp:38-39,55-77,105-113`,
  `src/core/owner_regions.cpp:39-41`,
  `src/core/correction_output.cpp:38-42`, and the audit benchmarks.
- **Recommended verification:** Track peak RSS and allocations for fully
  transparent, checkerboard-many-gap, large owner, and selection-only 4K/8K
  images; exercise allocation failure and cancellation.
- **Recommended eventual fix:** Use scanline/bounded-frontier traversal, stop
  retaining rejected component pixels, avoid unused correction images in native
  Quick Fix, and enforce/document resource ceilings.
- **Requires real Krita/CSP testing:** Yes for host memory/UI impact; pure
  benchmarks should remain in CI.

### C-09 — Owner regions are not learned region correspondence

- **Component:** CSP owner detector and predictor
- **Severity:** Medium
- **Confidence:** Confirmed
- **Current behavior:** Owner components are active-layer opaque pixels joined
  through pairwise neighbor RGB tolerance, so similarity is transitive. A probe
  joined red 0 to 20 to 40 with tolerance 30 although endpoints differ by 40.
  The user gap-connectivity setting also controls owners. Owner identity supplies
  only a 1.35 sample weight/metadata; it does not implement nearest large
  same-color line-art region correspondence.
- **Expected behavior or question:** “Owner” must either have its own defensible
  product contract or be replaced by the model's reviewed region
  correspondence. It must not be described as smart propagation without
  evidence.
- **Evidence:** `src/core/owner_regions.cpp:90-127`,
  `src/predictors/rule_based_predictor.cpp:68-83,118-123`, probe, and original
  `ml/src/utils/flood_fill/nearest_same_color.py:70-165`.
- **Recommended verification:** Goldens for color ramps/chains, two disconnected
  same colors, anti-aliased boundaries, line-colored opaque pixels, independent
  gap/owner connectivity, mean vs mode, and nearest-region identity.
- **Recommended eventual fix:** Remove or explicitly specify owner semantics;
  separate its settings from gap topology and select an actual reviewed region
  and modal color if retained.
- **Requires real Krita/CSP testing:** No for core semantics.

### C-10 — Soft selections use different topology and output coverage rules

- **Component:** CSP selection semantics
- **Severity:** Medium
- **Confidence:** Needs verification
- **Current behavior:** Every nonzero selection value is fully selected for
  detection/owner topology. The private adapter later blends corrections by the
  original 0–255 value, so selection 1 can determine connectivity/confidence but
  apply only 1/255 coverage. CLI mask loading instead binarizes nonzero alpha to
  255.
- **Expected behavior or question:** Analysis threshold/topology and mutation
  coverage for soft/sparse selections need one explicit, cross-surface policy.
- **Evidence:** `src/core/image_types.hpp:103-109`,
  `src/io/png_io.cpp:50-61`, and private adapter selection read/blend paths
  `GapAssistMain.cpp:263-365`.
- **Recommended verification:** Fractional masks at 1, 127, 254, holes, feathered
  boundaries, and selection-bounds edges through core, CLI, and real CSP;
  compare candidates and exact RGBA output.
- **Recommended eventual fix:** Specify a binary analysis threshold separately
  from output coverage, preserve mask values consistently, and expose deliberate
  differences if native SDK semantics require them.
- **Requires real Krita/CSP testing:** Yes, CSP.

### C-11 — Correction generation trusts stale or forged candidate indices

- **Component:** CSP correction invariant enforcement
- **Severity:** Medium
- **Confidence:** Confirmed
- **Current behavior:** Accepted candidate indices are written without verifying
  that source pixels are still transparent/in-scope. A forged accepted candidate
  replaced opaque `(9,8,7,255)` with `(1,2,3,255)`. The current synchronous
  pipeline uses one snapshot, but future review/host lifetimes make the trust
  boundary unsafe.
- **Expected behavior or question:** Commit must validate dimensions, unique
  in-range indices, source eligibility, selection, and snapshot identity before
  mutation.
- **Evidence:** `src/core/correction_output.cpp:43-51` and focused forged-candidate
  probe.
- **Recommended verification:** Negative tests for opaque, duplicate,
  overlapping, out-of-range, wrong-dimension, and changed-snapshot candidates;
  assert fail-closed with unchanged output.
- **Recommended eventual fix:** Make candidates provenance-bound or opaque
  engine values and revalidate all mutation invariants at generation/host
  commit.
- **Requires real Krita/CSP testing:** No for core; yes for host snapshot lifetime.

### C-12 — Generic richer-host mutation is not atomic

- **Component:** CSP future `GapAssistCommand` host abstraction
- **Severity:** Medium
- **Confidence:** Strong suspicion
- **Current behavior:** Undo capability is required only for active-layer
  overwrite. A host may expose correction/highlight layer creation without a
  transaction; an exception after creating the first layer has no rollback
  unless a transaction was already open. The current private adapter bypasses
  this path, so this is future-code risk rather than current native behavior.
- **Expected behavior or question:** Multi-step document mutation must be atomic
  or explicitly clean up every partial artifact on cancellation/error.
- **Evidence:** `src/plugin_entry/gap_assist_command.cpp:76-112` and public mock
  interface; tests do not inject failure after the first successful layer write.
- **Recommended verification:** Throwing-host tests at every mutation boundary,
  transaction begin/commit/rollback failures, cancellation between two layer
  writes, and a host with layer creation but no transaction.
- **Recommended eventual fix:** Require an atomic mutation capability for all
  document writes or implement explicit compensating cleanup with a proven host
  contract.
- **Requires real Krita/CSP testing:** Yes if a richer host adapter is built.

### C-13 — The actual CELSYS adapter is unversioned and unbuilt

- **Component:** CSP private SDK boundary/reproducibility
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** `/FilterPlugIn20210827` is ignored and `git ls-files`
  returns zero adapter/SDK files. Public `csp_sdk_adapter.hpp` is only an abstract
  placeholder. No CI or release job builds the actual `.cpm`; the private build
  disables public tests/tools. The public install contains CLI/docs/license only.
- **Expected behavior or question:** First-party adapter source needs
  terms-compliant version history, review, a pinned public-core commit, build
  provenance, and conformance evidence without publishing CELSYS materials.
- **Evidence:** `.gitignore`/local ignore state, `git ls-files`, public
  `src/plugin_entry/csp_sdk_adapter.hpp:7-14`, private CMake inspection, and
  isolated install inventory.
- **Recommended verification:** In an access-controlled repository, reproduce
  an MSVC build from a clean checkout and record compiler/SDK/core/plugin hashes;
  run shared adapter conformance tests.
- **Recommended eventual fix:** Version only permitted first-party adapter
  material in a restricted repository, keep SDK files out of public history,
  and make release provenance point to both immutable commits.
- **Requires real Krita/CSP testing:** Yes, CSP/Windows.

### C-14 — Native pixel, selection, Preview, Cancel, and Undo contracts are unverified

- **Component:** CSP private adapter/host mutation
- **Severity:** High
- **Confidence:** Needs verification
- **Current behavior:** The private code queries channel indices, reads separate
  image/alpha and selection blocks, writes destination blocks, and relies on the
  CSP filter lifecycle for Preview/restart/abort/one Undo. No MSVC build, load,
  or host execution was available. Project docs themselves leave runtime items
  pending.
- **Expected behavior or question:** Coordinate origins, block/row orientation,
  alpha representation, profiles, no/soft selection, layer offsets, Preview
  restart, cancellation, failure discard, OK, and exactly one Undo must match the
  actual supported CSP release.
- **Evidence:** Private adapter high-level read/write/run path; public
  `docs/CSP_SDK_20210827_CAPABILITIES.md:7-14`,
  `docs/SDK_INTEGRATION.md:53-67`, and
  `docs/MANUAL_TEST_PLAN.md:7-72` remain unchecked.
- **Recommended verification:** MSVC build plus disposable asymmetric RGBA/profile
  documents; test absent/soft selection, alpha lock, offsets, repeated Preview,
  cancel during every phase/write, forced exception, OK, exact output, and
  Undo/redo.
- **Recommended eventual fix:** Adjust the adapter only from recorded host
  evidence, add access-controlled regression/conformance tests, and publish the
  precise supported CSP/SDK/OS matrix.
- **Requires real Krita/CSP testing:** Yes, CSP.

### C-15 — CSP tests have no independent GapFill oracle

- **Component:** CSP semantic test suite
- **Severity:** High
- **Confidence:** Confirmed
- **Current behavior:** Detector and predictor units use solid opaque images with
  synthetic transparent dots. The PNG fixture is also one hole in a uniform
  color. Those cases pass while tracked real presets miss 4–12 multi-layer
  reference candidates; supplemental Git-ignored `C` assets miss 95–110. Owner
  behavior has no focused direct test; ONNX, private adapter, and resource/cancel
  latency tests are missing.
- **Expected behavior or question:** Tests must fail an internally consistent
  implementation that omits line/guides, patches/model, learned correspondence,
  or correct host mutation.
- **Evidence:** `tests/test_main.cpp:37-268,404-425`,
  `tests/cli_fixture.cpp:15-29`, §4 classification, and §3 preset comparison.
- **Recommended verification:** Independently review shared candidate masks,
  tensors, fixed model outputs, region/color decisions, adversarial CLI cases,
  and host conformance fixtures before coding to them.
- **Recommended eventual fix:** Run identical semantic vectors through web/ML,
  Krita, and C++; keep platform mutation tests separate from pure algorithm
  parity.
- **Requires real Krita/CSP testing:** No for the golden suite; yes for adapter
  conformance.

### C-16 — The host “probe” only prints a checklist

- **Component:** CSP test/diagnostic labeling
- **Severity:** Low
- **Confidence:** Confirmed
- **Current behavior:** `gap_assist_host_contract_probe` prints unchecked items
  and exits; it calls no CELSYS or host abstraction and is not registered as a
  test. A successful exit can be misreported as host evidence.
- **Expected behavior or question:** A probe should perform observable
  conformance checks, or the executable should be clearly named documentation.
- **Evidence:** `src/plugin_entry/host_contract_probe.cpp:3-15` and CMake test
  registration.
- **Recommended verification:** Assert its intended role in docs/CI; if retained
  as a probe, supply a host/adapter and machine-readable pass/fail checks.
- **Recommended eventual fix:** Rename it to a capability checklist generator or
  replace it with a real conformance probe.
- **Requires real Krita/CSP testing:** Only if converted into a native probe.

### CI-01 — Release workflows are neither registered nor exercised

- **Component:** CI/release process
- **Severity:** Medium
- **Confidence:** Confirmed
- **Current behavior:** Bundle workflows live only on feature branches, are not
  registered on default `main`, and have no matching tags/runs. Krita's job does
  not validate the vendored artifact; CSP's job does not build a plug-in.
- **Expected behavior or question:** A release gate must run from an immutable
  tag/commit, validate the exact installed artifacts, and distinguish CLI/core
  packages from real host plug-ins.
- **Evidence:** GitHub workflow registry/API, no release tags, YAML inspection,
  and install inventories in §1.
- **Recommended verification:** Land reviewed workflows on default, use dry-run
  dispatches, install/extract every artifact, run manifest/runtime/golden checks,
  and retain checksums/SBOM/build provenance.
- **Recommended eventual fix:** Make verified artifact tests mandatory before
  upload and name CSP CLI artifacts accurately until a native adapter is built.
- **Requires real Krita/CSP testing:** Yes before host plug-in release; artifact
  checks themselves run in CI.

### BASE-01 — Add-on commits do not contain current-main documentation changes

- **Component:** Branch integration
- **Severity:** Low
- **Confidence:** Confirmed
- **Current behavior:** Both add-on branches fork before four current-main
  commits. Only README/site SEO and branch-status prose differ; no implementation
  delta is missing.
- **Expected behavior or question:** Subsequent work should start from current
  `main` without losing either side's documentation.
- **Evidence:** Exact graph, merge-base, tree, and diff analysis in §1.
- **Recommended verification:** Rebase/transplant in a disposable branch, review
  `README.md`/`docs/index.html`, rerun every baseline check, and compare add-on
  trees apart from expected main changes.
- **Recommended eventual fix:** Rebase Krita then CSP in stack order before
  semantic implementation begins.
- **Requires real Krita/CSP testing:** No.

## 6. What remains unverified

The audit does not convert absence of a host into a pass:

- Krita itself, PyQt5, and PyQt6 were unavailable. No plug-in install, Docker,
  canvas interaction, color-managed mutation, selection, lock, Undo, multiwindow,
  HiDPI, or host shutdown behavior was executed.
- Windows/MSVC, the private CELSYS `.cpm` build, and CSP EX were unavailable.
  No SDK pixel block, selection, Preview/restart, progress/Cancel, destination,
  commit, or Undo assumption was executed.
- macOS/Windows release bundles and platform compiler/loader differences were
  not run. The feature-only bundle definitions have no demonstrated run.
- Full ML training/evaluation tests and training data were not installed/run.
  Source-level contract reconstruction and exact ONNX runtime smoke were used;
  model accuracy was not re-evaluated.
- LeakSanitizer was skipped because it cannot start under ptrace in this
  environment. ASan/UBSan ran without diagnostics after disabling leak checks.
- Public GitHub step conclusions were available; historical raw job logs/test
  counts were not, due the log endpoint's repository-admin requirement.

These are explicit release-gate items, not reasons to weaken the relevant
finding confidence.

## 7. Proposed next phases

The order below puts an independently reviewed contract before implementation,
then addresses data safety before broad correctness work. Each bullet group is
intended to become several small commits, not one rewrite.

### Phase 1 — Integrate and freeze the audited baseline

- **Exact scope:** Rebase/transplant `52f8c3f` and then `3a7a07e` onto current
  `main`; land this report; pin the audited head/model/tool evidence. Resolve only
  README/site text resulting from the graph update.
- **Likely files:** `README.md`, `docs/index.html`, `docs/addon-audit.md`; commit
  graph only for add-on trees.
- **Tests required before modification:** Re-run the full command matrix in §1
  on the old exact heads and archive manifests/checksums.
- **Tests required afterward:** Web tests; Krita pytest/Ruff/source ZIP manifest;
  CSP CMake/build/CTest and PNG E2E; `git diff --check`; compare add-on tree hashes
  excluding intentional main documentation changes.
- **Acceptance criteria:** Stack order remains Krita then CSP; no production
  behavior changes; current-main SEO/branch prose and add-on links both survive;
  all baseline results match.
- **Explicitly out of scope:** Every risk fix, test-oracle change, refactor, and
  release.

### Phase 2 — Specify and check in independent golden/reference fixtures

- **Exact scope:** Decide and document threshold inclusivity, image/selection
  boundary, alpha/line threshold, guide composition/type, connectivity,
  centroid/padding, model channels, region correspondence, and final color. Add
  small shared fixtures containing Coloring/Line/Guide/selection, expected gap
  pixel sets/types, raw 32x32 tensors, pinned ONNX outputs/tolerances, expected
  region labels, and RGB.
- **Likely files:** new `docs/addon-spec.md`; new shared
  `tests/fixtures/gapfill/` manifest/assets; a small reference exporter/validator
  under `scripts/`; web/ML reference tests; read-only fixture loaders in
  `krita-plugin/tests/` and `experimental/csp-plugin/tests/`.
- **Tests required before modification:** Capture current ML, web, Krita, and CSP
  results for each proposed fixture, including known disagreement, without using
  any result as expected truth.
- **Tests required afterward:** Schema/checksum validation; independent
  reference detector/patch/model/postprocess tests; round-trip fixture readers in
  Python, TypeScript, and C++. Known add-on mismatches may initially be a
  separately reported parity job, not silently rewritten expectations.
- **Acceptance criteria:** Every expected value has human-reviewable provenance;
  no expected file is generated by the implementation under test; all
  contradictions in §2 have an explicit decision; the model hash/opset/runtime
  tolerance is pinned.
- **Explicitly out of scope:** Production engine/host/UI changes, model retraining,
  performance optimization, and packaging.

### Phase 3 — Harden CSP companion output before algorithm changes

- **Exact scope:** Fix only path/output safety, atomic writes, decision
  precedence, settings/CLI option precedence, and correction candidate
  validation (C-04, C-05, C-06, C-11). Preserve current detection/prediction
  results.
- **Likely files:** `experimental/csp-plugin/src/cli/main.cpp`,
  `src/ui/review_session.*`, `src/core/correction_output.*`,
  `src/io/png_io.*`, review artifact I/O, and focused tests/fixtures.
- **Tests required before modification:** Add failing tests for input/output and
  inter-output aliases, symlinks/equivalent paths, partial-write failure,
  `Skip + apply-high`, every settings/flag order, and stale/forged indices.
- **Tests required afterward:** All new negatives plus current 25 core tests,
  CTest PNG chain, source-hash invariance, ASan/UBSan, and failure-injection
  cleanup.
- **Acceptance criteria:** The source and completed outputs are never partially
  overwritten; every output path is distinct; explicit decisions are stable;
  CLI order cannot change normalized settings; invalid candidates fail closed.
- **Explicitly out of scope:** Detector/predictor semantics, ONNX, SDK adapter,
  UI, and performance redesign.

### Phase 4 — Correct pure detection and raster semantics

- **Exact scope:** In separate Krita and CSP commits, make candidate construction
  and components conform to Phase 2. For CSP, introduce normalized multi-layer
  inputs, settle selection semantics, and bound/poll oversized traversal. For
  Krita, remove unjustified guide-component behavior, centralize boundary
  conversion, and retain deliberate edge rules. Keep prediction unchanged.
- **Likely files:** Krita `engine/detection.py`, `engine/patches.py`,
  `engine/types.py`; CSP `src/core/image_types.*`, `gap_detection.*`, pipeline
  input types/callers; both test suites and benchmarks.
- **Tests required before modification:** Failing candidate-map goldens for
  ordinary/guide gaps, line/alpha thresholds, `T-1/T/T+1`, edge/selection edge,
  4/8 choice, guide islands, soft masks, huge components, and cancel cadence.
- **Tests required afterward:** Exact pixel-set/type parity across reference,
  Python, TypeScript, and C++; bounded work/memory/cancel tests; current suites;
  sanitizer runs.
- **Acceptance criteria:** All deliberate platform differences are named in the
  fixture manifest; default candidate masks match the canonical contract; no
  fully open guide pixel is called enclosed; worst-case cancellation and memory
  meet documented budgets.
- **Explicitly out of scope:** Color prediction/model, host acquisition/mutation,
  overlay/review UX, and release packaging.

### Phase 5 — Correct learned prediction and region/color correspondence

- **Exact scope:** Resolve G-01/G-02/G-04/G-05; make Krita preprocessing and
  postprocessing match the reviewed contract; add CSP 32x32 extraction,
  inference adapter, output validation, region scoring, and modal color. Keep the
  CSP heuristic only under an accurately labeled fallback policy, with no
  uncalibrated auto-apply.
- **Likely files:** ML reference utilities/export metadata; web GapFill ONNX
  utilities if the canonical path needs repair; Krita `engine/patches.py`,
  `inference.py`, `postprocessing.py`, `colors.py`; CSP `src/predictors/`, new
  patch/postprocess modules, CMake/model packaging; shared golden loaders.
- **Tests required before modification:** Fixed input tensors, guide-only deltas,
  exact model contract/error/nonfinite cases, fixed output maps, label-0 and
  color-tolerance cases, actual-region/modal-color fixtures, fallback provenance,
  and backend unavailable/cancel cases.
- **Tests required afterward:** Cross-runtime tensor equality, ONNX output within
  pinned tolerance, exact selected region/RGB, real-art corpus results, corrupted
  model failure, no-gap/no-model behavior, and packaged-model smoke.
- **Acceptance criteria:** Krita and CSP match the canonical expected tensor,
  region, and color for every golden; no heuristic output is presented as
  learned/confident; model/runtime version and integrity are explicit.
- **Explicitly out of scope:** Host document mutation, canvas/review UI, broad
  performance tuning, and model retraining unless Phase 2 proves the artifact
  cannot support the chosen guide contract.

### Phase 6 — Qualify and repair Krita host integration

- **Exact scope:** Build a thin testable LibKis boundary; fix scan-generation
  invalidation, layer/raw-projection geometry, canvas/profile conversion,
  selection/foreground/locks, atomic Undo, cancellation teardown, and
  rotation/mirror/HiDPI/multiwindow overlay ownership.
- **Likely files:** `krita_adapter.py`, `controller.py`, `worker.py`,
  `overlay.py`, `docker.py`, `qt_compat.py`, host fakes/adapters, and a versioned
  real-Krita test document/manual harness.
- **Tests required before modification:** Failing Qt event-loop race tests and a
  recorded real-host matrix: asymmetric colors/profiles, no/existing/soft
  selection, node/global locks, offsets/transforms/masks, mutation after scan,
  multiple colors and undo history, pan/zoom/rotation/mirror, HiDPI, two windows,
  cancel/deactivate/shutdown, PyQt5 and PyQt6.
- **Tests required afterward:** All pure goldens, deterministic controller/worker
  integration tests, exact pixel/selection/foreground/Undo assertions in real
  Krita, and leak/orphan-widget checks across the supported matrix.
- **Acceptance criteria:** No stale/cancelled generation can mutate or install UI;
  predicted displayed color equals committed color in supported profiles; apply
  is atomic and restores exact user state; overlay coordinates/hits remain exact
  in every advertised view mode; unsupported nodes fail before preview.
- **Explicitly out of scope:** CSP work, cosmetic redesign, new interaction
  features, unsupported profiles/depths, and release bundling.

Phase 6 implementation is complete under the restricted/fail-closed contract
recorded in `docs/addon-phase6.md`. Its real-host acceptance work is tracked
separately as Phase 6.5 and does not reopen that implementation status.

### Phase 6.5 — Qualify the Krita integration in a real host

- **Status:** **CLOSED** in the recorded Windows 11 Pro x64 / Krita 5.3.3 host
  cell. A–P and R–V passed; Q is closed as
  `ROW_Q_HOST_CONDITION_UNAVAILABLE`, not PASS. Historical consumed failures
  remain preserved in `docs/addon-phase6.5.md` and the machine-readable matrix.
- **Exact scope:** The frozen A–V matrix was executed where the required host
  condition was available, with exact artifact and host metadata recorded. The
  tested one-step Undo/Redo route passed. Q's real HiDPI condition was
  unavailable; Row T is limited to its tested alternate RGBA/U8 profile cell;
  Row V excludes full application close with a worker active.
- **Acceptance criteria:** The applicable/available A–V rows passed for the
  recorded tested matrix, including Undo/data-safety behavior, and Q is
  explicitly represented as unavailable rather than converted to PASS.
- **Dependency:** Phase 7 CSP/CELSYS feasibility remained technically
  independent. Its canonical-input capability failure does not alter the
  closed Krita gate, and the Krita result does not alter CSP ineligibility.

### Phase 7 — Establish CSP feasibility and qualify the private adapter

- **Final status (2026-08-15):** **COMPLETE with capability failure.** Input
  feasibility is `C. INSUFFICIENT_FOR_GAPFILL_PARITY`; host qualification is
  `5. NOT_APPLICABLE_BECAUSE_INPUT_INFEASIBLE`. The evaluated 2021 Filter SDK
  and private adapter combination is permanently ineligible for release as
  canonical GapFill. This is not an unfinished implementation, a blocked host
  test, or a Phase 8 task. Host/core GapFill parity for this adapter is
  intentionally not applicable. See `docs/addon-phase7.md`.

- **Exact scope:** Decide whether the 2021 filter SDK can supply canonical
  line/guide geometry. Maintain permitted first-party adapter source in an
  access-controlled versioned repository pinned to public core. Add public
  failure-injection conformance tests and a private MSVC build/test pipeline;
  then execute the real CSP manual matrix.
- **Likely files:** Public SDK-independent adapter contract and conformance tests,
  `docs/SDK_INTEGRATION.md`, `MANUAL_TEST_PLAN.md`, capability/limitations docs;
  permitted private adapter/CMake/CI in the restricted repository.
- **Tests required before modification:** Preserve the private adapter build
  attempt/log and create disposable asymmetric RGBA/profile/selection documents;
  add conformance fakes for block origins/strides, partial reads/writes,
  cancellation, exception, restart, and transaction semantics.
- **Tests required afterward:** Clean MSVC build; exact channel/alpha/selection
  round trips; alpha lock; layer offset; Preview restart/replacement; cancel
  during detection/prediction/write; failure abort; OK; exact one-step Undo/redo;
  resource/cancel benchmarks in supported CSP EX versions.
- **Acceptance criteria:** No restricted SDK artifact enters public history;
  adapter/core/plugin hashes and supported matrix are recorded; every applicable
  manual item passes or becomes an explicit limitation. If separate layers are
  unavailable, native Quick Fix is withheld or clearly released as a differently
  named heuristic—not GapFill parity.
- **Explicitly out of scope:** Capabilities the SDK demonstrably cannot expose,
  paper-style canvas gestures if filters cannot receive them, and distribution
  approval.

### Phase 8 — UI, performance, packaging, and release qualification

- **Exact scope:** Preserve separate host gates for release qualification:
  Krita has satisfied Phase 6.5 for its recorded tested host matrix, subject to
  its explicit Q/T/V limits. The evaluated CSP SDK/adapter combination failed
  its Phase 7
  canonical-input capability gate and has no canonical GapFill Phase 8 release
  track. Work for one host may not turn the other host's gate into a pass. Only
  new capability evidence from a supported CSP integration mechanism could
  define a new CSP canonical-input qualification route. After an applicable
  semantic/host gate passes,
  optimize 4K/8K paths, polish interaction/review UX, complete Krita
  resource/license manifests and prune vendor contents, validate native
  dependencies, make workflows available on default, name CSP CLI/native
  artifacts accurately, and produce provenance.
- **Likely files:** Krita build/install scripts, requirements and bundle workflow;
  CSP CMake/install/release workflow and docs; performance harnesses; UI files
  whose host behavior is now covered.
- **Tests required before modification:** Freeze functional host recordings,
  package manifests/sizes, import/load timings, memory/cancel budgets, and release
  dry-run output for every target.
- **Tests required afterward:** Extracted-artifact imports and model goldens;
  clean Krita installs with action/shortcut/license; CSP CLI install and, only if
  qualified, native plug-in install; 4K/8K performance; platform shared-library
  inspection; SBOM/checksums; tag dry run; complete real-host smoke.
- **Acceptance criteria:** Exact artifacts—not source trees—pass supported
  OS/architecture/host matrices; package contents are minimal and complete;
  workflows are registered/reproducible; performance budgets and limitations are
  published; release names make no unsupported equivalence claim.
- **Explicitly out of scope:** New algorithms, model retraining, new host
  platforms, or feature expansion discovered during polish.

## Initial audit release decision (historical)

- **Krita:** keep as an audited prototype. Pure checks are healthy, but close the
  High semantic/host/package risks and execute the real-host matrix before a
  user-facing bundle.
- **CSP:** do not describe or release the evaluated native adapter/artifact as a
  GapFill implementation. Phase 7 later established that its canonical
  multi-layer input is infeasible through the evaluated SDK; the combination is
  permanently ineligible for canonical GapFill release, not pending completion.
- **Repository:** integrate current `main`, preserve this evidence, and begin
  Phase 2 only. Do not implement findings opportunistically before the golden
  contract is reviewed.

This report is the stopping point for the audit phase. No production fix has
been implemented.

## Final GapFill release/freeze preparation

After Phases 2–6.5 closed the semantic and real-Krita host gates, the exact
production checkpoint `df4e18c0b3f5e4ca8135ca52cba0b415ad3d52c8` was
audited and packaged without a production change. Two independent canonical
builds produced the same 895-entry Windows x86_64 artifact at SHA-256
`7001c1bf92aa7abb5840baf52fe07457ab06cb80074297488e67ded212ab74e2`;
that is also the exact historical qualified artifact identity, so production
payload drift is zero.

The concise release record is `docs/addon-release.md`; the authoritative
machine-readable freeze metadata is `krita-plugin/release/freeze.json`. The
repository history had no prior overall Krita plug-in version or `krita-v*`
release tag, so this freeze adopts GapFill `1.0.0` under governance identity
`GAPFILL_RELEASE_VERSION_V1_GOVERNANCE_ADOPTED` and prepares the prospective
tag `krita-v1.0.0`. No tag, push, or publication is part of this checkpoint.
