import assert from 'node:assert/strict';
import test from 'node:test';
import {
  resolveGapFillFallbackColor,
  resolveGapFillFallbackRgb,
  UNASSIGNED_MATERIAL_COLOR,
} from '../../utils/GapFill/gapFillColors.ts';

test('uses magenta for an unassigned fallback color', () => {
  assert.equal(resolveGapFillFallbackColor(), UNASSIGNED_MATERIAL_COLOR);
});

test('reports an invalid fallback color and resolves it to magenta', () => {
  const errors = [];
  const originalConsoleError = console.error;

  console.error = (...args) => errors.push(args);
  try {
    assert.equal(resolveGapFillFallbackColor('invalid'), '#FF00FF');
    assert.deepEqual(resolveGapFillFallbackRgb('invalid'), [255, 0, 255]);
  } finally {
    console.error = originalConsoleError;
  }

  assert.equal(errors.length, 2);
  assert.match(errors[0][0], /invalid fallback color.*invalid/i);
});
