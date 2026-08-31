# CSP SDK capability report

Do not include or quote confidential SDK headers, samples, documentation, symbols,
or API names in this report.

## Environment

- SDK release/date:
- SDK download date:
- Operating system and architecture:
- Compiler/toolchain required by the SDK:
- CLIP STUDIO PAINT edition: EX
- CLIP STUDIO PAINT version:

## Capabilities confirmed from the supplied SDK documentation

Use `Yes`, `No`, or `Unknown`.

| Capability | Result | Non-confidential note |
|---|---|---|
| Read active raster-layer RGBA pixels | Unknown | |
| Distinguish/reject non-raster layers | Unknown | |
| Read the current selection mask | Unknown | |
| Display one custom modal review dialog | Unknown | |
| Display image thumbnails/previews | Unknown | |
| Report progress | Unknown | |
| Cancel a running filter | Unknown | |
| Create and position a new raster layer | Unknown | |
| Write pixels to a newly created layer | Unknown | |
| Overwrite active-layer pixels | Unknown | |
| Group mutation into exactly one Undo item | Unknown | |
| Persist plug-in settings | Unknown | |
| Supported binary architecture/package format | Unknown | |

## Required fallback

- If new-layer creation is unavailable: use the PNG correction import workflow.
- If a custom review dialog is unavailable: do not apply predictions blindly; use
  the PNG contact sheet/manifest workflow.
- If one-step Undo cannot be guaranteed: disable direct overwrite.
- If selection access is unavailable: expose Whole Layer only.
