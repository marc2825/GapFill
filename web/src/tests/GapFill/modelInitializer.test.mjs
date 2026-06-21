import assert from 'node:assert/strict';
import test from 'node:test';
import { createModelInitializer } from '../../utils/GapFill/modelInitializer.ts';

test('concurrent initialization calls share and await the same promise', async () => {
  let resolvePreload;
  let preloadCalls = 0;
  const preload = () => {
    preloadCalls++;
    return new Promise((resolve) => {
      resolvePreload = resolve;
    });
  };
  const initialize = createModelInitializer({ preload });

  const first = initialize();
  const second = initialize();

  assert.equal(first, second);
  assert.equal(preloadCalls, 1);

  resolvePreload();
  await Promise.all([first, second]);
  await initialize();

  assert.equal(preloadCalls, 1);
});

test('initialization can be retried after preloading fails', async () => {
  let preloadCalls = 0;
  const errors = [];
  const initialize = createModelInitializer({
    preload: async () => {
      preloadCalls++;
      if (preloadCalls === 1) throw new Error('load failed');
    },
    onError: (error) => errors.push(error),
  });

  await initialize();
  await initialize();

  assert.equal(preloadCalls, 2);
  assert.equal(errors.length, 1);
});
