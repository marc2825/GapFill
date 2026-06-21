import assert from 'node:assert/strict';
import test from 'node:test';
import {
  captureHistoryState,
  prepareHistoryCanvasBlobs,
} from '../utils/historySnapshot.ts';

function createLayer(id, encodeCounts, order = 0) {
  const canvas = {
    width: 32,
    height: 32,
    toBlob(callback) {
      encodeCounts.set(id, (encodeCounts.get(id) ?? 0) + 1);
      callback(new Blob([`${id}-${encodeCounts.get(id)}`]));
    },
  };

  return {
    id,
    name: id,
    visible: true,
    opacity: 1,
    order,
    canvas,
  };
}

async function capture(layers, previousState, changedIds, replace = false) {
  const changedLayerIds = new Set(changedIds);
  const preparedBlobs = prepareHistoryCanvasBlobs(
    layers,
    previousState,
    changedLayerIds,
    replace,
  );
  return captureHistoryState(
    layers,
    previousState,
    changedLayerIds,
    preparedBlobs,
  );
}

test('history re-encodes only changed layers and shares other blobs', async () => {
  const encodeCounts = new Map();
  const lineArt = createLayer('line-art', encodeCounts, 1);
  const coloring = createLayer('coloring', encodeCounts, 0);
  const initial = await capture(
    [lineArt, coloring],
    null,
    ['line-art', 'coloring'],
    true,
  );
  const next = await capture(
    [lineArt, coloring],
    initial,
    ['coloring'],
  );

  assert.equal(encodeCounts.get('line-art'), 1);
  assert.equal(encodeCounts.get('coloring'), 2);
  assert.strictEqual(
    next.layers.find((layer) => layer.id === 'line-art').canvasBlob,
    initial.layers.find((layer) => layer.id === 'line-art').canvasBlob,
  );
  assert.notStrictEqual(
    next.layers.find((layer) => layer.id === 'coloring').canvasBlob,
    initial.layers.find((layer) => layer.id === 'coloring').canvasBlob,
  );
});

test('metadata-only history entries do not encode canvas pixels', async () => {
  const encodeCounts = new Map();
  const firstLayer = createLayer('first', encodeCounts, 0);
  const secondLayer = createLayer('second', encodeCounts, 1);
  const initial = await capture(
    [firstLayer, secondLayer],
    null,
    ['first', 'second'],
    true,
  );
  const reordered = [
    { ...firstLayer, order: 1 },
    { ...secondLayer, order: 0 },
  ];
  const next = await capture(reordered, initial, []);

  assert.deepEqual(Object.fromEntries(encodeCounts), {
    first: 1,
    second: 1,
  });
  assert.strictEqual(next.layers[0].canvasBlob, initial.layers[0].canvasBlob);
  assert.strictEqual(next.layers[1].canvasBlob, initial.layers[1].canvasBlob);
  assert.deepEqual(next.layers.map((layer) => layer.order), [1, 0]);
});
