import assert from 'node:assert/strict';
import test from 'node:test';
import { floodFill, getPixelColor } from '../utils/canvasUtils.ts';
import {
  fillEncloseAndFillSelection,
  floodFillWithReference,
} from '../utils/canvasToolUtils.ts';

function createCanvas(width, height) {
  let getImageDataCalls = 0;
  const context = {
    getImageData: () => {
      getImageDataCalls++;
      return { data: new Uint8ClampedArray(width * height * 4) };
    },
    putImageData: () => {},
  };

  return {
    canvas: {
      width,
      height,
      getContext: () => context,
    },
    getImageDataCalls: () => getImageDataCalls,
  };
}

test('out-of-bounds color reads return transparent without reading canvas data', () => {
  const { canvas, getImageDataCalls } = createCanvas(2, 2);

  assert.equal(getPixelColor(canvas, -1, 0), 'rgba(0,0,0,0)');
  assert.equal(getPixelColor(canvas, 2, 0), 'rgba(0,0,0,0)');
  assert.equal(getImageDataCalls(), 0);
});

test('out-of-bounds flood fills do not read canvas data', () => {
  const target = createCanvas(2, 2);
  const reference = createCanvas(2, 2);

  floodFill(target.canvas, -1, 0, '#ffffff');
  floodFillWithReference(
    target.canvas,
    reference.canvas,
    2,
    0,
    '#ffffff',
  );

  assert.equal(target.getImageDataCalls(), 0);
  assert.equal(reference.getImageDataCalls(), 0);
});

test('Enclose and Fill selections larger than 100,000 pixels are processed completely', () => {
  const width = 400;
  const height = 400;
  const activePixels = new Uint8ClampedArray(width * height * 4);
  const sourcePixels = new Uint8ClampedArray(width * height * 4);
  for (let index = 0; index < width * height; index++) {
    sourcePixels[index * 4] = 10;
    sourcePixels[index * 4 + 1] = 20;
    sourcePixels[index * 4 + 2] = 30;
    sourcePixels[index * 4 + 3] = 255;
  }

  const activeCanvas = {
    width,
    height,
    getContext: () => ({
      getImageData: () => ({ data: activePixels }),
      putImageData: () => {},
    }),
  };
  const sourceCanvas = {
    width,
    height,
    getContext: () => ({
      getImageData: () => ({ data: sourcePixels }),
    }),
  };

  fillEncloseAndFillSelection(
    activeCanvas,
    sourceCanvas,
    [
      { x: -1, y: -1 },
      { x: width + 1, y: -1 },
      { x: width + 1, y: height + 1 },
      { x: -1, y: height + 1 },
    ],
    '#abcdef',
  );

  const finalPixel = (width * height - 1) * 4;
  assert.deepEqual(
    [...activePixels.slice(finalPixel, finalPixel + 4)],
    [0xab, 0xcd, 0xef, 0xff],
  );
});
