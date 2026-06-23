# Windows CSP EX 4.0.10 manual test plan

Run this only after the CELSYS SDK adapter compiles. Use disposable documents and
copies of source artwork. Record the CSP version, SDK release, OS, architecture,
plug-in hash, and test date.

## Installation and host boundary

- [ ] The plug-in installs through the supported CSP mechanism without modifying
      application files manually.
- [ ] It appears only where the SDK documentation says a filter plug-in should.
- [ ] It rejects empty, vector, text, reference, or otherwise unsupported active layers.
- [ ] The UI states clearly when only the active raster layer is analyzed.
- [ ] Restarting CSP preserves only non-image settings.

## Detection

- [ ] A 1 px enclosed transparent gap is detected with Small.
- [ ] A 4–10 px gap is excluded by Small and detected by Medium.
- [ ] A 30 px gap is detected by Large; a 31 px gap is excluded.
- [ ] A custom threshold is honored.
- [ ] A transparent region connected to the canvas edge is excluded.
- [ ] Alpha threshold 0 excludes alpha 1; an increased threshold includes it.
- [ ] Four- and eight-neighbor diagonal behavior matches the unit tests.
- [ ] Selection Only excludes components touching the selection boundary.

## Review behavior

- [ ] Changing a native property updates CSP Preview without committing pixels.
- [ ] Quick Fix applies only High-confidence candidates.
- [ ] Apply High Confidence leaves Medium/Low unchanged.
- [ ] Re-preview replaces stale output rather than accumulating corrections.
- [ ] Cancel leaves document pixels and history unchanged.

## Output and Undo

- [ ] Native OK changes only High-confidence gap pixels on the active layer.
- [ ] Duplicating the coloring layer first provides an editable non-destructive copy.
- [ ] One CSP Undo restores the exact pre-filter pixel data.
- [ ] Cancelling progress creates no partial pixel change or Undo entry.

## PNG companion review and layer output

- [ ] Review List manifest/contact sheet contains summary, IDs, confidence,
      suggested color, owner ID, and status.
- [ ] Excluding Apply, Skip, and Mark Only produce no correction pixels.
- [ ] One-by-One decision files support Apply, Skip, Mark Only, and applying all
      remaining High-confidence candidates.
- [ ] Importing `*.gap-corrections.png` creates a transparent correction layer
      above the coloring layer without modifying the source.
- [ ] Optional highlights mark unresolved Medium/Low candidates and omit applied gaps.

## Pixel correctness

- [ ] RGBA channel order is correct (test red, green, blue, black, white, alpha).
- [ ] Top/bottom row orientation is correct using an asymmetric test image.
- [ ] Transparent RGB values do not create visible fringes.
- [ ] Premultiplied/unpremultiplied alpha conversion is verified.
- [ ] Behavior is recorded for non-sRGB profiles and higher-bit-depth documents.

## Performance and privacy

- [ ] 4096×4096 RGBA input completes with responsive progress/cancel behavior.
- [ ] Approximately 100 candidates can be reviewed without UI stalls.
- [ ] No image or pixel data is sent over the network.
- [ ] No image content appears in logs, settings, crash text, or undeleted temp files.

## Failure cases

- [ ] Missing/invalid settings fall back safely or produce a clear error.
- [ ] Unsupported host capabilities fail closed without pixel mutation.
- [ ] ONNX selected without a local adapter visibly falls back to Rule-Based.
- [ ] Exceptions close progress UI and CSP does not commit the filter destination.
