import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildOverflowOwnerRegions,
  getOverflowOwnerAtPoint,
} from '../../overflow/ownerRegions.ts';

function makeAlphaCanvas(width, height, opaquePixels) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (const index of opaquePixels) {
    data[index * 4 + 3] = 255;
  }

  return {
    width,
    height,
    getContext() {
      return {
        getImageData() {
          return { data };
        },
      };
    },
  };
}

test('builds large owner regions separated by line art alpha', () => {
  const width = 5;
  const height = 3;
  const lineArt = makeAlphaCanvas(width, height, [2, 7, 12]);

  const { owners, ownerLabels } = buildOverflowOwnerRegions({
    width,
    height,
    minArea: 2,
    lineArtCanvas: lineArt,
  });

  assert.equal(owners.length, 2);
  assert.equal(ownerLabels[0], 1);
  assert.equal(ownerLabels[4], 2);
  assert.equal(ownerLabels[2], 0);
});

test('filters out components at or below the owner minimum area', () => {
  const width = 3;
  const height = 1;
  const lineArt = makeAlphaCanvas(width, height, [1]);

  const { owners, ownerLabels } = buildOverflowOwnerRegions({
    width,
    height,
    minArea: 2,
    lineArtCanvas: lineArt,
  });

  assert.equal(owners.length, 0);
  assert.deepEqual([...ownerLabels], [0, 0, 0]);
});

test('finds an owner at a canvas point', () => {
  const width = 3;
  const height = 1;
  const { owners, ownerLabels } = buildOverflowOwnerRegions({
    width,
    height,
    minArea: 1,
  });

  const owner = getOverflowOwnerAtPoint(
    { owners, ownerLabels, width, height },
    { x: 1, y: 0 },
  );

  assert.equal(owner?.id, 'owner-1');
});
