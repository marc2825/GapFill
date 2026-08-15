# Add-on Phase 6.5 — Krita real-host qualification

Date: 2026-08-15 (Asia/Tokyo)

Qualification source: `ed7d2e1bc96c14e0f80908bc7d3a01a872a15f55`, the
committed Row-A lifecycle repair.

Status: **Rows A–E PASS** in the recorded real-host cell. Rows F–V were not
started and remain **UNTESTED**. Phase 6.5 remains open, and this record is not
a Krita release qualification.

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
