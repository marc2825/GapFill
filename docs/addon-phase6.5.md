# Add-on Phase 6.5 — Krita real-host qualification

Date: 2026-08-15 (Asia/Tokyo)

Source base: `d387926458f50ae9f99d805279650065eb71caa8` with the
uncommitted Row-A lifecycle repair recorded below.

Status: **Row A PASS** after a successful real-host retest of the replacement
artifact. Rows B–V were not started and remain **UNTESTED**. Phase 6.5 remains
open, and this record is not a Krita release qualification.

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

The source identity is base commit
`d387926458f50ae9f99d805279650065eb71caa8` plus this uncommitted repair.
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

Row A is now **PASS**. Rows B–V remain **UNTESTED** and were not begun. Phase
6.5 therefore remains open, the one-step Undo issue remains a Krita release
blocker, and no Phase 8/release conclusion changes.
