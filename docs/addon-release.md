# GapFill 1.0.0 Krita release/freeze preparation

> **Published 1.0.0 packaging issue:** the qualified file payload was published,
> but its ZIP omitted explicit directory members required by Krita's Python
> Plugin Importer. Normal **Tools → Scripts → Import Python Plugin** discovery
> reports “No plugins found in archive.” Manual resource-folder extraction is
> still possible. The packaging-only 1.0.1 hotfix is recorded in
> `docs/addon-release-1.0.1.md`; runtime and model behavior are unchanged.

Status: **GAPFILL RELEASE/FREEZE READY**. This record prepares the frozen
GapFill implementation for review; it does not create a release commit, tag,
push, or published release.

The first canonical overall GapFill plug-in version is **1.0.0**, governed by
`GAPFILL_RELEASE_VERSION_V1_GOVERNANCE_ADOPTED`. Its prospective release tag
is `krita-v1.0.0`; that tag is prepared but is not created by this checkpoint.
The canonical version source is `krita-plugin/release/freeze.json`.

Publication is governed separately by
`GAPFILL_1_0_0_FROZEN_ARTIFACT_PUBLICATION_V1_GOVERNANCE_ADOPTED`: GapFill
1.0.0 publishes the exact qualified frozen Windows artifact committed at
`krita-plugin/release/artifacts/gapfill-krita-windows-x86_64.zip`. Tag CI is a
**verify-and-publish** path; it does not rebuild qualified production bytes.

## Frozen candidate

The production and qualification source checkpoint is
`df4e18c0b3f5e4ca8135ca52cba0b415ad3d52c8` on
`qualify/csp-host-adapter`. Phase 6.5 is **CLOSED** with A–P and R–V PASS and Q
closed as `ROW_Q_HOST_CONDITION_UNAVAILABLE`, not PASS. The detailed evidence
and historical failures remain in `docs/addon-phase6.5.md` and
`krita-plugin/host_tests/matrix.json`.

The authoritative release/freeze metadata is
`krita-plugin/release/freeze.json`. Its subordinate deterministic source and
archive inventories are `krita-plugin/release/source-freeze.json` and
`krita-plugin/release/artifact-entries.json`.

## Existing release model

- `krita-plugin/scripts/build_plugin.py` is the canonical deterministic ZIP
  builder. It uses sorted entries, fixed 1980 timestamps, fixed regular-file
  modes, and DEFLATE level 9.
- `.github/workflows/krita-plugin-bundles.yml` publishes the committed frozen
  Windows artifact for a `krita-v*` tag only after exact verification. Its
  separate manual-dispatch matrix retains development/unqualified bundle
  generation and is not the GapFill 1.0.0 publication path.
- Before this freeze, the repository had no overall GapFill Krita plug-in
  version field and no existing `krita-v*` tag. The model's `1.0` and native
  helper's `1.0.0-krita-5.3.3-858d352` identify those components, not the
  plug-in release. With no historical overall release conflict, this freeze
  adopts `1.0.0` as the first canonical overall plug-in version and
  `krita-v1.0.0` as its release tag.
- The existing release checklist is the Krita README's Release Smoke Test plus
  the audit's Phase 8 acceptance criteria. No independent checksum-file naming
  convention exists.

## Artifact proof

Two independent fresh builds used the exact qualified Windows CPython 3.13
vendor tree and pinned native helper. Both produced:

| Property | Result |
| --- | --- |
| Filename | `gapfill-krita-windows-x86_64.zip` |
| SHA-256 | `7001c1bf92aa7abb5840baf52fe07457ab06cb80074297488e67ded212ab74e2` |
| Size | 48,197,787 bytes |
| Entries | 895 files |
| Uncompressed size | 103,302,091 bytes |
| Build A vs. B | byte-identical; `cmp` PASS |
| Historical qualified artifact | byte-identical by exact SHA-256 |
| Historical per-entry manifest | `14ab81ed4d6688a0e8da9800a032db53158e91c6094b8f7b5f88ed7e50cad2f61` |
| Production payload drift | none |

ZIP integrity passed. The archive has no session file, test, qualification
harness, cache, bytecode, repository metadata, absolute path, traversal path,
or duplicate entry. Desktop/action metadata, the production package, exact
native helper, vendored NumPy and ONNX Runtime, ONNX model, and canonical
sidecar are each present exactly once.

The source freeze inventory contains 901 inputs: all plug-in source/resources,
metadata, model/sidecar, package builder, runtime requirements, native source
and build recipe, 866 qualified vendor files, and the qualified native binary.
The package-local sidecar is explicitly recorded as shadowed because the
canonical builder replaces it with `web/public/models/model_info.json`; the
released sidecar is the frozen Line-only version.

The release audit independently proved that the source builder reproduced the
qualified ZIP. The historical native helper's complete external 85-archive
build closure is no longer available to tag CI, so reconstructing a partial
provenance chain would weaken that evidence. Committing and verifying the exact
already-qualified ZIP preserves the stronger byte identity. Release metadata,
the verifier, and this document are outside the packaged production-input and
entry-manifest boundaries; adding them does not change the ZIP payload.

## Install and smoke audit

Build A was extracted and mapped into a fresh disposable Krita resource tree.
The exact historical verifier passed all 895 files with no missing, changed, or
unexpected entries. The real user resource tree was not modified.

From that disposable tree, with repository source absent from `sys.path`, the
packaged module imported, model and native-helper paths resolved inside the
installed package, metadata/action XML parsed, and all 582 packaged Python
sources compiled. The Windows native binary was not loaded in Linux. A new
Krita host launch was intentionally not performed: the newly built ZIP is
byte-for-byte the artifact whose registration, model/runtime/native loading,
controller behavior, and shutdown path are already covered by the closed Phase
6.5 evidence. This packaging smoke does not replace or rerun A–V.

## Supported scope

The release candidate is admitted only for Windows 11 Pro x64, Krita 5.3.3 git
`858d352`, Qt 5.15.7, embedded CPython 3.13.5, and PyQt5 5.15.11. Available
real-host rows A–P and R–V passed. Q remains explicitly unavailable.
Linux and macOS bundles are not part of the frozen 1.0.0 qualified artifact
scope and are not published by its tag path.

Canonical GapFill remains Line-only in model channel 0; Guides affect detection
topology only. Native canonical CSP remains closed as
`INSUFFICIENT_FOR_GAPFILL_PARITY` for the evaluated SDK/adapter combination.

## Explicit limits

- Full Krita application close with an active worker was not formally
  qualified. Row V covers `docker.close()` → `closeEvent()` →
  `controller.shutdown()` while a real worker is active.
- Row T qualifies only the tested alternate RGBA/U8 ACEScg cell. It does not
  qualify mixed profiles, arbitrary other ICC profiles, HDR, or non-U8 data.
- Q's real HiDPI condition was unavailable and is not PASS.
- Opening-like regions such as sleeves remain outside GapFill's intended
  enclosed-gap capability.
- No other OS, architecture, Krita revision, Qt, Python, or PyQt cell is implied
  supported by this artifact.

## Actions remaining after review

1. Review and commit only the release/freeze metadata, documentation, and
   regression test. Proposed subject:
   `docs(krita): freeze GapFill 1.0.0 release`.
2. Use the adopted annotated tag `krita-v1.0.0`, targeting the release-freeze
   commit, only after separate explicit authorization.
3. Publish only the repository-controlled
   `gapfill-krita-windows-x86_64.zip` after the tag workflow verifies its
   frozen SHA-256, size, ZIP integrity, and complete entry manifest.
4. After explicit authorization, tag, push the branch/tag, create the release,
   and publish only the frozen artifact and its recorded checksum. None of
   these actions is performed by this preparation.
