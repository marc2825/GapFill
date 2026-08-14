import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import * as ort from 'onnxruntime-web';

import { buildGapMaskForPatch } from '../../utils/GapFill/onnxGapMask.ts';
import {
  buildCanonicalModelInput,
  canonicalBoundaryMask,
  segmentLineRegions,
  selectCanonicalRegion,
} from '../../utils/GapFill/onnxPostprocessing.ts';
import { getValidatedProbabilityMap } from '../../utils/GapFill/onnxOutputValidation.ts';
import {
  calculateCenteredPatchBounds,
  copyIntoZeroPaddedPatch,
} from '../../utils/GapFill/onnxPatchExtraction.ts';

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../../../',
);

function loadJson(relativePath) {
  return JSON.parse(
    readFileSync(
      path.join(repositoryRoot, 'tests/fixtures/gapfill', relativePath),
      'utf8',
    ),
  );
}

function image(width, height, pixels) {
  return {
    width,
    height,
    data: new Uint8ClampedArray(pixels.flat(2)),
    validPixels: new Uint8Array(width * height).fill(1),
  };
}

function paletteImage(raster) {
  const pixels = raster.rows.map((row) =>
    [...row].map((symbol) => raster.palette[symbol]),
  );
  return image(pixels[0]?.length ?? 0, pixels.length, pixels);
}

function sparseSource(caseDefinition) {
  const { width, height } = caseDefinition.source;
  const coloring = new Uint8ClampedArray(width * height * 4);
  const line = new Uint8ClampedArray(width * height * 4);
  for (let index = 0; index < width * height; index++) {
    coloring[index * 4 + 3] = 255;
  }
  for (const index of caseDefinition.source.gap_indices) {
    coloring[index * 4 + 3] = 0;
  }
  for (const index of caseDefinition.source.line_active_indices) {
    line[index * 4 + 3] = 255;
  }
  return { coloring, line };
}

function extractSparsePatch(source, sourceWidth, bounds) {
  const cropped = new Uint8ClampedArray(
    bounds.sourceWidth * bounds.sourceHeight * 4,
  );
  for (let y = 0; y < bounds.sourceHeight; y++) {
    for (let x = 0; x < bounds.sourceWidth; x++) {
      const sourceIndex =
        ((bounds.sourceY + y) * sourceWidth + bounds.sourceX + x) * 4;
      const destinationIndex = (y * bounds.sourceWidth + x) * 4;
      cropped.set(source.slice(sourceIndex, sourceIndex + 4), destinationIndex);
    }
  }
  return copyIntoZeroPaddedPatch(
    cropped,
    bounds.sourceWidth,
    bounds.sourceHeight,
    32,
    bounds.destinationX,
    bounds.destinationY,
  );
}

test('Phase 5 boundary conversion is inclusive grayscale 128 after white compositing', () => {
  const source = image(8, 1, [[
    [0, 0, 0, 0],
    [0, 0, 0, 1],
    [127, 127, 127, 255],
    [128, 128, 128, 255],
    [129, 129, 129, 255],
    [0, 0, 0, 255],
    [0, 0, 0, 126],
    [0, 0, 0, 127],
  ]]);
  assert.deepEqual(
    [...canonicalBoundaryMask(source)],
    [0, 0, 1, 1, 0, 1, 0, 1],
  );
});

test('Phase 5 input is exact NCHW float32 and has no Guide channel', () => {
  const boundary = new Uint8Array(32 * 32);
  const gap = new Float32Array(32 * 32);
  boundary[16 * 32 + 15] = 1;
  gap[16 * 32 + 16] = 1;
  const tensor = buildCanonicalModelInput(
    boundary,
    gap,
  );
  assert.ok(tensor instanceof Float32Array);
  assert.equal(tensor.length, 2048);
  assert.deepEqual(
    [...tensor.entries()].filter(([, value]) => value !== 0),
    [[16 * 32 + 15, 1], [1024 + 16 * 32 + 16, 1]],
  );
});

test('Phase 5 Web tensor matches all 13 canonical Line-only patch cases', () => {
  for (const caseDefinition of loadJson('patch/cases.json').cases) {
    const expected = caseDefinition.expectations.find(
      (item) => item.variant === 'training_line_only',
    ).result;
    const [centerX, centerY] = expected.centroid;
    const bounds = calculateCenteredPatchBounds(
      caseDefinition.source.width,
      caseDefinition.source.height,
      centerX,
      centerY,
      32,
    );
    const { coloring, line } = sparseSource(caseDefinition);
    const coloringPatch = extractSparsePatch(
      coloring,
      caseDefinition.source.width,
      bounds,
    );
    const linePatch = extractSparsePatch(
      line,
      caseDefinition.source.width,
      bounds,
    );
    const gapPixels = caseDefinition.source.gap_indices.map((index) => ({
      x: index % caseDefinition.source.width,
      y: Math.floor(index / caseDefinition.source.width),
    }));
    const gapMask = buildGapMaskForPatch(
      coloringPatch,
      bounds,
      { x: centerX, y: centerY },
      gapPixels,
    );
    const tensor = buildCanonicalModelInput(
      canonicalBoundaryMask(linePatch),
      gapMask,
    );
    assert.deepEqual(
      [...tensor.slice(0, 1024).entries()]
        .filter(([, value]) => value !== 0)
        .map(([index]) => index),
      expected.tensor.channel_0_active_indices,
      `${caseDefinition.id} channel 0`,
    );
    assert.deepEqual(
      [...tensor.slice(1024).entries()]
        .filter(([, value]) => value !== 0)
        .map(([index]) => index),
      expected.tensor.channel_1_active_indices,
      `${caseDefinition.id} channel 1`,
    );
  }
});

test('Phase 5 semantic regions come from Line fill geometry in row-major order', () => {
  const line = image(3, 2, [[
    [0, 0, 0, 0], [0, 0, 0, 255], [0, 0, 0, 0],
    [0, 0, 0, 0], [0, 0, 0, 255], [0, 0, 0, 0],
  ]]);
  assert.deepEqual(
    [...segmentLineRegions(line).labels],
    [1, 0, 2, 1, 0, 2],
  );
});

test('Phase 5 scoring excludes label zero, includes gap pixels in means, and ties by row order', () => {
  const coloring = image(3, 1, [[
    [250, 0, 0, 0],
    [240, 20, 20, 255],
    [20, 20, 240, 255],
  ]]);
  const result = selectCanonicalRegion(
    coloring,
    new Int32Array([9, 9, 3]),
    new Float32Array([1, 0, 0.5]),
  );
  assert.equal(result.label, 9);
  assert.deepEqual(result.rgb, [240, 20, 20]);
  assert.equal(result.meanProbability, 0.5);

  const tiedColors = image(2, 2, [[
    [240, 20, 20, 255], [20, 20, 240, 255],
    [20, 20, 240, 255], [240, 20, 20, 255],
  ]]);
  const modalTie = selectCanonicalRegion(
    tiedColors,
    new Int32Array([7, 7, 7, 7]),
    new Float32Array([0.5, 0.5, 0.5, 0.5]),
  );
  assert.deepEqual(modalTie.rgb, [240, 20, 20]);

  assert.throws(
    () => selectCanonicalRegion(
      coloring,
      new Int32Array([9, 9, 3]),
      new Float32Array([0, Number.NaN, 0.5]),
    ),
    /finite/,
  );
});

test('Phase 5 canonical region selection matches all eight frozen semantic cases', () => {
  const expected = {
    R001_manual_mean_winner: ['reviewed_semantic', 2, [20, 20, 220]],
    R002_label_zero: ['line_labels', 1, [40, 180, 40]],
    R003_disconnected_same_rgb: ['line_labels', 1, [200, 30, 30]],
    R004_tolerance_30_boundary: ['line_labels', 1, [0, 0, 0]],
    R005_transitive_color_chain: ['line_labels', 1, [0, 0, 0]],
    R006_modal_tie: ['selected_region', 1, [240, 20, 20]],
    R007_antialiased_colors: ['selected_region', 1, [100, 120, 140]],
    R008_line_vs_colored_regions: ['line_labels', 1, [200, 20, 20]],
  };

  for (const caseDefinition of loadJson('postprocess/cases.json').cases) {
    const [labelMap, label, rgb] = expected[caseDefinition.id];
    const labels = new Int32Array(caseDefinition.label_maps[labelMap].flat());
    const probabilities = new Float32Array(
      caseDefinition.probability_map.flat(),
    );
    const result = selectCanonicalRegion(
      paletteImage(caseDefinition.coloring_rgba),
      labels,
      probabilities,
    );
    assert.equal(result.label, label, `${caseDefinition.id} label`);
    assert.deepEqual(result.rgb, rgb, `${caseDefinition.id} RGB`);
  }
});

test('Phase 5 output validation rejects nonfinite and out-of-range probabilities', () => {
  assert.throws(
    () => getValidatedProbabilityMap(
      new Float32Array([Number.NaN]),
      [1, 1, 1, 1],
      [1, 1, 1, 1],
    ),
    /nonfinite/,
  );
  assert.throws(
    () => getValidatedProbabilityMap(
      new Float32Array([1.01]),
      [1, 1, 1, 1],
      [1, 1, 1, 1],
    ),
    /outside/,
  );
});

test('Phase 5 Web ONNX output selects the canonical M001 region and RGB', async () => {
  const modelCases = loadJson('model/cases.json');
  const caseDefinition = modelCases.cases.find(
    (item) => item.id === 'M001_no_guide',
  );
  const tensor = new Float32Array(2 * 32 * 32);
  for (const index of caseDefinition.tensor.channel_0_active_indices) {
    tensor[index] = 1;
  }
  for (const index of caseDefinition.tensor.channel_1_active_indices) {
    tensor[32 * 32 + index] = 1;
  }

  const session = await ort.InferenceSession.create(
    readFileSync(path.join(repositoryRoot, 'web/public/models/unet32.onnx')),
    { executionProviders: ['wasm'], graphOptimizationLevel: 'all' },
  );
  const output = await session.run({
    input_mask: new ort.Tensor('float32', tensor, [1, 2, 32, 32]),
  });
  const probabilities = getValidatedProbabilityMap(
    output.nearest_region_mask.data,
    output.nearest_region_mask.dims,
    [1, 1, 32, 32],
  );

  const line = new Uint8ClampedArray(32 * 32 * 4);
  for (const index of caseDefinition.tensor.channel_0_active_indices) {
    line.set([0, 0, 0, 255], index * 4);
  }
  const lineImage = { data: line, width: 32, height: 32 };
  const labels = segmentLineRegions(lineImage).labels;
  const coloring = new Uint8ClampedArray(32 * 32 * 4);
  for (let index = 0; index < labels.length; index++) {
    if (labels[index] === 1) coloring.set([240, 20, 20, 255], index * 4);
    if (labels[index] > 1) coloring.set([20, 20, 240, 255], index * 4);
  }
  for (const index of caseDefinition.tensor.channel_1_active_indices) {
    coloring.set([0, 0, 0, 0], index * 4);
  }
  const selection = selectCanonicalRegion(
    { data: coloring, width: 32, height: 32 },
    labels,
    probabilities,
  );
  assert.equal(selection.label, 2);
  assert.deepEqual(selection.rgb, [20, 20, 240]);
  assert.ok(Math.abs(selection.meanProbability - 0.8431808595754662) <= 1e-5);
  await session.release();
});
