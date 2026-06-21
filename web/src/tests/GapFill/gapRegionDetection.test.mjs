import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildGapCandidateMap,
  findConnectedCandidateRegion,
  findConnectedRegion,
  GUIDE_GAP_CANDIDATE,
  TRANSPARENT_GAP_CANDIDATE,
} from '../../utils/GapFill/gapRegionDetection.ts';

function createPixels(alphas) {
  const pixels = new Uint8ClampedArray(alphas.length * 4);
  alphas.forEach((alpha, index) => {
    pixels[index * 4 + 3] = alpha;
  });
  return pixels;
}

test('detects a connected transparent region at the threshold', () => {
  const pixels = createPixels([0, 0, 255, 0]);
  const visited = new Uint8Array(4);
  const stack = new Uint32Array(4);

  const region = findConnectedRegion(
    pixels,
    4,
    1,
    0,
    2,
    visited,
    stack,
  );

  assert.deepEqual(region, [{ x: 0, y: 0 }, { x: 1, y: 0 }]);
  assert.equal(visited[3], 0);
});

test('discards an oversized region but marks all of it visited', () => {
  const pixels = createPixels([0, 0, 0, 255]);
  const visited = new Uint8Array(4);
  const stack = new Uint32Array(4);

  const region = findConnectedRegion(
    pixels,
    4,
    1,
    0,
    2,
    visited,
    stack,
  );

  assert.equal(region, null);
  assert.deepEqual([...visited], [1, 1, 1, 0]);
});

test('classifies ordinary gaps and transparent Coloring above Guides separately', () => {
  const colored = createPixels([0, 0, 0, 255]);
  const lineArtMask = new Uint8Array([0, 0, 1, 0]);
  const guidesMask = new Uint8Array([0, 1, 1, 1]);

  const candidates = buildGapCandidateMap(
    colored,
    lineArtMask,
    guidesMask,
  );

  assert.deepEqual(
    [...candidates],
    [TRANSPARENT_GAP_CANDIDATE, GUIDE_GAP_CANDIDATE, 0, 0],
  );
});

test('does not connect an adjacent Guide gap to a transparent gap', () => {
  const candidates = new Uint8Array([
    TRANSPARENT_GAP_CANDIDATE,
    GUIDE_GAP_CANDIDATE,
  ]);
  const visited = new Uint8Array(2);
  const stack = new Uint32Array(2);

  const transparentRegion = findConnectedCandidateRegion(
    candidates,
    2,
    1,
    0,
    TRANSPARENT_GAP_CANDIDATE,
    2,
    visited,
    stack,
  );
  const guideRegion = findConnectedCandidateRegion(
    candidates,
    2,
    1,
    1,
    GUIDE_GAP_CANDIDATE,
    2,
    visited,
    stack,
  );

  assert.deepEqual(transparentRegion, [{ x: 0, y: 0 }]);
  assert.deepEqual(guideRegion, [{ x: 1, y: 0 }]);
});
