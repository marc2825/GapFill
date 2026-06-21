import assert from 'node:assert/strict';
import test from 'node:test';
import {
  isCurrentGenerationRequest,
  LatestRequestTracker,
} from '../utils/latestRequestTracker.ts';

test('only the latest preset load request may apply its result', async () => {
  const tracker = new LatestRequestTracker();
  const appliedRequests = [];
  const firstRequest = tracker.begin();

  const applyAfter = async (requestId, delay) => {
    await new Promise((resolve) => setTimeout(resolve, delay));
    if (tracker.isCurrent(requestId)) {
      appliedRequests.push(requestId);
    }
  };

  const firstLoad = applyAfter(firstRequest, 20);
  const secondRequest = tracker.begin();
  const secondLoad = applyAfter(secondRequest, 0);

  await Promise.all([firstLoad, secondLoad]);

  assert.deepEqual(appliedRequests, [secondRequest]);
  assert.equal(tracker.isCurrent(firstRequest), false);
});

test('a new generation invalidates an older manual file load', () => {
  const tracker = new LatestRequestTracker();
  const requestGeneration = 4;
  const requestId = tracker.begin();

  assert.equal(
    isCurrentGenerationRequest(
      tracker,
      requestId,
      requestGeneration,
      requestGeneration,
    ),
    true,
  );
  assert.equal(
    isCurrentGenerationRequest(
      tracker,
      requestId,
      requestGeneration,
      requestGeneration + 1,
    ),
    false,
  );
});
