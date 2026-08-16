# Add-on Phase 6.5 — Krita real-host qualification

Date: 2026-08-15–16 (Asia/Tokyo)

Qualification sources: `ed7d2e1bc96c14e0f80908bc7d3a01a872a15f55`, the
committed Row-A lifecycle repair, and the bounded Row-F ManagedColor repair
now recorded at `827e66ffe00fca3ed4387e4f896a41e479c5322e` (originally
prepared from checkpoint `454d345cdaa10bb9f2560ee1fe1ffcc3721bbc98`).

Status: **Rows A–F PASS; Row G FAIL; Rows H–V UNTESTED** in the recorded
real-host cell. Phase 6.5 remains open/failed, and this record is not a Krita
release qualification.

## Host and historical failed artifact

The real host was Windows 11 Pro x64, Krita 5.3.3, Qt 5.15.7, embedded CPython
3.13.5, and PyQt5 5.15.11. The installed qualification artifact was
`gapfill-krita-phase6.5-win-x64-py313-d387926.zip`, SHA-256
`46b27a4417e87bf5c5ccf4ef71bee212c7053ffcb30d006f8cfc1aa25d2da1fb`.

The following real-host observations passed before the failure:

- installation integrity;
- plug-in enablement;
- plug-in registration;
- vendored NumPy import, Python ABI, and DLL resolution; and
- creation and visibility of **Tools > Scripts > Show GapFill Docker**.

Invoking that action failed with this exact reported traceback:

```text
Traceback (most recent call last):

  File "...\\gapfill_krita\\extension.py", line 17, in <lambda>
    action.triggered.connect(lambda: self._show_docker(window))
                                     ~~~~~~~~~~~~~~~~~^^^^^^^^

  File "...\\gapfill_krita\\extension.py", line 21, in _show_docker
    docker = window.qwindow().findChild(QObject, "gapfill_krita_docker")
             ~~~~~~~~~~~~~~^^

RuntimeError: wrapped C/C++ object of type Window has been deleted
```

The evidence is therefore **registration PASS / action invocation FAIL**, not a
load failure. ONNX Runtime is lazy-loaded and this action failure occurred
before inference, so it provides no new real-host ONNX import result.

## Root cause and bounded repair

Krita calls `Extension.createActions(window)` for each created window. The
Phase 6 action connected a long-lived lambda that captured that particular
Python `Window` wrapper. The wrapper could be deleted before the action was
invoked; the callback then dereferenced it through `qwindow()` and raised the
reported exception. It also made the docker target depend on the creator
window rather than the active window at trigger time.

The repair connects the action directly to `_show_docker`. On each trigger it
resolves `Krita.instance().activeWindow()`, returns without error when there is
no active window, and searches only that window's public `Window.dockers()`
collection for the stable `gapfill_krita_docker` object name. A deletion race
during dispatch also fails closed. `qwindow().findChild(...)` and the captured
window wrapper were removed. Docker registration remains the existing
`DockWidgetFactory` registration and no docker, algorithm, or prediction code
changed.

This follows the official Krita contracts for
[`createActions(window)`](https://docs.krita.org/en/user_manual/python_scripting/krita_python_plugin_howto.html),
[`Krita.activeWindow()`](https://api.kde.org/legacy/krita/html/classKrita.html),
and [`Window.dockers()`](https://api.kde.org/legacy/krita/html/classWindow.html).

The prior suite had no extension-action lifecycle test. Its fake host and Qt
tests exercised other adapter, overlay, and worker lifetimes but never invoked
this action after deletion of the `createActions` wrapper. The new deterministic
regression failed all three cases against the Phase 6 implementation and passes
after the repair. It covers a deleted creator wrapper followed by a different
active window, no active window, and two windows with selection of only the
active window's GapFill docker.

## Verification

The final local verification results were:

- Krita plus Phase 2/4/5 parity suite: 60/60 passed, including the three new
  lifecycle cases;
- pre-fix lifecycle regression: 3/3 failed by dereferencing the creator
  window, reproducing the failure class;
- Ruff: passed;
- `compileall`: passed;
- neutral fixture validation: passed;
- independent reference tests: 15/15 passed;
- Phase 5 characterization: seven model cases at maximum absolute delta 0,
  with all frozen boundary, patch, and postprocessing comparisons passed;
- Web: 15/15 test files passed with no skips; ESLint, preset-asset checks,
  image-metadata checks, and the CI-equivalent Task-C-excluding build passed;
- source ZIP: `/tmp/gapfill-krita-phase6.5-rowA-source.zip`, 25 files,
  22,932,451 bytes, SHA-256
  `e9c9c76a04d2f2d97afc415928fb89cef7e0d1fa892a1f3fbad83569cf399f58`;
  `unzip -t` passed and the model and sidecar were present; and
- `git diff --check`: passed after the complete record was written.

Frozen semantic hashes remain:

| Artifact | SHA-256 |
| --- | --- |
| `tests/fixtures/gapfill/manifest.json` | `6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c` |
| `web/public/models/unet32.onnx` | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78` |
| `web/public/models/model_info.json` | `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5` |

No D-01 through D-07 decision, detector, tensor, model, region
correspondence, modal RGB, prediction provenance, snapshot, or staleness
semantic changed.

## Replacement qualification artifact

The replacement was built twice from separate clean staging directories using
the corrected worktree and the exact wheel closure from the failed artifact.
Both builds were byte-identical. The builder also verified that the complete
old/new file sets match, every vendored file is byte-identical, and
`gapfill_krita/extension.py` is the only changed packaged payload.

| Item | Value |
| --- | --- |
| Artifact | `/tmp/gapfill-krita-phase6.5-rowA-window-lifecycle-win-x64-py313-d387926.zip` |
| ZIP SHA-256 | `12a30dcf57f7aa703064e8babad05abe92626949b03e1acee0d0a0e7a0a7b5b9` |
| Compressed size | 47,842,566 bytes |
| Entries / files | 1,007 / 892 |
| Uncompressed file bytes | 101,967,793 |
| Manifest | `/tmp/gapfill-krita-phase6.5-rowA-window-lifecycle-win-x64-py313-d387926.zip.manifest.sha256` |
| Manifest SHA-256 | `5cdd17876e3ef7129e66e147ab0a29c9f9e3c7e6a64ea8fdb41b7887df4c8880` |
| Native-file inventory | 20 `.pyd`/`.dll` entries |
| Two-build reproducibility | PASS; both ZIP SHA-256 values identical |

The artifact's source identity was base commit
`d387926458f50ae9f99d805279650065eb71caa8` plus the then-uncommitted repair,
which is now committed as `ed7d2e1bc96c14e0f80908bc7d3a01a872a15f55`.
The packaged repaired `extension.py` SHA-256 is
`e089a789383a21133f511ee438defd8326b64ce189591badf63fe7706405f0c6`.

Dependency wheel hashes are unchanged:

| Wheel | SHA-256 |
| --- | --- |
| `flatbuffers-25.12.19-py2.py3-none-any.whl` | `7634f50c427838bb021c2d66a3d1168e9d199b0607e6329399f04846d42e20b4` |
| `numpy-2.5.2-cp313-cp313-win_amd64.whl` | `85aaccb24182c25df891ad0ec333585967e115269d5f1b17f2c9ae005bc96657` |
| `onnxruntime-1.28.0-cp313-cp313-win_amd64.whl` | `1a1a19175464665c9b8d50bc916f216cc0b569110045b7bbca8f9f290b186f58` |
| `packaging-26.3-py3-none-any.whl` | `d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c` |
| `protobuf-7.35.1-cp310-abi3-win_amd64.whl` | `230a75ddfc2de4806e56696ce9640c1cdfdb6543b7cfce98d42a4c0a0e7bdb87` |

ZIP CRC/integrity, duplicate and unsafe-path checks, model/sidecar hashes,
required desktop/action/package/model/dependency entries, the 20-file native
inventory, and restricted-material screening passed. Krita 5.3.3's own Python
Plugin Importer recognized exactly one `gapfill_krita` plug-in with its action
file.

## Row A replacement-artifact retest

The replacement artifact was cleanly reinstalled into the real host and Krita
was restarted. The manually observed Row A evidence was:

- clean reinstall: **PASS**;
- plug-in enabled after restart: **PASS**;
- **Tools > Scripts > Show GapFill Docker**: present;
- action invocation: **PASS**;
- GapFill docker: displayed successfully;
- error dialog: none; and
- previous `RuntimeError: wrapped C/C++ object of type Window has been deleted`:
  did not recur.

This real-host result confirms that the replacement artifact fixed the
demonstrated Window-wrapper lifetime defect in Windows 11 Pro x64 / Krita 5.3.3
for Row A. It does not erase or reclassify the original artifact's failure: its
SHA-256 and exact traceback above remain historical real-host evidence.

## Rows B–E capture integrity

The B–E baseline was clean commit
`ed7d2e1bc96c14e0f80908bc7d3a01a872a15f55`. Before capture, all 892 installed
non-cache files matched the replacement qualification ZIP exactly: no file was
missing, extra, or changed. The generator was the existing
`krita-plugin/host_tests/generate_fixtures.py`, SHA-256
`c07cdb6ab036a9fba626393a1d3fe4cf391cb5ae929a4f3eee4ddbb56c9eb42d`.

The real-host Scripter capture used production snapshot, detector, tensor,
postprocessing, and learned-predictor modules without invoking preview
writeback or any Apply route. It created only disposable test documents below:

```text
C:\Users\marck\AppData\Local\Temp\gapfill-phase65-be-ed7d2e1
```

`host-results.json` is 42,862 bytes, was last modified at
2026-08-15 21:54:49.3196276 +09:00, parses successfully, declares
`HOST_CAPTURE_COMPLETE`, and has SHA-256
`6a90364a9e82b745b28a27fc06e31fa6cbfc02b598ca7248e8c3aa10f0a74668`.
It contains three completed case records and all ten generated fixture hashes.
Every recorded fixture, dump, array key, shape, dtype, nonzero count, and hash
was revalidated against the preserved files with no discrepancy.

| Used case | Fixture SHA-256 | Dump SHA-256 | Dump size |
| --- | --- | --- | ---: |
| ordinary | `7010b5eafd9cb3828c34dfad258789a33685a615250b46375d99c44e28adca6b` | `3dd315fc19f6ff89b4a8c93330db49492e113b14148203aee9f5ddfe94d8f82b` | 7,714 bytes |
| Guide enclosure | `2441ed46cfac0b92f4336b161200328502a71bcc05766cf96f5a110cac57c2c2` | `237d8e60f17be62dc2369986a59f01105b41e39fdbf7e8e7fc028b6270797f9b` | 12,832 bytes |
| E102 Guide-associated | `5c7968338bf7c58e94304487f0d4198db166d1403b0972f6f902c16a2e877240` | `6cac2d87f99966990d3f0b4e41ec8809c9af0acb9037a042383d3431effd2fa9` | 8,118 bytes |

After the completed run, a later invocation reported
`FileExistsError: refusing to overwrite` for the same directory. The complete
JSON has no failure fields, and the dump/JSON timestamps form the expected
first-run completion sequence. The later attempt did not change the preserved
capture. It is a successful non-destructive repeated-run guard event, not a
Row B–E host failure.

## Row B — ordinary scan: PASS

The real process was PID 14832,
`C:\Program Files\Krita (x64)\bin\krita.exe`, Krita 5.3.3
(`git 858d352`), Windows 11 Pro x64, Qt 5.15.7, PyQt5 5.15.11, and embedded
CPython 3.13.5. Vendored NumPy 2.5.2 imported from the installed GapFill
`_vendor/numpy/__init__.py`; its CPython 3.13 `_multiarray_umath` and
`_umath_linalg` modules and two supporting NumPy DLLs were present in the
real-process module snapshot.

The generated ordinary document was 64×64 RGBA/U8,
`sRGB-elle-V2-srgbtrc.icc`, at document origin, with independent origin-aligned
Coloring, empty Guides, and Line Art paint layers and no selection. Coloring,
Line, and empty Guide acquisition matched the byte-exact generator recipe.
Detection returned exactly indices
`[1560,1561,1562,1624,1625,1626,1688,1689,1690]`, center `[25,25]`, bounds
`[24,24,27,27]`. Prediction was RGB `[13,117,241]`, winning Line region 2,
mean `0.6791881199677785`, provenance `learned`.

ONNX Runtime 1.28.0 imported from the installed
`_vendor/onnxruntime/__init__.py`. A model session was constructed with active
provider `CPUExecutionProvider`; `AzureExecutionProvider` and
`CPUExecutionProvider` were available. The real-process module snapshot showed:

- `onnxruntime_pybind11_state.pyd`, 18,481,152 loaded bytes, installed SHA-256
  `ccde72728a4496cfc32b2527d25380208ec0da02ded69e9f2ad14b4c02880bca`;
- `onnxruntime_providers_shared.dll`, 28,672 loaded bytes, installed SHA-256
  `ff7b6f864cd9e67e13f3b6c6709af97283ef95abe254babac3a81acbcb2781b1`.

The packaged `onnxruntime.dll` is present at the same vendored `capi` path,
SHA-256
`e23e1d0cef90ba2f10f48056fb8276b11c7fc714d1295aa4423c5ecd7a77a013`,
but was not listed as a separately loaded module. The loaded Python binding has
no import-table dependency on that separate DLL; the session, CPU execution,
and learned output establish that real embedded-host inference ran. This record
does not incorrectly claim that the unused separate DLL was loaded.

The session used model SHA-256
`8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`.
No heuristic fallback occurred and no host exception was recorded.

## Row C — pure/host parity: PASS

The captured ordinary arrays were fed independently through the frozen pure
engine. Results were:

| Stage | Result |
| --- | --- |
| Coloring membership | exact |
| Line detection boundary | exact |
| Guide mask | exact empty mask |
| selection/application mask | exact full mask; semantic selection absent |
| candidate pixel set | exact nine indices |
| centroid | exact `[25,25]` |
| bounds | exact `[24,24,27,27]` |
| 32×32 channel 0 | exact |
| 32×32 channel 1 | exact |
| ONNX output | exact; maximum absolute delta `0.0` |
| full Line-region labels and patch labels | exact |
| winning region | exact label 2 |
| representative RGB | exact `[13,117,241]` |
| provenance | exact `learned` |

The allowed ONNX comparison was `atol=1e-6`, `rtol=1e-5`; no stage diverged.
The independent analysis record SHA-256 was
`7f935687de14e2502155422ac16b96b26f25b2777122053d90b8ada4ccac4631`.

## Row D — Guide-enclosed detection: PASS

The controlled 64×64 document independently acquired byte-exact Coloring,
Line, and Guide layers. Its normalized Guide mask contained 56 boundary pixels
and created the expected 169-pixel enclosed transparent component at center
`[45,19]`, bounds `[39,13,52,26]`. The existing ordinary nine-pixel component
also remained; host and pure candidate sets/order were exact. The Guide-enclosed
candidate retained canonical kind `transparent`, so no artificial separate
“Guide gap” class/component was manufactured.

Both candidates' tensors, outputs, labels, region selection, RGB, and learned
provenance matched the pure run exactly. For the Guide-enclosed candidate,
channel 0 equaled the canonical Line-only patch, while the count of Guide-only
pixels entering channel 0 was zero. Guide therefore participated in detection
topology and remained excluded from the trained model boundary channel. The
versioned generator has no isolated/open-Guide document, so that optional
variant was not promoted to real-host evidence here.

## Row E — known near-white parity: PASS

The real E102 document was 32×32 RGBA/U8 with independently acquired Coloring,
Line, and Guide arrays exactly equal to the frozen PNG sources. Host and pure
both returned the sole candidate index `[729]`, center `[25,22]`, bounds
`[25,22,26,23]`. Geometry, both tensor channels, full and patch Line-region
labels, ONNX output, winning region 2, and representative RGB matched exactly;
the ONNX maximum absolute delta was `0.0`.

The real-host and frozen pure predictions were both near-white
`[243,242,239]`, mean `0.8293993421718835`, provenance `learned`. The completed
artwork value `[251,239,153]` remains separately recorded yellow accuracy
evidence and did not alter the host-parity expectation.

## B–E read-only result and gate state

For every tested document the complete before/after state records were equal.
Coloring, Line, Guide, and composite hashes were unchanged; selection remained
semantically absent; the intended Coloring node remained active; foreground
components, brush preset/size, eraser mode, global alpha lock, blend mode,
painting opacity/flow, and document-modified state were unchanged. The
disposable documents remained unmodified and were closed after capture. No
Apply path was invoked, and no relevant GapFill/ONNX/NumPy traceback or error
was found in the host evidence/logs.

Rows A–E are now **PASS** for this exact host/artifact cell. Rows F–V remain
**UNTESTED** and were not begun. Phase 6.5 therefore remains open, and the
one-step Undo issue remains a Krita release blocker. B–E exposed no blocker to
starting mutation/application Row F under separate authorization, but this
phase did not begin Row F and does not establish release qualification.

## Historical F–L harness preflight failure

The first F–L harness invocation stopped inside baseline validation before it
opened a fixture or entered Row F. Preserve it as an **F–L HARNESS PREFLIGHT
FAILURE**, not a row result:

- capture: `C:\Users\marck\AppData\Local\Temp\gapfill-phase65-fl-454d345\host-results.json`;
- SHA-256: `97a491aaff6ef895537db1f40eea5170586407b394a8cea7262d677149fa03de`;
- size: 1,735 bytes;
- modification/change timestamp: 2026-08-15 22:17:40.1833424 +09:00
  (a creation timestamp was not exposed through the WSL mount);
- status: `HARNESS_FAILURE`, with an empty `rows` object; and
- baseline booleans reported before the exception: artifact hash, fixture
  hashes, and frozen hashes true; `installed_tree_exact` false.

The installed-tree failure was a harness path-mapping defect. The importer ZIP
stores `gapfill_krita/**`, `gapfill_krita.desktop`, and
`gapfill_krita.action`, while Krita installs those paths as
`pykrita/gapfill_krita/**`, `pykrita/gapfill_krita.desktop`, and
`actions/gapfill_krita.action`. The original comparator incorrectly joined ZIP
paths directly to the resource root, which made its internal comparison report
all 892 payload files as missing and all 892 installed non-cache payload files
as extras. Its existing cache exclusion was not the cause of the failure.

A correctly mapped, read-only comparison found 892/892 artifact files present
and byte-exact, zero missing files, zero changed files, and 113 extras. Every
extra was a file below `__pycache__` named `*.cpython-313.pyc`: 21 GapFill
package caches, 84 vendored NumPy caches, and eight vendored ONNX Runtime
caches. Their names, locations, file signatures, and timestamps identify them
as embedded-CPython 3.13 runtime bytecode. There were zero differences in the
580 packaged `.py` files, desktop/action resources, four packaged `.onnx`
files, 16 `.pyd` files, four `.dll` files, the canonical model/sidecar, or any
other artifact source/data file. The complete per-file comparison record is
`/tmp/gapfill-phase65-fl-preflight-install-diff.json`, SHA-256
`a04def3eadd923b59c223ee2cf2db8f30d5cae72a4bb8a23115dc425ef2d0c98`.

The replacement harness is `/tmp/gapfill_phase65_fl_host_v2.py`, SHA-256
`0fd2c720c0c0e01ce32a0c3875c60191139e24ccd6ebfb9754918bcb4e0dd13b`,
and refuses to overwrite
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-fl-v2-454d345`. Its
comparator maps the importer layout explicitly, requires every artifact file's
exact hash, and allows extras only when they are under the installed GapFill
package's `__pycache__` directories and end in `.cpython-313.pyc`. Embedded
self-checks prove that this policy accepts exact payload plus such a cache, but
rejects changed Python, `.pyd`, and model payloads, arbitrary extras, and a
cache tagged for a different Python ABI.

No F–L semantic or host row was executed by that failed preflight. At that
historical point the matrix remained A–E **PASS**, F–V **UNTESTED**. The later
Row-F execution below supersedes only Row F; it does not reclassify the
preflight event.

## Row F — real-host apply failure

The corrected v2 harness, SHA-256
`0fd2c720c0c0e01ce32a0c3875c60191139e24ccd6ebfb9754918bcb4e0dd13b`,
was executed once. Its preserved capture is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-fl-v2-454d345\host-results.json`,
SHA-256 `1596ebc85b3cfc4a408e754f47707c557854efeb288ee91d4afbe3c59f5a7020`,
size 51,332 bytes, with modification/change timestamp
2026-08-15 22:47:46.1196005 +09:00. It passed artifact, fixture, frozen-hash,
installed-tree, and prior-preflight preservation checks, then entered
`row_f()` and failed in the production `apply_gap_colors()` path. Its empty
`rows` object reflects that the harness assigns a row record only after the row
function returns; the traceback through `row_f`, `_run_apply_case`,
`_assert_apply`, and `apply_gap_colors` proves that this was a real Row-F
execution, not another preflight failure. Rows G–L were not entered.
The only accompanying artifacts are `krita-before.log` (24,373 bytes,
SHA-256 `d2668c2a0d270344560259f688e252aef63d4a8f1b952c629b41c4f2a2c49ee1`,
source mtime 2026-08-15 21:54:48.9841453 +09:00) and
`krita-sysinfo-before.log` (8,334 bytes, SHA-256
`3283f424fc23d0ba0fb076449ad94d65d6c68a296c751a9561f52f1bd4db681a`,
source mtime 2026-08-15 21:53:31.3388471 +09:00). No after-log or Row-F NPZ
was written before exception propagation.

The fixture was the generated
`ordinary-srgb.kra`, SHA-256
`7010b5eafd9cb3828c34dfad258789a33685a615250b46375d99c44e28adca6b`:
64×64 RGBA/U8, `sRGB-elle-V2-srgbtrc.icc`, document offset `(0,0)`,
origin-aligned Coloring/Line/Guide paint layers, and no semantic selection.
The learned candidate and prediction had already passed Rows B/C: `gap-0`,
bounds `[24,24,27,27]`, indices
`[1560,1561,1562,1624,1625,1626,1688,1689,1690]`, RGB `[13,117,241]`,
provenance `learned`. Every target pixel was RGBA `[0,0,0,0]` before apply and
the exact expected value at each was `[13,117,241,255]`. Thus the expected
changed set was the nine coordinates `(24..26,24..26)` and no other pixel.

The production call reached this exact exception after triggering Krita's
public foreground-selection fill action and waiting for completion:

```text
RuntimeError: Krita's fill action did not produce the exact requested target pixels.
```

The first demonstrated divergence is the **HOST_ACTION_ASSUMPTION** boundary:
the action existed and was enabled; Coloring was asserted active immediately
before and after the action; `action.trigger()` and `document.waitForDone()`
returned; but the immediate raw Coloring read was not equal to the exact
expected array. The frozen exact postcondition remains correct and was not
weakened.

The capture cannot classify the transient action result as no-op, subset,
extra pixels, wrong RGB/alpha, wrong layer, selection reinterpretation, color
conversion, or timing. On mismatch, `apply_gap_colors()` conditionally restores
the complete original Coloring array before re-raising. The harness therefore
never received control to save its before/expected/observed NPZ. The capture
directory contains only the JSON and the two pre-operation log copies. The
post-action/pre-recovery `observed_changed`, missing/unexpected sets, and wrong
RGBA values are consequently **unavailable**, not zero.

The intended selection construction was internally consistent: 4,096 bytes at
document offset `(0,0)`, with exactly the nine candidate indices set to 255;
document, target, and selection coordinate origins were all zero. Production
did not read the installed global selection back before invoking the action,
so exact host selection interpretation, bounds, and byte preservation remain
unverified. Likewise, the source and target profiles were the same and
`CanvasColorBridge` expected `[13,117,241]`, but the foreground state at action
dispatch and the RGB actually written were not preserved. Selection, timing,
and color handling therefore remain distinct live hypotheses.

The original exception at `krita_adapter.py:594`, rather than the separate
recovery-failure or state-restoration exceptions, proves that emergency
recovery did not fail and that the semantic selection presence, active node,
foreground, eraser, alpha-lock, blend, opacity, and flow postconditions all
passed. It does not prove whether recovery was required: the action may have
been a no-op, or a changed array may have been restored and byte-verified. In
either case no failed target mutation escaped the production call. The
disposable document was closed without saving, and the source fixture remains
byte-identical. Record this as **Row F apply correctness: FAIL; failure
recovery: PASS at the enforced postcondition, with the recovery-write branch
not observable**.

A production repair is not yet unambiguous. The first one-shot diagnostic was
`/tmp/gapfill_phase65_rowf_action_diagnostic.py`, SHA-256
`a680d34f64b7dcb7bffb2ee7c50af29255c74672543b55f88c81cada77167d3a`.
Its preserved output is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowf-action-diagnostic-454d345`.
The result JSON has SHA-256
`3b4711379ecc575a46a1c83208f265e558830b7bd18fa580c156f1b4f89565dd`,
size 4,643 bytes, and modification/change timestamp 2026-08-15
23:02:41.6488576 +09:00. Its exact failure was:

```text
Traceback (most recent call last):
  File "<string>", line 665, in <module>
  File "<string>", line 437, in main
  File "<string>", line 149, in _selection_capture
AttributeError: 'Selection' object has no attribute 'bounds'
```

Preserve this as **ROW-F DIAGNOSTIC HARNESS FAILURE BEFORE ACTION
OBSERVATION**, not another Row-F failure. The fixture had opened, the frozen
scan and learned prediction had completed, original state had been captured,
and a standalone `Selection` had received the intended 4,096-byte mask with
nine selected pixels. The exception occurred while inspecting that standalone
object. Code order and an
empty `stages` list prove that `document.setSelection()`, foreground mutation,
action lookup, and `action.trigger()` had not run. No selection was installed,
no fill action executed, and no target pixel changed. Recovery reports
`required: false`, exact original pixels, absent semantic selection, and exact
active-node, foreground, and view state. The source fixture hash also remained
exact. The preserved NPZ has SHA-256
`c9629a69225b54d91e4b17ed4e706c840628e7c15e405bcb64603ed5b5ade22c`;
the before/after logs have SHA-256
`7d9bfff93838255b8d348b2721d21baaee68b0fc7e87205abb9d39b9f5125c9a`
and `f1730a6f6e433344aa2468369e47d81ceb56cd904d2c485bf418f86e3b2c404e`.

The root cause was solely a diagnostic API assumption. The installed Krita
5.3.3 `krita.pyi` exposes `Selection.x()`, `y()`, `width()`, `height()`, and
`pixelData(x, y, w, h)`, but no `bounds()` method; the real-host traceback
independently proves that the runtime object also lacks `bounds()`.
The replacement diagnostic is
`/tmp/gapfill_phase65_rowf_action_diagnostic_v2.py`, SHA-256
`2fd3ca781539b46d9e522269d80a9ca139226e9136bf505192cf16468d9f79db`.
It refuses to overwrite the new guarded directory
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowf-action-diagnostic-v2-454d345`,
does not call `apply_gap_colors()`, and was executed exactly once. It records the
four positional/size accessors plus the authoritative full 64×64 mask bytes,
length, hash, value counts, unique values, exact nonzero indices, and exact
coordinates. Both standalone and installed selections must match the nine
full-strength pixels exactly before action dispatch. It also records a
`before_trigger` checkpoint with document/node identities, foreground and
paint state, action availability, selection bytes, and target/Line/Guide
bytes. Subsequent checkpoints preserve exact target diffs and non-target
arrays before verified byte restoration of Coloring, Line, and Guide.

The helper-only test is
`/tmp/test_gapfill_phase65_rowf_action_diagnostic_v2.py`, SHA-256
`ed1d4b24de2fb48957fac7a813e39e3e6917e4a2943ae5acc1fd81758bac4d24`.
It passed with a fake Selection exposing only `x()`, `y()`, `width()`,
`height()`, and `pixelData()`. It also proved that unchanged metadata cannot
hide a missing selected pixel and that a short full-mask readback fails closed.
Its completed real-host evidence is analyzed below.

## Row-F action diagnostic #2 — timing and channel-order root cause

The diagnostic completed with status `DIAGNOSTIC_COMPLETE`; every intended
checkpoint and recovery record is present. Its guarded capture contains:

| Artifact | Bytes | Modification/change timestamp (+09:00) | SHA-256 |
|---|---:|---|---|
| `diagnostic-results.json` | 81,673 | 2026-08-15 23:36:13.6121948 | `df73922f27a465db79478fa1317e3963accc7e7f85a9f43f97de3e48c4032569` |
| `diagnostic-arrays.npz` | 9,002 | 2026-08-15 23:36:13.6151951 | `5993b65fb31091df81e9f6478fa9718a1b8db9e7773267394a436d4e543d9913` |
| `krita-before.log` | 25,381 | 2026-08-15 23:02:41.2928149 | `f1730a6f6e433344aa2468369e47d81ceb56cd904d2c485bf418f86e3b2c404e` |
| `krita-after.log` | 25,885 | 2026-08-15 23:36:13.1688596 | `efcb263b87303baacd32b39896b87858fd7bf6dbd5818b2205009e3281676d3e` |

The WSL mount did not expose an independent creation timestamp. The harness
hash is the prepared
`2fd3ca781539b46d9e522269d80a9ca139226e9136bf505192cf16468d9f79db`.
It revalidated the prior Row-F capture and failed diagnostic #1 at their exact
recorded hashes. The fixture remained `ordinary-srgb.kra`, SHA-256
`7010b5eafd9cb3828c34dfad258789a33685a615250b46375d99c44e28adca6b`,
before and after; no save appears in the diagnostic-period log delta.

Selection installation is exact, not merely bounds-compatible. The semantic
global selection was present; metadata was `x=24`, `y=24`, `width=3`,
`height=3`; the requested full-document read returned 4,096 bytes at SHA-256
`0282f8ce6c482aaa850599de0240d5b4ae15c1707f4f949f64069feb8d58bee9`.
Its only values were 0 and 255, with nine nonzero and nine 255 values. The
nonzero indices were exactly
`[1560,1561,1562,1624,1625,1626,1688,1689,1690]`, corresponding exactly to
`(24..26,24..26)`. The standalone object, installed global selection, and all
five checkpoint readbacks had that same full-mask hash. Therefore
`SELECTION_COORDINATE` and host selection expansion/subsetting are ruled out as
the first divergence.

Immediately before dispatch, the active document was the fixture and the
active paint-layer UUID was the Coloring target UUID
`{c08b3aca-9b92-4a47-90dc-2183d737d153}`. The action existed, was enabled, and
was the localized foreground-selection fill action. Eraser and global alpha
lock were false, blending was `normal`, and opacity and flow were 1.0. The
requested and view-read foreground both reported RGBA/U8,
`sRGB-elle-V2-srgbtrc.icc`, with `components()`
`[0.05098039284348488,0.4588235318660736,0.9450980424880981,1.0]`.
Those numbers equal `[13,117,241,255]/255`, but `components()` is the color
space's internal channel order, not an ordered RGB representation. The host
result below proves that this ManagedColor painted as `[241,117,13]` in the
engine's ordered RGBA representation.

All target differences reconstructed independently from the NPZ are:

| Checkpoint | Target raw SHA-256 | Changed | Missing expected | Unexpected | Wrong RGBA |
|---|---|---:|---:|---:|---:|
| `before_trigger` | `a3297caee6289cc0c44e903d6c05ea8326d9fd80a93ff488a7ba7d1e79357d4f` | 0 | 9 | 0 | 9 |
| `immediately_after_trigger` | `a3297caee6289cc0c44e903d6c05ea8326d9fd80a93ff488a7ba7d1e79357d4f` | 0 | 9 | 0 | 9 |
| `after_process_events` | `1ae99864046ad18286ef66609d990fb539fdbcfa1105173b491b21e74744bb7d` | 9 | 0 | 0 | 9 |
| `after_wait_for_done` | `1ae99864046ad18286ef66609d990fb539fdbcfa1105173b491b21e74744bb7d` | 9 | 0 | 0 | 9 |
| `after_refresh_wait_events` | `1ae99864046ad18286ef66609d990fb539fdbcfa1105173b491b21e74744bb7d` | 9 | 0 | 0 | 9 |

Before event processing, all nine requested indices remained
`[0,0,0,0]`; those are exactly the nine missing/wrong pixels and there were no
other differences. After `QApplication.processEvents()`, exactly those nine
indices changed from `[0,0,0,0]` to `[241,117,13,255]`. Every expected value
was `[13,117,241,255]`. The result did not change after `waitForDone()` or
projection refresh. There were never subset, expanded, or extra pixels.

Line Art remained at raw SHA-256
`896f4c6ce0e13abbae8a7f33d438fa70a465fd52f33ee72c3ccf9a9d755e4e82`
and Guides at
`4fe7b59af6de3b665b67788cc2f99892ab827efae3a467342b3bb4e3bc8e5bfe`
at every checkpoint, with zero changed pixels. The action wrote only to the
active Coloring target.

Timing is category **C** for the captured sequence: `trigger()` did not make a
mutation visible synchronously, while Qt event processing did. The diagnostic
then called `waitForDone()`, so it does not independently test
`trigger()` → `waitForDone()` without an intervening event pump. The original
production sequence failed, but the color defect below is already sufficient
to explain that failure whether or not `waitForDone()` dispatched the action.
Therefore asynchronous action timing is demonstrated behavior and a live
secondary repair concern, while the sufficiency of `waitForDone()` alone
requires the narrow isolation experiment below.

The first unambiguous semantic divergence in the requested
selection → foreground → action pipeline is **COLOR_CONVERSION / foreground
representation**, before the action writes pixels. `CanvasColorBridge` treats
`ManagedColor.components()` as ordered RGB even though Krita exposes
`componentsOrdered()` separately and integer RGBA storage/channel order is BGR
internally. Once dispatched, the action wrote the exact intended target set
with an exact R/B reversal. This is not an action-side selection or target
routing defect, and no evidence supports another profile transformation.

Observation is **PASS**: all five intended stages are present and independently
agree with the NPZ. Containment is **PASS**: recovery was required only for
Coloring, `setPixelData()` was accepted, and recovered Coloring, Line, and
Guide bytes exactly matched their before hashes. Semantic selection returned
to absent; document modified state, active node, foreground, eraser, alpha
lock, blending, opacity, and flow were exact. The fixture remained byte-exact
and the disposable document was closed without saving.

The root color defect and necessary bridge correction are unambiguous, but the
complete production repair is not yet unambiguous because action dispatch and
cross-profile construction each need one narrow real-host experiment before
production editing.
Retain the native fill action for that experiment: it demonstrated exact
selection and target behavior and preserves a better possibility of native
Undo than raw writes. Probe an asymmetric color on the ordinary and alternate
RGBA/U8 profiles while recording `components()`, `componentsOrdered()`,
`colorForCanvas()`, raw output, and engine RGBA. Separately capture
`trigger()` → `waitForDone()` → readback before any explicit event processing,
then prove whether a bounded event pump excluding user-input events dispatches
the action before the final wait/readback.
The prospective minimum repair is then to make `CanvasColorBridge` explicitly
translate between ordered RGB and Krita's internal channel order, dispatch the
queued action before waiting, and retain every existing exact readback,
staleness, state-restoration, and recovery postcondition. Focused asymmetric
channel-order and delayed-action fakes must accompany it.

Direct `Node.setPixelData()` is not selected as the Row-F repair. It can provide
exact sparse control only through a bounding-box or full-image
read/modify/write in integer BGRA, followed by refresh, dirty-state handling,
and exact readback; it also makes the selection and active node irrelevant.
However, the public operation is a direct paint-device byte write and does not
establish a normal user-visible Undo command. Its real-host Undo behavior must
be treated as unqualified and experimentally checked if that fallback is ever
reconsidered. The current selection/action path also remains unqualified for
one-step Undo—selection install/restore already modifies document state and
the diagnostic did not inspect command count—so Row I remains a separate
release blocker.

After the narrow color/dispatch experiment, the strict path is: implement the
two bounded repairs; add focused regressions; run the complete Krita and frozen
parity regression; build a deterministic replacement artifact; clean-install
it if native module locking requires; requalify Row F only; and resume G onward
only after Row F passes. No production repair, Row-F rerun, or later matrix row
was performed in this diagnostic-analysis step.

At completion of diagnostic #2 the matrix was A–E **PASS**, F **FAIL**, G–V
**UNTESTED**. Phase 6.5 remained open and failed; Krita was not
release-qualified. Row I was not begun, and the independent one-step Undo
release blocker remained uncleared.

## Row-F color/order and wait-isolation diagnostic

The final narrow pre-repair diagnostic completed with status
`DIAGNOSTIC_COMPLETE` in the same Windows 11 Pro x64 / Krita 5.3.3 / Qt
5.15.7 / CPython 3.13.5 / PyQt5 5.15.11 host cell. This section supersedes
only the prospective color/timing conclusions at the end of diagnostic #2; it
does not supersede or erase the original Row-F failure. The guarded capture is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowf-color-timing-diagnostic-454d345`:

| Artifact | Bytes | Modification/change timestamp (+09:00) | SHA-256 |
|---|---:|---|---|
| `diagnostic-results.json` | 559,428 | 2026-08-16 00:16:51.2938326 | `fe6bbd5082540a9f76a004eca59a5f5f92c0a110dbd1b75edbcc77a6e6c967f9` |
| `diagnostic-arrays.npz` | 66,866 | 2026-08-16 00:16:51.3078475 | `6e10d62fe871cd83b0f1ca49afec411d0e31a3fdd0abec25b68530ac6ca1b44b` |
| `krita-before.log` | 25,885 | 2026-08-15 23:36:13.1688596 | `efcb263b87303baacd32b39896b87858fd7bf6dbd5818b2205009e3281676d3e` |
| `krita-after.log` | 30,445 | 2026-08-16 00:16:50.8638205 | `7b5b42d4b1f0350ad043368765481157e3ccd750ae58de3d3bb6adc260c2f921` |
| `krita-sysinfo-before.log` | 8,334 | 2026-08-15 21:53:31.3388471 | `3283f424fc23d0ba0fb076449ad94d65d6c68a296c751a9561f52f1bd4db681a` |
| `krita-sysinfo-after.log` | 8,334 | 2026-08-15 21:53:31.3388471 | `3283f424fc23d0ba0fb076449ad94d65d6c68a296c751a9561f52f1bd4db681a` |

There is a harness-provenance correction. The preparation report named
SHA-256 `70ec3b86014512faef4fbcb8c5a2af2c1979bc5692fa7f9121df72e89ddde660`,
but that hash was sampled concurrently with a final formatting command. The
formatter completed at 2026-08-16 00:01:29.9638892 +09:00, before the capture,
and the preserved harness actually executed from
`/tmp/gapfill_phase65_rowf_color_timing_diagnostic.py` has SHA-256
`ab494054ba4a0467bd57a8037f2e3a735fc2e137b0584f3dc26c7f2956b364d9`.
The 00:01 harness timestamp precedes the 00:16 evidence timestamps. The
executed source remains preserved; the stale pre-format hash must not be used
as its identity.

The baseline revalidated the 892-file qualification artifact against the
installed tree: no file was missing or changed, and all 116 extras were
recognized CPython 3.13 bytecode caches. The artifact, prior Row-F capture,
diagnostic #2 JSON/NPZ/harness, both fixtures, and all frozen inputs matched
their recorded hashes. Eight color cases and one isolated timing case all
ended `COMPLETE`, with complete containment and unchanged source fixtures.
There is no missing case: the tenth, bounded-dispatch timing case was
conditional on a T2 result and was correctly skipped after T1. Independent
NPZ analysis loaded 178 arrays and cross-checked all 105 target/Line/Guide
stage arrays, hashes, changed sets, and wrong-pixel sets against the JSON with
zero discrepancy. Neither host log contains a relevant diagnostic error.

### Real ManagedColor order

Krita 5.3.3 exposes `components()`, `componentsOrdered()`, and
`setComponents(iterable)` but no `setComponentsOrdered()`. The asymmetric
probe supplied internal normalized components
`[0.1450980392156863,0.3568627450980392,0.6784313725490196,0.9372549019607843]`,
or `[37,91,173,239]/255`. Both tested profiles produced the same result:

| RGBA/U8 profile | `components()` after quantization | `componentsOrdered()` | ordered-to-internal |
|---|---|---|---|
| `sRGB-elle-V2-srgbtrc.icc` | `[37,91,173,239]/255` | `[173,91,37,239]/255` | `[2,1,0,3]` |
| `ACEScg-elle-V4-g10.icc` | `[37,91,173,239]/255` | `[173,91,37,239]/255` | `[2,1,0,3]` |

The full returned floats were
`[0.14509804546833038,0.35686275362968445,0.6784313917160034,0.9372549057006836]`
internally and
`[0.6784313917160034,0.35686275362968445,0.14509804546833038,0.9372549057006836]`
in ordered form. Thus, for the currently supported RGBA/U8 model/depth,
ordered `[R,G,B,A]` maps to internal `[B,G,R,A]`; the mapping did not vary by
profile. Node channel metadata independently listed internal positions 0–3 as
localized Blue, Green, Red, Alpha names in both documents. Those localized
names are not a suitable generic mapping API, and this result must not be
generalized to another color model or depth.

This is a ManagedColor component-order result. The diagnostic's Node arrays
are already normalized to ordered RGBA by the adapter's integer-byte boundary;
ManagedColor ordering and raw Node storage are separate contracts.

### Current and candidate color results

Every action used the exact 4,096-byte selection mask at SHA-256
`0282f8ce6c482aaa850599de0240d5b4ae15c1707f4f949f64069feb8d58bee9`:
metadata `(24,24,3,3)`, values `{0,255}`, and exactly indices
`[1560,1561,1562,1624,1625,1626,1688,1689,1690]`. Each completed action
changed those nine pixels, with zero missing and zero unexpected pixels.

| Profile / source | Construction | Target `components()` (U8) | Target `componentsOrdered()` (U8) | Canonical target RGB | Actual raw RGBA | Wrong |
|---|---|---|---|---|---|---:|
| sRGB / `[13,117,241]` | current | `[13,117,241,255]` | `[241,117,13,255]` | `[13,117,241]` | `[241,117,13,255]` | 9 |
| sRGB / `[13,117,241]` | candidate | `[241,117,13,255]` | `[13,117,241,255]` | `[13,117,241]` | `[13,117,241,255]` | 0 |
| sRGB / `[201,37,83]` | current | `[201,37,83,255]` | `[83,37,201,255]` | `[201,37,83]` | `[83,37,201,255]` | 9 |
| sRGB / `[201,37,83]` | candidate | `[83,37,201,255]` | `[201,37,83,255]` | `[201,37,83]` | `[201,37,83,255]` | 0 |
| ACEScg / `[13,117,241]` | current | `[16,112,191,255]` | `[191,112,16,255]` | `[56,122,236]` | `[191,112,16,255]` | 9 |
| ACEScg / `[13,117,241]` | candidate | `[236,122,56,255]` | `[56,122,236,255]` | `[56,122,236]` | `[56,122,236,255]` | 0 |
| ACEScg / `[201,37,83]` | current | `[200,37,83,255]` | `[83,37,200,255]` | `[166,33,82]` | `[83,37,200,255]` | 9 |
| ACEScg / `[201,37,83]` | candidate | `[82,33,166,255]` | `[166,33,82,255]` | `[166,33,82]` | `[166,33,82,255]` | 0 |

The normalized float records are retained in the JSON. The current sRGB
construction reproducibly swaps red and blue for both asymmetric colors and
is **EXPECTED-FAIL**. The sRGB candidate is **PASS**. The alternate result is
not judged against the original source RGB: the canvas/profile bridge converts
the two sources to `[56,122,236]` and `[166,33,82]`, respectively, and the
candidate wrote those exact target-profile values. The alternate candidate is
therefore **PASS**. Final color classification for each profile is
`CURRENT_CHANNEL_ORDER_CONFIRMED_WRONG` and
`CANDIDATE_ORDERED_CONSTRUCTION_PASS`.

### Isolated wait result

The fresh timing case used the correct candidate foreground and contained no
Qt event-processing call between trigger and the `after_wait` read:

| Checkpoint | Target raw SHA-256 | Selected RGBA | Changed | Missing | Unexpected | Wrong |
|---|---|---|---:|---:|---:|---:|
| before | `a3297caee6289cc0c44e903d6c05ea8326d9fd80a93ff488a7ba7d1e79357d4f` | `[0,0,0,0]` | 0 | 9 | 0 | 9 |
| immediate after `trigger()` | `a3297caee6289cc0c44e903d6c05ea8326d9fd80a93ff488a7ba7d1e79357d4f` | `[0,0,0,0]` | 0 | 9 | 0 | 9 |
| after `waitForDone()` | `3142182b6762b971fb5c78e6637917947fe84dc3240d386f6bcd459742503af3` | `[13,117,241,255]` | 9 | 0 | 0 | 0 |

This is T1: **`WAIT_FOR_DONE_SUFFICIENT`**. The timing case's dispatch list is
empty. The conditional 1/5/25/50 ms bounded-dispatch experiment did not run,
as required. Event dispatches used by the separate color controls and by
post-capture cleanup are not timing evidence and do not justify adding an
event pump to production.

### Containment and exact repair specification

All nine disposable cases report exact recovery of Coloring, Line, Guides,
selection presence/bytes, active node, foreground, eraser, global alpha lock,
blending, opacity, flow, and document-modified state. Coloring recovery was
required and accepted in every action case; Line and Guide recovery were never
required. Both `.kra` hashes remained unchanged, every document was closed
without saving, and there was no containment failure.

The production repair is now fully specified. For the explicitly supported
RGBA/U8 model/depth, `CanvasColorBridge` must:

1. construct canonical ordered `[R,G,B,A]` as ManagedColor internal
   `[B,G,R,A]` before calling `setComponents()`;
2. extract target RGB from `componentsOrdered()[:3]`, never from
   `components()[:3]`; and
3. keep the existing `trigger()` → `waitForDone()` sequence with no added Qt
   event pump.

No per-color runtime probe and no profile-specific cache is required for the
current support matrix: both profiles share the same model/depth mapping.
Production should keep this mapping explicitly scoped to RGBA/U8 and fail
closed or add a separately verified mapping if support expands. The exposed
channel names are localized and do not provide a stable generic inverse-map;
tests may verify the round trip with `componentsOrdered()`.

The minimum patch is confined to ManagedColor construction and ordered RGB
extraction in `CanvasColorBridge`. Exact post-write readback, snapshot/stale
validation, application planning, recovery, and state restoration must remain
unchanged. The native fill action remains the selected route, preserving the
possibility of later user-visible Undo qualification. It does not establish
one-step Undo: Row I remains **UNTESTED** and an independent release blocker.

The next authorized sequence is: make only that color bridge repair; add
asymmetric internal/ordered and alternate-profile regressions (and preserve a
delayed-action fake showing that `waitForDone()` is the synchronization
boundary); run the complete Krita and frozen parity suite; verify frozen
hashes; build and compare a deterministic replacement artifact; clean-install
it if required; and requalify **Row F only**. Rows G–V remain gated until Row F
passes in the repaired real host.

No production repair or Row-F rerun occurred here. The frozen manifest, model,
and sidecar remain
`6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`,
`8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`,
and `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5`.
At completion of this diagnostic the matrix remained A–E **PASS**, F **FAIL**,
G–V **UNTESTED**. Phase 6.5 remained open/failed and Krita was not
release-qualified.

## Row-F ManagedColor repair prepared; real-host requalification pending

Date: 2026-08-16 (Asia/Tokyo)

The repair baseline is branch `qualify/csp-host-adapter` at
`454d345cdaa10bb9f2560ee1fe1ffcc3721bbc98`, with the preceding Phase 6.5
evidence edits still uncommitted. The Row-A-qualified artifact remains
`gapfill-krita-phase6.5-rowA-window-lifecycle-win-x64-py313-d387926.zip`,
SHA-256
`12a30dcf57f7aa703064e8babad05abe92626949b03e1acee0d0a0e7a0a7b5b9`.
This section does not replace the original Row-F failure or either diagnostic;
it records a source repair and a package prepared for a future Row-F-only
real-host rerun.

### Bounded production repair

The repair changes only `CanvasColorBridge` in
`krita-plugin/pykrita/gapfill_krita/krita_adapter.py`. For the explicitly
supported RGBA/U8 contract, canonical ordered `[R,G,B,A]` is passed to
`ManagedColor.setComponents()` as internal `[B,G,R,A]`. Canonical target RGB is
now read from `componentsOrdered()[:3]`, rather than internal-order
`components()[:3]`. Construction also fails closed when asked to construct an
unsupported model/depth.

This is the direct implementation of the real-host mapping demonstrated above
for both `sRGB-elle-V2-srgbtrc.icc` and `ACEScg-elle-V4-g10.icc`. It does not
derive a per-color mapping at runtime, inspect localized channel names, or
generalize the mapping to another model/depth. No detector, tensor, model,
prediction, Guide, selection, recovery, state-restoration, or Undo semantic was
changed.

The apply sequence remains exactly `action.trigger()` followed by
`document.waitForDone()` and exact raw readback. No event pump was added. This
preserves the real-host `WAIT_FOR_DONE_SUFFICIENT` result. The test action model
now delays its mutation until the fake document's `waitForDone()` boundary, so
the regression tests the demonstrated host behavior without requiring a
production event-dispatch call.

### Source verification

Focused `test_krita_adapter.py` execution passed 16/16. Its new coverage
includes asymmetric `[13,117,241]` and `[201,37,83]` values; exact internal
`[B,G,R,A]` construction; a fake whose `components()` and
`componentsOrdered()` intentionally differ; the observed ACEScg round-trip
targets `[56,122,236]` and `[166,33,82]`; unsupported-space fail-close; exact
expected-byte application; and mutation visibility at `waitForDone()` without
event processing.

The complete established Krita plus Phase 2/4/5 suite passed 65/65. Neutral
fixture validation passed; the independent reference suite passed 15/15; and
the Phase 5 characterization reproduced all seven learned cases at maximum
absolute delta 0, plus 8 boundary, 13 patch, and 8 postprocessing cases. Ruff
passed from `krita-plugin`, `compileall` passed over the Krita, neutral-reference,
and parity Python paths, and `git diff --check` passed. The standard source ZIP
gate produced `/tmp/gapfill-krita-phase6.5-rowF-color-repair-source.zip`,
SHA-256
`0bf41d0353c28159fc4d6c13802448a024f748622af61611b226ad9e9c2ac0cc`,
22,932,490 bytes and 25 files; its ZIP integrity check passed. The platform
qualification bundle below, unlike that standard source-only builder output,
also includes the required action file and explicit directory entries.

An additional broader, non-established Ruff invocation over
`scripts/gapfill_reference` and `tests/parity` reported five pre-existing style
findings in two neutral reference files. Those files are outside this repair,
were not changed, and the actual established `krita-plugin` Ruff gate passed.

The frozen hashes remain unchanged:

| Artifact | SHA-256 |
|---|---|
| Fixture manifest | `6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c` |
| ONNX model | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78` |
| Model sidecar | `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5` |

### Deterministic Windows replacement bundle

The replacement was built twice from independent clean staging directories,
using the same five Windows x64/CPython 3.13 wheels as the Row-A-qualified
bundle. Both ZIPs and their per-file manifests are byte-identical.

| Item | Value |
|---|---|
| Artifact | `/tmp/gapfill-krita-phase6.5-rowF-managedcolor-win-x64-py313-454d345-worktree.zip` |
| ZIP SHA-256 | `bf19c8dc2fb3e44f160614f61fa189d52dac62bc24790b0094170ccd93fbe146` |
| Compressed size | 47,842,605 bytes |
| Entries / files | 1,007 / 892 |
| Uncompressed file bytes | 101,967,936 |
| Per-file manifest | `/tmp/gapfill-krita-phase6.5-rowF-managedcolor-win-x64-py313-454d345-worktree.zip.manifest.sha256` |
| Manifest SHA-256 | `92e14d82ff4f2ad71ba839cbb4dc3e00c53e2a39f448b88d3da8f60e999194c5` |
| Native inventory | 20 `.pyd`/`.dll` files |
| Builder | `/tmp/build_gapfill_phase65_rowf.py`, SHA-256 `25db43f02eb3441dba3a9ad24ac835fcebef3f322784dad05e81255a287353be` |
| Two-build reproducibility | PASS; ZIPs and manifests are byte-identical |

ZIP integrity passed. The desktop file, action file, Python package, model,
sidecar, explicit directories, vendored runtimes, and retained dependency
licenses are present. Compared with the Row-A-qualified ZIP, there are no added
or removed files and exactly one changed payload:
`gapfill_krita/krita_adapter.py`. Its packaged SHA-256 changed from
`0320a2704b44d3ee01bce072394f4d7a4110e3da266d53a38ad8ac8e035929d4`
to
`5dd75e58d70602d70ffa027b578a508333b1d2319612276012e3d680c9c09bf5`.
All 866 vendored files are byte-identical; their sorted manifest SHA-256 is
`030a116114b15b069c6c96681dd5d06dc715afb9852b115aea2c82e90c05ed85`
in both bundles. The model and sidecar bytes are also identical.

### Prepared Row-F-only rerun

The new, unexecuted harness is
`/tmp/gapfill_phase65_rowf_requalification_managedcolor_bf19c8dc.py`, SHA-256
`e3043bbf5a4f93c45c06c581021c7122a5d67a7fe3cf23574e9c0e078a768f25`.
It refuses to overwrite the unique guarded directory
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowf-requalification-managedcolor-bf19c8dc`.
Static compilation and Ruff checks passed; the harness has not been run in
Krita.

The harness executes only Row F. It validates the installed artifact against
all 892 packaged files while allowing only recognized CPython cache extras,
copies the reproducibly generated ordinary fixture to its guarded directory,
and opens only that disposable copy. It requires one Learned candidate with
indices `1560,1561,1562,1624,1625,1626,1688,1689,1690` and RGB
`[13,117,241]`, then calls the repaired production `apply_gap_colors()`. Its
JSON and NPZ evidence contain exact BEFORE/EXPECTED/AFTER arrays, expected and
actual changed sets, RGBA, selection readback, target identity, unchanged Line
and Guide data, user-state restoration, containment, and recovery state. Rows
G–V have no execution path in this harness.

Because the loaded plug-in contains native vendored modules that Windows may
lock, requalification requires this clean installation rather than an
in-place importer overwrite:

1. Disable GapFill in **Settings > Configure Krita > Python Plugin Manager** if
   practical, then fully exit Krita.
2. Confirm no `krita.exe` process remains, for example with Task Manager or
   `Get-Process krita -ErrorAction SilentlyContinue` in PowerShell.
3. Remove only the prior GapFill resources:
   `C:\Users\marck\AppData\Roaming\krita\pykrita\gapfill_krita`,
   `C:\Users\marck\AppData\Roaming\krita\pykrita\gapfill_krita.desktop`, and
   `C:\Users\marck\AppData\Roaming\krita\actions\gapfill_krita.action`.
4. Start Krita and use **Tools > Scripts > Import Python Plugin from File** to
   import
   `\\wsl.localhost\Ubuntu-24.04\tmp\gapfill-krita-phase6.5-rowF-managedcolor-win-x64-py313-454d345-worktree.zip`.
5. Enable GapFill in the Python Plugin Manager and fully restart Krita if the
   importer or manager requests it.
6. Confirm **Tools > Scripts > Show GapFill Docker** loads without an error,
   then run the prepared Row-F-only harness once from Scripter. Do not run the
   old F–L harness.

Row F may become PASS only if that fresh real-host run proves the Learned
candidate and exact nine-pixel `[13,117,241,255]` mutation with zero extra or
missing pixels, the intended target, unchanged Line/Guide inputs, restored
selection/user state, and no host exception. This source repair and bundle do
not themselves qualify the row. At package-preparation time the authoritative
matrix therefore remained A–E **PASS**, F **FAIL**, G–V **UNTESTED**. Phase
6.5 remained open/failed, Krita was not release-qualified, Row I/one-step Undo
remained an untested release blocker, and Row G had not begun.

## Row F — repaired real-host PASS

The dedicated Row-F-only requalification ran once in the same qualified host
cell and completed with `ROW_F_PASS`. The capture is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowf-requalification-managedcolor-bf19c8dc\row-f-results.json`,
SHA-256 `9bbf01083a3b59610e6609ce3a80ed13eb13ca95a787b51c961b7c1f8bd86ad8`,
size 24,544 bytes. Its internal creation time is
2026-08-16 00:03:25.760148 UTC (09:03:25.760148 +09:00); its WSL-observed
modification/change timestamp is 2026-08-16 09:03:27.8555926 +09:00. The WSL
mount did not expose a separate filesystem birth time.

The host record is Windows 11 build 26200 x64, Krita 5.3.3
(`git 858d352`), Qt 5.15.7, embedded CPython 3.13.5 AMD64, and PyQt5 5.15.11.
The executed harness remains
`/tmp/gapfill_phase65_rowf_requalification_managedcolor_bf19c8dc.py`,
SHA-256 `e3043bbf5a4f93c45c06c581021c7122a5d67a7fe3cf23574e9c0e078a768f25`.
The capture schema and scope are
`gapfill-phase6.5-row-f-requalification-v1` and “Row F only; Rows G–V are not
executed”; its final `rows_g_through_v` field is `UNTESTED_NOT_STARTED`.

### Capture and installed-artifact integrity

The capture revalidated the replacement artifact
`gapfill-krita-phase6.5-rowF-managedcolor-win-x64-py313-454d345-worktree.zip`
at SHA-256
`bf19c8dc2fb3e44f160614f61fa189d52dac62bc24790b0094170ccd93fbe146`.
All 892 packaged files were installed and byte-exact: zero missing, zero
changed, and zero unexpected extras. The other 105 installed files were
recognized `__pycache__`/`.cpython-313.pyc` products of the embedded runtime.
The loaded package resolved below
`C:\Users\marck\AppData\Roaming\krita\pykrita\gapfill_krita`.

Independent comparison against the Row-A-qualified artifact found no added or
removed payload and only `gapfill_krita/krita_adapter.py` changed. The current
production file and packaged file are byte-identical at SHA-256
`5dd75e58d70602d70ffa027b578a508333b1d2319612276012e3d680c9c09bf5`.
The frozen manifest, model, and sidecar hashes were revalidated as
`6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`,
`8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`,
and `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5`.

All capture-referenced evidence was present at its recorded identity:

| Evidence | Bytes | SHA-256 |
|---|---:|---|
| `row-f-before-expected-after.npz` | 2,682 | `927b27ddd5327dca40d3713ffaefa2a98db073f5f9e48a58924da7ce678d755c` |
| disposable `row-f-ordinary-disposable.kra` | 41,352 | `7010b5eafd9cb3828c34dfad258789a33685a615250b46375d99c44e28adca6b` |
| source `ordinary-srgb.kra` | 41,352 | `7010b5eafd9cb3828c34dfad258789a33685a615250b46375d99c44e28adca6b` |
| `krita-before.log` | 32,619 | `6ecf08ad85a83dc951697d7320b5dcd0d2f15b7de8d816f280b2bc14c9cd0687` |
| `krita-after.log` | 33,193 | `c0364ecad2c7f50f183f2f99e01102b3b67a11f91eb3b5581cfee2b13e74bb2b` |
| `krita-sysinfo-before.log` | 8,334 | `3f7a0c625c87d4ef678a1fddb4fcbf780693bd1e3a89d2b95a287ae7de89b9c5` |
| `krita-sysinfo-after.log` | 8,334 | `3f7a0c625c87d4ef678a1fddb4fcbf780693bd1e3a89d2b95a287ae7de89b9c5` |

The after-log begins with the complete before-log and its delta contains only
the expected load of the disposable 64×64 `.kra`; no traceback, exception, or
relevant error is present. The disposable and source fixture hashes remained
unchanged, and the document was closed without saving.

### Machine-verified Row-F result

The scan produced exactly one `learned` prediction, `gap-0`, bounds
`[24,24,27,27]`, center `[25,25]`, confidence
`0.6791881199677785`, and RGB `[13,117,241]`. Candidate and application indices
were exactly:

```text
1560 1561 1562
1624 1625 1626
1688 1689 1690
```

Independent NPZ analysis found that the actual before-to-after changed set and
the expected before-to-expected changed set are both exactly those nine
indices. The actual full Coloring image is byte-identical to the independent
expected full image, SHA-256
`3142182b6762b971fb5c78e6637917947fe84dc3240d386f6bcd459742503af3`.
Every changed pixel is exactly RGBA `[13,117,241,255]`; there are zero missing
and zero unexpected pixels. The expected mask has exactly those nine nonzero
pixels and SHA-256
`0282f8ce6c482aaa850599de0240d5b4ae15c1707f4f949f64069feb8d58bee9`.

The intended Coloring target UUID
`{c08b3aca-9b92-4a47-90dc-2183d737d153}` was active before and after. The
fixture tree contains only Coloring, Guides, and Line Art under its root. Line
is byte-identical before/after at SHA-256
`896f4c6ce0e13abbae8a7f33d438fa70a465fd52f33ee72c3ccf9a9d755e4e82`;
Guide is byte-identical before/after at SHA-256
`4fe7b59af6de3b665b67788cc2f99892ab827efae3a467342b3bb4e3bc8e5bfe`.
Together with the exact nine-pixel Coloring comparison, this establishes that
no unrelated fixture layer changed.

The production call returned `changed_pixels: 9` and completed its exact
post-write verification. The capture contains no error fields. Emergency
recovery was neither needed nor observed. Semantic no-selection was restored
as no-selection. Active node, target/Line/Guide identities, layer tree,
document geometry/profile, foreground internal and ordered components, eraser,
global alpha lock, blend, opacity, flow, zoom, rotation, and mirror are all
exactly equal before and after.

### Repair boundary and gate result

The qualified production diff remains confined to `CanvasColorBridge`:
supported RGBA/U8 ordered `[R,G,B,A]` is supplied to internal
`setComponents()` as `[B,G,R,A]`, and canonical target RGB is extracted with
`componentsOrdered()[:3]`. The current file is byte-identical to the packaged
and installed artifact. No Qt event pump was added; the action path remains
`action.trigger()` → `document.waitForDone()` → exact raw readback. There is no
change to detection, prediction, Guide semantics, selection semantics,
application planning, stale validation, recovery, Undo behavior, or OFFF.

Row F is therefore **PASS** for this exact tested host/artifact cell. The full
historical chain above remains authoritative: original Row-F failure;
diagnostic #1 harness failure before action observation; diagnostic #2 proving
the red/blue reversal; the color/timing diagnostic proving candidate
construction and `WAIT_FOR_DONE_SUFFICIENT`; the bounded production repair and
replacement artifact; and this fresh repaired real-host PASS.

The authoritative matrix is now A–F **PASS**, G–V **UNTESTED**. Phase 6.5
remains **OPEN** and is not a release qualification. Row I remains an
**UNTESTED release blocker** because the successful apply reports
`atomic_undo: false` and no Undo test was performed. Rows G–L may proceed under
separate authorization; none was begun here.

## Row G — Apply Selected PASS; Apply All real-host failure

The G–L harness was executed once against committed baseline
`827e66ffe00fca3ed4387e4f896a41e479c5322e` and the already Row-F-qualified
artifact
`gapfill-krita-phase6.5-rowF-managedcolor-win-x64-py313-454d345-worktree.zip`,
SHA-256 `bf19c8dc2fb3e44f160614f61fa189d52dac62bc24790b0094170ccd93fbe146`.
The harness is `/tmp/gapfill_phase65_gl_host_rowfpass_827e66f.py`, SHA-256
`b2433e929baa3502b2f568b301786c1dd694dc21927a79069acd613ebe2207d3`.
The real host remained Windows 11 AMD64, Krita 5.3.3 (`git 858d352`), Qt
5.15.7, embedded CPython 3.13.5, and PyQt5 5.15.11.

The preserved guarded capture is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-gl-rowfpass-827e66f`.
It must not be overwritten or rerun. Its principal artifacts are:

| Artifact | Bytes | Modification/change timestamp (+09:00) | SHA-256 |
|---|---:|---|---|
| `host-results.json` | 61,066 | 2026-08-16 09:22:13.1075249 | `c55fc40eadda59c87766268eb36fc86980219261e51da60090c7fc4652111c2a` |
| `row-g-apply-selected.npz` | 2,777 | 2026-08-16 09:22:12.4476933 | `8eeaae330e1c60a957f46d00f1e8aa71dae7b3ac3dc89a70d87406f6f5014e6d` |
| `row-g-apply-all-failure.npz` | 2,824 | 2026-08-16 09:22:13.0595248 | `4d49bd5364c342af484baa156f2c594011d7fb4672ca72d4a7ac9fcc7d6d478d` |
| `krita-before.log` | 33,193 | copied before Row G | `c0364ecad2c7f50f183f2f99e01102b3b67a11f91eb3b5581cfee2b13e74bb2b` |
| `krita-failure.log` | 34,245 | copied after failure | `b4824247101760bb71db34a4ab70c71ffd5c6805f1e5ab0196dc305aa86cf062` |
| `krita-sysinfo-before.log` / `krita-sysinfo-failure.log` | 8,334 each | unchanged | `3f7a0c625c87d4ef678a1fddb4fcbf780693bd1e3a89d2b95a287ae7de89b9c5` |

The JSON status is `STOPPED_ROW_G_FAILURE`. Its traceback is exactly
`row_g()` → `row-g-apply-all` → `_run_apply_case()` → `_assert_apply()` →
production `apply_gap_colors()` →
`RuntimeError("Krita's fill action did not produce the exact requested target pixels.")`.
The log delta contains only the two expected loads of the disposable 64×64
fixture and no relevant Krita error or traceback.

### Validated subcase state

The harness did not contain a separate Row-G single-gap apply; Row F already
qualified that primitive. Row G's actual subcases are therefore:

| Row-G subcase | Result | Exact evidence |
|---|---|---|
| standalone individual apply | **NOT RUN** | no such Row-G subcase exists |
| corrected decision | **PASS** | the red learned decision was explicitly corrected to `[211,47,29]`; the other decision stayed unchanged; exact output contains the correction at all nine intended pixels |
| Apply Selected | **PASS** | 18 expected and 18 actual changed indices; full target equals expected byte-for-byte; Line/Guide unchanged |
| Apply All after required fresh rescan | **FAIL** | production exact-target postcondition raised; failure NPZ preserves BEFORE, EXPECTED_AFTER, post-containment target, Line, and Guide |

Because `row_g()` publishes its detailed row record only after both subcases
return, the later Apply-All exception prevented the local Apply-Selected JSON
record from being attached to `rows.G`. The hash-identified harness plus the
completed `row-g-apply-selected.npz` are the preserved evidence for that
subcase; it must not be represented as an absent execution.

Apply Selected itself used two sequential native fill actions, not one. In
application-plan order it wrote the nine-pixel blue gap at indices
`1560–1562, 1624–1626, 1688–1690` to `[13,117,241,255]`, then wrote the
nine-pixel explicitly corrected red gap at indices
`2990–2992, 3054–3056, 3118–3120` to `[211,47,29,255]`. The exact expected and
observed full arrays are identical. This proves that a generic “second native
action always fails” explanation is false.

Rows H–L were assigned `UNTESTED` with reason “stopped after Row G failure.”
The capture says `rows_m_through_v: UNTESTED_NOT_STARTED`; no H–V test was
entered.

### Reconstructed failing Apply-All plan

The failing fixture is the generated disposable `multiple-colors.kra`,
SHA-256 `3df7b2087c535d2e4eaab4409f3becb3379886bca8fc82f452bee63148911d79`:
64×64 RGBA/U8, `sRGB-elle-V2-srgbtrc.icc`, origin-aligned Coloring, Line Art,
and Guides paint layers, with no semantic selection. The disposable and source
copies match that hash.

Detection orders gaps by first flat index. The harness requires every scanned
gap to have `learned` provenance, and Apply All selects every gap without an
explicit correction. Candidate and application indices are identical because
there is no selection restriction. Reconstructing the frozen detector output,
fixture geometry, full EXPECTED_AFTER array, and production grouping gives:

| Order / ID | Bounds; candidate/application indices | Provenance | Prediction / correction / final | Eligible |
|---|---|---|---|---|
| 1 / `gap-0` | `[39,13,52,26]`; every `y*64+x` for `y=13..25`, `x=39..51` (169 pixels) | `learned` | `[13,117,241]` / none / `[13,117,241]` | yes |
| 2 / `gap-1` | `[24,24,27,27]`; `1560–1562, 1624–1626, 1688–1690` (9 pixels) | `learned` | `[13,117,241]` / none / `[13,117,241]` | yes |
| 3 / `gap-2` | `[46,46,49,49]`; `2990–2992, 3054–3056, 3118–3120` (9 pixels) | `learned` | `[227,61,17]` / none / `[227,61,17]` | yes |

For avoidance of ambiguity, the complete 169-index `gap-0` set is the
inclusive flat ranges
`871–883, 935–947, 999–1011, 1063–1075, 1127–1139, 1191–1203, 1255–1267,
1319–1331, 1383–1395, 1447–1459, 1511–1523, 1575–1587, 1639–1651`.

`build_application_plan()` preserves first color insertion order and sorts the
indices within each color group. It therefore produced exactly two groups and
production invoked exactly two native fill actions:

| Native action / group | Ordered source RGB | Target-profile RGB | Exact indices | Pixels |
|---|---|---|---|---:|
| 1 | `[13,117,241]` | `[13,117,241]` | union of all `gap-0` ranges above plus `1560–1562, 1624–1626, 1688–1690`, sorted | 178 |
| 2 | `[227,61,17]` | `[227,61,17]` | `2990–2992, 3054–3056, 3118–3120` | 9 |

For the supported sRGB RGBA/U8 bridge, group 1's ordered
`[13,117,241,255]` is supplied to ManagedColor internal components as
`[241,117,13,255]/255`; group 2's ordered `[227,61,17,255]` is supplied as
`[17,61,227,255]/255`. The target-profile values above are independently
confirmed by the captured expected full image; this evidence does not reopen
the Row-F ManagedColor repair.

### BEFORE, EXPECTED_AFTER, and containment

The complete Coloring BEFORE raw bytes have SHA-256
`65bb88d6d6e39df02623588a1acb940cf2133d766416674f30e00c23106af383`
(shape-aware image SHA-256
`b62573d0c81373419cf6fc19ac3e85f9fb4a4907ae2725f4b65f9981ce348d9d`).
Every one of the 187 intended pixels is `[0,0,0,0]` in BEFORE. The complete
EXPECTED_AFTER raw bytes have SHA-256
`f28c2d02c639512ab21a4602fdd6789ae49d298743695cb726fca018cca51bf8`
(shape-aware
`f9ad86d8e72a8e544a6fc5dfcc72fd78b3a4990b94690fa0a15b311780dae5b5`).
Its complete expected-changed set is the exact union of the three gap sets
listed above: 187 pixels. Group 1's 178 pixels become
`[13,117,241,255]`; group 2's nine pixels become `[227,61,17,255]`; all other
Coloring pixels remain byte-identical.

Line Art and Guides were expected unchanged. Their before and post-failure raw
SHA-256 values respectively remain
`05045b3e38a18a35705b95e3620d8f57c2294fc74b5fc2ce98c34900b82c7842`
and `aedd228999843fa6a7930ce1476373e002e242ac38ae8cce2864546603e7e2e3`.
The tree contains no other fixture content layer, and no unrelated layer was
expected to change.

The failing transient target is **not available**. Production reads it,
detects inequality, enters its containment block, conditionally restores the
complete BEFORE array if the target differs, restores host state, and only then
returns control to the harness. The failure NPZ therefore contains the
post-containment target. It is byte-identical to BEFORE and must not be
interpreted as evidence that the native actions were no-ops. The capture cannot
distinguish whether the conditional pixel-recovery write was required; it does
prove that the containment/recovery check completed without its own exception
and that no failed Coloring mutation escaped. Line and Guide are byte-exact,
semantic no-selection and the active Coloring target were restored, and the
foreground returned to black. Classify **Row-G correctness FAIL; failure
containment PASS; conditional recovery-write branch UNOBSERVED**.

### First-divergence boundary and prepared diagnostic

The current capture has no state between native group actions. It therefore
does not identify the first divergent group, selection, foreground, or timing
boundary. No group-specific selection bytes or foreground readbacks were
captured. The action path is known only to have completed both
`trigger()` → `waitForDone()` iterations before the exact final comparison.
Apply Selected proves the same two-action structure succeeds for two separate
nine-pixel masks and two colors. Apply All adds the Guide-enclosed `gap-0` and
coalesces it with `gap-1` into one disconnected 178-pixel first-group mask.
That difference is demonstrated; its causal role is not.

The precise classification before running the diagnostic was therefore
**MULTI_ACTION_HOST_BEHAVIOR_UNRESOLVED**. Selection installation/readback,
foreground consumption, action dispatch, group-1 multi-component behavior,
and cross-action sequencing remain distinguishable live hypotheses.
Application planning and color conversion match the frozen inputs and exact
EXPECTED_AFTER, but the absent transient prevents ruling them out solely from
host bytes. A production repair is not yet unambiguous and no production code
was changed.

The prepared one-shot diagnostic is
`/tmp/gapfill_phase65_rowg_multigroup_diagnostic_827e66f.py`, SHA-256
`631c2a1037c7673cdf5bb20bff07dad5cb5fac56b5ceb137f4294680383a1ea1`.
It has **not** been executed and is not qualification evidence. It refuses to
overwrite
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowg-multigroup-diagnostic-827e66f-v1`,
which was confirmed absent at preparation time. It revalidates the preserved
failure, installed artifact tree, Row-F capture, frozen hashes, fixture, model,
and exact two-group plan; opens only a copied disposable fixture; and does not
call production `apply_gap_colors()`.

For each group it installs and reads back the exact selection, sets and reads
back both internal and ordered foreground components, and captures target,
Line, Guide, active node, and selection before trigger, immediately after
trigger, and after `document.waitForDone()`. It does not pump unrestricted Qt
events in the action sequence. It preserves the raw arrays in NPZ, restores
the complete original target and user state, closes without saving, and keeps
Rows H–V outside its execution path. Static `py_compile` and Ruff checks pass,
an AST check found zero `apply_gap_colors()` calls, and the guarded output was
absent. It was prepared for one manual Scripter invocation and had not been
invoked at that point. Its subsequent execution and restoration-harness defect
are recorded below.

The frozen fixture manifest, ONNX model, and sidecar remain respectively
`6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`,
`8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`,
and `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5`.

The authoritative matrix is now **A–F PASS; G FAIL; H–V UNTESTED**. Phase 6.5
remains **OPEN / FAILED** and Krita is not release-qualified. Row I was not
begun; its one-step Undo requirement remains an independent UNTESTED release
blocker. The failing Apply-All plan used two native fill actions, an important
future Row-I observation but not evidence that Row I itself failed. Rows H and
I must not begin until the Row-G failure is resolved and explicitly
requalified.

## Row-G multi-group diagnostic #1 — observation PASS, containment FAIL

The prepared diagnostic was executed once and must not be rerun. Its guarded
output is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowg-multigroup-diagnostic-827e66f-v1`.
The final `DIAGNOSTIC_FAILED` status records a cleanup-harness exception, not a
second Row-G execution or matrix-row failure. The action observations were
already complete and persisted before restoration began:

| Artifact | Bytes | Modification/change timestamp (+09:00) | SHA-256 |
|---|---:|---|---|
| `diagnostic-results.json` | 689,059 | 2026-08-16 09:39:11.2663074 | `ee7293d90d93b1f4f3551120af248bde1562e3ab9b51ce006af3860fae26b96a` |
| `diagnostic-arrays.npz` | 12,949 | 2026-08-16 09:39:11.2553014 | `190f1aa4baed638ecf209e422de7d09c9c9f124cd736896a4626b76b29df2daa` |
| copied `multiple-colors.kra` | 43,251 | 2026-08-16 09:39:09.0419323 | `3df7b2087c535d2e4eaab4409f3becb3379886bca8fc82f452bee63148911d79` |
| `krita-before.log` | 34,245 | copied before diagnostic | `b4824247101760bb71db34a4ab70c71ffd5c6805f1e5ab0196dc305aa86cf062` |
| `krita-failure.log` | 34,807 | copied after failure | `9a933c69bd7fe6f2d7f9b037c6c0c477dafa1812999bd74ddadec33fd0721e19` |
| both sysinfo copies | 8,334 each | unchanged | `3f7a0c625c87d4ef678a1fddb4fcbf780693bd1e3a89d2b95a287ae7de89b9c5` |

The harness was the hash-identified
`/tmp/gapfill_phase65_rowg_multigroup_diagnostic_827e66f.py`, SHA-256
`631c2a1037c7673cdf5bb20bff07dad5cb5fac56b5ceb137f4294680383a1ea1`.
Its baseline revalidated the earlier Row-G failure, Row-F capture, 892-file
artifact, installed tree, model, fixture, and all frozen hashes. The source and
copied fixture still independently hash to the value above. The log delta
contains only the expected disposable fixture load and no relevant Krita
error.

### Execution and persistence boundary

Both groups completed every intended action stage. For each group, selection
installation/readback, foreground installation/readback, before-trigger raw
capture, `action.trigger()`, immediate raw capture, `document.waitForDone()`,
and after-wait raw capture are **EXECUTED_AND_PERSISTED**. The trigger calls
are established by source order and the persisted immediate checkpoints that
follow them; the wait calls are established by the subsequent persisted
after-wait checkpoints. There is no executed-but-unpersisted or unexecuted
group stage.

After Group 2, the diagnostic also persisted the complete
`final_before_recovery_coloring` array, raw SHA-256
`009cfa849ca5001918acc93755d448e56dd0f90bd2e260485d21314bf0fbcec0`,
then set status `DIAGNOSTIC_CAPTURED` and rewrote both JSON and NPZ. This was
the last successfully persisted phase before `_restore()` was called. The
outer exception handler later changed the final JSON status to
`DIAGNOSTIC_FAILED` while retaining all checkpoints and arrays.

### Group 1 — first exact divergence

Group 1's installed selection is an exact 4,096-byte full-document mask at
SHA-256 `db46885e3e247d2c9b909c774d0b67a836a972503be60bd3e649343e29867484`.
It contains only values 0/255 and exactly 178 full-strength pixels. The
nonzero set equals the application plan byte-for-byte and has exactly two
four-connected components:

- 169 pixels at bounds `[39,13,52,26]`; and
- 9 pixels at bounds `[24,24,27,27]`.

The host selection metadata bounds are `(x=24, y=13, width=28, height=14)`.
Metadata breadth does not hide an expanded mask: the authoritative full mask
readback remains the exact sparse two-component selection before trigger,
immediately after trigger, and after wait.

The installed foreground is RGBA/U8 sRGB. Its exact `components()` are
`[0.9450980424880981, 0.4588235318660736, 0.05098039284348488, 1.0]` and its
exact `componentsOrdered()` are
`[0.05098039284348488, 0.4588235318660736, 0.9450980424880981, 1.0]`, or
ordered `[13,117,241,255]` after U8 quantization. The active node remained the
intended Coloring UUID `{50e9f493-3640-44e7-8037-542594f7f62b}`.

Before trigger and immediately after trigger the target was byte-identical to
BEFORE at raw SHA-256
`65bb88d6d6e39df02623588a1acb940cf2133d766416674f30e00c23106af383`:
zero observed changes and all 178 expected pixels still missing. After
`waitForDone()`, the target raw SHA-256 was
`a0b5ecb05aa2c610ab1d8189659bc285bfe012a4d723eaecf033f6f2ceaba6bd`.
It had 321 changed pixels:

- all 178 selected pixels were exactly `[13,117,241,255]`;
- no selected pixel was missing or the wrong color;
- 143 unselected transparent pixels had their RGB bytes changed to
  `[13,117,241]` while alpha remained 0; and
- there were no other values or changes.

The exact unexpected set is `x=32..38` and `x=52..55`, for every
`y=13..25`: 11 pixels per row × 13 rows = 143. Thus the large selected
component appears in the raw changed footprint as a 312-pixel rectangle at
bounds `[32,13,56,26]`, while the separate nine-pixel component remains exact
at `[24,24,27,27]`. Both disconnected selected components were filled
correctly. The native action additionally wrote foreground RGB under zero
alpha in horizontally padded, unselected pixels around the large component.
The full selection readback proves this is not selection-mask expansion.

Line Art and Guide arrays remained byte-exact at every stage, respectively
`05045b3e38a18a35705b95e3620d8f57c2294fc74b5fc2ce98c34900b82c7842`
and `aedd228999843fa6a7930ce1476373e002e242ac38ae8cce2864546603e7e2e3`.

### Group 2 — exact sequential action

Group 2 began with the complete Group-1 result unchanged. Its installed
selection is an exact nine-pixel, one-component mask at indices
`2990–2992, 3054–3056, 3118–3120`, bounds `[46,46,49,49]`, raw SHA-256
`cfd6e7fd5e33b02160e4ccc846cc962ed4fedb03580cc79e8bf0033206ada068`.
It contains only 0/255, exactly nine full-strength pixels, and host metadata
`(x=46, y=46, width=3, height=3)`.

The Group-2 foreground's exact `components()` are
`[0.06666667014360428, 0.239215686917305, 0.8901960849761963, 1.0]` and its
exact `componentsOrdered()` are
`[0.8901960849761963, 0.239215686917305, 0.06666667014360428, 1.0]`, or
ordered `[227,61,17,255]`. The active target remained correct. Before trigger
and immediately after trigger, the target retained Group 1's raw SHA-256
`a0b5ecb05aa2c610ab1d8189659bc285bfe012a4d723eaecf033f6f2ceaba6bd`.
After wait, exactly the nine Group-2 pixels were added as
`[227,61,17,255]`; no new unexpected pixel was added, and the entire Group-1
footprint—including its 143 RGB-under-zero-alpha writes—remained byte-exact.
The final target therefore has 330 changes from BEFORE: all 187 intended
pixels correct, zero missing, and the same 143 unexpected transparent RGB
writes. Line and Guide remained unchanged.

Immediate reads were unchanged for both actions and each mutation was visible
after `waitForDone()`. This confirms the previously qualified
`trigger()` → `waitForDone()` synchronization boundary here. Group 2's exact
selection, foreground, target, and preservation of Group 1 rule out a stale
second selection, stale first foreground, later overwrite, and generic
multi-action sequencing failure.

### Production comparison and superseding classification

The diagnostic used the same frozen scan, prediction, group ordering,
preconverted ManagedColor objects, target activation, exact Selection
construction/replacement, `action.trigger()`, and `waitForDone()` primitives as
production. It added read-only selection/foreground/array checkpoints and an
immediate read before each wait, but no Qt event pump. Its final raw mismatch
is precisely sufficient to explain production Apply-All's exact postcondition
failure: production requires the complete target to equal EXPECTED_AFTER, and
the 143 unselected RGB changes violate that invariant even though they remain
visually transparent.

The first demonstrated divergence is Group 1 and the superseding
classification is **NATIVE_FILL_UNSELECTED_TRANSPARENT_RGB_WRITE**. More
specifically, the real Krita foreground-selection fill action writes
foreground RGB under alpha 0 into an observed horizontally padded footprint
outside the exact host selection. This rejects the disconnected-selection and
sequential-state hypotheses. The application plan, selection bytes,
ManagedColor ordering, active target, waiting, and Group-2 behavior are exact.
No production repair is made here.

### Separate restoration-harness failure and containment

After all evidence was persisted, `_restore()` failed on its first statement:

```text
KeyError: '_rgba_to_bgra_bytes'
```

The diagnostic dynamically executed definitions from the preserved G–L
harness into `helpers`, then assumed that namespace contained
`_rgba_to_bgra_bytes`. It did not: that private function exists in production
`krita_adapter.py`, while the G–L harness imported only
`apply_gap_colors`, `canvas_color_bridge`, `iter_nodes`, `read_node_rgba`, and
`snapshot_host`. No extraction filtering or namespace mismatch occurred; this
was a diagnostic-only **HELPER_IMPORT_OMISSION / INVALID_HELPER_LOOKUP**.
Because the lookup was the first restoration statement, pixel and editor-state
restoration did not begin. Production is not implicated.

Diagnostic observation is **PASS**; diagnostic containment is **FAIL**. At the
failed cleanup boundary, the disposable view still held the Group-2 foreground,
no eraser, no global alpha lock, normal blend, opacity 1, flow 1, the Group-2
selection, active Coloring, and the final transient target. However, a nested
`finally` still called `setModified(False)` and `document.close()`. The
disposable document was therefore closed without saving; neither its changed
pixels nor its diagnostic selection remain in an open document, and both the
source and copied `.kra` files remain byte-exact at
`3df7b2087c535d2e4eaab4409f3becb3379886bca8fc82f452bee63148911d79`.
The original user document was never targeted.

Foreground/view-state restoration did not run before the disposable view was
closed. The capture cannot establish whether Krita propagated those
view-specific values to the surviving user view. The same Krita process
(PID 43608) remained running when checked read-only. No document cleanup is
normally required because code order proves the disposable closed. If a
`multiple-colors.kra` diagnostic document is nevertheless visibly open, close
it **without saving**. Otherwise, only restore foreground/tool settings
manually if the GUI visibly differs from the desired user state; do not touch
document pixels.

No diagnostic v2 or further host run is necessary to establish this root
cause: all action and final transient evidence is complete. A later
mutation-strategy experiment is a separate diagnostic, not a rerun of this
root-cause capture. This event does not change the matrix. The
authoritative state remains **A–F PASS; G FAIL; H–V UNTESTED**. Phase 6.5
remains **OPEN / FAILED**, Krita is not release-qualified, and Row I's
one-step-Undo requirement remains an independent UNTESTED release blocker.

## Row G mutation-strategy source audit and prepared COPY diagnostic

This subsection records source/design evidence only. No additional host
diagnostic was executed, no production repair was made, and no matrix row was
reclassified. Installed `krita-sysinfo.log` identifies the qualified binary as
Krita 5.3.3, Git revision `858d352`, Qt 5.15.7, Windows x86-64. The installed
`krita.pyi` exposes `View.setCurrentBlendingMode()` and
`View.currentBlendingMode()`; its SHA-256 is
`9246ab2133d16f4662f4fd094b88be35715a8809d4deb3b170069c1f5ba7850c`.
The source audit used exact upstream commit
`858d352e52e68831693067763b9cdaf8bb9a05ce`.

The native action path is:

```text
fill_selection_foreground_color
  -> KisFillActionFactory::run("fg", ...)
  -> FillProcessingVisitor(selectionOnly = true)
  -> selectionFill()
  -> KisPainter(target, selection).bitBlt(...)
```

`KisFillActionFactory` snapshots the current canvas resources. The snapshot
reads `CurrentEffectiveCompositeOp`, and `setupPainter()` assigns that value to
the painter. Production currently forces public view mode `normal`, so the
demonstrated fill used the native Normal/Over operation rather than a
fill-specific fixed operation. `selectionFill()` fills a temporary composition
source across `selection->selectedRect()` and passes the real selection
projection as the `bitBlt` mask.

The exact RGBA/U8 Normal fast path explains the observed collateral footprint.
It multiplies source alpha by each mask byte. When an SIMD batch has an
all-transparent destination, however, it sets `src_blend` to one for the whole
batch. It then copies source RGB for every lane while writing the mask-derived
alpha. A zero-mask lane can therefore receive foreground RGB and retain alpha
zero. The observed x-aligned padding around the selected rectangle is
consistent with this vector path. This source explanation does not replace the
authoritative real-host byte capture.

COPY is a supported public candidate, not merely a discovered string literal.
The exact installed revision's RGBA/U8 color space registers standard
`KoBgrU8Traits` operations; that specialization constructs and registers
`KoOptimizedCompositeOpCopy32` under the `copy` identifier. Public LibKis
routes `setCurrentBlendingMode()` into the view resource provider used by the
fill snapshot. In COPY's vector implementation, mask zero is tracked per lane
and `PixelStateRecoverHelper::recoverPixels()` restores the original color
channels; alpha also remains the original value. With production's generated
application masks—fresh full-document arrays initialized to 0 with exactly the
application-plan indices set to 255—this is semantically compatible with the
frozen apply contract: mask 255 receives the exact foreground RGBA with alpha
255, and mask 0 remains byte-exact. Actual `copy` setter/readback and mutation
behavior still require the prepared real-host diagnostic; source evidence is
not recorded as a host PASS.

One focused, not-yet-executed diagnostic was prepared at
`/tmp/gapfill_phase65_rowg_copy_diagnostic_827e66f.py`, SHA-256
`ed0e1d42552061bcec65ee39432a87994085f41c38f9d2d93a790ad7aeb33b00`.
Its guarded output directory is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowg-copy-diagnostic-827e66f-v1`.
It refuses overwrite and uses three separate byte-exact disposable copies of
`multiple-colors.kra`:

- Case A requests and reads back `normal`, applies Group 1 only, and requires
  the known 178 correct opaque pixels plus the exact 143-pixel
  RGB-under-alpha-zero footprint.
- Case B requests and reads back `copy`, applies Group 1 only, and requires
  exactly 178 changes, zero missing/unexpected pixels, and exact
  `[13,117,241,255]` output.
- Case C requests and reads back `copy`, applies Group 1 then Group 2, and
  requires exactly 187 changes, zero missing/unexpected pixels, and exact
  per-group colors.

Every case records requested/read-back composite mode, full selection bytes,
foreground `componentsOrdered()`, active target, target before/after
`waitForDone()`, exact changed/missing/unexpected/wrong-RGBA records, and Line
and Guide hashes. It does not call production `apply_gap_colors()`, contains no
Qt event pump, and does not execute Rows H–V. Each transient document is
restored and verified before it is closed without saving. Recovery uses a
self-contained local RGBA-to-BGRA converter rather than the invalid prior
helper lookup. Python syntax compilation, AST scope checks, and a packed-byte
conversion/round-trip vector all passed. The diagnostic has **not** been run,
so neither `NATIVE_COPY_CANDIDATE_PASS` nor
`NATIVE_COPY_CANDIDATE_FAIL` is assigned yet. It is prepared for one manual
Scripter invocation.

The separate Undo audit found the native one-action boundary explicitly.
Every `KisFillActionFactory::run()` allocates a new
`KisStrokeStrategyUndoCommandBased("Flood Fill Layer", ...)`, calls
`image->startStroke()`, adds the processing/update jobs, and calls
`image->endStroke()`. That strategy creates and publishes one undo macro for
that stroke. A multi-color GapFill currently invokes the native action once per
color group, so N color groups have an apparent N-stroke/N-history-entry
architecture. A complete search of the installed public Python stub and the
exact public LibKis `Document`/`View` headers found no supported begin/end undo
macro, image undo-stack accessor, or equivalent transaction API:
**NO_PUBLIC_UNDO_GROUPING_API_FOUND**. This is architecture evidence only;
Row I remains **UNTESTED** and a release blocker.

The authoritative state remains **A–F PASS; G FAIL; H–V UNTESTED**. Phase 6.5
remains **OPEN / FAILED**. Exact-byte verification is unchanged, direct
`Node.setPixelData()` remains only an unqualified fallback, and no production
source changed in this audit/preparation step.

## Row G COPY candidate real-host result and architecture boundary

The focused diagnostic above was executed once in the qualified Windows 11
Pro x64 / Krita 5.3.3 host and stopped as designed on the first COPY
exact-byte failure. This subsection supersedes the preceding pre-execution
status and its source-only expectation that integer RGBA/U8 COPY would recover
mask-zero color channels. It does not reclassify any matrix row.

The guarded capture is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowg-copy-diagnostic-827e66f-v1`.
Its principal evidence is:

- `diagnostic-results.json`: 219,929 bytes, modified
  2026-08-16 10:16:42.3020555 +09:00, SHA-256
  `1c27c08f75e7fe9817e1277592a867f4d097ed2cab0509f5dc918a62edb43f9c`;
- `diagnostic-arrays.npz`: 9,040 bytes, modified
  2026-08-16 10:16:42.2980554 +09:00, SHA-256
  `1d628f79254a35f898b97e1394ba06e1096c662ab2969b502324c086e526a370`;
- `krita-before.log` / `krita-failure.log`: 34,807 / 35,923 bytes,
  SHA-256 `9a933c69bd7fe6f2d7f9b037c6c0c477dafa1812999bd74ddadec33fd0721e19`
  / `8bd227f0f45751073e8767f562131a6cbf74ab5c801908da53bdec2fc40e4429`;
- `krita-sysinfo-before.log` and `krita-sysinfo-failure.log`: each 8,334
  bytes and byte-identical, SHA-256
  `3f7a0c625c87d4ef678a1fddb4fcbf780693bd1e3a89d2b95a287ae7de89b9c5`;
  and
- the three disposable `.kra` copies: each 43,251 bytes and each still
  SHA-256
  `3df7b2087c535d2e4eaab4409f3becb3379886bca8fc82f452bee63148911d79`.

The JSON status is `DIAGNOSTIC_FAILED` with
`NATIVE_COPY_CANDIDATE_FAIL`; the preserved traceback is
`AssertionError: B_COPY_GROUP1 Group 1 failed exact intended-byte semantics.`
Case A completed as `KNOWN_NORMAL_BASELINE_REPRODUCED`. Case B reached
`action.trigger()` → `waitForDone()` and preserved the after-target, Line,
Guide, and selection arrays before the exact comparison raised; it is
therefore **FAIL**, although its in-progress case record remains `RUNNING`
because the group record was appended only after that comparison. Restoration
then completed. Persisted JSON contains no Case C record, the NPZ contains no
Case C arrays, and the host log contains no Case C open/load event. The Case C
file was only copied during preparation: **Case C was NOT RUN** and is not
needed after the first-group failure.

The NORMAL control is comparable and exact. Its 64×64 binary selection has
raw SHA-256
`db46885e3e247d2c9b909c774d0b67a836a972503be60bd3e649343e29867484`,
178 full-strength pixels, and two four-connected components: the 13×13
component at x=39–51, y=13–25 (169 pixels) and the 3×3 component at
x=24–26, y=24–26 (9 pixels). NORMAL was requested and read back both before
the trigger and after the wait. It changed 321 pixels: all 178 intended pixels
became `[13,117,241,255]`, with zero missing or wrong intended pixels, and the
known additional 143 pixels became `[13,117,241,0]`. That collateral footprint
is exactly x=32–38 and x=52–55 for every y=13–25. Only the intended 178 alpha
bytes changed; the additional 143 changes were RGB under alpha zero. Its final
raw target SHA-256 is
`a0b5ecb05aa2c610ab1d8189659bc285bfe012a4d723eaecf033f6f2ceaba6bd`.

Case B used the identical before image and selection. The setter input was
`copy`; the persisted immediate readback before the group was `copy`. The
before-trigger readback was held in a local group record that was not appended
after the assertion, but the script checked it for exact equality with `copy`
*before* triggering the action. The preserved after-wait arrays prove that
this guard passed. No separate normalized runtime identifier was captured.
Exact source revision `858d352e52e68831693067763b9cdaf8bb9a05ce` and the
mode-specific output close that evidence gap, so the result is
**COPY_MODE_CONFIRMED_ACTIVE**, not merely a successful setter call.

The Case B raw hashes are:

- `BEFORE_B`:
  `65bb88d6d6e39df02623588a1acb940cf2133d766416674f30e00c23106af383`;
- intended exact `EXPECTED_B`:
  `e385eedf81a568fe88fc9af1987b0ae87246bf52753efb17f3f760dac23f2390`;
  and
- `OBSERVED_B_AFTER_WAIT`:
  `3389c75470814a8fe404f311dd6295dc91e12f3b841c88c89310e49219ab6459`.

COPY also changed 321 pixels. All 178 selected pixels were exactly
`[13,117,241,255]`: intended-correct=178, missing=0, wrong-intended=0, and
unchanged-intended=0. The remaining 143 selection-zero pixels changed from
`[0,0,0,0]` to `[255,255,255,0]`, with the exact same x=32–38 and x=52–55,
y=13–25 footprint. Alpha changed only at the 178 intended pixels; all 143
unexpected changes were RGB-under-zero-alpha changes. Relative to before,
each RGB channel changed at 321 pixels and alpha at 178. Thus the pattern has
the same selected result and collateral footprint as NORMAL, but a distinct
collateral RGB value. It is specifically a selection-zero hidden-RGB
replacement, not a selected-pixel error or an unselected-alpha change.

The NORMAL and COPY after-images are not byte-identical. They differ at
exactly those 143 collateral pixels and only in R, G, and B: NORMAL has
`[13,117,241,0]`, while COPY has `[255,255,255,0]`; their alpha bytes are
identical. The first divergence from the desired COPY contract is therefore
the first selection-zero lane in that footprint, coordinate (32,13), where
the expected `[0,0,0,0]` became `[255,255,255,0]`.

The exact source establishes the complete resource path. LibKis
`View::setCurrentBlendingMode("copy")` writes `CurrentCompositeOp` through
`KisCanvasResourceProvider`. `KisCompositeOpResourceConverter` writes that
value into the current paint-op preset, while
`KisEffectiveCompositeOpResourceConverter` derives
`CurrentEffectiveCompositeOp` from the same preset. Because the diagnostic
sets eraser mode false, `effectivePaintOpCompositeOp()` returns the requested
paint composite rather than `erase`. `KisFillActionFactory` then constructs a
`KisResourcesSnapshot`, which reads `CurrentEffectiveCompositeOp`; its
non-opacity fill branch changes only snapshot opacity to 1.0. `setupPainter()`
installs the snapshotted composite ID. `FillProcessingVisitor::selectionFill()`
does not enable its custom-blending override, and calls
`KisPainter(target, selection).bitBlt(...)`. The fill action therefore does
consume the requested `copy` operation; it does not normalize or override it
to NORMAL.

With a selection present, COPY cannot take `KisPainter`'s no-selection fast
copy. `KisPainter` reads the selection projection and supplies it as the mask
to `KoOptimizedCompositeOpCopy32`. All-mask-zero vector batches are no-ops and
mask-255 selected lanes copy correctly. In a mixed vector batch over a
transparent destination, however, a mask-zero lane has `newAlpha == 0`; the
vector path divides premultiplied color by that zero alpha, substitutes the
channel unit value for the resulting NaN, and writes alpha zero. The code then
calls `PixelStateRecoverHelper`, but its generic integer-channel
implementation is a no-op; only the `float` specialization restores original
colors. For RGBA/U8 this yields `[255,255,255,0]` in the mixed mask-zero lanes.
That source behavior exactly matches the preserved host bytes and corrects
the earlier source-only mask-zero recovery claim.

Containment passed. Case A recorded exact layer, selection, active-node,
foreground, and view restoration, was closed without saving, and retained its
fixture hash. Case B recorded the same exact restoration before the assertion
propagated. Its `closed_without_saving` field was not reached, but the nested
`finally` unconditionally calls `setModified(False)` and `document.close()`;
the on-disk fixture is still byte-exact and no Case B document remained open.
The restored view state was NORMAL, eraser off, global alpha lock off, opacity
1.0, and flow 1.0. The before/failure host-log delta contains only the Case A
and B open/load records and no host error. No manual cleanup is required.

The production Row G defect remains
**NATIVE_FILL_UNSELECTED_TRANSPARENT_RGB_WRITE**. The COPY candidate is more
narrowly **NATIVE_COPY_CANDIDATE_FAIL_COLLATERAL_RGB**: COPY is active and all
selected bytes are correct, but 143 unselected transparent pixels receive
white hidden RGB. No additional composite-mode search or Case C run is
justified.

The remaining mutation choices and their Row I implications are:

- Native fill followed by collateral restoration can reconstruct exact bytes
  only by an additional raw write such as `Node.setPixelData()`. That write
  cannot be included atomically in the action's private native stroke through
  public LibKis, and the per-color native actions already create separate
  strokes. This is incompatible with one GapFill Apply → one Undo in the
  current Python architecture.
- A full exact read/modify/`Node.setPixelData()` write is straightforward for
  Row G, but exact LibKis source calls the paint device's `writeBytes()`
  directly without creating an undo command. With no public undo-grouping API,
  this is likewise incompatible with Row I in the current architecture.
- Relaxing equality for RGB under alpha zero would be a frozen-specification
  change, is not authorized, and would not resolve the independent multi-stroke
  Undo issue.
- A compiled Krita-side helper could, in principle, perform one exact
  multi-color mutation inside one explicit native undo transaction. It is the
  only remaining direction compatible in principle with both Row G and Row I,
  but introduces ABI/Krita-version/platform packaging coupling and requires
  its own real-host qualification.
- The exact public LibKis/API audit found no other concrete mutation primitive
  that supplies both exact bytes and a groupable user-visible undo command.

Accordingly, the next boundary is an explicit architecture decision, not a
production patch or another blend-mode experiment. If exact byte semantics and
one-step Undo remain mandatory, the best-supported direction is a narrowly
scoped native mutation/undo helper while retaining the Python acquisition,
prediction, planning, and UI layers. No further public-action experiment is
source-justified, so none was prepared. Row I remains **UNTESTED**; this source
assessment is not a Row I execution or failure classification.

The authoritative matrix remains **A–F PASS; G FAIL; H–V UNTESTED**. Phase 6.5
remains **OPEN / FAILED**, Krita remains not release-qualified, and Rows H and
I were not begun. The frozen fixture manifest, ONNX model, and sidecar hashes
remain respectively
`6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`,
`8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`,
and `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5`.
No production source was changed, and future OFFF work remains out of scope.

## Version-pinned native transactional-helper feasibility gate

This bounded study was performed at repository commit
`827e66ffe00fca3ed4387e4f896a41e479c5322e` on
`qualify/csp-host-adapter`. Before this note, the only worktree changes were
the existing Phase 6.5 evidence changes in this file and
`krita-plugin/host_tests/matrix.json`; there were no staged changes. No
installed plugin file, production source, fixture, model, or matrix status was
changed by the study.

The installed Row-F-qualified artifact remains
`/tmp/gapfill-krita-phase6.5-rowF-managedcolor-win-x64-py313-454d345-worktree.zip`,
47,842,605 bytes, 1,007 ZIP entries / 892 file payloads, SHA-256
`bf19c8dc2fb3e44f160614f61fa189d52dac62bc24790b0094170ccd93fbe146`.
A fresh read-only comparison found all 892 payloads present and byte-exact in
the user resource tree, with no non-cache extra; the 116 extra files were all
recognized `__pycache__`/bytecode products. The plugin remains under
`C:\Users\marck\AppData\Roaming\krita\pykrita\gapfill_krita`. The last
authoritative host record remains Windows 11 build 26200 AMD64, Krita 5.3.3
(`git 858d352`), Qt 5.15.7, embedded CPython 3.13.5 AMD64, and PyQt5 5.15.11.
The current WSL-to-Windows process query failed at the pre-existing vsock
boundary, so this study does not make a new process-liveness claim.

The frozen fixture manifest, ONNX model, and sidecar hashes were rechecked and
remain respectively
`6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`,
`8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`,
and `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5`.

### Decision

The exact classification is:

> **NATIVE_TRANSACTION_HELPER_FEASIBLE_BUT_VERSION_PINNED**

The one preferred integration is a **CPython 3.13 native extension (`.pyd`)
inside `gapfill_krita/`**, built against the exact Krita 5.3.3 / git `858d352`
Windows x64 ABI. It accepts only simple Python integers, strings, and byte
buffers, resolves Krita objects itself, and exposes one synchronous exact-patch
call. It does not accept PyKrita/SIP wrapper pointers. Detection, prediction,
decisions, selection eligibility, stale provenance, and color conversion stay
in Python.

This is an architecture result, not a load or mutation result. No helper was
implemented, built, installed, or loaded, and no native mutation was run. The
missing local build surface is an explicit prerequisite for a future prototype,
not evidence that the transaction design is unavailable.

### Exact internal transaction and undo pattern

The study used the exact public source revision
`858d352e52e68831693067763b9cdaf8bb9a05ce`. The audited source archive was
kept outside the repository as `/tmp/krita-858d352-source.tar.gz`, SHA-256
`0039425577a8b27506bc332134714d4ed7a021e985ee0111029dea19ac6883a6`.
The required installed DLL symbols are exported, including
`KisTransactionData`, `KisTransactionBasedCommand`,
`KisProcessingApplicator`, `KisStrokeStrategyUndoCommandBased`,
`KisPaintDevice::readBytes()` / `writeBytes()` / `sequenceNumber()`,
`KisLayerUtils::findNodeByUuid()`, and image start/end/cancel/wait methods.

The source establishes this supported mechanism:

1. `KisTransaction` obtains a tile memento from the target
   `KisPaintDevice`.
2. A `KisTransactionBasedCommand::paint()` implementation performs the work
   once and returns `transaction.endAndTake()` as its `KUndo2Command`.
3. One undo-command-based stroke executes that one command with
   `BARRIER` / `EXCLUSIVE` scheduling and publishes one
   `KisSavedMacroCommand` with the label `GapFill Apply`.
4. `KisTransactionData` suppresses the first redo because the original write
   already happened. Undo rolls the saved tile memento back; Redo rolls it
   forward without rerunning GapFill or color conversion.
5. The initial successful write explicitly calls
   `targetNode->setDirty(affectedRunRects)`; transaction Undo/Redo derives its
   dirty extent from the memento and invalidates it through
   `KisTransactionData::startUpdates()`.

Krita's Smart Patch tool is the direct production precedent: its
`InpaintCommand` derives from `KisTransactionBasedCommand`, opens one
`KisTransaction`, returns `endAndTake()`, submits the command through one
`KisProcessingApplicator` as `BARRIER` / `EXCLUSIVE`, ends the applicator, and
waits for the image.

For GapFill's fail-closed requirement, the future helper should add a minimal
failure-aware subclass of `KisStrokeStrategyUndoCommandBased` around that
single `ExactPatchCommand`. The command reports a shared result. The strategy
adds the command to its undo macro only after successful exact readback. On a
rejection or mutation error it follows the strategy cancellation path, which
deletes the unpublished macro and schedules inverse jobs for anything already
saved. This avoids publishing a semantic-failure/no-op history entry. The
normal success path still contains exactly one transaction command in exactly
one user-visible stroke.

The command must call `KisTransaction::revert()` on any failure after the
transaction begins. `KisTransaction::end()` is explicitly unsuitable for
rollback: it discards the memento without reverting already changed pixels.
The future prototype must failure-inject and prove the custom strategy's
success/cancel paths; source inspection alone does not qualify that new code.

### Exact raw write and Python/native contract

The recommended write is
`KisPaintDevice::writeBytes(data, QRect(x, y, length, 1))`, once per validated
horizontal run, inside the single transaction. `readBytes()` checks the same
runs before and after the writes. This path has no painter, compositing,
selection mask, blend mode, SIMD composite operation, or fill algorithm and
therefore does not expose the Row-G hidden-RGB behavior. Paint-device
iterators are possible but add cursor/stride state without improving the
contract; `KisPainter` is rejected.

Python should send **exact native/raw four-byte pixels**, not ordered RGBA for
native conversion. `CanvasColorBridge` remains authoritative for converting
the frozen prediction into target-profile ordered RGB. Python then performs
the already established RGBA-to-raw BGRA/U8 layout conversion and submits one
plan containing all final colors. Native code treats replacement pixels only
as opaque bytes and does no color management.

The proposed serializable call payload is:

- an opaque document/target binding token;
- expected document origin and width/height;
- target node UUID;
- expected `RGBA` / `U8`, pixel size four, and profile unique ID;
- expected paint-device sequence number; and
- a sorted, non-overlapping tuple of `(x, y, length, expected_before_bytes,
  replacement_bytes)` horizontal runs, with both byte buffers exactly
  `4 * length` bytes.

The extension copies and validates all Python buffers before scheduling work.
It does not retain NumPy memory or wrapper pointers. Combining blue and red
runs in this one payload is what makes the whole Row-G plan one transaction,
instead of one fill action per color.

### Native target resolution and final stale boundary

Python's existing full provenance/stale validation remains primary. Native
code adds only the final race boundary:

- The extension issues an unguessable opaque token bound in module state to a
  `QPointer<KisDocument>`, its `KisImageWSP`, target UUID, paint-device
  identity, and initial sequence number. Tokens are explicit per document and
  target, expire when the document closes, and avoid an ambiguous “current
  document” singleton protocol.
- On apply, the native job must run on Krita's GUI-owned call path, resolve the
  same document/image from the token, find the node freshly from the image
  root with `KisLayerUtils::findNodeByUuid()`, and require the same paint
  device. It must not select or mutate whichever layer is currently active.
- Immediately inside the exclusive job it rechecks open document/image,
  document bounds/origin, node UUID/type/ownership, editable/unlocked state,
  alpha lock, animation exclusion, device position, color model/depth,
  four-byte pixel size, profile `uniqueId()`, and device sequence number.
- It rejects empty, unsorted, overlapping, duplicate, out-of-bounds,
  overflowing, oversized, or length-mismatched runs. It then reads and
  compares every run with `expected_before_bytes` before starting writes.
- After all writes it reads every run back and requires exact replacement
  bytes before finalizing the transaction. A different device sequence,
  target replacement, profile change, or byte mismatch is stale/rejected,
  not a reason to retarget the active layer.

The token is host identity only; it does not move detection, decision, or
color semantics into native code. A future implementation may bind it during
snapshot acquisition, but must not weaken the existing Python hashes or
context checks.

### Integration-form ranking

| Candidate | Ranking | Feasibility and transport |
|---|---|---|
| A — CPython 3.13 `.pyd` in `gapfill_krita/` | **preferred** | Direct Python values/bytes and structured result; internally resolves `KisPart`/document/node state. The shipped `PyKrita/krita.pyd` already imports `python313.dll`, Qt5, libc++, `libkritaimage.dll`, `libkritalibkis.dll`, and `libkritaui.dll`, proving this kind of in-process bridge for this build. It is still pinned to CPython 3.13 and the exact Krita C++ ABI. |
| B — plain DLL loaded through a narrow C ABI | **viable fallback** | A packed byte request and caller-owned result buffer could cross `ctypes.PyDLL`; the DLL could resolve Krita internals itself, so no wrapper pointer is needed. It does not remove the Krita C++ ABI/toolchain requirement and adds manual buffer ownership, exception translation, GUI-thread enforcement, and DLL-load handling. |
| C — normal native Krita C++ plugin | **impractical for the current package** | Mechanically capable, but normal modules install under `lib/kritaplugins` (with metadata embedded by `K_PLUGIN_FACTORY_WITH_JSON` and optional files under `share/kritaplugins`). The Python Plugin Importer copies only a desktop file, optional action, and Python package into the user resource tree; it does not install native modules into Krita's program directories. A separate native installer/admin/manual step plus a QObject/QByteArray service bridge would be required. |

Candidate B's only acceptable transport would be a versioned C function over
packed caller-owned bytes, with all C++ exceptions caught before the C ABI.
Candidate C's least ambiguous transport would be a per-document native
`QObject` service receiving a `QByteArray`, not action properties or global
mutable state. Neither offers an advantage over Candidate A for the existing
single-ZIP installation model.

### Installed Windows ABI and build surface

The installed `krita.exe`, `krita.dll`, `libkritaimage.dll`, Qt5 DLLs, and
`python313.dll` are PE32+ x86-64. Qt reports
`x86_64-little_endian-llp64` and exact compiled/loaded Qt 5.15.7.
`libkritaimage.dll` exports Itanium-mangled C++ symbols and imports
`libc++.dll`, `libunwind.dll`, `libwinpthread-1.dll`, UCRT API sets, Qt5, and
Krita libraries; it does not use the MSVC C++ ABI. Its CodeView record says
`LLD PDB.`. Runtime strings contain the llvm-mingw build path. The bundled
LLVM runtime DLLs have 2025-11-18 timestamps, matching the official
[`llvm-mingw-20251118-ucrt`](https://docs.krita.org/en/untranslatable_pages/building_krita.html)
toolchain; the
[`20251118` toolchain release](https://github.com/mstorsjo/llvm-mingw/releases/tag/20251118)
is LLVM/Clang 21.1.6. This identifies LLVM-MinGW/UCRT + libc++/libunwind,
not MSVC or clang-cl. The Python runtime is CPython 3.13.5 AMD64 /
`python313.dll` and itself imports `VCRUNTIME140.dll`; that does not change
the Krita C++ ABI.

The distribution is release-style and has `.gnu_debuglink` / LLD CodeView
records, but the referenced `.debug` sidecars are not installed. Exact core
libraries relevant to the helper include `libkritaversion.dll`,
`libkritacommand.dll`, `libkritapigment.dll`, `libkritaimage.dll`,
`libkritaui.dll`, and `libkritalibkis.dll`.

The installed Krita tree contains **zero** C/C++ headers, import/static
libraries (`.lib`, `.a`, or `.dll.a`), CMake package files, or pkg-config
files. The current Windows/WSL environment has only Linux ELF GCC/G++/Make;
it has no LLVM-MinGW cross compiler, Windows clang/clang-cl, CMake, Ninja, or
matching Krita dependency developer prefix. No current SDK/dev package was
found.

The exact Krita source tree is necessary but not sufficient by itself: the
build also needs generated configuration/export headers, Qt/KF and other
dependency headers/import libraries, and an import-library/developer surface
for the installed Krita DLLs. Because the required symbols are already
exported, a helper does not inherently require modified Krita libraries; with
an exact developer prefix it could be built out of tree. In the current
environment, however, the safe reproducible route is to recreate the official
LLVM-MinGW 20251118 / dependency environment and perform a full exact-commit
configure/build/install, then build the extension in that tree. Building only
the transitive `kritaversion`/command/pigment/image/ui/libkis targets is
theoretically possible but the dependency closure is not packaged here and is
not the recommended qualification route. Compatibility with the official
binary must still be checked by static imports and a no-op real-host load.

### Packaging and version policy

Candidate A preserves one Python Plugin Importer ZIP. It adds a file such as
`gapfill_krita/_native_exact_patch.cp313-win_amd64.pyd` plus a small build/ABI
manifest and license/provenance material. Krita's importer copies arbitrary
files under the detected Python module directory, so the `.pyd` is installed
with the package. The helper must link only to DLLs already shipped by this
Krita build; it must not bundle a second Qt, Krita, libc++, or Python runtime.
Krita must be fully restarted after install. Windows locks the loaded `.pyd`,
so overwrite/uninstall is deterministic only while Krita is exited; a clean
reinstall must remove the old package directory before copying the replacement.

Initial support is exactly **official Krita 5.3.3, git `858d352`, Windows x64,
Qt 5.15.7, embedded CPython 3.13.5**. At import and again before mutation, the
helper must reject unless `KritaVersionWrapper::versionString(true)` is exactly
`5.3.3 (git 858d352)`, Qt is 5.15.7, the process is Windows x64/LLP64, the
extension is running under the expected CPython 3.13 cell, and fingerprints of
the core Krita DLLs match the qualified package manifest. A different Krita
version or rebuild receives a separate binary and qualification; there is no
claim of a stable Krita C++ ABI.

### Failure containment and result protocol

The future native implementation sequence is:

1. parse, bound, copy, and preallocate the complete request;
2. resolve and validate the explicit target and every expected-before run;
3. begin one `KisTransaction` only after validation;
4. write all runs, exact-readback all runs, and dirty only affected rects;
5. on success, `endAndTake()` and publish the single stroke macro;
6. on any failure after transaction start, call `revert()`, verify the original
   run bytes, cancel/delete the unpublished macro, and return failure.

No C++ exception may cross the CPython or C ABI. The synchronous return is a
closed enum plus detail, with at least `SUCCESS`, `STALE_REJECTED`,
`UNSUPPORTED_HOST`, `MUTATION_FAILURE`, and `INTERNAL_EXCEPTION`. Python then
performs its existing exact full-target readback. Buffer arithmetic uses
checked sizes and explicit pixel/run caps. The extension rejects calls off the
Krita GUI thread. A crash is not a supported outcome and a future prototype
must cover allocation/write/readback failure injection before production use.

### Complexity and future real-host proof

For `K` changed pixels in `R` horizontal runs, parsing, expected-before
validation, writing, and exact readback are `O(K)` with `O(R)` paint-device
calls and `O(K)` request storage. Krita's undo is tile-memento based, so undo
storage is proportional to touched tiles rather than a copied full document.
Dirty propagation uses the run rects (or their bounded union). This is adequate
for the 187-pixel proof; correctness takes precedence over iterator or batching
micro-optimization.

The smallest future real-host prototype is one disposable copy of the Row-G
two-color fixture and one native call containing all 187 target pixels. It must
prove:

- after apply, exactly those 187 pixels changed to their exact raw expected
  colors and every other byte, including RGB under alpha zero, stayed equal;
- one user-visible Undo returns the complete document to S0;
- one Redo restores exact S1;
- Line, Guide, selection, foreground, active node, blending, opacity, flow,
  global alpha lock, and eraser state are unchanged; and
- stale/unsupported/failure injections leave S0 exact and publish no command.

That prototype may inform both Row G and Row I, but neither matrix row may be
updated from a standalone prototype. Only a later production-integrated
real-host qualification can reclassify them.

### No-op spike and remaining gate state

The optional no-op binary spike was **SKIPPED**. A viable `.pyd` form is clear,
but the matching LLVM-MinGW compiler, CMake/Ninja, Krita headers/import
libraries, generated headers, and dependency developer prefix are absent.
Building with Linux GCC, MSVC, or a guessed ABI would not be a meaningful load
test. No source directory, build command, or binary was produced.

The exact future build prerequisites are therefore: obtain the official
LLVM-MinGW 20251118 (LLVM 21.1.6) UCRT toolchain without mixing runtimes;
reconstruct the matching Krita dependency developer prefix; configure/build
exact source `858d352e52e68831693067763b9cdaf8bb9a05ce`; build the one `.pyd`;
inspect its imports to exclude duplicate runtimes; then perform a no-op load in
a disposable Krita 5.3.3 cell before any mutation prototype. Those are pending
implementation/build tasks, not authorization to begin them here.

The authoritative matrix remains **A–F PASS; G FAIL; H–V UNTESTED**. Row I
remains **UNTESTED** and a release blocker; architecture evidence is not a Row-I
execution. Phase 6.5 remains **OPEN / FAILED**, Krita remains not
release-qualified, H–V were not begun, and OFFF remains out of scope.
