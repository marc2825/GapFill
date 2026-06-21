import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildGapMaskForPatch,
  excludeTargetGapFromGuides,
} from '../../utils/GapFill/onnxGapMask.ts';

function createOpaquePatch(width, height) {
  const data = new Uint8ClampedArray(width * height * 4);
  const validPixels = new Uint8Array(width * height);

  for (let index = 0; index < width * height; index++) {
    data[index * 4 + 3] = 255;
    validPixels[index] = 1;
  }

  return { data, width, height, validPixels };
}

function setTransparent(patch, x, y) {
  patch.data[(y * patch.width + x) * 4 + 3] = 0;
}

const patchBounds = {
  virtualX: 0,
  virtualY: 0,
  sourceX: 0,
  sourceY: 0,
  sourceWidth: 5,
  sourceHeight: 5,
  destinationX: 0,
  destinationY: 0,
};

test('fallback masks only the transparent component connected to gapCenter', () => {
  const patch = createOpaquePatch(5, 5);
  setTransparent(patch, 1, 1);
  setTransparent(patch, 2, 1);
  setTransparent(patch, 4, 4);

  const mask = buildGapMaskForPatch(patch, patchBounds, { x: 1, y: 1 });

  assert.equal(mask[1 * 5 + 1], 1);
  assert.equal(mask[1 * 5 + 2], 1);
  assert.equal(mask[4 * 5 + 4], 0);
});

test('fallback does not mark virtual padding as a gap', () => {
  const patch = createOpaquePatch(4, 4);
  patch.validPixels[0] = 0;
  patch.data[3] = 0;

  const mask = buildGapMaskForPatch(patch, patchBounds, { x: 0, y: 0 });

  assert.equal(mask[0], 0);
});

test('explicit gapPixels masks only the provided current gap coordinates', () => {
  const patch = createOpaquePatch(5, 5);
  setTransparent(patch, 0, 0);
  setTransparent(patch, 4, 4);

  const mask = buildGapMaskForPatch(
    patch,
    patchBounds,
    { x: 0, y: 0 },
    [{ x: 4, y: 4 }],
  );

  assert.equal(mask[0], 0);
  assert.equal(mask[4 * 5 + 4], 1);
});

test('explicit gapPixels ignore opaque pixels and virtual padding', () => {
  const patch = createOpaquePatch(3, 2);
  patch.validPixels[1] = 0;
  setTransparent(patch, 1, 0);

  const mask = buildGapMaskForPatch(
    patch,
    patchBounds,
    { x: 0, y: 0 },
    [
      { x: 0, y: 0 },
      { x: 1, y: 0 },
    ],
  );

  assert.deepEqual([...mask], [0, 0, 0, 0, 0, 0]);
});

test('supports rectangular patches when masking explicit gap pixels', () => {
  const patch = createOpaquePatch(3, 2);
  setTransparent(patch, 2, 1);

  const mask = buildGapMaskForPatch(
    patch,
    patchBounds,
    { x: 0, y: 0 },
    [{ x: 2, y: 1 }],
  );

  assert.equal(mask.length, 6);
  assert.equal(mask[5], 1);
});

test('removes only the target Guide gap from the prediction Guide mask', () => {
  const guides = createOpaquePatch(3, 1);
  const gapMask = new Float32Array([0, 1, 0]);

  const effectiveGuides = excludeTargetGapFromGuides(guides, gapMask);

  assert.deepEqual(
    [
      effectiveGuides.data[3],
      effectiveGuides.data[7],
      effectiveGuides.data[11],
    ],
    [255, 0, 255],
  );
  assert.deepEqual(
    [guides.data[3], guides.data[7], guides.data[11]],
    [255, 255, 255],
  );
});
