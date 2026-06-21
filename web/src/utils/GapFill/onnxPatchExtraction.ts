export interface PixelPatch {
  data: Uint8ClampedArray;
  width: number;
  height: number;
  validPixels: Uint8Array;
}

export interface PatchBounds {
  virtualX: number;
  virtualY: number;
  sourceX: number;
  sourceY: number;
  sourceWidth: number;
  sourceHeight: number;
  destinationX: number;
  destinationY: number;
}

interface CanvasDimensions {
  width: number;
  height: number;
}

export function assertMatchingCanvasDimensions(
  ...canvases: CanvasDimensions[]
): void {
  const [firstCanvas, ...remainingCanvases] = canvases;
  if (!firstCanvas) return;

  for (const canvas of remainingCanvases) {
    if (
      canvas.width !== firstCanvas.width ||
      canvas.height !== firstCanvas.height
    ) {
      throw new Error('ONNX input canvases must have matching dimensions.');
    }
  }
}

export function calculateCenteredPatchBounds(
  canvasWidth: number,
  canvasHeight: number,
  centerX: number,
  centerY: number,
  patchSize: number,
): PatchBounds {
  const halfPatch = Math.floor(patchSize / 2);
  // Match NumPy's integer conversion used for training-region centroids.
  const virtualX = Math.floor(centerX) - halfPatch;
  const virtualY = Math.floor(centerY) - halfPatch;
  const sourceX = Math.max(0, virtualX);
  const sourceY = Math.max(0, virtualY);
  const sourceEndX = Math.min(canvasWidth, virtualX + patchSize);
  const sourceEndY = Math.min(canvasHeight, virtualY + patchSize);

  return {
    virtualX,
    virtualY,
    sourceX,
    sourceY,
    sourceWidth: Math.max(0, sourceEndX - sourceX),
    sourceHeight: Math.max(0, sourceEndY - sourceY),
    destinationX: sourceX - virtualX,
    destinationY: sourceY - virtualY,
  };
}

export function copyIntoZeroPaddedPatch(
  source: Uint8ClampedArray,
  sourceWidth: number,
  sourceHeight: number,
  patchSize: number,
  destinationX: number,
  destinationY: number,
): PixelPatch {
  const data = new Uint8ClampedArray(patchSize * patchSize * 4);
  const validPixels = new Uint8Array(patchSize * patchSize);

  for (let y = 0; y < sourceHeight; y++) {
    for (let x = 0; x < sourceWidth; x++) {
      const sourceIndex = (y * sourceWidth + x) * 4;
      const patchX = destinationX + x;
      const patchY = destinationY + y;
      const patchPixelIndex = patchY * patchSize + patchX;
      const destinationIndex = patchPixelIndex * 4;

      data[destinationIndex] = source[sourceIndex];
      data[destinationIndex + 1] = source[sourceIndex + 1];
      data[destinationIndex + 2] = source[sourceIndex + 2];
      data[destinationIndex + 3] = source[sourceIndex + 3];
      validPixels[patchPixelIndex] = 1;
    }
  }

  return {
    data,
    width: patchSize,
    height: patchSize,
    validPixels,
  };
}

export function extractCanvasPatchWithBounds(
  canvas: HTMLCanvasElement,
  bounds: PatchBounds,
  patchSize: number,
): PixelPatch {
  const context = canvas.getContext('2d');
  if (!context) {
    throw new Error('Failed to get canvas context for ONNX patch extraction.');
  }

  if (bounds.sourceWidth === 0 || bounds.sourceHeight === 0) {
    return copyIntoZeroPaddedPatch(
      new Uint8ClampedArray(),
      0,
      0,
      patchSize,
      0,
      0,
    );
  }

  const sourceImage = context.getImageData(
    bounds.sourceX,
    bounds.sourceY,
    bounds.sourceWidth,
    bounds.sourceHeight,
  );

  return copyIntoZeroPaddedPatch(
    sourceImage.data,
    bounds.sourceWidth,
    bounds.sourceHeight,
    patchSize,
    bounds.destinationX,
    bounds.destinationY,
  );
}

export function extractCenteredCanvasPatch(
  canvas: HTMLCanvasElement,
  centerX: number,
  centerY: number,
  patchSize: number,
): PixelPatch {
  const bounds = calculateCenteredPatchBounds(
    canvas.width,
    canvas.height,
    centerX,
    centerY,
    patchSize,
  );

  return extractCanvasPatchWithBounds(canvas, bounds, patchSize);
}
