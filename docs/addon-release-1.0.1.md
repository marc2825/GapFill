# GapFill 1.0.1 Krita importer-compatibility hotfix

Status: **GAPFILL 1.0.1 IMPORTER-COMPATIBILITY HOTFIX READY — READY TO TAG**.
This is a packaging-only patch release. It has not been tagged, pushed, or
published by this checkpoint.

## Reason for the patch release

The published GapFill 1.0.0 ZIP contains the correct desktop metadata,
`gapfill_krita/__init__.py`, production package, model, native helper, and
dependencies, but has no explicit `gapfill_krita/` ZIP directory member. Krita
5.3.3's Python Plugin Importer enumerates archive directory members to locate the
module named by `X-KDE-Library`. Consequently, normal **Tools → Scripts → Import
Python Plugin** reports “No plugins found in archive.”

Classification:

```text
GAPFILL_1_0_0_KRITA_IMPORTER_DIRECTORY_ENTRY_PACKAGING_DEFECT
PACKAGING / DISTRIBUTION COMPATIBILITY
```

This is not evidence of a model, algorithm, native transaction, lifecycle, or
Phase 6.5 semantic defect. Manual installation by extracting/copying the archive
contents into Krita's resource folders remained possible.

## Actual importer confirmation

| Item | Evidence |
| --- | --- |
| Krita | 5.3.3, git `858d352` |
| Installed importer | `C:\Program Files\Krita (x64)\share\krita\pykrita\plugin_importer\plugin_importer.py` |
| Importer source SHA-256 | `99e0c5edd82e073f106173106d02f91addef23caa5ab793ee91d7df3a00c8614` |
| Source-module predicate | Find an explicit member equal to `<name>/` or ending in `/<name>/`, then require `<directory>__init__.py` |
| Frozen 1.0.0 result | `PLUGIN_NOT_DISCOVERED`; `REQUIRED_MODULE_DIRECTORY_ENTRY_ABSENT` |
| 1.0.1 result | Exactly one plugin: module/name `gapfill_krita`, UI name `GapFill`, action `actions/gapfill_krita.action` |

The real installed `PluginImporter` class was executed on Windows against the
new artifact and a fresh disposable resource directory. `import_all()` passed,
and exact comparison proved that all 895 archive files were installed with
unchanged bytes. The execution used the installed Krita 5.3.3 importer source;
the UI file chooser and confirmation dialogs were not part of this automated
smoke.

## Minimal deterministic builder fix

`krita-plugin/scripts/build_plugin.py` now emits every directory represented in
the staging tree as an explicit ZIP member. Directory names use POSIX separators
and a trailing `/`. Entries are ordered by normalized archive path and use:

```text
timestamp       1980-01-01 00:00:00
compression     stored
create system   Unix (3)
mode            directory 0755
DOS directory   flag 0x10
```

File-entry timestamp, compression, permissions, CRC, compressed size,
uncompressed size, and content are unchanged. No arbitrary empty directory,
absolute path, traversal path, backslash path, duplicate path, cache, or session
file is present.

## Frozen artifacts and exact delta

| Property | GapFill 1.0.0 | GapFill 1.0.1 |
| --- | ---: | ---: |
| Repository artifact | `krita-plugin/release/artifacts/gapfill-krita-windows-x86_64.zip` | `krita-plugin/release/artifacts/1.0.1/gapfill-krita-windows-x86_64.zip` |
| SHA-256 | `7001c1bf92aa7abb5840baf52fe07457ab06cb80074297488e67ded212ab74e2` | `e001ad4db0a049db23f2839d780ff0ede810fc3f21c2d3fc574ef8bc12c93b19` |
| Byte size | 48,197,787 | 48,218,711 |
| Ordinary files | 895 | 895 |
| Directory entries | 0 | 117 |
| Total entries | 895 | 1,012 |

Every 1.0.0 ordinary file path, uncompressed byte count, SHA-256, and ZIP file
metadata exactly matches 1.0.1. There is no removed, renamed, changed, or added
ordinary file:

```text
semantic_payload_relation = FILE_ENTRIES_BYTE_IDENTICAL_TO_1_0_0
```

The 117 added directories are exactly the parent directories represented by the
895 file paths. Their authoritative full list and metadata are the entries with
`kind: "directory"` in
`krita-plugin/release/1.0.1/artifact-entries.json`. The required module root
`gapfill_krita/` is present.

Two independent fresh builds produced byte-identical candidates with SHA-256
`e001ad4db0a049db23f2839d780ff0ede810fc3f21c2d3fc574ef8bc12c93b19`.
The committed artifact is byte-identical to both.

## Freeze and publication model

| Item | Value |
| --- | --- |
| Version | `1.0.1` |
| Prospective tag | `krita-v1.0.1` |
| Governance | `GAPFILL_1_0_1_IMPORTER_PACKAGING_HOTFIX_V1_GOVERNANCE_ADOPTED` |
| Publication mode | `FROZEN_ARTIFACT_VERIFY_AND_PUBLISH` |
| Predecessor | `krita-v1.0.0` |
| Freeze metadata | `krita-plugin/release/1.0.1/freeze.json` |
| Entry manifest | `krita-plugin/release/1.0.1/artifact-entries.json` |

The 1.0.0 artifact, manifest, freeze metadata, tag, and GitHub Release remain
unchanged. Tag CI selects the versioned freeze record, verifies exact version,
tag, SHA, size, member ordering/metadata, importer discovery, and manifest, then
uploads the already-frozen ZIP. It does not rebuild production bytes.

## Frozen runtime identities

| Identity | Unchanged SHA-256 |
| --- | --- |
| Production semantics | `b3812c8a00aa359097d9395b13d27e55433b311584a00e6906de0f426f5acc38` |
| Lifecycle | `94b42368efc0df7c37333fe864f57593254557c2b181676106efd0a45e535e5f` |
| Display Oracle V2 | `a0d6a02bcc678ed316a18e26da17a693293e0ac22d4579d992de6eeb21844f35` |
| Native helper | `ad2fa7463d59dca74a92dc867734b38eb7aa49821b163547da442147348f8746` |
| ONNX model | `8219bf639a06942f07ea5867b8ffae2f20f85473155c0b45a57fa18d43f1aa78` |
| Model sidecar | `2ccc406b1e0647499af6657877309e6a8d66ff7aebb0dd307ba0d7de306e55e5` |

Phase 6.5 A–V was not rerun. Its frozen semantic and host evidence remains
unchanged because the ordinary file payload is byte-identical. The new gate is
importer/installability compatibility, which passed against the actual installed
Krita importer. No separate Krita startup smoke was performed from the disposable
tree; it is not used as substitute evidence for the passed importer smoke or the
existing host qualification.

## Prospective release notes

```text
GapFill 1.0.1

Packaging hotfix:
fixes "No plugins found in archive" when using Krita's Python Plugin Importer.

Runtime/model behavior is unchanged from 1.0.0.

Windows x86_64.
```

## Tag preparation

After the hotfix commit is reviewed, the prospective annotated tag command is:

```text
git tag -a krita-v1.0.1 <HOTFIX_COMMIT_SHA> -m "GapFill 1.0.1"
```

Do not execute it until separately authorized. Do not replace the 1.0.0 tag or
release asset.
