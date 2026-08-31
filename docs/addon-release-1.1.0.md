# GapFill for Krita 1.1.0 release preparation

Status: **GAPFILL FOR KRITA 1.1.0 RELEASE CANDIDATE PREPARED**. No
`krita-v1.1.0` tag or public GitHub Release exists at this checkpoint.

GapFill for Krita is a Python plugin for Krita that finds small unpainted
transparent gaps in anime-style coloring and predicts likely fill colors. The
user-facing and Plugin Manager name is **GapFill for Krita**. Its technical
module, package, import, and `X-KDE-Library` identity remain `gapfill_krita`.
The prospective release title is **GapFill for Krita 1.1.0**, its prospective
tag is `krita-v1.1.0`, and its production Windows asset is
`gapfill-for-krita-windows-x86_64.zip`.

## Prospective release notes

### Highlights

Version 1.1.0 adds a selectable **Model input** policy:

- **Line only** remains the default. Prediction channel 0 contains the
  canonical Line boundary and therefore matches the model's training input
  semantics.
- **Line + Guides** adds the normalized effective Guide boundary to prediction
  channel 0. It is a compatibility/extended inference mode and may be
  out-of-distribution relative to the Line-only training data. It is not
  claimed to be more accurate.
- The selected mode persists across a normal Krita restart.
- Changing the mode during an active frozen Scan safely invalidates the
  analysis, overlay, candidates, and known checkpoints. It requires an
  explicit new Scan and never automatically rescans or runs inference.
- Both modes completed bounded real-host qualification on the documented host.

Guides can affect detection topology independently of prediction input.
Detection uses Line Art OR Guides in both modes. The selector changes only the
model's channel 0 policy; channel 1 remains the target gap and semantic regions
remain Line-derived.

The Web product has an independent historical compatibility runtime and is not
included in this Krita release bundle.

## Qualified host

The release candidate is qualified only for this exact cell:

| Component | Qualified value |
| --- | --- |
| Operating system | Windows 11 Pro x64, build 26200 |
| Krita | 5.3.3, git `858d352` |
| Qt | 5.15.7 |
| Embedded Python | CPython 3.13.5 x64 |
| PyQt | PyQt5 5.15.11 |
| ONNX provider | `CPUExecutionProvider` |

No arbitrary Linux, macOS, HiDPI, rotated/mirrored canvas, or split-view
support claim is made. Unsupported or stale host state fails closed.

## Installation

1. Download `gapfill-for-krita-windows-x86_64.zip` from the future 1.1.0
   GitHub Release. Do not extract the ZIP.
2. In Krita, choose **Tools → Scripts → Import Python Plugin From File…** and
   select the ZIP.
3. Restart Krita completely.
4. Open **Settings → Configure Krita… → Python Plugin Manager**, enable
   **GapFill for Krita**, and restart Krita again.
5. Open **Settings → Dockers → GapFill**. If needed, use
   **Tools → Scripts → Show GapFill Docker**.

The release ZIP is self-contained and includes the model, model metadata,
NumPy, ONNX Runtime, and the version-pinned native Apply helper. Do not install
extra packages into Krita's embedded Python.

## Basic usage

1. Choose the transparent paint layer as **Coloring**.
2. Choose the transparent-background boundary layer as **Line Art**.
3. Optionally choose a transparent-background **Guides** layer.
4. Choose **Model input**: **Line only** or **Line + Guides**.
5. Select **Scan / Activate**.
6. Inspect the candidates and predicted colors. Correct suggestions when
   needed, apply individually or from the docker, or sweep across candidates.
7. Select **Deactivate** when finished.

Remaining candidates stay in the same frozen Scan after Apply; GapFill does
not silently rescan or rerun inference. Known GapFill Undo/Redo steps restore
known adjacent checkpoints. Changing **Model input** invalidates the current
Scan and requires a new explicit Scan.

## Qualification evidence and limits

The model-input feature's automated and bounded host evidence is recorded in
[Krita model-input modes](krita-model-input-modes.md). Historical Phase 6.5
A–V and [1.0.2 interaction evidence](addon-interaction-1.0.2.md) remain
unchanged and are referenced rather than claimed as rerun.

After the automated feature harness had completed, Krita later recorded an
`EXCEPTION_ACCESS_VIOLATION` at `libkritaflake.dll+0x7279b`, associated with
`KoToolProxy::qt_static_metacall`. The same module-relative signature exists in
six dumps predating this feature. It is preserved as a pre-existing host
KoToolProxy lifecycle signature observed after harness completion and is not
attributed to the model-input feature without new causal evidence. Persistence
and interaction regression checks passed after normal restart.

Current limits include the exact host boundary above,
`CPUExecutionProvider`, fail-closed unsupported/stale state, and no broader
HiDPI or split-view qualification. **Line + Guides** is not the canonical
training-distribution input and has no accuracy-superiority claim.

## Preparation identities

- Starting `main` commit:
  `57ef6aeda0696b64a9f975899ed9cc419664561a`.
- Release-source commit:
  `6093dc40a391711ec087692a53eade5f2b6834e9`
  (`release(krita): prepare GapFill for Krita 1.1.0`).
- Frozen-candidate commit:
  `956773c044a817e47cba91fc70fee23ab45c00e5`
  (`docs(krita): freeze GapFill for Krita 1.1.0 candidate`). This is the exact
  intended `krita-v1.1.0` target. This later evidence-only documentation
  commit is not the tag target.
- Publication governance:
  `GAPFILL_1_1_0_MODEL_INPUT_MODES_V1_GOVERNANCE_ADOPTED`.
- Publication mode: `FROZEN_ARTIFACT_VERIFY_AND_PUBLISH`; eventual tag CI must
  verify and upload committed bytes rather than rebuild them.

The ONNX model, historical fixture identity, and version-pinned native helper
remain unchanged. The committed sidecar will truthfully distinguish Line-only
training, Web compatibility behavior, and the two Krita runtime modes.

## Frozen candidate artifact

Two independent clean-tree builds from the exact release-source commit used
the qualified Windows CPython 3.13 vendor payload and hash-pinned native
helper. `cmp` and SHA-256 proved the outputs byte-for-byte identical.

| Property | Frozen value |
| --- | --- |
| Repository artifact | `krita-plugin/release/artifacts/1.1.0/gapfill-for-krita-windows-x86_64.zip` |
| SHA-256 | `541cba4b205d50ff307191afed349209c19d54506a0930413b9a92780a22a767` |
| Size | 48,225,467 bytes |
| ZIP entries | 1,012 total: 895 files and 117 explicit directories |
| Importer | `PLUGIN_DISCOVERABLE`; exactly one `gapfill_krita` / `GapFill for Krita` plugin |
| Disposable install | 895/895 ordinary files present and byte-identical |

The archive contains the required explicit `gapfill_krita/` record, desktop
and action metadata, model and sidecar, vendored NumPy and ONNX Runtime, and
the version-pinned native helper. It contains no OFFF payload, tests, caches,
bytecode, probes, host harness, JSONL/crash/session evidence, source-control
files, or release-only scripts.

Compared with immutable 1.0.2, no ordinary files were added or removed. The
exact changed payloads are `Manual.html`, `controller.py`, `docker.py`,
`engine/inference.py`, `engine/patches.py`, `engine/types.py`,
`resources/models/model_info.json`, `settings.py`, and `worker.py`. They are
the reviewed model-mode UI, persistence, tensor policy, propagation, frozen
session identity/invalidation, manual, and truthful model-contract metadata.
The ONNX, dependency vendor tree, and native helper did not change.

Frozen identities:

- fixture manifest:
  `6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`;
- ONNX:
  `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`;
- 1.1.0 model sidecar:
  `58ca7fb15c414fabdf65019fc42d341f30398d3dc27b81b97da9c5a4ebffa398`;
- native helper:
  `ad2fa7463d59dca74a92dc867734b38eb7aa49821b163547da442147348f8746`.

The sidecar change from the historical 1.0.2 hash `2ccc406b...` is intentional:
it records Line-only training truth separately from Web compatibility behavior
and the two qualified Krita runtime choices. The ONNX bytes are unchanged.

## Local candidate validation

- focused model-mode/session tests: 36 passed;
- complete Krita/parity suite: 166 passed;
- release/freeze/importer/build tests: 33 passed;
- independent reference suite: 15 passed; provenance validation and Phase 5
  characterization passed with zero model delta;
- Web: 16 passed; ESLint, preset checks, image-metadata checks, and production
  TypeScript/Vite build passed;
- Ruff and compileall: passed;
- importer, ZIP integrity, disposable extraction, deterministic A/B build, and
  exact frozen verifier: passed;
- `git diff --check`: passed.

The local environment did not provide CMake, so the unchanged CSP gate was run
on the standard GitHub Actions runner.

## Frozen-candidate CI

Normal `main` CI run
[`33395516007`](https://github.com/marc2825/GapFill/actions/runs/33395516007)
passed on frozen-candidate commit `956773c044a817e47cba91fc70fee23ab45c00e5`:

- Krita plugin job `99498976183`: PASS;
- reference fixtures job `99498976361`: PASS;
- Web job `99498976417`: PASS;
- CSP Gap Assist core job `99498976519`: PASS, including CMake configure,
  build, and core/PNG end-to-end CTest.

Pages run
[`33395514923`](https://github.com/marc2825/GapFill/actions/runs/33395514923)
also passed and is recorded separately from release-artifact qualification.
The only annotations were GitHub-hosted action-runtime Node.js deprecation
warnings; no repository gate failed.

## Publication boundary

Preparation stops before creating or pushing `krita-v1.1.0`, creating a GitHub
Release, or uploading a public asset. Those operations require separate
explicit authorization after the frozen candidate and normal CI are green.
