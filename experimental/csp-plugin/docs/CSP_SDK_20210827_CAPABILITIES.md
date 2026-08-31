# Evaluated CELSYS filter SDK capabilities

This report records capability conclusions for the locally accepted
`FilterPlugIn20210827` SDK without reproducing SDK headers, documentation, sample
code, or confidential API details.

## Target

- Initial platform: Windows x64
- Host target: CLIP STUDIO PAINT EX 4.0.10
- SDK package: 2021-08-27 filter plug-in SDK
- macOS: not evaluated; it does not alter the Windows API capability failure
- Runtime status: private MSVC build completed; real CSP matrix untested
- Phase 7 input decision: `C. INSUFFICIENT_FOR_GAPFILL_PARITY`
- Phase 7 host decision: `5. NOT_APPLICABLE_BECAUSE_INPUT_INFEASIBLE`
- Canonical GapFill release status: permanently ineligible for this evaluated
  SDK/adapter combination

## Findings

| Capability | Result | Product consequence |
|---|---|---|
| One filter RGB raster and alpha | Exposed by SDK; runtime details untested | Supplies only one source and cannot represent independent canonical inputs. |
| Independent Coloring, Line, and Guide sources | Not exposed | Canonical Phase 4/5 input cannot be recovered without information loss. |
| Arbitrary/named/typed sibling layers or layer tree | Not exposed | Unsupported documents cannot be identified or normalized through this filter API. |
| Independent document projection | Not exposed | A visual composite is not a substitute for source identity. |
| Write filter destination pixels and alpha | Exposed by SDK; runtime details untested | Exact channel/profile/write behavior remains unqualified. |
| Read selection bounds/mask | Exposed by SDK; runtime details untested | Origin, fractional values, and application behavior remain unqualified. |
| Standard host property dialog | Exposed by SDK | Does not solve missing canonical inputs. |
| Preview and parameter restart | Exposed by SDK; runtime semantics untested | Replacement/reversibility were not observed in CSP. |
| Progress and cancellation | Exposed by SDK; runtime semantics untested | Cancellation latency and no-partial-write behavior were not observed in CSP. |
| Normal filter OK/Cancel/Undo | Host lifecycle surface only; runtime semantics untested | One-step Undo/Redo remains a release blocker, not an assumed property. |
| Create or place document layers | Not exposed | The native filter cannot create Correction or Highlight layers. |
| Dynamic custom list/thumbnail review UI | Not exposed | Review List and One-by-One cannot be implemented faithfully in this SDK. |
| Direct document Undo transaction control | Not exposed | The adapter relies on CSP's normal filter Undo behavior. |

## Phase 7 product boundary

The evaluated 2021 filter SDK is insufficient for a native product advertised as
GapFill. The adapter cannot acquire independent Line or Guide inputs and has no
packaged ONNX backend. It does not simulate unavailable capabilities with UI
scraping, process injection, composites, inference from the active raster, or
undocumented hooks. Heuristic fallback remains excluded from automatic
application.

The existing single-layer/rule-based behavior may survive only as a clearly
differentiated heuristic quick-fix feature. It is not GapFill parity, lacks
canonical multi-layer semantics, and requires explicit confirmation for
heuristic results. It must disclose its single-raster input and heuristic
prediction and receive separate host/release qualification. This document does
not choose a final product name or implement that feature.

The SDK-independent PNG companion retains Review List, One-by-One, Correction
Layer, Highlight Layer, manifests, and contact sheets. This keeps the complete
workflow available without claiming capabilities the host SDK does not provide.

The private adapter compiled with MSVC in Phase 7, but was not installed or
qualified in CSP. Compilation is not host verification. All real-host manual
rows remain `UNTESTED`; exact Preview, cancellation, write, profile, selection,
Undo, and Redo behavior is unknown. Distribution of any native `.cpm` must also
follow CELSYS's current submission and approval process. The ignored local SDK
directory, private adapter, and build artifact are not public source artifacts.

Those untested lifecycle rows do not make canonical GapFill qualification
pending: host/core parity is intentionally not applicable after input
feasibility failed. Reconsidering native CSP GapFill requires new capability
evidence from a different supported integration surface, not more work on this
adapter or a weaker canonical algorithm.
