# GapFill for Krita 1.0.2 release preparation

Status: **GAPFILL 1.0.2 RELEASE CANDIDATE PREPARED — LOCAL VERIFICATION AND
NORMAL CI PASS**. No `krita-v1.0.2` tag or public GitHub Release exists at this
checkpoint.

GapFill for Krita 1.0.2 is an interaction/lifecycle patch over the immutable
1.0.1 release. The user-facing product name is **GapFill for Krita**; the
technical module, package directory, imports, and `X-KDE-Library` identity
remain `gapfill_krita`. The prospective tag remains `krita-v1.0.2`, and the
production Windows asset is named `gapfill-for-krita-windows-x86_64.zip`.

## Prospective release notes

### GapFill for Krita 1.0.2

This release updates the GapFill Python plugin/add-on for Krita with focused
interaction and session-lifecycle fixes:

- Scan / Activate remains active as candidates are applied.
- Remaining candidates retain the original frozen scan and prediction; no
  automatic rescan or inference is performed.
- Known adjacent GapFill Undo/Redo steps reconcile exact session checkpoints
  and restore candidate state.
- Undo of a corrected Apply restores the candidate's original frozen prediction
  instead of a stale correction preview.
- Immediate known GapFill Undo can restore an exhausted session.
- The interactive overlay no longer blocks ordinary pointer movement.
- Hover magnification works through the passive event bridge and samples the
  source represented inside the popup, not the obscured physical canvas.
- The dotted correction connector targets the final displayed magnifier center.
- Sweep-to-apply pointer routing is repaired and displays a temporary pale
  yellow-green trail.
- Detector, model, prediction, and native-transaction semantics are unchanged.
  Prediction still uses `CPUExecutionProvider`; GPU/performance work remains a
  future task.

Qualified release platform: Windows x86_64 for the recorded Krita 5.3.3 host
cell only. See [the bounded interaction evidence](addon-interaction-1.0.2.md)
and historical Phase 6.5 limits before publication.

## Preparation identities

- Starting interaction branch checkpoint: `039be0199d84e4a260d1df52cb4ace6ddfaccea8`.
- Host-tested repair commit: `d48366d` (`fix(krita): harden interaction routing and undo restoration`).
- Current preparation branch: `fix/gapfill-interaction-session`.
- Release-source commit: `d0e1fbfb825d983d5a208f9b3990418a821f1160`
  (`chore(krita): prepare GapFill for Krita 1.0.2 source`).
- Release-candidate freeze commit:
  `232db61f79e4d100a19978e82013868430950c59`
  (`docs(krita): freeze GapFill for Krita 1.0.2 candidate`).
- Publication governance:
  `GAPFILL_1_0_2_INTERACTION_LIFECYCLE_PATCH_V1_GOVERNANCE_ADOPTED`.
- Publication mode: `FROZEN_ARTIFACT_VERIFY_AND_PUBLISH`; tag CI must verify and
  upload the committed bytes rather than rebuild them.

## Qualification boundary

The patch-specific host result is
`GAPFILL INTERACTION PATCH BOUNDED REAL-HOST SMOKE PASS`. The intentionally
omitted case remains
`MANUAL_EXTERNAL_MUTATION_FAIL_CLOSED_SMOKE_SKIPPED_BY_SCOPE`; automated
fail-closed regressions cover unknown external state. Historical Phase 6.5
A–V evidence is not rewritten or claimed as rerun.

The frozen ONNX model, model sidecar, fixture manifest, and native helper must
remain at their recorded hashes. OFFF remains paused and is excluded from this
release.

## Frozen release candidate

Two clean-equivalent builds from source commit `d0e1fbf` used the exact
qualified Windows CPython 3.13 vendor tree and native helper. `cmp` proved the
two outputs byte-for-byte identical.

| Property | Result |
| --- | --- |
| Repository artifact | `krita-plugin/release/artifacts/1.0.2/gapfill-for-krita-windows-x86_64.zip` |
| SHA-256 | `34121098dc8f9e50707f686f5585176d0d7067858f21d241e190a2f4f25fa54b` |
| Size | 48,223,574 bytes |
| ZIP entries | 1,012 total: 895 files and 117 directories |
| Importer | `PLUGIN_DISCOVERABLE`; exactly one `gapfill_krita` plugin, UI name `GapFill for Krita` |
| Disposable install | 895/895 files present and byte-identical to the ZIP |

ZIP integrity and the exact frozen-artifact verifier passed. The archive
contains the required `gapfill_krita/` directory, desktop/action metadata,
model/sidecar, native helper, vendored NumPy, and vendored ONNX Runtime. It
contains no OFFF code, tests, caches, bytecode, session file, JSONL evidence,
host harness, or development probe.

Compared with frozen 1.0.1, no ordinary file was added or removed. Exactly
eight packaged files changed: `gapfill_krita.desktop`, `Manual.html`,
`controller.py`, `docker.py`, `host_contract.py`, `krita_adapter.py`,
`overlay.py`, and `qt_compat.py`. These are the reviewed product naming,
persistent-session, passive pointer bridge, sweep trail/routing, known
Undo/Redo checkpoint, and verified host-context changes. Model, sidecar,
vendor, and native-helper bytes did not change.

## Local release-preparation validation

- focused interaction/session/history tests: 38 passed;
- complete Krita/parity suite: 153 passed;
- independent reference suite: 15 passed, validation and Phase 5
  characterization passed with zero model delta;
- Web: 15 passed; lint, preset checks, image-metadata checks, and production
  build passed;
- CSP core: CMake build and all 10 CTest cases passed, including learned
  prediction parity;
- Ruff: passed;
- PyCompile/compileall: passed;
- `git diff --check`: passed.

The frozen identities remain:

- fixture manifest `6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`;
- ONNX `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`;
- sidecar `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5`;
- native helper `ad2fa7463d59dca74a92dc867734b38eb7aa49821b163547da442147348f8746`.

Normal branch CI run
[`33323573954`](https://github.com/marc2825/GapFill/actions/runs/33323573954)
passed for freeze commit `232db61`: Krita plugin job `99289662672`, reference
fixtures job `99289662758`, CSP core job `99289662764`, and Web job
`99289662783` all completed successfully. The Web job reported only the
GitHub-hosted Node.js action-runtime deprecation warning; no project gate
failed. Tag-only publication verification remains an explicit publication step
and was not triggered during release-candidate preparation.

## Publication boundary

Preparation stops before creating or pushing `krita-v1.0.2`, creating a GitHub
Release, or uploading the public production asset. Those operations require a
separate explicit authorization after the committed release candidate and its
normal CI matrix are green.
