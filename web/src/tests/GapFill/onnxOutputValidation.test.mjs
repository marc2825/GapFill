import assert from 'node:assert/strict';
import test from 'node:test';
import { getValidatedProbabilityMap } from '../../utils/GapFill/onnxOutputValidation.ts';

test('accepts a Float32 probability map of the expected size', () => {
  const output = new Float32Array(4);

  assert.equal(
    getValidatedProbabilityMap(output, [1, 1, 2, 2], [1, 1, 2, 2]),
    output,
  );
});

test('rejects an output tensor with the wrong data type', () => {
  assert.throws(
    () => getValidatedProbabilityMap(
      new Uint8Array(4),
      [1, 1, 2, 2],
      [1, 1, 2, 2],
    ),
    /not Float32Array/i,
  );
});

test('rejects an output tensor with an unexpected shape', () => {
  assert.throws(
    () => getValidatedProbabilityMap(
      new Float32Array(4),
      [1, 2, 2],
      [1, 1, 2, 2],
    ),
    /expected output shape.*received/i,
  );
});

test('rejects an output tensor with an unexpected value count', () => {
  assert.throws(
    () => getValidatedProbabilityMap(
      new Float32Array(3),
      [1, 1, 2, 2],
      [1, 1, 2, 2],
    ),
    /expected 4 output values.*received 3/i,
  );
});
