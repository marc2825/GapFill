# Krita model-input modes

Status: **implemented, bounded-real-host qualified on the recorded Windows /
Krita 5.3.3 host cell, integrated into `main`, and selected for the GapFill for
Krita 1.1.0 release candidate**.

This additive feature does not modify the published GapFill for Krita 1.0.2
tag or artifact. Version 1.0.2 remains the current published Line-only release;
the separately frozen 1.1.0 candidate adds the qualified selector without
rewriting that history.

## Contracts kept separate

The bundled model was trained with a binary Line-only channel 0 and target-gap
channel 1. The ONNX bytes, input/output names, shape `[1,2,32,32]`, and provider
policy are unchanged.

The development Docker exposes two prediction modes:

| Serialized value | Display | Channel 0 |
| --- | --- | --- |
| `line_only` | Line only | canonical Line boundary |
| `line_or_guides` | Line + Guides | canonical Line OR normalized effective Guide boundary |

`line_only` is the default for a fresh installation, an upgrade with no stored
key, and an unrecognized stored value. The setting is stored under
`modelBoundaryMode`; display text is never serialized.

Guide normalization uses the same any-nonzero-alpha binary boundary supplied
to Krita detection. In `line_or_guides`, a target Guide gap removes only its
own target-gap pixels from the Guide contribution before the OR. Channel 1 is
unchanged. Detection always uses Line OR Guides and is independent of this
selector. Full-image, Line-derived semantic regions, output scoring, Apply,
and all host mutation rules are also unchanged.

The Web product has its own restored compatibility runtime policy. Matching
normalized inputs give matching Line-or-effective-Guides composition, but this
does not redefine the Line-only training contract or the published 1.0.2
Krita default.

## Frozen-session boundary

Scan freezes the selected enum through the controller, worker, predictor, and
tensor builder. Every prediction and session checkpoint records that mode.
Changing the selector during a running or published analysis cancels/retire the
worker, removes the overlay, clears candidates and known history checkpoints,
and asks for a new explicit Scan. It does not rescan or invoke inference.
Undo/Redo reconciliation rejects a checkpoint from another mode.

## Automated evidence

The host-independent suite covers:

- missing, invalid, and persisted settings;
- exact default/explicit Line-only tensor identity;
- exact Line-or-Guides OR composition and target Guide-gap exclusion;
- unchanged target channel and detection topology;
- mode propagation through worker/predictor metadata;
- frozen checkpoint identity and fail-closed cross-mode restoration;
- mode-change invalidation without constructing a new worker;
- Apply/Undo restoration in each mode, plus the existing interaction,
  persistent-session, external-mutation, importer, release-freeze, and
  Line-only parity regressions.

These tests do not establish real-host qualification.

## Minimal real-Krita smoke plan

Use a disposable fixture whose normalized Guide geometry changes channel 0 and,
preferably, its prediction:

1. start without a stored mode and confirm **Line only**;
2. Scan, record the tensor/prediction identity, and leave the session active;
3. switch to **Line + Guides** and confirm the overlay/session disappears and a
   new Scan is required without automatic inference;
4. Scan again and verify the expected Guide contribution and prediction;
5. Apply one candidate, Undo once, and verify the same frozen second-mode
   prediction and candidate return without inference;
6. switch back to **Line only** and confirm another explicit Scan is required;
7. restart Krita after selecting **Line + Guides** and confirm persistence.

The smoke must also confirm that correction, magnifier, sweep, native Apply,
and known-checkpoint Undo/Redo behavior remain intact. Do not publish or claim
support for the new mode until this real-host smoke succeeds on the intended
support cell.

## Bounded real-host qualification

The feature was qualified from commit
`03a60fed522f446211adeb9b04fe7fb062e88207`. Its permanent Web baseline was
`main` at `efc63ce9b72bb21d719c1df36030c28a362fad56`, which was an ancestor of
the tested feature commit. No Web, CSP, OFFF, model, or published 1.0.2 bytes
were changed by qualification.

The exact host cell was:

| Component | Tested value |
| --- | --- |
| OS | Windows 11 Pro x64, build 26200 |
| Krita | 5.3.3, git `858d352` |
| Qt | 5.15.7 |
| Embedded Python | CPython 3.13.5 x64 |
| PyQt | PyQt5 5.15.11 |
| NumPy | 2.5.2, vendored under the installed plug-in |
| ONNX provider | `CPUExecutionProvider` |

### Qualification artifact and automated gates

The first working-tree build was rejected before host use because an ignored,
untracked directory would have entered that ZIP. The authoritative disposable
artifact was rebuilt twice from a clean `git archive HEAD` tree and the two
outputs were byte-identical. This excluded ignored local content, including
the unrelated OFFF directory and both protected `:memory:.ses` files.

| Evidence | Result |
| --- | --- |
| Artifact | `/tmp/gapfill-krita-model-modes-03a60fe-clean-win-x64-py313.zip` |
| SHA-256 | `3ad47d8b03f8a528c0a4846dffcc472fc032ab73bad19550bf1a73af58c586d1` |
| Size | 48,225,479 bytes |
| ZIP entries | 1,012 |
| Deterministic rebuild | **AUTOMATED PASS**, byte-identical SHA-256 |
| ZIP integrity | **AUTOMATED PASS** |
| Importer-faithful discovery | **AUTOMATED PASS**: exactly one `gapfill_krita/` / `GapFill for Krita` plug-in |
| Focused mode/session tests | **AUTOMATED PASS**, 36 passed |
| Full Krita suite | **AUTOMATED PASS**, 152 passed |
| Ruff | **AUTOMATED PASS** |
| `compileall` / PyCompile | **AUTOMATED PASS** |
| `git diff --check` | **AUTOMATED PASS** |
| Bundled ONNX SHA-256 | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`, unchanged |

The disposable ZIP was installed byte-for-byte into the user resource tree
while Krita was fully closed. The prior installed plug-in, desktop entry, and
action file were retained in a Windows Temp backup; no published release asset
was overwritten.

### Direct real-host model-input evidence

The real-host capture used the generated `real-guide-e102.kra` fixture. Its
SHA-256 was
`35f7f1c315f9b93974ec9aa3248ce284c62a1e030ee334a0e4f6cf555c2c3e45`.
Both modes used the same real Krita snapshot, Coloring, Line Art, Guides,
detected one-pixel gap at center `(25, 22)`, target channel, and frozen ONNX
model. Only the selected channel-0 policy changed.

| Real-host value | Line only | Line + Guides |
| --- | --- | --- |
| Serialized mode | `line_only` | `line_or_guides` |
| Channel-0 SHA-256 | `e55c5f074e823e5543ad0aa4dcd2ece25c46b2a11a72bc0c23149d2f51b37c94` | `18580e12cdcc654f75d4dbbf03280dc232d240c3ffa8e17a7fd0cfe42866b630` |
| Channel-0 active pixels | 79 | 151 |
| Complete tensor SHA-256 | `3cc843c1fa867a7dd056ded00551f224b54c9e674379ec659b2ae2be4d17eed0` | `1f4719fc3bf5c293a2b3612792fdaec4497760d0b4263f3f6e8955205984e5f7` |
| Channel-1 SHA-256 | `14d844aa2e0e84d6248e0c8af72be744722c5a54b588479de3ce1aafe9eb6f1f` | same |
| ONNX output SHA-256 | `fed6a7d79a2fecf1682785a999dfc3eb19f6abe631b745f37b5ef21eb7dbbfd1` | `23168e9bbb6048d94b83fc816e9ef52a3db4511f40c2abf34d9fe7f351defaad` |
| Learned RGB | `(243, 242, 239)` | `(251, 98, 115)` |
| Learned confidence | `0.8293993421718835` | `0.5089666837646115` |
| Provenance | `learned` | `learned` |

This is direct input and inference evidence, not a combo-box-label inference.
Detection geometry and candidate identity stayed fixed while channel 0,
ONNX output, prediction, and confidence changed.

### Production Docker/session results

| Smoke | Result |
| --- | --- |
| Missing stored key on first load | **REAL-HOST PASS**: UI `Line only`, effective `line_only` |
| Line-only Scan | **REAL-HOST PASS**: one learned candidate; mode frozen as `line_only`; overlay published |
| Line + Guides Scan | **REAL-HOST PASS**: one learned candidate; mode frozen as `line_or_guides`; overlay published |
| Active-session mode change | **REAL-HOST PASS**: snapshot, candidates, overlay, publication, and checkpoints cleared |
| Automatic rescan on mode change | **REAL-HOST PASS**: none; no worker remained |
| Automatic inference on mode change | **REAL-HOST PASS**: invocation delta zero |
| Explicit Scan after mode change | **REAL-HOST PASS**: new analysis used `line_or_guides` |
| Line-only Apply then Undo | **REAL-HOST PASS**: exact Coloring H0 restored; original frozen near-white candidate returned; inference delta zero |
| Line + Guides Apply then Undo | **REAL-HOST PASS**: exact Coloring H0 restored; original frozen pink candidate returned; inference delta zero |
| Cross-mode boundary | **REAL-HOST PASS**: Undo restored document H0 but did not resurrect the retired Line-only session into Line + Guides |
| Non-default persistence | **REAL-HOST PASS**: `line_or_guides` survived an abnormal restart, then a separate normal close/restart round-trip and appeared as `Line + Guides` |

The exact Coloring H0 was
`3ebc2952a5c1ba5d013e80972426729ba0abaa374ae36c2b876e6ae4d2c27d1e`.
Line-only Apply produced H1
`2393de93c3c9184cc45aaf3e3910b324d526403beb4c783671e523ca03edf1bf`;
Line + Guides Apply produced H1
`4549878328a72489d79a713e6268218ce03caf0eeaec54bac1149da9276f19ea`.
Each Undo returned byte-exactly to H0.

### Bounded interaction regression

The existing disposable 512×512 three-candidate interaction fixture was
opened after a fresh restart. Manual real-host observation passed all bounded
checks: free passive pointer, hover magnifier, A-to-B hover switching,
move-away disappearance, canvas leave/re-enter recovery, represented-source
red selection over the physically blue obscured canvas, correction drag,
connector termination at the final clamped magnifier center, outside-circle
single-candidate sweep, no stuck pointer, pale yellow-green trail and cleanup,
exactly one swept candidate applied, remaining candidates retained in the same
frozen session without automatic rescan, and Deactivate cleanup.

This is a bounded regression smoke on the recorded host cell. It does not
reclassify the historical Phase 6.5 A–V matrix or broaden support to another
Krita/OS/HiDPI/split-view cell.

### Preserved harness-lifecycle incident

The one-shot automated harness wrote its complete result with status
`AUTOMATED_HOST_PASS_RESTART_REQUIRED` at 21:01:45 local time. Approximately
nine seconds later Krita generated
`C:\Users\marck\AppData\Local\CrashDumps\krita.exe.3036.dmp`, SHA-256
`00b278dfaf7a063eea468bf0d26f8f4df03b03add9c13ffcc6a74f02ce5c70c3`.
The dump records `EXCEPTION_ACCESS_VIOLATION` in
`libkritaflake.dll+0x7279b`, symbol
`KoToolProxy::qt_static_metacall`. Six preserved dumps from before this feature
contain the exact same module-relative fault address across ASLR bases. The
incident occurred after the feature evidence was flushed and after the harness
rapidly opened and closed several disposable views; it is therefore recorded
as a pre-existing Krita tool/view lifecycle condition exercised by the harness,
not silently counted as a feature PASS or diagnosed as a model-input semantic
failure.

The automated harness was not rerun. Required persistence and bounded
interaction checks were instead completed after clean restarts, including a
normal close/restart cycle, without another crash. No production repair was
made for this harness-lifecycle incident.
