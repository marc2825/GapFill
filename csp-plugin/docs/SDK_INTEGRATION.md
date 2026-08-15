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

## 2. Public host contract and private Windows adapter

The public, SDK-independent requirement boundary is
`src/plugin_entry/native_host_contract.hpp`. It represents canonical
document-coordinate Coloring, Line, Guide and Selection input; channel/stride
layout; normalized straight RGBA8 sRGB conversion evidence; snapshot identity;
replaceable Preview; cancellation; atomic final mutation; abort; and explicit
one-step Undo/Redo evidence. Its fake-host conformance suite does not prove any
real CSP behavior.

The evaluated adapter is kept at
`FilterPlugIn20210827/GapAssistPrivate` under the ignored local SDK directory.
It is not copied into the public source tree. Build it on Windows x64 with the
commands in that directory's README.

The current private adapter performs these operations only:

1. Read the active RGB raster source and alpha into `gap_assist::Image`.
2. Read the current selection mask and retain soft-selection values for output blending.
3. Run the compatibility `QuickFixPipeline`, which receives empty Line and
   Guide inputs. The adapter has no packaged learned backend, so its heuristic
   result is intentionally not auto-applied.
4. Forward progress, restart, and cancellation through the filter lifecycle.
5. Write the corrected destination and let CSP own Preview, OK, Cancel, and Undo.

The public `HostFilterContext`/`GapAssistCommand` boundary remains useful for a
future host API that can create document layers and render the complete review
dialog. The 2021 filter SDK cannot satisfy that richer contract; the private
adapter therefore calls `QuickFixPipeline` directly instead of pretending that
the unavailable capabilities exist.

Phase 7 determined that this filter API also cannot satisfy the smaller
canonical input contract: no permitted independent Line/Guide or layer-tree
source is exposed. The Phase 7 clean MSVC build therefore establishes only that
the current private adapter compiles. It is not GapFill parity and was not
installed or host-qualified. Do not change the public algorithm to fit that
limitation.

See [the capability report](CSP_SDK_20210827_CAPABILITIES.md) for the conclusions.

## 3. Native property dialog

The native Windows filter uses CSP's standard property dialog. It exposes gap
threshold, alpha threshold, confidence preset, and four/eight-neighbor
connectivity. Preview/restart and normal filter lifecycle surfaces exist, but
their exact runtime behavior remains untested. The current adapter cannot
construct canonical learned input and is not release-ready. Review List and
One-by-One remain PNG companion workflows because this SDK does not expose
their required UI or layer operations.

## 4. Capability probe checklist

- [ ] Correct SDK/host version and desktop EX support recorded.
- [ ] Active raster layer read verified for transparent RGBA pixels.
- [ ] Non-raster/empty layer rejected with a useful message.
- [ ] Selection coordinate origin and dimensions verified.
- [x] Standard filter property dialog and Preview are available.
- [x] Rich list/thumbnail review UI is not exposed by this SDK.
- [x] Raster layer creation and placement are not exposed by this SDK.
- [x] Independent sibling Line/Guide/layer-tree acquisition is not exposed by
      this SDK.
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

Run the SDK-independent tests first. A native GapFill qualification may proceed
only with an adapter/host route that can first satisfy the complete canonical
input contract and fail closed on unsupported documents. The evaluated 2021
filter SDK cannot, so its private artifact must not be installed merely to turn
compile success into a GapFill claim. The manual plan remains the required
matrix for any future capable route; unchecked/`UNTESTED` rows are not passes.
