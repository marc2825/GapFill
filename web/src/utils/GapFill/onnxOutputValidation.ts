export function getValidatedProbabilityMap(
  outputData: unknown,
  outputDimensions: readonly number[],
  expectedDimensions: readonly number[],
): Float32Array {
  if (!(outputData instanceof Float32Array)) {
    throw new Error('ONNX inference failed: output tensor is not Float32Array.');
  }

  if (
    outputDimensions.length !== expectedDimensions.length ||
    outputDimensions.some(
      (dimension, index) => dimension !== expectedDimensions[index],
    )
  ) {
    throw new Error(
      `ONNX inference failed: expected output shape ` +
        `[${expectedDimensions.join(', ')}], received ` +
        `[${outputDimensions.join(', ')}].`,
    );
  }

  const expectedLength = expectedDimensions.reduce(
    (length, dimension) => length * dimension,
    1,
  );
  if (outputData.length !== expectedLength) {
    throw new Error(
      `ONNX inference failed: expected ${expectedLength} output values, ` +
        `received ${outputData.length}.`,
    );
  }

  return outputData;
}
