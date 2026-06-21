import assert from 'node:assert/strict';
import test from 'node:test';
import {
  fillGapRegion,
  fillGapRegions,
} from '../../utils/GapFill/gapFillApplication.ts';

test('Apply All paints every region with its predicted color', () => {
  const data = new Uint8ClampedArray(3 * 4);
  let getImageDataCalls = 0;
  let putImageDataCalls = 0;
  const context = {
    getImageData: () => {
      getImageDataCalls++;
      return { data, width: 3, height: 1 };
    },
    putImageData: () => {
      putImageDataCalls++;
    },
  };
  const canvas = {
    width: 3,
    height: 1,
    getContext: () => context,
  };

  fillGapRegions(canvas, [
    {
      pixels: [{ x: 0, y: 0 }],
      predictedColor: '#112233',
    },
    {
      pixels: [{ x: 2, y: 0 }],
      predictedColor: '#abcdef',
    },
  ]);

  assert.deepEqual([...data.slice(0, 4)], [0x11, 0x22, 0x33, 0xff]);
  assert.deepEqual([...data.slice(8, 12)], [0xab, 0xcd, 0xef, 0xff]);
  assert.equal(getImageDataCalls, 1);
  assert.equal(putImageDataCalls, 1);
});

test('an invalid color is reported and does not paint the region', () => {
  const data = new Uint8ClampedArray(4);
  let putImageDataCalls = 0;
  const errors = [];
  const originalConsoleError = console.error;
  const context = {
    getImageData: () => ({ data, width: 1, height: 1 }),
    putImageData: () => {
      putImageDataCalls++;
    },
  };
  const canvas = {
    width: 1,
    height: 1,
    getContext: () => context,
  };

  console.error = (...args) => errors.push(args);
  try {
    fillGapRegion(
      canvas,
      {
        pixels: [{ x: 0, y: 0 }],
        predictedColor: '#123456',
      },
      'not-a-color',
    );
  } finally {
    console.error = originalConsoleError;
  }

  assert.deepEqual([...data], [0, 0, 0, 0]);
  assert.equal(putImageDataCalls, 0);
  assert.equal(errors.length, 1);
  assert.match(errors[0][0], /invalid color.*not-a-color/i);
});
