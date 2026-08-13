import assert from 'node:assert/strict';
import { readFile, readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import * as ort from 'onnxruntime-web';
import {
  buildGapCandidateMap,
  findConnectedCandidateRegion,
  GUIDE_GAP_CANDIDATE,
} from '../../utils/GapFill/gapRegionDetection.ts';
import {
  buildGapMaskForPatch,
  excludeTargetGapFromGuides,
} from '../../utils/GapFill/onnxGapMask.ts';
import {
  calculateCenteredPatchBounds,
  copyIntoZeroPaddedPatch,
} from '../../utils/GapFill/onnxPatchExtraction.ts';
import {
  segmentColoredRegions,
  selectRegionColor,
} from '../../utils/GapFill/onnxPostprocessing.ts';

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../../../',
);
const fixtureRoot = path.join(repositoryRoot, 'tests/fixtures/gapfill');

function loadJson(relativePath) {
  return JSON.parse(readFileSync(path.join(fixtureRoot, relativePath), 'utf8'));
}

function decodePaletteRgba(raster) {
  const height = raster.rows.length;
  const width = raster.rows[0]?.length || 0;
  const data = new Uint8ClampedArray(width * height * 4);
  raster.rows.forEach((row, y) => {
    assert.equal(row.length, width);
    [...row].forEach((symbol, x) => {
      data.set(raster.palette[symbol], (y * width + x) * 4);
    });
  });
  return { data, width, height };
}

function decodeRows(raster) {
  return new Uint8Array(raster.rows.flat());
}

function normalizeComponents(regions, width, height) {
  const components = regions.map(({ points, kind }) => {
    const indices = points
      .map(({ x, y }) => y * width + x)
      .sort((left, right) => left - right);
    const xs = indices.map((index) => index % width);
    const ys = indices.map((index) => Math.floor(index / width));
    return {
      id: 0,
      kind,
      pixel_indices: indices,
      pixel_count: indices.length,
      centroid: [
        Math.floor(xs.reduce((sum, value) => sum + value, 0) / xs.length),
        Math.floor(ys.reduce((sum, value) => sum + value, 0) / ys.length),
      ],
      bbox: [
        Math.min(...xs),
        Math.min(...ys),
        Math.max(...xs) - Math.min(...xs) + 1,
        Math.max(...ys) - Math.min(...ys) + 1,
      ],
      touches_image_edge: indices.some((index) => {
        const x = index % width;
        const y = Math.floor(index / width);
        return x === 0 || y === 0 || x + 1 === width || y + 1 === height;
      }),
      touches_selection_edge: false,
    };
  });
  components.sort(
    (left, right) => left.pixel_indices[0] - right.pixel_indices[0],
  );
  components.forEach((component, index) => {
    component.id = index;
  });
  return components;
}

function runWebDetection(caseDefinition) {
  const colored = decodePaletteRgba(caseDefinition.rasters.coloring_rgba);
  const lineMask = decodeRows(caseDefinition.rasters.line_alpha).map(
    (value) => (value > 0 ? 1 : 0),
  );
  const guideMask = decodeRows(caseDefinition.rasters.guide_alpha).map(
    (value) => (value > 0 ? 1 : 0),
  );
  const candidates = buildGapCandidateMap(
    colored.data,
    lineMask,
    guideMask,
  );
  const visited = new Uint8Array(caseDefinition.width * caseDefinition.height);
  const stack = new Uint32Array(visited.length);
  const regions = [];
  for (let index = 0; index < visited.length; index++) {
    const kind = candidates[index];
    if (kind === 0 || visited[index] !== 0) continue;
    const points = findConnectedCandidateRegion(
      candidates,
      caseDefinition.width,
      caseDefinition.height,
      index,
      kind,
      caseDefinition.threshold,
      visited,
      stack,
    );
    if (points) {
      regions.push({
        points,
        kind: kind === GUIDE_GAP_CANDIDATE ? 'guide' : 'transparent',
      });
    }
  }
  return normalizeComponents(
    regions,
    caseDefinition.width,
    caseDefinition.height,
  );
}

function sourcePatch(rgba, bounds, patchSize) {
  const source = new Uint8ClampedArray(
    bounds.sourceWidth * bounds.sourceHeight * 4,
  );
  for (let y = 0; y < bounds.sourceHeight; y++) {
    for (let x = 0; x < bounds.sourceWidth; x++) {
      const sourceIndex =
        ((bounds.sourceY + y) * rgba.width + bounds.sourceX + x) * 4;
      const destinationIndex = (y * bounds.sourceWidth + x) * 4;
      source.set(rgba.data.slice(sourceIndex, sourceIndex + 4), destinationIndex);
    }
  }
  return copyIntoZeroPaddedPatch(
    source,
    bounds.sourceWidth,
    bounds.sourceHeight,
    patchSize,
    bounds.destinationX,
    bounds.destinationY,
  );
}

function sparseSource(caseDefinition) {
  const { width, height } = caseDefinition.source;
  const coloring = {
    width,
    height,
    data: new Uint8ClampedArray(width * height * 4),
  };
  for (let index = 0; index < width * height; index++) {
    coloring.data[index * 4 + 3] = 255;
  }
  for (const index of caseDefinition.source.gap_indices) {
    coloring.data[index * 4 + 3] = 0;
  }
  const line = {
    width,
    height,
    data: new Uint8ClampedArray(width * height * 4),
  };
  const guide = {
    width,
    height,
    data: new Uint8ClampedArray(width * height * 4),
  };
  for (const index of caseDefinition.source.line_active_indices) {
    line.data[index * 4 + 3] = 255;
  }
  for (const index of caseDefinition.source.guide_active_indices) {
    guide.data[index * 4 + 3] = 255;
  }
  return { coloring, line, guide };
}

function activeIndices(values) {
  return [...values]
    .map((value, index) => (value > 0 ? index : -1))
    .filter((index) => index >= 0);
}

function denseRgba(caseDefinition) {
  return decodePaletteRgba(caseDefinition.coloring_rgba);
}

test('Phase 2 web detection matches independently characterized current behavior', () => {
  const detection = loadJson('detection/cases.json');
  const characterization = loadJson('parity/characterization.json');
  const cases = new Map(detection.cases.map((item) => [item.id, item]));
  for (const row of characterization.detection) {
    const caseDefinition = cases.get(row.case_id);
    assert.ok(caseDefinition, row.case_id);
    assert.deepEqual(
      runWebDetection(caseDefinition),
      row.observations.web_current,
      row.case_id,
    );
  }
});

test('Phase 2 web patch helpers consume every shared patch fixture', () => {
  const data = loadJson('patch/cases.json');
  for (const caseDefinition of data.cases) {
    const variants = new Map(
      caseDefinition.expectations.map((item) => [item.variant, item.result]),
    );
    const variantName =
      caseDefinition.id === 'P006_target_guide_suppression'
        ? 'suppress_target_guide'
        : caseDefinition.id === 'P005_guide_delta'
          ? 'line_plus_guide'
          : 'training_line_only';
    const expected = variants.get(variantName);
    assert.ok(expected, caseDefinition.id);
    const center = expected.centroid;
    const bounds = calculateCenteredPatchBounds(
      caseDefinition.source.width,
      caseDefinition.source.height,
      center[0],
      center[1],
      32,
    );
    assert.deepEqual(
      {
        virtual_x: bounds.virtualX,
        virtual_y: bounds.virtualY,
        source_x: bounds.sourceX,
        source_y: bounds.sourceY,
        source_width: bounds.sourceWidth,
        source_height: bounds.sourceHeight,
        destination_x: bounds.destinationX,
        destination_y: bounds.destinationY,
      },
      expected.bounds,
      caseDefinition.id,
    );
    const { coloring, line, guide } = sparseSource(caseDefinition);
    const coloringPatch = sourcePatch(coloring, bounds, 32);
    const linePatch = sourcePatch(line, bounds, 32);
    let guidePatch = sourcePatch(guide, bounds, 32);
    const gapPixels = caseDefinition.source.gap_indices.map((index) => ({
      x: index % caseDefinition.source.width,
      y: Math.floor(index / caseDefinition.source.width),
    }));
    const gapMask = buildGapMaskForPatch(
      coloringPatch,
      bounds,
      { x: center[0], y: center[1] },
      gapPixels,
    );
    if (caseDefinition.id === 'P006_target_guide_suppression') {
      guidePatch = excludeTargetGapFromGuides(guidePatch, gapMask);
    }
    const boundary = new Uint8Array(32 * 32);
    for (let index = 0; index < boundary.length; index++) {
      boundary[index] =
        linePatch.data[index * 4 + 3] > 0 ||
        guidePatch.data[index * 4 + 3] > 0
          ? 1
          : 0;
    }
    assert.deepEqual(
      activeIndices(boundary),
      expected.tensor.channel_0_active_indices,
      `${caseDefinition.id} channel 0`,
    );
    assert.deepEqual(
      activeIndices(gapMask),
      expected.tensor.channel_1_active_indices,
      `${caseDefinition.id} channel 1`,
    );
  }
});

test('Phase 2 web postprocessing matches characterized current behavior', () => {
  const postprocess = loadJson('postprocess/cases.json');
  const characterization = loadJson('parity/characterization.json');
  const cases = new Map(postprocess.cases.map((item) => [item.id, item]));
  for (const row of characterization.postprocess) {
    const caseDefinition = cases.get(row.case_id);
    assert.ok(caseDefinition, row.case_id);
    const image = denseRgba(caseDefinition);
    const labelsName = Object.hasOwn(caseDefinition.label_maps, 'colored_components')
      ? 'colored_components'
      : Object.hasOwn(caseDefinition.label_maps, 'seed_relative')
        ? 'seed_relative'
        : Object.keys(caseDefinition.label_maps)[0];
    const labels = new Int32Array(caseDefinition.label_maps[labelsName].flat());
    if (Object.hasOwn(caseDefinition.label_maps, 'seed_relative')) {
      const blank = {
        width: image.width,
        height: image.height,
        data: new Uint8ClampedArray(image.width * image.height * 4),
      };
      const actual = segmentColoredRegions(image, blank, blank);
      assert.deepEqual(
        [...actual.labels],
        caseDefinition.label_maps.seed_relative.flat(),
        `${row.case_id} labels`,
      );
    }
    const color = selectRegionColor(
      image,
      labels,
      Math.max(...labels),
      new Float32Array(caseDefinition.probability_map.flat()),
      '#ff00ff',
    );
    assert.deepEqual(color, row.observations.web_current.rgb, row.case_id);
  }
});

test('Phase 2 ONNX outputs match Python CPU characterization in Web WASM', async () => {
  const modelCases = loadJson('model/cases.json');
  const modelBytes = await new Promise((resolve, reject) => {
    readFile(
      path.join(repositoryRoot, 'web/public/models/unet32.onnx'),
      (error, data) => (error ? reject(error) : resolve(data)),
    );
  });
  const session = await ort.InferenceSession.create(modelBytes, {
    executionProviders: ['wasm'],
    graphOptimizationLevel: 'all',
  });
  assert.deepEqual(session.inputNames, [modelCases.contract.input.name]);
  assert.deepEqual(session.outputNames, [modelCases.contract.output.name]);
  const absolute = modelCases.comparison_tolerance.absolute;
  const relative = modelCases.comparison_tolerance.relative;
  let maximumAbsoluteDelta = 0;
  for (const caseDefinition of modelCases.cases) {
    const input = new Float32Array(2 * 32 * 32);
    for (const index of caseDefinition.tensor.channel_0_active_indices) {
      input[index] = 1;
    }
    for (const index of caseDefinition.tensor.channel_1_active_indices) {
      input[32 * 32 + index] = 1;
    }
    const output = await session.run({
      [session.inputNames[0]]: new ort.Tensor('float32', input, [1, 2, 32, 32]),
    });
    const actual = output[session.outputNames[0]].data;
    const expected = caseDefinition.characterized_output.values_row_major;
    assert.equal(actual.length, expected.length, caseDefinition.id);
    for (let index = 0; index < actual.length; index++) {
      const delta = Math.abs(actual[index] - expected[index]);
      maximumAbsoluteDelta = Math.max(maximumAbsoluteDelta, delta);
      const bound = absolute + relative * Math.abs(expected[index]);
      assert.ok(
        delta <= bound,
        `${caseDefinition.id}[${index}] delta ${delta} exceeds ${bound}`,
      );
    }
  }
  console.log(
    `Phase 2 Web WASM/Python CPU maximum absolute model delta: ${maximumAbsoluteDelta}`,
  );
  await session.release();
});
