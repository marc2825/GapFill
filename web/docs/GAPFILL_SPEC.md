# GapFill Specification

## Status

GapFill is the main web-demo implementation of the interaction described in
Section 4 of the paper. The released implementation targets clean binary line
art without anti-aliasing. Anti-aliased line-art support is planned as a future
extension.

## Goal

GapFill helps users find and resolve small unpainted regions that are commonly
left behind during anime-style manual colorization.

The workflow is designed around five functions:

1. Detect small unpainted gaps and highlight them.
2. Suggest a fill color for each detected gap using a deep-learning model.
3. Provide a fixed-scale pop-up magnifier for quick inspection.
4. Let users correct suggested colors with a color-pick-like drag operation.
5. Let users apply suggested colors in batches through sweep selection or an
   Apply-All button.

## Layer Assumptions

The current web implementation assumes:

- **Line Art** is a transparent-background layer whose visible pixels form clean
  binary boundaries.
- **Guides** are transparent-background helper/boundary layers.
- **Coloring** is the active paint layer.
- Unpainted regions on the Coloring layer are represented by transparent pixels.
- A white Background layer may exist for display, but it is not treated as part
  of the unpainted-region detection source.

Guide pixels are treated as boundaries for ordinary region detection. If a
Coloring pixel is transparent while a Guide pixel is visible below it, the
system can still treat that Coloring pixel as an unpainted gap candidate,
because removing the Guide layer would reveal transparency.

## User Interface

GapFill is activated on demand through a toggle button. This keeps the feature
separate from ordinary painting workflows and lets users enable it only when
gap correction is useful.

When GapFill is active:

1. The system detects small gaps on the active Coloring layer.
2. Each detected gap receives a temporary suggested fill color.
3. A circular highlight is drawn around each gap.
4. The user can inspect, correct, sweep-apply, or apply all suggestions.

The UI exposes a **Gap Threshold** control. Connected regions whose pixel count
is at or below this threshold are treated as small gaps.

## 1. Unpainted Gap Detection

### Definition

A gap is a connected unpainted region on the active Coloring layer whose pixel
count is at or below the user-adjustable threshold.

In the clean-binary implementation, unpainted means:

```text
coloringAlpha == 0
```

Line Art pixels are excluded from gap candidates. Guide-visible transparent
Coloring pixels may be treated as a separate guide-gap candidate type.

### Region Search

Gap candidates are grouped with a grid-based connected-component traversal.
The current implementation uses 4-connected traversal over image pixels.

For each candidate component:

1. Traverse neighboring candidate pixels.
2. Stop retaining the component if it exceeds the threshold.
3. Keep the component if its size is at or below the threshold.
4. Compute a representative center from the component pixels.

The resulting gap record contains:

```text
id
center
pixels
predictedColor
```

Internally, the detector also distinguishes ordinary transparent gaps from
guide gaps so that model input masks can handle Guide pixels correctly.

## 2. Automatic Color Suggestion

When GapFill is active, each detected gap is assigned a temporary suggested
color. The primary path uses an ONNX-exported U-Net-style model.

If the model cannot be loaded, GapFill reports the model-loading error instead
of silently treating it as an ordinary prediction failure. For non-loading
prediction failures, a temporary greedy color fallback may be used.

### Model Input

For each gap, the system extracts a fixed-size local patch centered on the gap.
The model patch size is:

```text
32 x 32
```

The model receives a two-channel binary input:

1. **Line mask**: pixels from Line Art and Guides are encoded as `1`.
2. **Gap mask**: pixels belonging to the target gap are encoded as `1`.

Areas outside the canvas are zero-padded so that the target gap stays at the
same patch-relative position even near image borders.

For guide gaps, the target gap is temporarily removed from the Guide mask during
prediction. Other Guide pixels remain as boundaries.

### Model Output

The model outputs a spatial probability map over the patch. Each value
indicates how likely the corresponding pixel is to belong to the same semantic
color region as the target gap.

The output shape is validated before use.

### Color Selection

The system does not directly regress RGB values. Instead, it predicts region
correspondence and then derives a color from existing painted pixels:

1. Segment painted regions inside the patch without crossing Line Art or Guides.
2. For each painted region, compute the average predicted probability.
3. Select the region with the highest average probability.
4. Use the modal color of that selected painted region as the suggested color.

If no usable painted region is found, the configured fallback color is used.

## 3. Temporary Suggested-Color Overlay

Suggested colors are shown as a temporary preview over detected gaps. This
preview does not commit pixels to the Coloring layer.

The preview is drawn above the Coloring layer while preserving Line Art above
the suggested fills. This lets users inspect what the image would look like if
the suggestions were accepted, without modifying the actual layer data.

## 4. Circular Highlights

Each detected gap is highlighted with a circle around its representative center.

The circle radius is adjusted relative to the current canvas zoom so that
highlights remain usable at different zoom levels.

These circles serve three purposes:

1. Make small gaps visible.
2. Provide hover targets for magnification.
3. Provide selection targets for correction and sweep-apply interactions.

## 5. Hover-Activated Pop-up Magnification

When the cursor hovers over a highlighted gap, GapFill displays a local pop-up
magnifier.

The magnifier:

- Uses a fixed 5x zoom independent of the main canvas zoom.
- Is centered on the detected gap.
- Shows the surrounding region with temporary suggested colors.
- Displays a hollow translucent marker at the detected gap center.

This helps users inspect local color context without manually zooming the main
canvas in and out.

## 6. In-Circle Color Pick

When the cursor is inside a gap highlight and the user starts a drag operation,
GapFill enters color-correction mode for that gap.

During color-correction mode:

1. The pixel color under the cursor is sampled dynamically.
2. The sampled color temporarily replaces the gap's suggested color.
3. A dotted connector line is drawn from the cursor to the target gap marker.
4. Releasing the pointer commits the color to the gap.

If the user releases on the cancel control in the magnifier, the correction is
cancelled and the gap is not filled.

This interaction is intended to make occasional AI prediction errors cheap to
correct while keeping the user's attention near the local image context.

## 7. Out-Circle Sweep-to-Apply

When GapFill is active and the user starts dragging outside any circular
highlight, the system enters sweep-selection mode.

During sweep-selection:

1. A translucent stroke follows the pointer.
2. Any gap circle crossed by the stroke is marked as selected.
3. Selected circles are visually emphasized.
4. On pointer release, all selected gaps are filled with their suggested colors.

The operation creates a single history entry for the affected layer.

## 8. Apply-All

The Apply-All button fills every currently detected gap with its suggested
color in a single operation.

This is useful when the user trusts the current suggestions or wants to quickly
resolve all remaining small gaps.

## 9. Fallback Color Handling

GapFill uses a shared fallback color for unassigned or invalid material/color
states:

```text
#FF00FF
```

This color is intentionally conspicuous, making it easier to notice cases where
no reliable color could be inferred.

Invalid fallback color inputs are reported with `console.error`, including in
production builds.

## 10. Cancellation and Responsiveness

Gap detection may scan a large number of pixels. To keep the UI responsive, the
detector periodically yields back to the browser event loop and checks for
abort signals.

This prevents stale detection results from overwriting newer requests when the
user changes layers, toggles modes, or adjusts thresholds.

## Current Limitations

- The released web implementation targets clean binary line art.
- Anti-aliased line-art gaps are not fully supported yet.
- Gap detection uses transparency-based candidates rather than a full
  trapped-ball segmentation pipeline.
- The model uses local 32x32 context, so predictions depend on nearby visual
  evidence.
- The greedy fallback is intentionally simple and should not be treated as the
  main color-prediction method.

## Planned Extensions

- Anti-aliased line-art support.
- More robust topology handling for broken or semi-transparent boundaries.
- Tighter integration with Overflow Flood Fill.
- Native add-ons for Krita and CLIP STUDIO PAINT.
