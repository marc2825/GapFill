# Phase 3 — CSP companion/CLI data safety

Date: 2026-08-14

Branch: `fix/csp-data-safety`

Baseline: `7e6afaf6ded88c8aa4c7b7bbd98f14a1f5a4b072`

This phase fixes only audit findings C-04, C-05, C-06, and C-11. It does not
change the CSP detector, owner-region algorithm, rule predictor, confidence
formula/bands, ONNX status, line/guide architecture, Web, ML, Krita, or the CSP
SDK adapter. No commit was created.

## Baseline and red regressions

The branch and clean baseline were recorded with `git status`,
`git branch --show-current`, `git rev-parse HEAD`, and `git diff --check`.
Before production edits, Make passed 25/25 core tests, all 38 explicitly
non-canonical CSP characterization rows, the Phase 2 reader, and PNG E2E.
Release CMake/CTest passed 5/5. ASan/UBSan passed 5/5 with leak checking
disabled; LSan was unavailable under ptrace. The neutral validator, nine
reference unit tests, and Python characterizer passed.

The new regressions were then observed failing against the unchanged baseline:

- bulk helpers replaced explicit Skip/Mark decisions;
- contradictory duplicate decision-file entries were silently order-dependent;
- a forged opaque candidate was accepted by correction generation;
- the CLI accepted an input/output alias and changed the input bytes.

## Findings closed in the pure/CLI boundary

### C-04 — path and output safety

Root cause: the CLI encoded directly to each requested path without a complete
path plan, identity check, existing-output policy, or rollback.

Fix: the CLI now constructs and validates every active output role before
analysis. Existing files use filesystem identity checks, catching symbolic and
hard links where supported; missing paths use normalized absolute/weakly
canonical identity without case folding on this case-sensitive platform. The
input and all outputs must be pairwise distinct. Existing outputs fail unless
`--force` is present, and force cannot bypass alias checks.

All PNG, manifest, contact-sheet, and saved-settings bytes are generated before
filesystem commit. Each output is staged under a unique hidden name in its
destination directory. Existing files are moved to recoverable backups before
the staged files are renamed into place. Reported staging/rename failures remove
new files and restore prior files. Tests inject temporary-write, backup-rename,
final-rename, pre-cleanup, and encoding failures.

This is deliberately described as best-effort process-level rollback, not an
OS-level multi-file transaction. The implementation does not `fsync` files or
directories. Abrupt process/OS loss can leave a destination missing with its
hidden backup still available, and a backup-cleanup failure can leave a hidden
recovery file. Filesystem races outside the process and Windows-specific path,
locking, antivirus, and durability behavior remain platform qualification work.

### C-05 — explicit decision precedence

Root cause: `applyHighConfidence()` and selected bulk helpers wrote a new state
without checking the candidate's current review state.

Fix: `apply-high`, apply-all-remaining-high, apply-selected, and skip-selected
act only on `Unreviewed` candidates. Explicit Apply, Skip, and Mark Only remain
unchanged. Exact duplicate identical decision-file rows are idempotent;
contradictory duplicates fail clearly.

### C-06 — settings/CLI precedence

Root cause: argument parsing mutated the final `Settings` object while walking
argv, so a later `--settings` replaced earlier explicit values.

Fix: parsing now records a settings path and typed optional overrides, loads the
last requested settings file once, and applies explicit overrides once afterward.
The order is defaults, settings file, then CLI. Repeated instances of the same
CLI option use the conventional last-occurrence-wins rule. Settings loading now
rejects unreadable, malformed, unknown, out-of-range, or invalid values rather
than silently defaulting or clamping them.

### C-11 — stale/forged correction candidates

Root cause: correction generation trusted candidate indices and metadata and
silently skipped an out-of-range index.

Fix: analysis now attaches a compact source/selection fingerprint plus image
dimensions and candidate-producing settings provenance. Correction generation
validates that context and the complete candidate set before allocating or
writing outputs: IDs and per-candidate indices are unique, candidates do not
overlap, all indices are in range, area/bounds/finite centroid match the pixel
set, every target is still canonical alpha 0, and Selection Only targets remain
inside the bound selection. Any invalid member rejects the complete set.

The pure engine can bind only the in-memory snapshot it receives. The future CSP
adapter must still prove that the host document/layer does not change between
host read and host commit. The fingerprint is a stale-state guard, not a
cryptographic authentication mechanism.

## Regression coverage

- C-04: all six active CLI output roles against the input; all 15 inter-output
  pairs; textual, normalized, relative/absolute, symbolic-link, and hard-link
  aliases; existing-output refusal; force replacement; source-byte invariance;
  successful staged commit; encoding and four deterministic commit failures;
  cleanup and rollback of both existing and newly requested outputs.
- C-05: mixed Unreviewed/Apply/Skip/Mark tables for high-confidence,
  apply-selected, and skip-selected helpers; loaded Skip and Mark plus
  `--apply-high`; contradictory and identical duplicate decisions.
- C-06: settings-file placement permutations across selection, mode, gap size,
  alpha threshold, confidence, connectivity, predictor, highlight, and debug;
  repeated-option last-wins; normalized settings equality; applicable output-byte
  equality; invalid CLI and settings values.
- C-11: opaque, partial-alpha, out-of-range, duplicate, overlap, duplicate-ID,
  wrong-area/bounds/centroid/nonfinite-centroid, wrong-dimension,
  outside-selection, changed-selection, missing-selection, changed-settings, and
  stale-source cases; the source remains unchanged and no partial candidate set
  is generated.

## Final verification

The final commands/results are:

- `make -C experimental/csp-plugin clean` and `make -C experimental/csp-plugin -j2 all`: pass with GCC
  13.3.0 and C++20 warnings enabled;
- `make -C experimental/csp-plugin test`: pass, 35/35 core and focused safety tests, the
  expanded Python CLI safety suite, and all 38 frozen CSP rows;
- `make -C experimental/csp-plugin test-e2e`: pass, PNG fixture/create/apply/verify;
- `python -m scripts.gapfill_reference.validate`: pass;
- `python -m unittest scripts.gapfill_reference.test_reference -v`: pass, 9/9;
- `python -m scripts.gapfill_reference.characterize_python`: pass, 19 detection,
  13 patch, eight postprocess, and seven model cases; maximum model delta `0.0`;
- clean Release CMake configure/build: pass;
- Release CTest: pass, 6/6 (core/safety, 38-row reader, PNG chain, CLI safety);
- CMake install and installed-CLI PNG smoke: pass;
- Debug ASan/UBSan CTest with `detect_leaks=0`: pass, 6/6 with no diagnostics;
- LSan with `detect_leaks=1`: unverified/fails before tests because LeakSanitizer
  reports that it cannot run under ptrace;
- `git diff --check`: pass.

Frozen Phase 2 hashes are unchanged:

- `manifest.json`: `6243be8f2a26b383ef0293bd585318c0072011ccabf959cb25f42127aba5908c`
- `characterization.json`: `353787fb3c94a8d477183629e9df78b6a942b74c8d9c81de343aa552d9b584e9`
- `csp_detection_current.csv`: `fd15146d8c996b72c7a9e2abf0f1e6c0d843ef6e06cf71b51306f621872af118`

No detection, candidate-membership, prediction, confidence, or suggested-color
golden changed. The detector, owner-region, and predictor source files have no
diff. Phase 2's known semantic mismatches remain deliberately open.

## Changed files and audit classification

- C-04: `src/io/atomic_output.*`, `src/io/png_io.*`,
  `src/io/review_artifacts.*`, `src/cli/main.cpp`, build files, CLI fixture and
  safety tests, plus README/spec/limitations documentation.
- C-05: `src/ui/review_session.cpp`, `src/io/review_artifacts.cpp`, and tests.
- C-06: `src/cli/arguments.*`, `src/core/settings.*`, `src/cli/main.cpp`, and
  tests/documentation.
- C-11: `src/core/candidate_context.*`, `src/core/correction_output.*`,
  `src/core/image_types.hpp`, `src/core/smart_gap_propagation.*`, context plumbing
  in `src/core/quick_fix_pipeline.cpp` and
  `src/plugin_entry/gap_assist_command.cpp`, and tests/documentation.
- Test/build integration: `experimental/csp-plugin/CMakeLists.txt`, `experimental/csp-plugin/Makefile`,
  `experimental/csp-plugin/tests/cli_fixture.cpp`, `experimental/csp-plugin/tests/phase3_cli_safety.py`, and
  `experimental/csp-plugin/tests/test_main.cpp`.
- Phase record: this file.

Real CSP/CELSYS, MSVC/Windows, native Preview/Undo/writeback, and host snapshot
lifetime remain unverified. C-01, C-02, C-03, C-07 through C-10, and C-12 through
C-16 remain open. Phase 3's pure/CLI acceptance and semantic-preservation gates
are satisfied, so the repository meets the recorded entry condition for a
separately authorized Phase 4. Phase 4 was not started.
