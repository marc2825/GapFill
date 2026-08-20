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

## Native no-op build/load feasibility — 2026-08-16

This section supersedes only the preceding statement that the optional no-op
spike was skipped. It does not supersede the transaction architecture, does not
qualify mutation, and changes no host-test row. The exact result is:

> **NOOP_EXTENSION_BUILT_AND_STATICALLY_VALIDATED**

The no-op was not installed in the GapFill package and was not loaded in Krita.
No document, selection, Undo stack, foreground color, active node, tool, or
other user state was touched.

### Frozen baseline

| Item | Frozen value |
|---|---|
| Repository commit | `b4acabf3cea64c118ea7eb62510d73e7bb0e887b` |
| Branch | `qualify/csp-host-adapter` |
| Initial repository status | clean |
| Windows host | Windows 11 Pro x64, version `10.0.26200`, build `26200` |
| Running host process | PID `43608`, `C:\Program Files\Krita (x64)\bin\krita.exe` |
| Krita identity | `5.3.3 (git 858d352)` |
| Host runtime | Qt `5.15.7`; CPython `3.13.5`; PyQt5 `5.15.11` |
| Installed qualification artifact | `/tmp/gapfill-krita-phase6.5-rowF-managedcolor-win-x64-py313-454d345-worktree.zip` |
| Qualification ZIP SHA-256 | `bf19c8dc2fb3e44f160614f61fa189d52dac62bc24790b0094170ccd93fbe146` |
| Installed artifact comparison | 892/892 payload files exact; zero missing/changed; 116 extras, all recognized `*.cpython-313.pyc` caches; zero other extras |
| Fixture manifest SHA-256 | `6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c` |
| ONNX SHA-256 | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78` |
| Sidecar SHA-256 | `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5` |

Relevant installed-file fingerprints were re-read before the spike was built:

| Installed file | SHA-256 |
|---|---|
| `krita.exe` | `4e40b4e63d31d281a3239317ffdc9c204656b8328df97ec5eb56726ef7966373` |
| `Qt5Core.dll` | `e6ec243ce0791dc3406547f85a3582024a0fe69bc7cc5c49afa4b1538fea31b9` |
| `python313.dll` | `df56bb381bffbdd80863110ee88654625c09eb325fb99ceaceeca7f4402c7b5a` |
| `libc++.dll` | `7583e11bdd380d367003b55b90e459b04d105be55f6e4900606503487bb4bccf` |
| `libunwind.dll` | `cc0d3c1a55e848cd064949346855225e39779ece3b807407ea851875930ca9d2` |
| `libwinpthread-1.dll` | `cfcb538f66f69bec04ebb8c55e6bc484f213bf3266a122045234e643a420c71b` |
| `libkritaversion.dll` | `0812b1500e53e9cc6bc2d8251df3a9160d4d8125ec2f5995a029b32d2637a95c` |
| `libkritacommand.dll` | `db9a968484787c1e03b69bff796d906c211c5bf75c5d6d7d25412bc5d9d27691` |
| `libkritapigment.dll` | `d39a933c612847f0aa37ad9827c4f903796f92264ef4d0b218758d063bc78e9b` |
| `libkritaimage.dll` | `2580944bea1d72561dd54c31e146c269b690ebbe979d8e0e3767ea83f1db8cc9` |
| `libkritaui.dll` | `1bf7372a819a9cf7f3a64a95b6c8fd8f0264bda3bf8478284ee454d32fa00e12` |
| `libkritalibkis.dll` | `5aaf7ddd71d4a91d87ad4558eeaeceee82abe93e653964b1e8d12bfbf5dc2507` |
| `PyKrita/krita.pyd` | `7fd53d08f60ed2b72fd70df1592431cfb21398eddb2803e600a0091574f3b661` |

### Exact official Windows build route

The authoritative source-to-binary route is the successful KDE GitLab
[`windows-release-qt5` job 4762524](https://invent.kde.org/graphics/krita/-/jobs/4762524)
in [pipeline 1301828](https://invent.kde.org/graphics/krita/-/pipelines/1301828).
The job checked out `release/6.0.3` at exact revision
`858d352e52e68831693067763b9cdaf8bb9a05ce`; the Qt5 branch of that source
declares Krita `5.3.3`. The surviving raw job trace is
`/tmp/krita-858d352-windows-qt5-trace-raw.log`, SHA-256
`0c27740e4d2eb0f5eef3e2f47d49430ae83a2b9c7b8bdd26fd288f622e0e1239`.
The job's CMake cache and package artifact expired on 2026-08-05 and return
HTTP 404, so they cannot be used as a developer archive.

The job used VM image
`storage.kde.org/vm-images/krita-windows-clang21-twinpy`, cloned
`krita-deps-management` master as it existed at
`e1171184a8c98d962a9e19ca13000b506d56a299`, and cloned
`krita-ci-utilities` master as it existed at
`9285a277a971fcea3e0332bb5b7906ecfe6116bd`. Most dependency packages were
the caches produced at dependency revision
`890295fc42249606a471254e622f14612e087e8e`; the three x265 packages used
the later `e1171184` revision. The dependency registry is the public
`teams/ci-artifacts/krita-windows` project, ID `16406`.

The exact build sequence was:

1. generate `.kde-ci.yml` from the dependency seed;
2. merge cached dependency archives into
   `C:\builds\graphics\krita\_install`, with its `bin` and `lib` first on
   `PATH`;
3. configure exact Krita source with CMake `3.31.8` and generator `Ninja`;
4. build and install the `all` / `install` targets into `_install`;
5. run `packaging/windows/package-complete.py`, `windeployqt`, binary signing,
   ZIP creation, and NSIS installer creation.

The exact configure invocation recorded by the trace was:

```text
cmake -DCMAKE_BUILD_TYPE=RelWithDebInfo -DBUILD_TESTING=ON \
  -DCMAKE_INSTALL_PREFIX="C:\builds\graphics\krita\_install" \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DKRITA_ENABLE_PCH=OFF \
  -DFOUNDATION_BUILD=ON -G Ninja -DHIDE_SAFE_ASSERTS=ON \
  -DBUILD_TESTING=OFF "C:\builds\graphics\krita"
```

The last `BUILD_TESTING` value wins. The compiler was
`C:\Tools\llvm-mingw-20251118-ucrt-x86_64\bin\c++.exe`, LLVM/Clang
`21.1.6` at LLVM revision `a832a5222e489298337fbb5876f8dcaf072c5cca`;
the linker was LLD `21.1.6`. The target was x86-64 Windows GNU/Itanium ABI,
UCRT, libc++, libunwind, and POSIX-thread llvm-mingw. It was not MSVC ABI and
did not use libstdc++.

Relevant source-derived compile/link settings were C++17 with CMake's GNU
extensions (`-std=gnu++17`), RelWithDebInfo (`-O2 -g -DNDEBUG`),
`-gdwarf-aranges`, exceptions enabled, and Qt5's Windows floor defines
`_WIN32_WINNT=0x0602`, `WINVER=0x0602`, and `_WIN32_IE=0x0602`. Module
hardening was `--dynamicbase`, `--nxcompat`, `--disable-auto-image-base`,
`--high-entropy-va`, and image base `0x180000000`. The expired cache prevents
recovery of the literal final `CMAKE_CXX_FLAGS` string; the values above are
the corresponding CMake/Krita source settings and are the ABI/security-
relevant flags reproduced by the spike. The trace did not record the Ninja
version.

The dependency prefix contained the custom Qt `5.15.7` tree at Qt fork commit
`835aaa7afeffe87151c4c4614d54827c1d997a09`, ECM/KF5 `5.101.0`, Boost
`1.90.0`, LCMS `2.19`, and the other cached dependencies listed by the job.
It also contained normal `include`, `lib`, `bin`, and `lib/cmake` development
surfaces. The build bootstrap interpreter was CPython `3.13.14` and CMake
found its `C:\Tools\Python-3.13\libs\python313.lib`; the separately pinned
`ext_python` package supplied the shipped CPython `3.13.5` embeddable runtime.
This explains the two patch versions in the official trace. Both use the
`python313.dll` ABI; the shipped runtime, not the bootstrap interpreter, is
the no-op load target.

### Reproducible inputs and workspace

No package manager or system installation was changed. The isolated workspace
is `/tmp/gapfill-krita-native-build/`, separated into `source/`, `toolchain/`,
`deps/`, `build/`, `install/`, `spike/`, and `evidence/`.

| Input | SHA-256 / verification |
|---|---|
| Exact Krita source archive, `/tmp/krita-858d352-source.tar.gz` | `0039425577a8b27506bc332134714d4ed7a021e985ee0111029dea19ac6883a6` |
| `krita-deps-management` `e1171184` archive | `22813fa89f19eb3929574c6c942f21acaa419a73a9a4039baad49cbb93e83076` |
| `krita-ci-utilities` `9285a277` archive | `69829bf93ddea679edcf989736e17d1a7c86597cf6c8a00fe2def65bc0da790b` |
| Upstream `llvm-mingw-20251118-ucrt-ubuntu-22.04-x86_64.tar.xz` | `53a0c22caa46b501e1c089e1c31b24a7c0e0d5a86f8ad12b131aafd4cee01ef4`; exact match to the digest published by the upstream `20251118` release |
| Exact KDE `ext_python/master-1783414987` archive | `66714cf6d0de0b128ee3dba5941f538523a29d759835811c169a82d6a3479f68`; versioned registry metadata identifies dependency revision `890295fc` |
| Its metadata JSON | `2fa3445d4969a6117965ec3d55872706d877de329d446d6be8abd183930c4230` |
| Exact Qt cache metadata, `ext_qt/master-1783419270` | `0421ed4c3389c40dd6f95933376503465f9fcc3996d9c7171e59faa6a632da4f`; dependency revision `890295fc` |
| CPython `3.13.5` source | `93e583f243454e6e9e4588ca2c2662206ad961659863277afcdb96801647d640`; MD5 `dbaa8833aa736eddbb18a6a6ae0c10fa` exactly matches Krita's dependency recipe |

The exact 345,149,440-byte Qt developer archive remains available from the
registry, but was intentionally not downloaded: the no-op has no Qt or Krita
C++ dependency. Fetching that archive and the rest of the full dependency
closure would have been unrelated to the load-only spike.

Before acquisition, the WSL environment had GCC/G++ `13.3.0`, Python
`3.12.3`, Git `2.43.0`, GNU binutils/objdump `2.42`, and Make. It had no
clang/clang++, LLVM-MinGW, CMake, Ninja, Python 3.13 development install, or
LLVM binary tools. The isolated download now provides the exact
LLVM-MinGW/Clang/LLD/llvm-readobj/llvm-objdump/llvm-dlltool `21.1.6` tools.
CMake `3.31.8`, Ninja, a runnable local Python 3.13, the Qt/KF developer
prefix, and Krita import libraries remain absent locally because the no-op
does not require them.

### Future helper dependency and import-library decision

Installed exports and exact headers establish this minimum future dependency
graph:

| Helper surface | Header | Defining DLL / direct consequence |
|---|---|---|
| `KritaVersionWrapper::versionString()` | `libs/version/KritaVersionWrapper.h` | `libkritaversion.dll` → `Qt5Core.dll` |
| `KUndo2Command` / `KUndo2MagicString` | `libs/command/kundo2command.h` | `libkritacommand.dll` → Qt5 Core/Gui/Widgets, KF5, Krita global/widget utilities |
| `KisTransaction` / `KisTransactionData` | `libs/image/kis_transaction.h`, `kis_transaction_data.h` | inline wrapper plus exported `libkritaimage.dll` transaction data → command/pigment/image closure |
| `KisTransactionBasedCommand` | `libs/image/commands_new/kis_transaction_based_command.h` | `libkritaimage.dll` |
| `KisPaintDevice::readBytes()`, `writeBytes()`, `sequenceNumber()` | `libs/image/kis_paint_device.h` | `libkritaimage.dll` |
| `KisNode`, `KisPaintLayer`, `KisLayerUtils::findNodeByUuid()` | `libs/image/kis_node.h`, `kis_paint_layer.h`, `kis_layer_utils.h` | `libkritaimage.dll`; `KisPaintLayer::paintDevice()` and `alphaLocked()` are exported |
| `KisImage` start/add/end/cancel/wait | `libs/image/kis_image.h` | `libkritaimage.dll` |
| `KisStrokeStrategyUndoCommandBased` and `BARRIER` / `EXCLUSIVE` job data | `libs/image/kis_stroke_strategy_undo_command_based.h`, `kis_stroke_job_strategy.h` | `libkritaimage.dll` |
| `KisPart` and `KisDocument::image()` host resolution | `libs/ui/KisPart.h`, `libs/ui/KisDocument.h` | `libkritaui.dll` → image/pigment/command/version, Qt5, KF5, and its wider UI closure |
| CPython bridge | CPython `Include/Python.h` and generated Windows `pyconfig.h` | `python313.dll`; no SIP/PyKrita pointer transport |

The named constructors, destructors, read/write/sequence methods, target lookup,
stroke methods, transaction command methods, and version/host-resolution
methods were all re-confirmed in the official installed DLL export tables.
The eventual helper's direct DLL set is therefore at least
`python313.dll`, `libkritaversion.dll`, `libkritacommand.dll`,
`libkritapigment.dll`, `libkritaimage.dll`, `libkritaui.dll`, Qt5 Core/Gui/
Widgets, libc++, libunwind, and UCRT. `libkritalibkis.dll` is not intrinsically
required by the preferred internal host-resolution design, although the
shipped `PyKrita/krita.pyd` imports it.

For the no-op only, `llvm-dlltool` generated a five-symbol CPython C import
library from the exact `python313.dll` export names. The unsigned cached DLL
and signed installed DLL have identical 1,655-name export sets, so this is a
narrow, technically safe C-ABI thunk library.

That decision does **not** authorize the analogous shortcut for Krita's C++
internals. An import library reconstructed from decorated exports can name the
right thunk, but cannot itself prove matching class layout, inline/template
code, RTTI, exceptions, Qt value types, generated configuration/export headers,
or correct data/vtable treatment. The future transaction helper is therefore
classified **FULL_BUILD_REQUIRED**: reconstruct the complete exact KDE
dependency prefix, configure exact source `858d352`, and build/install the
needed Krita library closure with its generated headers and native import
libraries before compiling the mutation helper. A no-op CPython-only build is
not evidence that a partial Krita developer prefix is sufficient.

### No-op binary and static validation

The source is
`/tmp/gapfill-krita-native-build/spike/gapfill_krita_native.cpp`, SHA-256
`39e96cead7dd223b0754bd6d9eab5b44082273f17f3ce19abd737ad7d82f06d9`.
It exposes only `abi_info()` and a read-only `host_probe()`. Import fails closed
unless the process is 64-bit CPython 3.13 inside `krita.exe`. The source has no
Krita document, paint-device, transaction, Undo, selection, foreground, node,
or tool mutation API.

The complete build command is preserved in
`/tmp/gapfill-krita-native-build/spike/build.sh`, SHA-256
`302a5620ea3c515d28edab5862d4b1ac6f51dcfbd412392346bc35199aca89a1`.
Its two effective commands are:

```text
llvm-dlltool -m i386:x86-64 -D python313.dll \
  -d spike/python313.def -l install/lib/libpython313.dll.a

x86_64-w64-mingw32-clang++ -std=gnu++17 -O2 -g \
  -gdwarf-aranges -fexceptions -DNDEBUG \
  -D_WIN32_WINNT=0x0602 -DWINVER=0x0602 -D_WIN32_IE=0x0602 \
  -Ispike/include -Isource/cpython-3.13.5/Include -shared \
  -Wl,--dynamicbase -Wl,--nxcompat -Wl,--disable-auto-image-base \
  -Wl,--high-entropy-va -Wl,--no-insert-timestamp \
  -Wl,--image-base,0x180000000 \
  spike/gapfill_krita_native.cpp -Linstall/lib -lpython313 \
  -o spike/out/gapfill_krita_native.cp313-win_amd64.pyd
```

The built file is
`/tmp/gapfill-krita-native-build/spike/out/gapfill_krita_native.cp313-win_amd64.pyd`,
130,560 bytes, SHA-256
`8c239b66244a258493c8965713ccd51b94d02f498d73955e43c4afea55218227`.
It is PE32+ AMD64, Windows GUI DLL, has `HIGH_ENTROPY_VA`, `DYNAMIC_BASE`, and
`NX_COMPAT`, and exports exactly the required
`PyInit_gapfill_krita_native` initializer.

Two consecutive clean link invocations produced that same SHA-256. The only
change required after detecting PE timestamp variance was LLD's
`--no-insert-timestamp`; it changes no code, imports, ABI, or hardening.

Its DLL imports are `python313.dll`, `libc++.dll`, `libunwind.dll`,
`KERNEL32.dll`, and UCRT API-set DLLs for runtime/string/private/stdio/heap.
Every non-system DLL is already in the qualified Krita `bin` directory. There
is no MSVC C++ runtime, libstdc++, libgcc, second Qt, or Krita DLL dependency.
The installed `PyKrita/krita.pyd` is likewise PE32+ AMD64 with the same
`python313.dll`/libc++/libunwind/UCRT runtime family and the same PE hardening;
its additional Qt/Krita imports are expected because it is the full binding.
This is a static compatibility pass, not an import result.

### Prepared but unexecuted load-only harness

The one-shot Scripter harness is
`/tmp/gapfill-krita-native-build/spike/load_harness.py`, SHA-256
`f1e1c5ba615b4df51cc9f6036819fe004aa4f43ec79b3016821ef99be90e0d5e`;
its AST parse passed. The exact `.pyd` and harness were staged, without
installation, at:

```text
C:\Users\marck\AppData\Local\Temp\gapfill-phase65-native-noop-spike-b4acabf-8c239b66\
```

The staged file hashes match the isolated originals. The guarded result path
is:

```text
C:\Users\marck\AppData\Local\Temp\gapfill-phase65-native-noop-result-b4acabf-8c239b66\result.json
```

The result directory is absent, proving the harness was not run. It refuses a
pre-existing output directory or preloaded module, verifies the `.pyd` hash,
Windows x64, CPython 3.13, Krita 5.3.3, and Qt 5.15.7, temporarily adjusts only
`sys.path` and the process DLL search handle, imports the no-op, calls its two
read-only methods, writes one JSON result, and restores `sys.path`. It contains
zero document and zero Undo calls. Static inspection supports one manual
load-only invocation in this exact host cell; that future execution is still
required before any claim of real-host load PASS.

An obsolete first-iteration staging directory created during this build was
removed after the final hash-keyed staging directory was verified. It contained
only the superseded temporary no-op binary and harness and was not recoverable;
no Krita resource, plugin, configuration, or repository file was removed.

### Ephemeral workspace replay — 2026-08-20

After the WSL `/tmp` workspace was cleared between sessions, it was reconstructed
from the same pinned archives. Every recorded input digest matched; the no-op
source and build-script digests matched; two fresh builds again produced the
same 130,560-byte `8c239b66...18227` binary; and that binary remained byte-for-
byte identical to the staged Windows copy. The staged harness still matched
`f1e1c5ba...e0d5e`, and its guarded result directory remained absent. This was
a static reproducibility replay only: the harness was not invoked and no host
test row changed.

### Native no-op load attempt 1 false reject — 2026-08-20

The first manual invocation of the original load-only harness did **not** reach
the native module. The exact real-host error was:

```text
RuntimeError: unsupported Krita: 5.3.3 (git 858d352)
```

The failure was raised by `main()` at original harness line 52. The original
harness remains preserved at
`/tmp/gapfill-krita-native-build/spike/load_harness.py`, SHA-256
`f1e1c5ba615b4df51cc9f6036819fe004aa4f43ec79b3016821ef99be90e0d5e`.
Its staged copy remains byte-identical at:

```text
C:\Users\marck\AppData\Local\Temp\gapfill-phase65-native-noop-spike-b4acabf-8c239b66\load_harness.py
```

The faulty condition was an exact comparison of
`Krita.instance().version()` to the bare string `"5.3.3"`. The qualified host
correctly returned the combined string `"5.3.3 (git 858d352)"`, so that
incorrect Python guard rejected the intended host. This event is classified:

> **LOAD_HARNESS_HOST_VERSION_GUARD_FALSE_REJECT**

Control flow and preserved filesystem state establish the exact attempt-1
stage classification:

| Stage | Classification | Evidence |
|---|---|---|
| `VERSION_GUARD` | EXECUTED | The supplied exception is the guard at lines 51–52. |
| `SYS_PATH_INSERTION` | NOT_EXECUTED | It was at line 78, after the failed guard. |
| `IMPORT` | NOT_EXECUTED | `import_module()` was at line 83, after the failed guard and path insertion. |
| `PyInit` | NOT_EXECUTED | No import was attempted, so the Python loader could not call the initializer. |
| `ABI_INFO` | NOT_EXECUTED | It was called only after successful import at line 84. |
| `HOST_PROBE` | NOT_EXECUTED | It was called only after successful import at line 85. |

The harness had also already proved that `gapfill_krita_native` was absent from
`sys.modules`, because its preloaded-module refusal at lines 42–43 did not fire.
The output directory creation was after the faulty guard, so the original
guarded output directory remains absent and no result JSON was written:

```text
C:\Users\marck\AppData\Local\Temp\gapfill-phase65-native-noop-result-b4acabf-8c239b66\
```

Accordingly, the `.pyd` did not enter the process through this harness,
attempt 1 says nothing about DLL resolution or ABI compatibility, and it is
neither a native load PASS nor a native load/ABI FAIL.

### Prepared load-only harness v2 — not executed

The corrected harness is
`/tmp/gapfill-krita-native-build/spike/load_harness_v2.py`, SHA-256
`6deed287c63a8e79e06c51a79ee917d1ea7dd86c8c9a360cc8c0496f31e34612`.
It accepts only an exact full match for the qualified combined host identity:

```text
^5\.3\.3 \(git 858d352\)$
```

Thus both product version `5.3.3` and short revision `858d352` are mandatory;
other revisions, versions, arbitrary suffixes, and malformed identities remain
rejected. The frozen native binary was not rebuilt or changed. Its local,
attempt-1, and v2-staged copies are byte-identical: 130,560 bytes, SHA-256
`8c239b66244a258493c8965713ccd51b94d02f498d73955e43c4afea55218227`.

The v2 harness and unchanged binary are staged, without installation, at:

```text
C:\Users\marck\AppData\Local\Temp\gapfill-phase65-native-noop-spike-v2-b4acabf-8c239b66\
```

Its new one-invocation guarded output is:

```text
C:\Users\marck\AppData\Local\Temp\gapfill-phase65-native-noop-result-v2-b4acabf-attempt2\result.json
```

That output directory is absent, proving v2 was not run. The harness refuses
overwrite and reuse of a preloaded module. It persists the required stage
sequence—`HARNESS_STARTED`, `HOST_IDENTITY_ACCEPTED`,
`SYS_PATH_TEMPORARILY_ADDED`, `IMPORT_ATTEMPTED`, `IMPORT_SUCCEEDED`,
`ABI_INFO_SUCCEEDED`, `HOST_PROBE_SUCCEEDED`, and `LOAD_PROOF_PASS`—and records
`IMPORT_FAILED`, exception type, message, traceback, and last stage when import
raises.

Before import and after restoring `sys.path`, v2 takes read-only snapshots of
the active document identity, modified flag, active node identity, selection
presence/bounds/hash when within the safety limit, and foreground color. It
requires both the stable host state and complete `sys.path` value to match
before marking `LOAD_PROOF_PASS`. It does not create a document and contains no
document mutation, transaction, Undo, target-node resolution, or production
plugin import.

Python syntax compilation and AST parsing passed. The AST contained all
required stage labels and no forbidden mutation calls. Ruff was unavailable in
the isolated WSL environment (`No module named ruff`), so no Ruff result is
claimed. Static review supports exactly one future manual load-only invocation
in the qualified host cell; v2 has not supplied that proof yet.

### Gate state

Production Python source is unchanged. `krita-plugin/host_tests/matrix.json`
is unchanged. The authoritative matrix remains **A–F PASS; G FAIL; H–V
UNTESTED**. Row I remains **UNTESTED** and a release blocker. Phase 6.5 remains
**OPEN / FAILED**, Krita remains not release-qualified, and no H–V row or
transactional mutation prototype has begun.

## Native exact-transaction prototype preparation — 2026-08-20

This section supersedes only the preceding no-op gate statement and the claim
that a transaction prototype had not begun. It preserves the failed Row-G
native-fill evidence and does not change a matrix result. The no-op extension
has now passed its separately authorized real-host load proof, and the smallest
isolated exact-transaction prototype has been built and prepared for a future
one-shot host proof. The mutation prototype and proof harness were **not
executed** in this task.

The exact classifications remain:

```text
architecture feasibility = NATIVE_TRANSACTION_HELPER_FEASIBLE_BUT_VERSION_PINNED
no-op build/static status = NOOP_EXTENSION_BUILT_AND_STATICALLY_VALIDATED
no-op real-host load status = PASS
mutation prototype status = BUILT_AND_STATICALLY_VALIDATED_NOT_EXECUTED
```

### Frozen baseline and no-op real-host load

The baseline immediately before transaction-prototype work was:

| Item | Value |
|---|---|
| Repository commit | `b4acabf3cea64c118ea7eb62510d73e7bb0e887b` |
| Branch | `qualify/csp-host-adapter` |
| Initial status | one existing evidence-only modification: `docs/addon-phase6.5.md`; no production change |
| Qualified host | Windows 11 x64; Krita `5.3.3 (git 858d352)`; Qt `5.15.7`; CPython `3.13.5` |
| Installed production artifact | `gapfill-krita-phase6.5-rowF-managedcolor-win-x64-py313-454d345-worktree.zip` |
| Production artifact SHA-256 | `bf19c8dc2fb3e44f160614f61fa189d52dac62bc24790b0094170ccd93fbe146` |
| No-op binary | `/tmp/gapfill-krita-native-build/spike/out/gapfill_krita_native.cp313-win_amd64.pyd` |
| No-op binary SHA-256 | `8c239b66244a258493c8965713ccd51b94d02f498d73955e43c4afea55218227` |
| No-op result | `C:\Users\marck\AppData\Local\Temp\gapfill-phase65-native-noop-result-v2-b4acabf-attempt2\result.json` |
| No-op result SHA-256 / size | `03a428a75233471e36b660670f2d3ebd3e55336b3c1d391dda42bfc7456963d1`; 6,195 bytes |
| Fixture manifest SHA-256 | `6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c` |
| ONNX SHA-256 | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78` |
| Model sidecar SHA-256 | `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5` |

The no-op result records `status = PASS`, exact host identity, and the complete
stage chain `HARNESS_STARTED` → `HOST_IDENTITY_ACCEPTED` →
`SYS_PATH_TEMPORARILY_ADDED` → `IMPORT_ATTEMPTED` → `IMPORT_SUCCEEDED` →
`ABI_INFO_SUCCEEDED` → `HOST_PROBE_SUCCEEDED` → `LOAD_PROOF_PASS`. The module
therefore entered the real Krita process and returned from both read-only calls.
The result also records `host_state_unchanged = true`,
`sys_path_restored = true`, `document_mutation_calls = 0`, and `undo_calls = 0`.
This is real-process evidence for the no-op binary only; it is not a mutation or
Undo result.

### Exact developer-prefix reconstruction

The earlier `FULL_BUILD_REQUIRED` decision was followed. Everything remains
under `/tmp/gapfill-krita-native-build/`; no system package was installed and
no installed Krita file was modified.

- Exact Krita source revision:
  `858d352e52e68831693067763b9cdaf8bb9a05ce`; source archive SHA-256
  `0039425577a8b27506bc332134714d4ed7a021e985ee0111029dea19ac6883a6`.
- Exact official Windows Qt5 trace:
  `/tmp/krita-858d352-windows-qt5-trace-raw.log`, SHA-256
  `0c27740e4d2eb0f5eef3e2f47d49430ae83a2b9c7b8bdd26fd288f622e0e1239`.
- LLVM-MinGW `20251118`, Clang/LLD `21.1.6`, UCRT/POSIX/libc++/libunwind;
  archive SHA-256
  `53a0c22caa46b501e1c089e1c31b24a7c0e0d5a86f8ad12b131aafd4cee01ef4`.
- CMake `3.31.8`, archive SHA-256
  `630615d8e98ac33eba7fbe472626dff5c899c85af3c024585ae109166a6909d0`;
  Ninja `1.13.1`, archive SHA-256
  `0830252db77884957a1a4b87b05a1e2d9b5f658b8367f82999a941884cbe0238`.
- The exact official dependency set comprises 85 archives. The resolved
  registry records are in
  `/tmp/gapfill-krita-native-build/evidence/package-manifest.tsv`, SHA-256
  `7755e25cfbc7f0e95f9d6e68ed17578abe44407026f08ed3ce129181e76fe3f`;
  the archive digest list is `dependency-archive-sha256.txt`, SHA-256
  `a8670762c57b21726ad16c30c6375526154b70734b0b5127f977caa77d0463ab`.
  All 85 archives passed extraction/integrity checks. Eighty-two match the
  trace's `890295...` dependency revision and the three x265 packages match
  its later `e117...` revision.
- The merged prefix is
  `/tmp/gapfill-krita-native-build/deps/official-prefix`, approximately
  1.8 GiB, and identifies Qt `5.15.7` and KF5 `5.101.0`.

Cross-building generated Qt resources required build-host tools. The original
Windows `rcc.exe` and `uic.exe` remain preserved in the prefix with SHA-256
`3474f1d2...99bd` and `5712a037...a9d`; build-only symlinks point to exact Qt
`5.15.7` Linux-host `rcc` (`6692376c...d6bd`) and `uic`
(`4dddbfc7...760`). That host Qt archive is
`ext_qt-linux-host-835aaa7.tar`, SHA-256 `0313cc1...151`. The isolated host
`uic` runtime uses Ubuntu `libicu70` archive SHA-256 `58a154f6...dfd9a` and
`libpcre2-16` archive SHA-256 `d4b3cd60...9d87`. These substitutions are build
tools only; no host Linux Qt/ICU/PCRE library is linked into the Windows helper.

Exact source was configured in
`/tmp/gapfill-krita-native-build/build/krita-exact-5` as `RelWithDebInfo`, with
tests off, foundation build on, PCH off, safe asserts hidden, and
`HAVE_BACKTRACE=0`. The last setting reproduces the official Windows trace's
`Looking for backtrace - not found`; it is a cache setting, not a source patch.
The `kritaimage` and `kritaui` targets and their `kritapigment`,
`kritacommand`, `kritaversion`, and `kritaglobal` closure built successfully,
including native DLL import libraries. This satisfies the exact-header,
generated-header, class-layout, inline/template, exception, and import-library
requirements that prevented a decorated-export-only shortcut.

### Narrow prototype contract and target resolution

The module exposes only `abi_info()` and one mutation operation,
`apply_exact_patch(...)`. It accepts simple Python strings, integers, a sequence
of tuples, and exact `bytes`; it accepts no SIP/PyKrita C++ pointer. The
operation contract is:

```text
document_path
target_uuid
expected_width, expected_height
expected_origin_x, expected_origin_y
expected_color_model, expected_color_depth, expected_profile
runs = [(x, y, pixel_count, expected_before_bytes, replacement_bytes), ...]
```

For this constrained prototype, document identity is the canonical path of a
saved disposable file. It scans `KisPart::instance()->documents()`, compares
canonical paths case-insensitively on Windows, and requires exactly one match.
This is deterministic for the one disposable fixture, but it is explicitly
**not** a production-strength document-generation token: unsaved documents and
multiple open aliases need a stronger production design.

Within only the resolved document's `KisImage`, the helper recursively counts
the supplied UUID and requires exactly one match. It verifies that the node's
image pointer is the resolved image, that it is a `KisPaintLayer`, is editable
and unlocked, is not animated, and exposes the expected `KisPaintDevice`.
The active document and active node are irrelevant to resolution.

Before any transaction, it fails closed unless all of these checks pass:

- Windows x64 `krita.exe`, exact Krita `5.3.3 (git 858d352)`, exact Qt
  `5.15.7`, CPython 3.13, and the Krita GUI thread;
- unique canonical document path and unique target UUID;
- same document/image/node/device binding;
- exact image/device origin and bounds;
- target paint layer editable, unlocked, and nonanimated;
- color model `RGBA`, depth `U8`, pixel size 4, and exact profile name;
- positive image dimensions and a non-null UUID;
- nonempty sorted, non-overlapping horizontal runs wholly inside bounds;
- each expected/replacement payload exactly `pixel_count * 4` bytes;
- at most 1,000,000 pixels and 16 MiB combined expected/replacement payload;
- every expected-before run exactly equal to a current device read.

An image barrier protects the outer expected-before validation. The exclusive
stroke command repeats document/node/device resolution and expected-before
validation immediately before creating the transaction. A mismatch returns
`STALE_REJECTED`, performs zero writes, and publishes zero Undo commands.

### One-command transaction, rollback, update, and Redo design

The complete two-color patch is one `ExactPatchCommand`, derived from
`KisTransactionBasedCommand`, inside one exclusive
`KisStrokeStrategyUndoCommandBased` stroke. Static control flow contains
exactly one `startStroke()`, one `addJob()`, and one `endStroke()`. The job is
`BARRIER`/`EXCLUSIVE`; the strategy does not create its own macro. Only after
the command reports success does the finish callback add the single command to
the image's post-execution Undo adapter. The intended counts are therefore:

```text
startStroke calls                  1
endStroke calls                    1
top-level user-visible commands    1
KisTransactionBasedCommand objects 1
```

`paint()` creates one `KisTransaction` on the target device. It writes only the
validated horizontal runs using `KisPaintDevice::writeBytes()`, then reads each
run back and requires byte-exact replacement. It never creates a `KisPainter`,
selection, fill action, compositing operation, or bounding-box padding write.
It marks one union dirty rectangle with `node->setDirty()`; that invalidation
does not add another history command.

On success, `transaction.endAndTake()` supplies the one transaction-data
command. Krita's tile memento skips the already-performed first Redo, rolls back
on Undo, and rolls forward on later Redo; no prototype-side manual Redo buffer
exists. `KisSavedCommand` replays the same one command in Krita's normal Undo/
Redo strokes.

All conditions that can be checked are checked before transaction creation. If
a C++ exception or replacement readback failure occurs after creation, the
catch path calls `KisTransaction::revert()`, destroys the transaction, verifies
every expected-before run again, marks the same dirty rect, and does not publish
the command. `KisTransaction::end()` is not used as rollback. This design does
not claim recovery from process termination, access violation, or another
non-C++ catastrophic failure.

By construction, the helper does not read or write the global selection,
foreground color, active node, blending mode, opacity, flow, eraser state,
global alpha lock, rotation, mirror, zoom, wraparound, or level-of-detail mode.

### Mutation binary and static ABI result

| Artifact | Path | SHA-256 |
|---|---|---|
| C++ source | `/tmp/gapfill-krita-native-build/spike/txn/src/gapfill_krita_native_txn.cpp` | `e9a16ffb32e74dadfb98b5f37f28b48c647ee20feaf4070447bbf0ae282f5107` |
| CPython import definition | `/tmp/gapfill-krita-native-build/spike/txn/python313-txn.def` | `b3c64f7c71b3748c238785d599266c59daa5477f578575b81e9cf28b5c5ecf73` |
| Build script | `/tmp/gapfill-krita-native-build/spike/txn/build-txn.sh` | `411fd90136198519e0af74bc570b9e4f97316d217bf9e8e2b5b6885ed5d4b0a6` |
| Mutation binary | `/tmp/gapfill-krita-native-build/spike/txn/out/gapfill_krita_native_txn.cp313-win_amd64.pyd` | `6ee912013bfb917c676836b9103809480301e185cfff62cf8982badf6525efb1` |

The mutation binary is 1,337,344 bytes. Two clean output directories produced
the same SHA-256 and `cmp` passed. The PE/COFF timestamp is zero. Static
inspection reports PE32+ AMD64, 64-bit address size, DLL, large-address-aware,
`DYNAMIC_BASE`, `HIGH_ENTROPY_VA`, and `NX_COMPAT`; it exports exactly
`PyInit_gapfill_krita_native_txn`.

Direct imports are `python313.dll`, `libkritaui.dll`, `libkritaimage.dll`,
`libkritapigment.dll`, `libkritacommand.dll`, `libkritaversion.dll`,
`libkritaglobal.dll`, `Qt5Core.dll`, `libc++.dll`, `libunwind.dll`,
`KERNEL32.dll`, and UCRT API-set DLLs. Imported Krita symbols include the
document/image resolvers, UUID/node/device checks, `readBytes`, `writeBytes`,
stroke strategy/job methods, transaction command methods, dirty invalidation,
and the post-execution Undo adapter. There is no MSVC C++ runtime,
`libstdc++`, `libgcc`, second Qt copy, wrong Python ABI, or wrong architecture.
Qt Gui/Widgets and the wider UI closure are supplied transitively by the exact
host `libkritaui.dll`; LLD removed unused direct imports.

A final name-by-name comparison against the actual installed DLL export tables
also passed: all 13 imported CPython names, 4 `libkritaui` names, 54
`libkritaimage` names, 1 `libkritapigment` name, 15 `libkritacommand` names, 1
`libkritaversion` name, 4 `libkritaglobal` names, 25 Qt5 Core names, 28 libc++
names, and 1 libunwind name are present. Only the normal Windows Kernel/UCRT
API-set imports were treated as system-provided. There is therefore no missing
named import in the installed host closure at static inspection time.

### Disposable fixture and exact raw patch

The future proof fixture is an exact copy of the preserved Row-G capture:

```text
/tmp/gapfill-krita-native-build/spike/txn/fixture/multiple-colors.kra
SHA-256 3df7b2087c535d2e4eaab4409f3becb3379886bca8fc82f452bee63148911d79
size 43,251 bytes
```

It is 64×64, origin (0,0), `RGBA/U8`, profile
`sRGB-elle-V2-srgbtrc.icc`, with unique paint-layer UUIDs Coloring
`{50e9f493-3640-44e7-8037-542594f7f62b}`, Line Art
`{7d6486fa-b754-431d-9c88-fc9a4958cdcd}`, and Guides
`{95d3b93c-d702-44e2-b400-ba3b42414465}`. The machine-readable patch plan is
`fixture/patch-plan.json`, SHA-256
`0c919e41fad4b38445674d4f4475d354430f7a1af4e16d94c2ad237ea5a08e0f`.
Mechanical validation passed: 19 sorted non-overlapping horizontal runs, 187
unique pixels, 178 blue and 9 red.

The frozen ordered colors and final device bytes are:

| Group | Canonical ordered RGBA | Target-profile ordered RGBA | Native `pixelData`/`writeBytes` BGRA/U8 |
|---|---|---|---|
| Blue | `[13,117,241,255]` | `[13,117,241,255]` | `[241,117,13,255]` |
| Red | `[227,61,17,255]` | `[227,61,17,255]` | `[17,61,227,255]` |

Color management is complete before the helper call; the helper receives only
the final native bytes. Expected-before is `[0,0,0,0]` at every target pixel.
The 187-pixel identity is:

- blue gap 0: x 39–51, y 13–25, 169 pixels;
- blue gap 1: indices 1560–1562, 1624–1626, and 1688–1690, 9 pixels;
- red gap 2: indices 2990–2992, 3054–3056, and 3118–3120, 9 pixels.

Both colors are passed in the same one-call, one-command plan.

### Prepared one-shot real-host harness — not executed

The harness is:

```text
/tmp/gapfill-krita-native-build/spike/txn/gapfill_phase65_native_txn_proof_b4acabf_6ee91201_v1.py
SHA-256 2d4e871a6dfa527ceea8c9fb4cd09f507726265a5bc33114ba94d5e55f666ceb
size 21,098 bytes
```

The harness, exact `.pyd`, and fixture are staged outside the installed plugin
at:

```text
C:\Users\marck\AppData\Local\Temp\gapfill-phase65-native-txn-spike-b4acabf-6ee91201-v1\
```

All three staged hashes match the isolated originals. No file was copied into
the Krita resource directory or production GapFill package. The unique guarded
output directory is:

```text
C:\Users\marck\AppData\Local\Temp\gapfill-phase65-native-txn-result-b4acabf-6ee91201-v1\
```

It is absent, which is direct filesystem evidence that this harness has not
run. The harness refuses an existing output directory or preloaded module,
checks exact host/module/fixture hashes, copies the source to a disposable KRA,
resolves all three UUIDs, and captures whole-layer raw arrays and editor state
at S0/S1/S2/S3. It temporarily adds only the isolated module path and Krita DLL
search directory, then restores `sys.path` and closes the disposable document
without save or `setModified(false)`.

Static AST inspection finds exactly one `apply_exact_patch()` call and two
`QAction.trigger()` call sites: one for `edit_undo` and one for `edit_redo`.
Runtime counters require one native call and one Undo; the Redo branch is
reachable only if S2 Coloring is byte-identical to S0 and is capped at one
call. The harness requires exact 187-pixel APPLY with zero missing,
unexpected, wrong-color, or non-target byte changes; Line/Guide and all captured
editor state except the normal modified flag must remain exact. It stops before
Redo if one Undo does not restore S0. One Redo must restore exact S1. It writes
machine-readable `result.json` and `raw-states.npz` in the guarded directory.

Python syntax compilation and AST parsing passed. The AST also finds zero
`setPixelData`, `setSelection`, `setForeGroundColor`, `setActiveNode`,
`setModified`, `save`, or `saveAs` calls. The C++ source contains one
`writeBytes` call site inside the validated-run loop; no `KisPainter`, fill
action, selection mutation, or production-plugin import exists. Ruff remains
unavailable in this isolated WSL environment, so no Ruff result is claimed.

The artifacts are statically suitable for **one future explicitly authorized
manual attempt** in the exact qualified host cell, using only the guarded
Scripter harness and disposable fixture. This is permission/readiness for an
attempt, not evidence that the mutation binary loads, applies, undoes, or
redoes in the real host. The helper was not imported and
`apply_exact_patch()` was not called in this task.

### Verification and unchanged gates

The fixture manifest, ONNX, and sidecar re-hashed to their frozen values above.
`git diff --check` passed. The only repository path changed remains this
evidence document; production source, the installed production plugin, and
`krita-plugin/host_tests/matrix.json` are unchanged. No production ZIP includes
the prototype.

The authoritative matrix remains **A–F PASS; G FAIL; H–V UNTESTED**. Row G
remains `NATIVE_FILL_UNSELECTED_TRANSPARENT_RGB_WRITE`; neither its NORMAL nor
COPY result is reclassified. Row I remains **UNTESTED** and a release blocker;
prototype control-flow and static ABI evidence are not a one-step Undo result.
Phase 6.5 remains **OPEN / FAILED**, and Krita remains not release-qualified.
Rows H–V and OFFF were not begun.

## Native transaction prototype real-host result and production integration — 2026-08-20

This section is later, time-ordered evidence. It supersedes only the preceding
prototype section's `NOT_EXECUTED` status. It does **not** reclassify a matrix
row: the isolated prototype was not the production GapFill Apply route.

### Frozen integration baseline and preserved prototype proof

The integration began on branch `qualify/csp-host-adapter` at commit
`b4acabf3cea64c118ea7eb62510d73e7bb0e887b`. Before production integration,
the only repository modification was this evidence document. The prototype
source, build recipe, import definition, binary, fixture, result JSON, and raw
arrays remain at their original paths and hashes; none was overwritten:

| Evidence | SHA-256 |
|---|---|
| Prototype source | `e9a16ffb32e74dadfb98b5f37f28b48c647ee20feaf4070447bbf0ae282f5107` |
| Prototype build script | `411fd90136198519e0af74bc570b9e4f97316d217bf9e8e2b5b6885ed5d4b0a6` |
| Prototype import definition | `b3c64f7c71b3748c238785d599266c59daa5477f578575b81e9cf28b5c5ecf73` |
| `gapfill_krita_native_txn.cp313-win_amd64.pyd` | `6ee912013bfb917c676836b9103809480301e185cfff62cf8982badf6525efb1` |
| `multiple-colors.kra` | `3df7b2087c535d2e4eaab4409f3becb3379886bca8fc82f452bee63148911d79` |
| Real-host `result.json` | `12c8760eba3e1e6f6ae391a5e4ca535511879259b06b421f6b0efda2298c12d6` |
| Real-host `raw-states.npz` | `72b094172f967c6231f73222ada818b82c49a53a37be68cb0b827ef6992fc223` |

The previously prepared prototype was run once on the qualified Windows 11
x64 / Krita 5.3.3 git `858d352` / Qt 5.15.7 / CPython 3.13.5 host. Its guarded
result directory is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-native-txn-result-b4acabf-6ee91201-v1`.
The result is `PASS`:

- one native call carried 19 horizontal runs and 187 pixels in two colors;
- exactly 187 intended pixels changed, with zero missing, unexpected, or
  wrong-valued pixels and byte-exact non-target data;
- Line and Guide were unchanged;
- the helper reported one start stroke, one end stroke, one top-level Undo
  command, one transaction command, and one published transaction;
- one normal Krita Undo restored exact S0, and one Redo restored exact S1;
- selection, foreground, active node, and captured view/tool state were
  unchanged except for the normal document-modified flag;
- the disposable document closed without save, the source fixture remained
  byte-identical, the prior view and `sys.path` were restored.

This is the architectural classification
`NATIVE_TRANSACTION_PROTOTYPE_PASS`. Row G remains failed on the historical
production fill implementation, and formal production Row I remains untested.

### Minimum production architecture

The existing Python application plan, correction precedence, selection
eligibility, and `CanvasColorBridge` remain authoritative. For one user Apply,
Python now:

1. revalidates the immutable scan context and complete application plan;
2. reads the whole target's exact native BGRA/U8 bytes and requires equality
   with the frozen Coloring snapshot, including RGB under alpha zero;
3. converts each final source-profile RGB through the existing qualified
   `CanvasColorBridge` into target-profile ordered RGB;
4. writes those final colors into an expected-after byte image and merges the
   complete, strictly sorted pixel set into nonoverlapping same-row runs;
5. loads one exact helper, sends every selected gap and every color in one
   `apply_exact_patch` call, validates its command counters, waits for Krita,
   and requires the complete target raw image to equal expected-after.

Apply Selected and Apply All therefore share the same invariant:

```text
one user Apply -> one Python native call -> one native stroke -> one transaction
```

The production route no longer calls
`fill_selection_foreground_color`, constructs a selection, changes foreground
or paint state, or uses direct Python `setPixelData` recovery. There is no
fallback to the historical fill action. A successful native call followed by
a Python full-layer mismatch fails loudly and instructs the user to invoke one
Undo; it does not create a second cleanup/history command.

The production document token reuses Phase-6 scan provenance instead of a
saved path. Python freezes the LibKis image-root node UUID together with its
existing document/view object identity and full node/content provenance. The
native helper enumerates `KisPart::instance()->documents()` and requires that
UUID to resolve to exactly one open `KisImage` root. This supports unsaved
documents without path ambiguity, fails closed if multiple documents match,
and naturally rejects a closed/reopened image because the root UUID changes.
It never chooses `activeDocument()`.

Inside only that resolved image, the helper recursively counts the exact target
UUID and requires one paint-layer match whose image/device binding, dimensions,
origin, bounds, editability, lock/animation/visibility/opacity/composite/alpha
state, RGBA/U8 pixel size, and profile match the Python request. Active node is
irrelevant. Runs must be nonempty, sorted, nonoverlapping, in-bounds, below the
pixel/payload caps, and contain exact expected-before bytes. An outer image
barrier validates before scheduling; the exclusive stroke command resolves and
validates again before constructing the transaction.

After the transaction starts, a C++ exception or replacement-readback mismatch
calls `KisTransaction::revert()`, destroys the transaction, verifies all
expected-before run bytes, and publishes no successful Undo command. On success
`endAndTake()` supplies the one transaction command, which is added once through
the post-execution Undo adapter. Native and Python both use strict byte equality;
there is no alpha-zero equivalence.

### Exact production helper identity and packaging

The helper is production-named
`gapfill_krita_native_5_3_3.cp313-win_amd64.pyd`, version
`1.0.0-krita-5.3.3-858d352`. It admits exactly Windows x64, Krita
`5.3.3 (git 858d352)`, Qt 5.15.7, and CPython 3.13.5. Python checks the host
before import, the expected file SHA before import, the loaded module's exact
resolved path and hash after import, ABI metadata, and operation presence. The
C++ module independently checks process architecture, exact Krita/Qt/Python,
and the GUI thread. Unsupported or mismatched hosts fail closed with no old
fill/direct-write fallback.

The production build source is
`krita-plugin/native/krita_5_3_3/gapfill_krita_native_5_3_3.cpp` (SHA-256
`72fc77cbcc93b41028925319d7dfb48e2d0c2fd9b6d9b3eed2edd6b6adaa412d`),
with the pinned build script
`da089b936a5363a70574a4b6df6adb6be3d07d6c5fb2c766e2135d1f9c17b8bc`
and import definition
`b3c64f7c71b3748c238785d599266c59daa5477f578575b81e9cf28b5c5ecf73`.
Two independent output directories produced byte-identical 1,328,128-byte
binaries at SHA-256
`ad2fa7463d59dca74a92dc867734b38eb7aa49821b163547da442147348f8746`.

Static inspection identifies PE32+ AMD64, Windows GUI DLL, zero COFF timestamp,
large-address-aware, ASLR/high-entropy/NX, and the single export
`PyInit_gapfill_krita_native_5_3_3`. Its non-system imports are only the pinned
host's `python313.dll`, Krita UI/image/pigment/command/version/global DLLs,
Qt5 Core, libc++, and libunwind; it does not bundle a second runtime. The ZIP
path is exactly:

```text
gapfill_krita/_native/gapfill_krita_native_5_3_3.cp313-win_amd64.pyd
```

The builder validates the filename/hash, includes the action metadata, uses
fixed timestamps/modes and sorted entries, and excludes caches. Krita must be
fully exited before binary replacement because Windows locks loaded `.pyd`
files.

### Focused and full regression evidence

The focused native-loader/adapter/host-contract/build suite passed **44/44**.
It covers exact-host admission and every host-cell mismatch, missing/wrong-path/
wrong-hash/import/ABI rejection, run ordering/merging/bounds/duplicates,
native BGRA layout and hidden-RGB expected-before payloads, one-call Apply
Selected, one-call multi-color Apply All, no selection/tool changes, native
failure mapping with verified rollback, strict full-layer mismatch handling,
and an unreachable legacy fill action. These fakes do not prove real-host Undo.

The complete Krita-independent suite passed **72/72**, and Ruff passed. All 39
non-vendored Python sources compiled via `compile()` without writing bytecode.
The source ZIP built successfully, passed ZIP integrity, contained desktop,
action, package, model/sidecar and the native package initializer, and correctly
omitted both binary dependencies and the optional `.pyd`. Web reference tests
passed **15/15** with zero skips; ESLint and the TypeScript/Vite build passed.
No sanitizer result is claimed for the version-pinned Windows/Krita native
binary in this WSL environment, and no new real-Krita matrix row was executed.

The canonical frozen hashes remain exact:

| Frozen input | SHA-256 |
|---|---|
| Fixture manifest | `6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c` |
| ONNX model | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78` |
| Model sidecar | `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5` |

### New release candidate and prepared host harnesses

The final qualification candidate is:

```text
/tmp/gapfill-krita-phase6.5-native-transaction-win-x64-py313-b4acabf-worktree-final-c.zip
SHA-256 46c98b98ec16a7618842db1a0b9f1da59af3ccebce583552a29fca3b7428c1bf
size 48,197,789 bytes
895 file entries; 103,302,091 uncompressed bytes
canonical per-entry manifest SHA-256
62178de2bc63659a6680e6c0ff5e852b242f7b6723ae41d2d234e80d6a3de5b1
```

An independent `final-d` build is byte-identical (`cmp` and SHA-256 pass), and
ZIP integrity passes. The model, sidecar, and native helper entries have their
frozen/pinned hashes above. The candidate is also staged, byte-identically, at:

```text
C:\Users\marck\AppData\Local\Temp\gapfill-phase65-production-native-b4acabf-v1\
gapfill-krita-phase6.5-native-transaction-win-x64-py313-b4acabf-worktree.zip
```

Formal production Row-G-only and Row-I-only harnesses are prepared in that same
staging directory. Their WSL source paths and SHA-256 values are:

| Prepared file | SHA-256 |
|---|---|
| `/tmp/gapfill_phase65_production_requalification_common.py` | `3ed60727011c8ca394de6e79dd6648827386eda95be50141b860c4213a723f26` |
| `/tmp/gapfill_phase65_rowg_production_native_b4acabf_v1.py` | `302848e977bf836b767bfcd10d568bb87ea7f12d5a3f3aded1c76349ac9cd3b1` |
| `/tmp/gapfill_phase65_rowi_production_native_b4acabf_v1.py` | `76d9486e0b330256888e09b5650faa332b3b0a9359b8f63548d62ecfdeba30ef` |

Both wrappers and their common implementation pass syntax and Ruff checks. The
common harness verifies the exact ZIP and installed tree, frozen model/sidecar,
native binary, unchanged 64×64 fixture, exact host cell, and fresh output
directory before mutation. Row G uses fresh disposable documents to test
production corrected-decision Apply Selected (18 exact pixels) and production
Apply All (187 exact blue/red pixels), requiring one native call per user Apply,
whole-target byte equality, unchanged Line/Guide, and unchanged editor state.
Row I uses one production multi-color `apply_all()`, requires one native call,
then at most one normal Undo to exact S0 and—only if that passes—one Redo to
exact S1. Both preserve raw arrays/JSON and close disposable documents without
saving.

The guarded future output directories are:

```text
C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowg-production-native-b4acabf-v1
C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowi-production-native-b4acabf-v1
```

Both directories were confirmed absent after preparation. Neither harness was
executed; the installed production plug-in was not replaced in this task.

### Gate state after integration

Production integration and a deterministic qualification candidate are
complete, but host qualification has not advanced. The authoritative matrix
remains **A–F PASS; G FAIL; H–V UNTESTED**. Row I remains **UNTESTED** and a
release blocker. Phase 6.5 remains **OPEN / FAILED**, and Krita remains not
release-qualified. Rows H/J–V and OFFF were not begun.

## Production Row-G requalification harness-preflight attempt 1

The first formal production Row-G requalification attempt used the preserved
v1 wrapper at
`/tmp/gapfill_phase65_rowg_production_native_b4acabf_v1.py` (SHA-256
`302848e977bf836b767bfcd10d568bb87ea7f12d5a3f3aded1c76349ac9cd3b1`)
and the unchanged production candidate at SHA-256
`46c98b98ec16a7618842db1a0b9f1da59af3ccebce583552a29fca3b7428c1bf`.
It is classified narrowly as
`PRODUCTION_ROW_G_HARNESS_PREFLIGHT_FAIL_ZIPINFO_SORT`. This result does not
qualify the new production mutation backend as either passing or failing.

The preserved guarded evidence is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowg-production-native-b4acabf-v1\result.json`
(1,911 bytes, SHA-256
`e9ff242d577528dbb33d6803497c95d5fbfd274b43f097383d882da8dbc297de`).
It records the qualified Windows 11 / Krita 5.3.3 git `858d352` / Qt 5.15.7 /
CPython 3.13.5 host, the expected artifact hash, and an unchanged source
fixture before and after at SHA-256
`3df7b2087c535d2e4eaab4409f3becb3379886bca8fc82f452bee63148911d79`.
No case JSON, raw-state NPZ, or disposable document was created.

The exact execution boundary, proven from the persisted traceback and v1
control flow, is:

| Boundary | Result | Evidence |
|---|---|---|
| Artifact staged/copied | EXECUTED | The exact artifact and fixture were already present in the guarded staging directory. |
| Artifact SHA verified | EXECUTED | `verify_installed_artifact()` passed its first SHA guard and entered the ZIP. |
| Installed-payload verification begun | EXECUTED | `ZipFile.infolist()` returned entries and reached their ordering step. |
| Installed-payload verification completed | NOT EXECUTED | Ordering raised before the per-entry installed-file loop. |
| Production module import | EXECUTED, Python only | The common module imported the production controller/adapter/types before `run()`; the production native `.pyd` was not loaded. |
| Production scan/snapshot | NOT EXECUTED | `run_row_g()` and `open_case()` were never reached. |
| Apply Selected | NOT EXECUTED | No application case began. |
| Corrected decision | NOT EXECUTED | `fixture_gaps()` was never reached. |
| Apply All | NOT EXECUTED | No application case began. |
| Native apply | NOT EXECUTED | `load_native_helper()` / `apply_exact_patch()` were never reached. |

The defect was the raw-object comparison in v1:

```python
entries = sorted(info for info in archive.infolist() if not info.is_dir())
```

CPython 3.13 correctly reported that two `ZipInfo` objects do not define `<`.
The v2 preflight changes only this harness boundary: it retains complete
`ZipInfo` objects but orders them with `key=lambda info: info.filename`.
Consequently the existing CRC, size, compression, external-attribute,
`archive.read(info)`, installed-path allowlist, installed-file hashing, extra
file detection, and pinned native/model/sidecar checks remain available. The
v1 verifier had no explicit duplicate-member rejection; v2 strengthens this
boundary by rejecting adjacent equal filenames after deterministic ordering,
rather than silently accepting ambiguous duplicate paths. The nearby v1
common helper contains no other `sorted()` call; all v2 nearby sorts operate
on filenames or integer pixel indices.

A host-independent focused regression constructs real `ZipInfo` objects and
checks deterministic filename ordering, retained CRC/file-size/compressed-size/
external-attribute metadata, explicit duplicate-name rejection, unchanged
delegation to the v1 path allowlist and `archive.read(info)`, and both the Row-G
and Row-I wrapper preparation paths without importing or executing Krita. It
passed **4/4** under the available CPython 3.12.3 environment; syntax checks and
Ruff also passed. The actual failure was captured under embedded CPython 3.13.5,
and no raw `ZipInfo` comparison remains in v2. The WSL-to-Windows PowerShell
bridge was unavailable during preparation, so the focused regression was not
separately executed by a standalone Windows CPython 3.13 process.

The corrected files are prepared in `/tmp` and copied byte-identically beside
the preserved v1 stage:

| Prepared v2 file | SHA-256 |
|---|---|
| `/tmp/gapfill_phase65_zip_preflight_v2.py` | `9d9ed5ec9522bec1d2123848b45943188fb4efde6e0150840e85bdcd0fce61b9` |
| `/tmp/gapfill_phase65_production_requalification_common_v2.py` | `ed708b61c22d1a5e242e9d207234f18ecdb17c2ca42088faed77d90cd58cc4ea` |
| `/tmp/gapfill_phase65_rowg_production_native_b4acabf_v2.py` | `51727faab642e3ffc0ac418d0dba2bafe65bd26a15f8d2c6bb7f513b189fe7ce` |
| `/tmp/gapfill_phase65_rowi_production_native_b4acabf_v2.py` | `7923dac9a57c584c6db9db581c7718f9bc9dbf83917bbb9f5f30527aac15a085` |
| `/tmp/test_gapfill_phase65_zip_preflight_v2.py` | `7df377301d5ce805ebabd1a08000077c3abab4073de535bdedaafaacfc47deae` |

Row G v2 preserves the v1 post-preflight cases and acceptance criteria,
including corrected-decision Apply Selected and multi-color Apply All. Its new
guarded output is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowg-production-native-b4acabf-v2`.
Row I shared the same broken verifier, so a corrected v2 wrapper was prepared
with output
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowi-production-native-b4acabf-v2`.
Both output directories remain absent: neither v2 wrapper was executed, and
Row I remains untested.

The qualification artifact was not rebuilt and remains byte-identical. The
fixture manifest, ONNX model, and canonical sidecar hashes remain
`6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`,
`8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`,
and `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5`.
No production source changed for this harness-only repair. The authoritative
matrix remains **A–F PASS; G FAIL (historical production fill); H–V UNTESTED**.
Row I remains **UNTESTED** and a release blocker. Phase 6.5 remains
**OPEN / FAILED**.

## Production Row-G requalification preflight attempt 2 and clean-install v3

The formal production Row-G v2 wrapper at
`/tmp/gapfill_phase65_rowg_production_native_b4acabf_v2.py` (SHA-256
`51727faab642e3ffc0ac418d0dba2bafe65bd26a15f8d2c6bb7f513b189fe7ce`)
was executed once. It is classified narrowly as
`PRODUCTION_ROW_G_PREFLIGHT_FAIL_INSTALLED_ARTIFACT_MISMATCH`; it is not a
PASS or FAIL result for the new production native mutation backend.

The preserved guarded result is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowg-production-native-b4acabf-v2\result.json`
(3,554 bytes, SHA-256
`665842b92bd5d05f6aaec6240cdb1643b7907f18722c630a491deb1a4d1c45eb`).
It records the exact qualification artifact at SHA-256
`46c98b98ec16a7618842db1a0b9f1da59af3ccebce583552a29fca3b7428c1bf`
and source-fixture hashes before and after of
`3df7b2087c535d2e4eaab4409f3becb3379886bca8fc82f452bee63148911d79`.
Only `result.json` exists in the guarded directory; no case JSON, NPZ, or
disposable document was created.

The exact v2 execution boundary is:

| Boundary | Result | Evidence |
|---|---|---|
| Artifact staged/copied | EXECUTED | The pinned ZIP was already present in the guarded staging directory. |
| Artifact SHA verification | EXECUTED | The verifier passed the SHA guard and opened the ZIP. |
| Installed-payload verification | EXECUTED / FAILED | All mapped entries were compared and cache extras scanned; exactness failed before the later pinned-entry checks returned. |
| Production native import | NOT EXECUTED | `native_backend.load_native_helper()` was never reached. |
| Production scan | NOT EXECUTED | `run_row_g()` / `open_case()` were never reached. |
| Apply Selected | NOT EXECUTED | No application case began. |
| Corrected decision | NOT EXECUTED | `fixture_gaps()` was never reached. |
| Apply All | NOT EXECUTED | No application case began. |
| Native apply | NOT EXECUTED | `apply_exact_patch()` was never reached. |

The persisted v2 exception printed the verifier's first five differences:
missing `_native/__init__.py` and the production `.pyd`, plus changed
`controller.py`, `host_contract.py`, and `krita_adapter.py`; it recorded no
unexpected extras. The installed plug-in had explicitly not been replaced
before this attempt.

### Pre-replacement installed-tree identity

An independent read-only comparison captured the complete current identity at
`C:\Users\marck\AppData\Roaming\krita`. The installed package root is
`pykrita\gapfill_krita`; it contains 1,006 files: 890 non-cache payload files
and 116 files under `__pycache__` ending in `.cpython-313.pyc`. All 116 are
recognized embedded-CPython cache products. The qualification ZIP expects 893
package files plus one desktop and one action file, for 895 total files.

The independent comparison explains that the persisted v2 message was
truncated to its first five mismatches. The complete installed difference is:

| Entry | Installed state/hash | Expected hash |
|---|---|---|
| `gapfill_krita/_native/__init__.py` | missing | `645d2f51894b14fdac912214213727eea30d8fc6d0cd35f8a73c2725b8c4785b` |
| `gapfill_krita/_native/gapfill_krita_native_5_3_3.cp313-win_amd64.pyd` | missing | `ad2fa7463d59dca74a92dc867734b38eb7aa49821b163547da442147348f8746` |
| `gapfill_krita/native_backend.py` | missing | `7fbadcf164b3e5517b7f2383d1bbbd6ed76af8f73b27bb1d2364c3b6382a2bab` |
| `gapfill_krita/controller.py` | `eb045c85718a39f109695e89c528cc88d968ecf71676c22e018e3c43bcf2cbd8` | `c32bc5638b4ccc0026830394e8cd81cf0b6021e7b5e11b3684c4fae206a8797c` |
| `gapfill_krita/host_contract.py` | `c8a38bb751153034713b13b4a8b28749be7e841dcf48f00b5e07f274d5c64f77` | `eb7e02e2b9aa0138326088eb0c2aa5544d7ff3422fd6b7f4b69b88e72dafd6df` |
| `gapfill_krita/krita_adapter.py` | `5dd75e58d70602d70ffa027b578a508333b1d2319612276012e3d680c9c09bf5` | `c50b52ce5de0dee76460532e0c2e81f929a2ca7cc9a8d7185c9eb030d84a02ac` |
| `gapfill_krita/qt_compat.py` | `bf39554b11457b71e79a74e4c5f629aa0beeae4b644d45dea0d5ca64ce353ab7` | `977f0a6c3ad6f859f87b59021e3ddfc5bb678ff83bdc3844586d2a875a40cf6a` |

The `_native` directory is absent. The installed desktop and action are
present and already exact: respectively
`74ae85fdf002e17af88b2cf5807854eccdc3791d27f88698f85311fd7da2fb6a`
and `f10b3e3a4761659e0695c98326c19ce87b9cfb2c7fa9fa7f7e4e0d6c057d3ff0`.
There are zero unrecognized package extras.

### Deterministic offline replacement

The selected route is an offline resource-folder replacement, not Krita's
in-process Python Plugin Importer. A package containing a version-pinned
native `.pyd` must be replaced while every `krita.exe` process is fully
exited; an in-process importer cannot provide that lock/lifecycle guarantee.
The only admitted artifact remains
`/tmp/gapfill-krita-phase6.5-native-transaction-win-x64-py313-b4acabf-worktree-final-c.zip`
at the SHA-256 above. It was not rebuilt or modified.

The prepared, unexecuted PowerShell procedure is
`/tmp/gapfill_phase65_clean_install_production_native_b4acabf_v3.ps1`,
SHA-256
`0a8bbf9a53709c884dcfb92876df7a994acafb2409d504dd00893e42ff534036`.
It refuses to proceed if `krita.exe` exists, if its fresh stage or backup guard
already exists, if the artifact hash/count/member paths/duplicates differ, or
if the pinned native/model/sidecar hashes differ. It expands and verifies all
895 files before changing the resource tree.

Replacement is limited to these three GapFill targets:

```text
C:\Users\marck\AppData\Roaming\krita\pykrita\gapfill_krita
C:\Users\marck\AppData\Roaming\krita\pykrita\gapfill_krita.desktop
C:\Users\marck\AppData\Roaming\krita\actions\gapfill_krita.action
```

The whole old package directory—including stale payload and recognized
caches—is moved, not deleted, to
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-clean-install-backup-b4acabf-v3`.
The exact artifact is expanded first under the separately guarded
`gapfill-phase65-clean-install-stage-b4acabf-v3` directory. The three targets
are then moved into place and every installed file is hashed again. Failure
after replacement begins moves the new targets aside and restores preserved
old targets. Other plug-ins, actions, brushes, documents, configuration,
credentials, and all unrelated Krita user resources are outside the target
set and remain untouched. Recognized caches may be regenerated only after a
fresh Krita start.

### Prepared read-only v3 preflight and row harnesses

The read-only verifier is
`/tmp/gapfill_phase65_installed_artifact_verifier_v3.py`, SHA-256
`e2dbaaa04aaeb67e87a07dc51ae91247c698cd83ab68fd5f2d5dcc7f750e8bd0`.
After restart and before scan/application it requires all 895 mapped files and
hashes, exact desktop/action/native/model/sidecar, no duplicate/unsafe paths,
no unexpected package files, and permits only extras located under
`__pycache__` whose names end in `.cpython-313.pyc`. It reports the complete
missing/changed/unexpected sets rather than truncating them.

The v3 common helper then calls the production fail-closed native loader and
records the loaded module path/hash, complete `abi_info()`, and callable
operation identity without invoking `apply_exact_patch`. Only after both
preflights pass does it enter the unchanged v2 Row-G application flow and
byte-exact acceptance checks. Prepared identities are:

| Prepared v3 file | SHA-256 |
|---|---|
| `/tmp/gapfill_phase65_production_requalification_common_v3.py` | `250c182f6a467381bf0209611a38053911d7daf2a34086886cd66e9e88900622` |
| `/tmp/gapfill_phase65_rowg_production_native_b4acabf_v3.py` | `0a6262a6a552962168570f15568b42f33d83fa5cf511781afbd47120fb0ae9f4` |
| `/tmp/gapfill_phase65_rowi_production_native_b4acabf_v3.py` | `88115937e8f279d9c055ea9aa6b459f70d0a3900b4645cbc10a8bfc394286ccb` |

The new guarded outputs are respectively
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowg-production-native-b4acabf-v3`
and
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowi-production-native-b4acabf-v3`.
Both remain absent. Neither v3 harness, Row G, nor Row I was executed. Row I v3
was prepared because it shares the stricter installed/native preflight; Row I
remains untested.

The focused v3 verifier/preparation regression passed **6/6**, with PyCompile
and Ruff passing. Windows PowerShell 5.1's parser accepted the prepared
installer with zero syntax errors. The installer itself was not run. No
installed file or production source was changed.

The six production-required files hidden by local
`.git/info/exclude:10:/krita-plugin/` remain an eventual-commit release hygiene
blocker and must become tracked before the production work is committed. The
authoritative matrix remains **A–F PASS; G FAIL (historical production fill);
H–V UNTESTED**. Row I remains **UNTESTED** and a release blocker. Phase 6.5
remains **OPEN / FAILED**; OFFF was not begun.

## Production-native Row-G and Row-I v3 real-host qualification

After the deterministic offline replacement, the exact production-native
qualification artifact at SHA-256
`46c98b98ec16a7618842db1a0b9f1da59af3ccebce583552a29fca3b7428c1bf`
was exercised in the qualified Windows 11 x64 / Krita 5.3.3 git `858d352` /
Qt 5.15.7 / embedded CPython 3.13.5 host. This new evidence is appended; it
does not replace the historical native-fill Row-G failure, COPY failure,
prototype proof, v1 ZipInfo harness failure, or v2 installed-artifact mismatch
recorded above.

Both v3 runs passed the read-only installation/native preflight before any
mutation. Row G verified all 895 packaged files with zero missing, changed, or
unexpected payload entries and 106 recognized CPython 3.13 caches; Row I did
the same with 107 regenerated caches. Both loaded the expected production
native helper from the installed `_native` package at SHA-256
`ad2fa7463d59dca74a92dc867734b38eb7aa49821b163547da442147348f8746`,
validated its complete pinned ABI metadata and callable operation, and retained
the frozen model and sidecar hashes.

### Row G — production apply multiple colors: PASS

The preserved capture is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowg-production-native-b4acabf-v3`.
Its top-level `result.json` is 28,226 bytes, SHA-256
`0a6a8d17cceddfac44677b165bb0adb8a710ff870f9abf288cd284745d67e6b5`,
and records final status `PASS`.

Corrected-decision Apply Selected passed with:

- exactly 18 target and 18 changed pixels;
- zero missing, unexpected, or wrong-valued target pixels;
- byte-exact non-target data and complete target raw equality;
- unchanged Line and Guide;
- one production native apply call; and
- one top-level Undo command, one transaction command, and one published
  transaction.

Its case JSON/NPZ hashes are respectively
`62408b40e9a50059fa739c192e349e78da0cb3d0602e0781571ac89a1e963527`
and `cb1f965cd1332c12c0f436a8b5cd0f9cb479a4de9fc6c617a2620eb4280a28ca`.

Apply All passed with:

- exactly 187 target and 187 changed pixels;
- zero missing, unexpected, or wrong-valued target pixels;
- byte-exact non-target data and complete target raw equality;
- unchanged Line and Guide;
- one production native apply call; and
- one top-level Undo command, one transaction command, and one published
  transaction.

Its case JSON/NPZ hashes are respectively
`9692a6383897c17fee1b318d7ecd56e72e49bf797936099dcafcca1c268ec5f4`
and `53d1344c1f387a9d8fd83067b95d663b9a0fd00887d8e49cbb2d80c7c3f4b371`.
Both disposable documents closed without saving, and both retained the exact
source-fixture SHA-256
`3df7b2087c535d2e4eaab4409f3becb3379886bca8fc82f452bee63148911d79`.
Therefore authoritative Row G is now **PASS** for this tested host/artifact
cell.

### Row I — production one-step Undo/Redo: PASS

The preserved capture is
`C:\Users\marck\AppData\Local\Temp\gapfill-phase65-rowi-production-native-b4acabf-v3`.
Its top-level `result.json` is 24,142 bytes, SHA-256
`aca8687b10203118b3e36196937d94e2546d996e84047a136f209467cecbf5a0`,
and its authoritative raw-state NPZ is SHA-256
`72b094172f967c6231f73222ada818b82c49a53a37be68cb0b827ef6992fc223`.

The run made exactly one production Apply and one native apply. The helper
reported one top-level Undo command, one transaction command, and one
published transaction. Exactly one normal Krita Undo restored exact S0, and
exactly one Redo restored exact S1; the counters are one Apply, one native
apply, one Undo, and one Redo. Line and Guide remained exact, the disposable
document closed without saving, and the source fixture remained byte-identical.
Therefore authoritative Row I is **PASS** and the demonstrated one-step Undo
release blocker is resolved for this tested host/artifact cell.

### Current Phase 6.5 gate

The authoritative matrix is now **A–G PASS; H UNTESTED; I PASS; J–V
UNTESTED**. Phase 6.5 remains **OPEN** because H and J–V have not been run.
Krita is not yet release-qualified across the Phase 6.5 matrix. No H/J–V row
or OFFF work was begun by this evidence update.

The final staged-clone audit found that the native recipe had relied on a
pre-existing 82-byte `spike/include/pyconfig.h` wrapper in its external build
workspace. The tracked build script now generates that wrapper itself from the
pinned external CPython 3.13.5 `PC/pyconfig.h.in` before compilation. At the
default qualified workspace path the generated bytes are exactly the bytes
used by the qualified build; compile/link flags and production source are
unchanged. This is a build-reproducibility repair only. The qualified artifact
was not rebuilt and no additional host row was run.
