# GapFill shared Phase 2 fixtures

This corpus separates reviewed specification evidence from observations of the
current implementations. Passing a current-behavior parity check does not make
that behavior canonical.

The canonical manifest is `manifest.json`. JSON is UTF-8, deterministically
serialized with sorted object keys and two-space indentation. Coordinates use
an upper-left origin. Flat pixel indices are row-major: `index = y * width + x`.
Bounding boxes are `[x, y, width, height]` unless a field explicitly says
`xyxy`.

Raster encodings:

- `palette_rgba8`: each row is a string; each character indexes an RGBA palette.
- `rows_u8`: rows contain decimal unsigned 8-bit values.
- sparse binary 32x32 tensors: active row-major indices are `1.0`; all omitted
  positions are exactly `0.0`. The declared model layout is NCHW.
- model outputs: all 1024 float32 values are listed in row-major order and are
  also hashed as little-endian float32 bytes.

Directories:

- `detection`: controlled raster inputs and explicitly named policy variants.
- `patch`: centroid, bounds, padding, channel-0, and channel-1 fixtures.
- `model`: exact inputs and characterized outputs from the pinned ONNX artifact.
- `postprocess`: fixed labels/probabilities and independently derivable results.
- `policy`: hand-reviewed selection-scope and fallback-application contracts
  where an artificial raster would not improve the oracle.
- `end_to_end`: synthetic PNGs and reviewed crops with annotations.
- `parity`: non-golden current-behavior observations and the strict CSV
  projection consumed by the C++ reader.

The cross-implementation readers live outside this generated directory in
`web/src/tests/GapFill/phase2Fixtures.test.mjs` and `tests/parity/`. The neutral
generator/validator lives in `scripts/gapfill_reference/`.

Every expectation contains `evidence_ids` and `decision_ids`. Those identifiers
resolve through `manifest.json`. Only expectations marked both `STABLE` and
`canonical: true` are canonical in Phase 2. `EMPIRICAL_DECISION_REQUIRED`
variants remain unresolved experiments. `NONCANONICAL_REFERENCE` variants keep
historical, platform-specific, or experimental behavior visible without making
it canonical. Maintainer decisions `D-01` through `D-07` are frozen `STABLE`.
