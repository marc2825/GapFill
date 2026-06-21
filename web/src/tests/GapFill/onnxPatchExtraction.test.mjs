import assert from 'node:assert/strict';
import test from 'node:test';
import {
  assertMatchingCanvasDimensions,
  calculateCenteredPatchBounds,
  copyIntoZeroPaddedPatch,
  extractCanvasPatchWithBounds,
} from '../../utils/GapFill/onnxPatchExtraction.ts';

test('rejects ONNX input canvases with different dimensions', () => {
  assert.throws(
    () => assertMatchingCanvasDimensions(
      { width: 100, height: 80 },
      { width: 99, height: 80 },
    ),
    /must have matching dimensions/i,
  );
});

test('keeps a top-left edge gap at patch coordinate 16,16', () => {
  const bounds = calculateCenteredPatchBounds(100, 80, 0, 0, 32);

  assert.equal(bounds.virtualX, -16);
  assert.equal(bounds.virtualY, -16);
  assert.equal(bounds.sourceX, 0);
  assert.equal(bounds.sourceY, 0);
  assert.equal(bounds.sourceWidth, 16);
  assert.equal(bounds.sourceHeight, 16);
  assert.equal(bounds.destinationX, 16);
  assert.equal(bounds.destinationY, 16);
  assert.equal(0 - bounds.virtualX, 16);
  assert.equal(0 - bounds.virtualY, 16);
});

test('keeps a bottom-right edge gap centered and clips the source rectangle', () => {
  const bounds = calculateCenteredPatchBounds(100, 80, 99, 79, 32);

  assert.equal(bounds.virtualX, 83);
  assert.equal(bounds.virtualY, 63);
  assert.equal(bounds.sourceWidth, 17);
  assert.equal(bounds.sourceHeight, 17);
  assert.equal(bounds.destinationX, 0);
  assert.equal(bounds.destinationY, 0);
  assert.equal(99 - bounds.virtualX, 16);
  assert.equal(79 - bounds.virtualY, 16);
});

test('floors fractional centers to match ML preprocessing', () => {
  const bounds = calculateCenteredPatchBounds(100, 80, 10.75, 20.75, 32);

  assert.equal(bounds.virtualX, -6);
  assert.equal(bounds.virtualY, 4);
  assert.equal(Math.floor(10.75) - bounds.virtualX, 16);
  assert.equal(Math.floor(20.75) - bounds.virtualY, 16);
});

test('copies only canvas pixels and leaves the virtual exterior zero padded', () => {
  const source = new Uint8ClampedArray([
    1, 2, 3, 255,
    4, 5, 6, 255,
    7, 8, 9, 255,
    10, 11, 12, 255,
  ]);

  const patch = copyIntoZeroPaddedPatch(source, 2, 2, 4, 2, 2);
  const firstCopiedPixel = (2 * 4 + 2) * 4;
  const lastCopiedPixel = (3 * 4 + 3) * 4;

  assert.deepEqual(
    [...patch.data.slice(firstCopiedPixel, firstCopiedPixel + 4)],
    [1, 2, 3, 255],
  );
  assert.deepEqual(
    [...patch.data.slice(lastCopiedPixel, lastCopiedPixel + 4)],
    [10, 11, 12, 255],
  );
  assert.deepEqual([...patch.data.slice(0, 4)], [0, 0, 0, 0]);
  assert.equal(patch.validPixels[0], 0);
  assert.equal(patch.validPixels[2 * 4 + 2], 1);
});

test('extracts multiple canvases with the same precomputed bounds', () => {
  const requestedRectangles = [];
  const canvas = {
    getContext: () => ({
      getImageData: (x, y, width, height) => {
        requestedRectangles.push({ x, y, width, height });
        return { data: new Uint8ClampedArray(width * height * 4) };
      },
    }),
  };
  const bounds = calculateCenteredPatchBounds(100, 80, 0, 0, 32);

  extractCanvasPatchWithBounds(canvas, bounds, 32);
  extractCanvasPatchWithBounds(canvas, bounds, 32);

  assert.deepEqual(requestedRectangles, [
    { x: 0, y: 0, width: 16, height: 16 },
    { x: 0, y: 0, width: 16, height: 16 },
  ]);
});
