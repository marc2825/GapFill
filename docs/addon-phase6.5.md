# Add-on Phase 6.5 — Krita real-host qualification

Date: 2026-08-15–16 (Asia/Tokyo)

Qualification sources: `ed7d2e1bc96c14e0f80908bc7d3a01a872a15f55`, the
committed Row-A lifecycle repair, plus the bounded Row-F ManagedColor repair
in the checkpoint worktree based on
`454d345cdaa10bb9f2560ee1fe1ffcc3721bbc98`.

Status: **Rows A–F PASS** in the recorded real-host cell. Rows G–V
remain **UNTESTED**. Phase 6.5 remains open, and this record is not a Krita
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
