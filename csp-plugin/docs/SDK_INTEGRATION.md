# CELSYS SDK integration guide

## 1. Obtain the SDK yourself

Read and accept the [current SDK terms](https://www.clipstudio.net/ja/dl/cspsdk_term/)
from CELSYS's [official SDK page](https://www.clipstudio.net/ja/sdk/), then download
the SDK through CELSYS's procedure. Do not commit its headers, binaries, samples,
credentials, or generated proprietary material. Point a local `CSP_SDK_ROOT`
environment/CMake cache variable at the extracted SDK.

The repository cannot accept those terms for you. API names must be taken from
the exact downloaded documentation rather than guessed from public marketing pages.
The agreement also contains confidentiality obligations. An ignored local SDK
directory may be used for private development, but `.gitignore` is not a security
boundary; an external access-limited directory is safer. Before making
the SDK visible to any external coding or build service, confirm that doing so is
permitted by the agreement and your organization. Do not paste SDK contents into
GitHub issues, CI logs, or chat; a capability answer and first-party adapter compiler
error are normally sufficient for collaboration.

## 2. Implemented private Windows adapter

The evaluated adapter is kept at
`FilterPlugIn20210827/GapAssistPrivate` under the ignored local SDK directory.
It is not copied into the public source tree. Build it on Windows x64 with the
commands in that directory's README.

The adapter performs these operations only:

1. Read the active RGB raster source and alpha into `gap_assist::Image`.
2. Read the current selection mask and retain soft-selection values for output blending.
3. Run `QuickFixPipeline`, which accepts High-confidence learned predictions
   only. The current private adapter has no packaged learned backend/Line input,
   so its heuristic result is intentionally not auto-applied.
4. Forward progress, restart, and cancellation through the filter lifecycle.
5. Write the corrected destination and let CSP own Preview, OK, Cancel, and Undo.

The public `HostFilterContext`/`GapAssistCommand` boundary remains useful for a
future host API that can create document layers and render the complete review
dialog. The 2021 filter SDK cannot satisfy that richer contract; the private
adapter therefore calls `QuickFixPipeline` directly instead of pretending that
the unavailable capabilities exist.

See [the capability report](CSP_SDK_20210827_CAPABILITIES.md) for the conclusions.

## 3. Native property dialog

The native Windows filter uses CSP's standard property dialog. It exposes gap
threshold, alpha threshold, confidence preset, and four/eight-neighbor
connectivity. In a future runtime-enabled build, Preview shows the
High-confidence learned Quick Fix result. OK commits it; Cancel leaves the
document unchanged. The current Phase 5 build is not release-ready for this
learned path. Review List and One-by-One remain PNG
companion workflows because this SDK does not expose their required UI or layer
operations.

## 4. Capability probe checklist

- [ ] Correct SDK/host version and desktop EX support recorded.
- [ ] Active raster layer read verified for transparent RGBA pixels.
- [ ] Non-raster/empty layer rejected with a useful message.
- [ ] Selection coordinate origin and dimensions verified.
- [x] Standard filter property dialog and Preview are available.
- [x] Rich list/thumbnail review UI is not exposed by this SDK.
- [x] Raster layer creation and placement are not exposed by this SDK.
- [ ] Pixel row order, premultiplication, and color profile behavior verified.
- [ ] Cancel leaves the document byte-for-byte unchanged.
- [ ] Native OK commits once and one CSP Undo restores the input.
- [ ] Progress cancellation returns without partial output.
- [ ] CSP restart/settings-path behavior verified.
- [ ] Release package has passed CELSYS's required distribution procedure.

Do not upload the native plug-in binary as an ordinary GitHub Release until the
distribution method has been confirmed under the current CELSYS process. The
SDK-independent core/CLI bundles are separate and contain no CELSYS SDK material.

## 5. Validation

Run the SDK-independent tests first. Then test the native Quick Fix build in a
disposable CSP document using the exact pinned model/runtime, a separately
acquired Line input, multiple gap thresholds, exact-zero alpha membership, both
connectivities, full-geometry selection scope, Preview, Cancel, OK, and Undo.
Confirm heuristic fallback produces no automatic writes. Test Review List,
One-by-One, Correction Layer, and Highlight Layer separately through the PNG
companion; they are not native 2021-SDK capabilities.
Use `docs/MANUAL_TEST_PLAN.md` to record the result rather than relying on an
informal smoke test.
