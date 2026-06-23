# Overflow Flood Fill Specification

## Status

Overflow Flood Fill is an experimental extension of GapFill. The current
implementation targets clean binary line art without anti-aliasing. Support for
anti-aliased line art is planned as a future extension.

## Goal

Overflow Flood Fill extends the normal paint-bucket operation so that small
unpainted gaps can be filled at the same time as the larger region they most
likely belong to.

Unlike the normal GapFill workflow, this feature is not designed as a separate
post-processing correction step. Instead, it anticipates small gaps during
bucket filling. When the user fills or clicks a large owner region, linked small
gaps are filled as a side effect.

## Terminology

- **Small gap**: A connected transparent region on the active Coloring layer
  whose pixel count is at or below the user-adjustable GapFill threshold.
- **Guide gap**: A transparent Coloring-layer region where a visible Guide
  pixel exists below it. These pixels are still treated as unpainted because
  removing the Guide layer would reveal transparency.
- **Owner region**: A large connected region separated by Line Art and Guides.
  Owner candidates are computed from topology, not from the current paint state.
- **Assignment**: A predicted link from one small gap to one owner region.
- **Owner likelihood**: The mean ONNX probability over owner pixels inside the
  model patch. Assignments below the UI threshold are ignored.

## Layer Assumptions

The current implementation assumes:

- Line Art is a transparent-background layer whose visible pixels form clean
  binary boundaries.
- Guides are also transparent-background boundary/helper layers.
- Coloring is the active paint layer, and unpainted areas are transparent.
- A white Background layer may exist for viewing, but it is not used as an
  unpainted-region source.

## User Interface

Overflow Flood Fill is controlled by an independent toggle shown near the
GapFill controls.

When Overflow Flood Fill is enabled:

1. The system switches to Paint Bucket behavior.
2. Other drawing tools are disabled while the mode is active.
3. Small gaps and owner links are precomputed.
4. Hovering over an owner region highlights linked small gaps.
5. Clicking an owner region fills the owner and/or propagates its color to the
   linked gaps.

The UI also exposes an **Owner Likelihood** threshold. Only assignments whose
confidence is greater than or equal to this value are used for hover previews
and click propagation.

## Precomputation Pipeline

When Overflow Flood Fill is enabled, or when relevant layer/history state
changes, the system recomputes the following data:

1. Detect small transparent gaps on the active Coloring layer.
2. Detect Guide gaps separately from ordinary transparent gaps.
3. Build owner regions from the Line Art / Guides topology.
4. For each small gap, run the ONNX model to produce a probability map.
5. Score each owner by the mean probability over owner pixels inside the patch.
6. Assign the gap to the owner with the highest score.

Owner candidates are filtered by area. The minimum owner area is:

```text
gapFillThreshold + 1
```

This prevents small gap-sized components from becoming owner regions.

## Model Usage

The ONNX model is used in the same conceptual form as GapFill color prediction:

- Input channel 0: binary Line Art / Guides mask.
- Input channel 1: target small-gap mask.
- Output: spatial probability map indicating pixels likely to share the same
  semantic color region as the target gap.

For Overflow Flood Fill, the output probability map is not converted directly
into a color. Instead, it is used to choose the most likely owner region.

For each candidate owner:

```text
ownerConfidence = sum(probability over owner pixels in patch)
                / count(owner pixels in patch)
```

The owner with the highest confidence becomes the gap's assigned owner.

## Click Behavior

### Clicking an unpainted owner

If the clicked pixel on the active Coloring layer is transparent:

1. The owner region is filled with the current brush color.
2. All linked small gaps above the Owner Likelihood threshold are filled with
   the same color.
3. One history entry is added.
4. Overflow precomputation is refreshed.

### Clicking an already painted owner

If the clicked pixel on the active Coloring layer has alpha greater than zero:

1. The clicked pixel color is treated as the owner color.
2. The owner region itself is not repainted.
3. All linked small gaps above the Owner Likelihood threshold are filled with
   the owner color.
4. One history entry is added if any pixels changed.
5. Overflow precomputation is refreshed.

### Clicking outside any owner

If the clicked position does not belong to an owner region:

1. The system falls back to normal bucket fill.
2. Overflow precomputation is refreshed afterward.

If Overflow precomputation is still running, clicks are ignored with a status
message instead of falling through to ordinary bucket fill.

## Hover Preview

When the cursor is over an owner region, the system highlights small gaps that:

1. Are assigned to that owner.
2. Have confidence greater than or equal to the Owner Likelihood threshold.
3. Are not currently suppressed by the undo-retry rule.

The highlight is only a preview. No pixels are changed until the user clicks.

## Undo Retry Suppression

If an Overflow Flood Fill operation propagates color into linked gaps and the
user immediately undoes that operation, the system suppresses propagation for
the last affected owner.

On the next click of that owner:

- The owner can still be filled normally if it is unpainted.
- Linked gaps are not filled.
- The suppression state for that owner is cleared after the click.

This supports the interaction pattern where a user rejects the automatic gap
propagation and retries the owner fill without repeating the same unwanted
propagation.

## Current Limitations

- The implementation assumes clean binary Line Art and Guides.
- Anti-aliased line-art topology is not yet supported.
- Owner detection is based on 4-connected regions.
- The model only evaluates owner candidates that overlap the 32x32 inference
  patch around the target gap.
- Assignment quality depends on the trained ONNX model and the selected Owner
  Likelihood threshold.

## Planned Extensions

- Anti-aliased line-art support.
- Topology proxy generation for AA line art.
- AA fringe propagation near line boundaries.
- Debug overlays for owner labels, probability maps, assignments, and final
  propagation masks.
