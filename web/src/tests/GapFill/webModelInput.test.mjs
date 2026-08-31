import assert from 'node:assert/strict';
import test from 'node:test';

import { buildLegacyWebModelInput } from '../../utils/GapFill/webModelInput.ts';

function patch(width, height, activeIndices = [], validIndices) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (const index of activeIndices) data[index * 4 + 3] = 255;
  const validPixels = new Uint8Array(width * height);
  if (validIndices) {
    for (const index of validIndices) validPixels[index] = 1;
  } else {
    validPixels.fill(1);
  }
  return { data, width, height, validPixels };
}

function activeIndices(channel) {
  return [...channel.entries()]
    .filter(([, value]) => value !== 0)
    .map(([index]) => index);
}

test('restores pre-addon Web channel 0 as Line OR effective Guides', () => {
  const gap = new Float32Array([0, 0, 1, 0]);
  const tensor = buildLegacyWebModelInput(
    patch(2, 2, [0]),
    patch(2, 2, [1]),
    gap,
    false,
  );

  assert.deepEqual(activeIndices(tensor.slice(0, 4)), [0, 1]);
  assert.deepEqual(activeIndices(tensor.slice(4)), [2]);
});

test('a missing Guide contribution leaves the historical Line-alpha channel', () => {
  const tensor = buildLegacyWebModelInput(
    patch(2, 2, [0, 3]),
    patch(2, 2),
    new Float32Array(4),
    false,
  );

  assert.deepEqual(activeIndices(tensor.slice(0, 4)), [0, 3]);
});

test('a target Guide gap removes only its own Guide pixels', () => {
  const gap = new Float32Array([0, 1, 0, 0]);
  const tensor = buildLegacyWebModelInput(
    patch(2, 2, [0]),
    patch(2, 2, [1, 2]),
    gap,
    true,
  );

  assert.deepEqual(activeIndices(tensor.slice(0, 4)), [0, 2]);
  assert.deepEqual(activeIndices(tensor.slice(4)), [1]);
});

test('zero-padded transparent pixels stay zero in both model channels', () => {
  const tensor = buildLegacyWebModelInput(
    patch(2, 2, [], [3]),
    patch(2, 2, [], [3]),
    new Float32Array(4),
    false,
  );

  assert.deepEqual([...tensor], new Array(8).fill(0));
});

test('Guide geometry demonstrably changes only the restored Web boundary channel', () => {
  const line = patch(2, 2, [0]);
  const gap = new Float32Array([0, 0, 0, 1]);
  const lineOnly = buildLegacyWebModelInput(
    line,
    patch(2, 2),
    gap,
    false,
  );
  const lineAndGuide = buildLegacyWebModelInput(
    line,
    patch(2, 2, [2]),
    gap,
    false,
  );

  assert.notDeepEqual([...lineOnly.slice(0, 4)], [...lineAndGuide.slice(0, 4)]);
  assert.deepEqual([...lineOnly.slice(4)], [...lineAndGuide.slice(4)]);
});
