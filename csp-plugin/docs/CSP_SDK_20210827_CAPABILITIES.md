# Evaluated CELSYS filter SDK capabilities

This report records capability conclusions for the locally accepted
`FilterPlugIn20210827` SDK without reproducing SDK headers, documentation, sample
code, or confidential API details.

## Target

- Initial platform: Windows x64
- Host target: CLIP STUDIO PAINT EX 4.0.10
- SDK package: 2021-08-27 filter plug-in SDK
- macOS: planned after the Windows implementation is validated
- Runtime status: pending the first MSVC build and manual CSP test

## Findings

| Capability | Result | Product consequence |
|---|---|---|
| Read active RGB raster pixels and alpha | Supported | Gap detection can run on the active coloring layer. |
| Write filter destination pixels and alpha | Supported | Accepted Quick Fix pixels can be previewed and committed. |
| Read selection bounds/mask | Supported | Selection-scoped processing, including soft selection blending, is possible. |
| Standard host property dialog | Supported | Threshold, alpha threshold, confidence preset, and connectivity are exposed. |
| Preview and parameter restart | Supported | Changes can be inspected before OK. |
| Progress and cancellation | Supported | Long detection can be cancelled without partial commit. |
| Normal filter OK/Cancel/Undo | Supported by host flow | Quick Fix uses CSP's conventional filter lifecycle. |
| Create or place document layers | Not exposed | The native filter cannot create Correction or Highlight layers. |
| Dynamic custom list/thumbnail review UI | Not exposed | Review List and One-by-One cannot be implemented faithfully in this SDK. |
| Direct document Undo transaction control | Not exposed | The adapter relies on CSP's normal filter Undo behavior. |

## Chosen product boundary

The native plug-in is a conventional **Quick Fix** filter and applies only
High-confidence predictions. It does not simulate unavailable capabilities with
UI scraping, process injection, or undocumented hooks. Users should duplicate the
coloring layer before running the filter when they want an editable backup.

The SDK-independent PNG companion retains Review List, One-by-One, Correction
Layer, Highlight Layer, manifests, and contact sheets. This keeps the complete
workflow available without claiming capabilities the host SDK does not provide.

Distribution of a native `.cpm` must follow CELSYS's current submission and
approval process. The ignored local SDK directory and derived private adapter are
not public source artifacts.
