# GapFill for Krita 1.0.2 release preparation

Status: **RELEASE CANDIDATE PREPARATION IN PROGRESS**. No `krita-v1.0.2` tag or
public GitHub Release exists at this checkpoint.

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
- Final release-source and freeze-commit identities will be recorded after the
  deterministic candidate is built and frozen.
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

## Publication boundary

Preparation stops before creating or pushing `krita-v1.0.2`, creating a GitHub
Release, or uploading the public production asset. Those operations require a
separate explicit authorization after the committed release candidate and its
normal CI matrix are green.
