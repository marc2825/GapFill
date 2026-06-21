import assert from 'node:assert/strict';
import test from 'node:test';
import { predictColorGreedy } from '../../utils/GapFill/greedyColorPrediction.ts';

function createPixels(colors) {
  const pixels = new Uint8ClampedArray(colors.length * 4);

  colors.forEach((color, index) => {
    if (!color) return;
    pixels.set(color, index * 4);
  });

  return pixels;
}

test('uses the supplied fallback color when no nearby color exists', () => {
  const pixels = createPixels([null]);

  const color = predictColorGreedy(
    pixels,
    1,
    1,
    [{ x: 0, y: 0 }],
    '#123456',
  );

  assert.equal(color, '#123456');
});

test('does not inspect the extra pixel beyond the expansion radius', () => {
  const pixels = createPixels([
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    [255, 0, 0, 255],
  ]);

  const color = predictColorGreedy(
    pixels,
    8,
    1,
    [{ x: 1, y: 0 }],
    '#123456',
  );

  assert.equal(color, '#123456');
});

test('allows black from the colored image as a candidate', () => {
  const pixels = createPixels([null, [0, 0, 0, 255]]);

  const color = predictColorGreedy(
    pixels,
    2,
    1,
    [{ x: 0, y: 0 }],
  );

  assert.equal(color, '#000000');
});

test('ignores pixels marked as Line Art or Guides', () => {
  const pixels = createPixels([
    null,
    [0, 0, 0, 255],
    [255, 0, 0, 255],
  ]);
  const excludedPixels = new Uint8Array([0, 1, 0]);

  const color = predictColorGreedy(
    pixels,
    3,
    1,
    [{ x: 0, y: 0 }],
    '#123456',
    excludedPixels,
  );

  assert.equal(color, '#ff0000');
});
