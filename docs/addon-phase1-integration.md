# Add-on Phase 1 baseline integration

Date: 2026-08-12 (Asia/Tokyo)
Branch: `audit/addons-hardening`

This note records Phase 1 only: transplanting and freezing the audited Krita and
CSP add-on baseline on the current `origin/main`. No audit finding was repaired,
no production code was refactored, and no algorithmic or test semantics were
intentionally changed.

## Integrated history

`git fetch origin --prune` completed before the refs were verified. The old
stack and its rebased equivalents are:

| Checkpoint | Audited commit | Rebased commit |
| --- | --- | --- |
| Common/new base | `6ae5167d838cc79ae8d05328744a83df40b038e4` | `1341885dbfab562348f5dce4e42824798f5feb6c` (`origin/main`) |
| Krita add-on | `52f8c3fa04414e5f5290016e949941369f070f0c` | `7916dca9e577e51730e47625c15243a5da1e4cd3` |
| CSP add-on | `3a7a07e0f384b3cb2c6f5cb0b306bb11558bbaa3` | `5310688dacfc2aa0842db41e791d615a910bf38f` |
| Audit report | `dafb392ab3ea3a2f15f2cf1902b2106b6a79d1fb` | `b323b8bac18079d0a41861563243f2bca6dbe129` |

The resulting parent chain is `1341885` -> `7916dca` -> `5310688` ->
`b323b8b`. The report was already committed before history rewriting; there was
no uncommitted report-only change requiring a preliminary commit.

No unresolved conflict remained. The only old-to-new checkpoint differences
were `README.md` and `docs/index.html`. Review of those diffs confirmed that the
current-main branch-status, site, and SEO changes were retained alongside the
add-on documentation and links.

## Tree-preservation evidence

`git range-diff 6ae5167..3a7a07e 1341885..5310688` paired both add-on commits.
Path-excluded `git diff --exit-code` comparisons passed for the old/new Krita,
CSP, and audit checkpoints when `README.md` and `docs/index.html` were excluded.
The relevant old/new subtree IDs are identical:

- `krita-plugin`: `5c01aaf660c88e175d46ac5f23fe452d1bb19871`
- Krita checkpoint `.github`: `37b25acc218bb6f020f619c8ca7cff86e9466ac6`
- `experimental/csp-plugin`: `ef6a50fc68658cdee9c05973efad2ac4f831b948`
- CSP checkpoint `.github`: `747d674fc8da26540c6957ab0bad889b4458bb15`
- `docs/addon-audit.md` blob: `139b144d031581b5f5556b70b8cca72781208545`

No unexpected production-tree difference was found.

## Baseline gates rerun

Web reference (`web`, Node `v22.22.1`, npm `10.9.4`):

- `npm ci`: passed.
- `npm test`: 13/13 passed; 0 failed, skipped, cancelled, or todo.
- `npm run lint`: passed.
- `test -s public/models/unet32.onnx`: passed.
- `npm run check:preset-assets`: passed; 30 assets verified.
- `npm run check:image-metadata`: passed; 51 preset PNGs and 17 documentation images verified.
- `GAPFILL_INCLUDE_TASK_C=false npm run build`: passed.
- CI exclusion checks for `dist/preset-images/C` and `coloring_full.png`: passed.

Krita (`krita-plugin`, isolated Python 3.12.3 environment):

- `python -m pytest -ra`: 13/13 passed; no skips.
- `python -m ruff check .`: passed.
- `python -m compileall -q pykrita scripts`: passed.
- `python scripts/build_plugin.py --output /tmp/gapfill-krita-phase1.zip`: passed.
- `unzip -t /tmp/gapfill-krita-phase1.zip`: passed; 23 entries.
- Archive manifest comparison against the audited source ZIP: identical.
- Desktop file, package initializer, and ONNX model presence: verified.
- ONNX payload SHA-256: `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78`, identical to the audited ZIP.
- The known source-ZIP omissions (`gapfill_krita.action` and the project license) remain unchanged.

CSP (`experimental/csp-plugin`, GNU C++ 13.3.0):

- `make clean` and `make -j2 all`: passed.
- `make test`: 25/25 passed.
- `make test-e2e`: passed; PNG fixture creation, CLI application, and correction verification completed.
- `gap_assist_host_contract_probe`: ran; as audited, it prints a checklist and does not exercise a real host.
- Fresh CMake 4.4.2 Release configure/build/install: passed.
- `ctest -C Release --output-on-failure`: 4/4 passed; no skipped tests.
- Fresh ASan/UBSan Debug build and CTest with `ASAN_OPTIONS=detect_leaks=0`: 4/4 passed with no sanitizer diagnostic.

Whitespace checks:

- `git diff --check` for the worktree: passed.
- Rebased Krita and audit-report commit deltas: passed.
- Rebased CSP and full integrated deltas: returned exit 2 only for the already-audited trailing whitespace/new blank line at EOF in `experimental/csp-plugin/third_party/lodepng/LICENSE:21`. It was intentionally not changed in Phase 1.

## Not reverified

- No real Krita/PyQt host was available, so canvas transforms, selection/Undo,
  color management, fill-tool state, overlay input, cancellation, and host
  lifecycle behavior remain unverified.
- The local Krita run used CPython 3.12.3. CPython 3.13 and the workflow's
  per-OS vendored bundles were not rebuilt locally.
- No CELSYS SDK, CSP EX host, MSVC, Windows, or macOS environment was available.
  The private native adapter and real pixel/selection/preview/cancel/Undo
  contracts remain unverified.
- LeakSanitizer remained disabled because the audit environment runs under
  ptrace; ASan and UBSan were rerun successfully.

Phase 2 was not started.
