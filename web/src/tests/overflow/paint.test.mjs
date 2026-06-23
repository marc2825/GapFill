import assert from 'node:assert/strict';
import test from 'node:test';
import { paintOverflowOwner } from '../../overflow/paint.ts';

function makeCanvas(width, height, pixels) {
  const data = new Uint8ClampedArray(width * height * 4);
  pixels.forEach((rgba, index) => {
    data[index * 4] = rgba[0];
    data[index * 4 + 1] = rgba[1];
    data[index * 4 + 2] = rgba[2];
    data[index * 4 + 3] = rgba[3];
  });

  return {
    width,
    height,
    data,
    getContext() {
      return {
        getImageData() {
          return { data };
        },
        putImageData(imageData) {
          data.set(imageData.data);
        },
      };
    },
  };
}

const owner = {
  id: 'owner-1',
  label: 1,
  pixels: [{ x: 0, y: 0 }, { x: 1, y: 0 }],
  center: { x: 0, y: 0 },
  boundingBox: { x: 0, y: 0, width: 2, height: 1 },
  area: 2,
};

test('fills a transparent owner and linked gap with the selected color', () => {
  const canvas = makeCanvas(3, 1, [
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
  ]);

  const result = paintOverflowOwner({
    canvas,
    owner,
    linkedGaps: [{
      id: 'gap-1',
      center: { x: 2, y: 0 },
      pixels: [{ x: 2, y: 0 }],
      kind: 'transparent',
    }],
    clickPoint: { x: 0, y: 0 },
    fillColor: '#123456',
  });

  assert.equal(result.changed, true);
  assert.deepEqual(result.propagatedGapIds, ['gap-1']);
  assert.deepEqual([...canvas.data], [
    0x12, 0x34, 0x56, 255,
    0x12, 0x34, 0x56, 255,
    0x12, 0x34, 0x56, 255,
  ]);
});

test('propagates an existing owner color without repainting the owner', () => {
  const canvas = makeCanvas(3, 1, [
    [10, 20, 30, 255],
    [10, 20, 30, 255],
    [0, 0, 0, 0],
  ]);

  const result = paintOverflowOwner({
    canvas,
    owner,
    linkedGaps: [{
      id: 'gap-1',
      center: { x: 2, y: 0 },
      pixels: [{ x: 2, y: 0 }],
      kind: 'transparent',
    }],
    clickPoint: { x: 0, y: 0 },
    fillColor: '#ffffff',
  });

  assert.equal(result.usedExistingOwnerColor, true);
  assert.deepEqual([...canvas.data], [
    10, 20, 30, 255,
    10, 20, 30, 255,
    10, 20, 30, 255,
  ]);
});
