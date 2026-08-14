# CSP Gap Assist release checklist

The SDK-independent source and CLI may follow this repository's normal MIT release
process. A CSP SDK-linked native binary has additional CELSYS requirements.

## Source and legal boundary

- [ ] No CELSYS headers, sample code, documentation, binaries, confidential names,
      screenshots, or generated SDK artifacts are tracked by Git.
- [ ] No CELSYS logo/trademark is bundled or used to imply endorsement.
- [ ] LodePNG notice/license is present in source and binary documentation.
- [ ] GapFill copyright, privacy policy, and third-party image restrictions remain intact.
- [ ] Native distribution has been submitted through CELSYS's current process and
      the approved delivery method is documented privately.

## Build provenance

- [ ] Version and git commit are recorded.
- [ ] SDK release/date, CSP target version, compiler, OS, and architecture are recorded.
- [ ] Build is performed from a clean checkout plus an untracked/private SDK path.
- [ ] Release archive contains no absolute paths, debug symbols with private paths,
      sample artwork, SDK documentation, or credentials.
- [ ] Binary hash and a software bill of materials are retained.

## Automated verification

- [ ] `make test` or CTest passes all core tests.
- [ ] Phase 5 tensor/ONNX/region/RGB parity passes against the pinned model.
- [ ] The native package contains a supported ONNX Runtime adapter and verifies
      model SHA-256/interface before host mutation; no stub/fallback is presented
      as learned Quick Fix.
- [ ] PNG end-to-end test passes.
- [ ] Sanitizer run passes on a supported development platform.
- [ ] Cross-platform core bundle workflow passes.
- [ ] Native adapter build passes on every platform explicitly supported by the SDK.

## Manual verification

- [ ] Every item in `MANUAL_TEST_PLAN.md` is recorded.
- [ ] A clean CSP profile can install, run, update, and remove the plug-in.
- [ ] Native documentation tells users to duplicate the coloring layer first
      when an editable non-destructive copy is required.
- [ ] The PNG companion leaves its source image unchanged and produces a separate
      correction image.
- [ ] Cancel and errors leave no partial document changes.
- [ ] Native OK creates one normal filter history step and exactly one CSP Undo
      restores the input.

## Publication

- [ ] Store description says “post-process Gap Assist,” not real-time overflow fill.
- [ ] Supported edition, OS, architecture, CSP versions, active-raster-only scope,
      Quick Fix-only native scope, ONNX status, and known limitations are explicit.
- [ ] Privacy statement says local processing/no telemetry.
- [ ] Support contact, issue template, version history, and rollback build are ready.
