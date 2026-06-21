import assert from 'node:assert/strict';
import test from 'node:test';
import {
  segmentColoredRegions,
  selectRegionColor,
} from '../../utils/GapFill/onnxPostprocessing.ts';

function image(width, height, pixels) {
  return {
    width,
    height,
    data: new Uint8ClampedArray(pixels),
  };
}

function transparentImage(width, height) {
  return image(width, height, new Array(width * height * 4).fill(0));
}

test('Line Art and Guides split painted regions, including one-pixel regions', () => {
  const colored = image(3, 1, [
    255, 0, 0, 255,
    255, 0, 0, 255,
    255, 0, 0, 255,
  ]);
  const lineArt = transparentImage(3, 1);
  const guides = transparentImage(3, 1);

  lineArt.data[7] = 255;
  let segmentation = segmentColoredRegions(colored, lineArt, guides);
  assert.equal(segmentation.regionCount, 2);
  assert.notEqual(segmentation.labels[0], segmentation.labels[2]);

  lineArt.data[7] = 0;
  guides.data[7] = 255;
  segmentation = segmentColoredRegions(colored, lineArt, guides);
  assert.equal(segmentation.regionCount, 2);
  assert.notEqual(segmentation.labels[0], segmentation.labels[2]);
});

test('selects the modal color rather than the first pixel color', () => {
  const colored = image(3, 1, [
    255, 0, 0, 255,
    0, 0, 255, 255,
    0, 0, 255, 255,
  ]);

  const color = selectRegionColor(
    colored,
    new Int32Array([1, 1, 1]),
    1,
    new Float32Array([1, 1, 1]),
    '#000000',
  );

  assert.deepEqual(color, [0, 0, 255]);
});

test('selects the modal color only after choosing the best region', () => {
  const colored = image(5, 1, [
    255, 0, 0, 255,
    255, 0, 0, 255,
    0, 0, 255, 255,
    0, 255, 0, 255,
    0, 255, 0, 255,
  ]);

  const color = selectRegionColor(
    colored,
    new Int32Array([1, 1, 2, 2, 2]),
    2,
    new Float32Array([0.1, 0.1, 0.9, 0.9, 0.9]),
    '#000000',
  );

  assert.deepEqual(color, [0, 255, 0]);
});
