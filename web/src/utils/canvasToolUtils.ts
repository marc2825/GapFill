import type { Layer, Point } from '../types';
import { hexToRgb } from './canvasUtils.ts';

interface CanvasSize {
  width: number;
  height: number;
}

interface Bounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

interface RgbaColor {
  r: number;
  g: number;
  b: number;
  a: number;
}

export function rgbaStringToHex(rgba: string): string {
  const values = rgba.match(/\d+/g);
  if (!values) return '#000000';
  const [r, g, b] = values.map(Number);
  return `#${((1 << 24) + (r << 16) + (g << 8) + b)
    .toString(16)
    .slice(1)}`;
}

export function createCompositeCanvas(
  layers: Layer[],
  canvasSize: CanvasSize,
): HTMLCanvasElement {
  const composite = document.createElement('canvas');
  composite.width = canvasSize.width;
  composite.height = canvasSize.height;
  const context = composite.getContext('2d');

  if (context) {
    context.imageSmoothingEnabled = false;
    [...layers]
      .sort((a, b) => a.order - b.order)
      .forEach((layer) => {
        if (!layer.visible) return;
        context.globalAlpha = layer.opacity;
        context.drawImage(layer.canvas, 0, 0);
      });
  }

  return composite;
}

export function createFillReferenceCanvas(
  layers: Layer[],
  canvasSize: CanvasSize,
): HTMLCanvasElement {
  const composite = document.createElement('canvas');
  composite.width = canvasSize.width;
  composite.height = canvasSize.height;
  const context = composite.getContext('2d');

  if (context) {
    context.imageSmoothingEnabled = false;
    layers
      .filter(
        (layer) =>
          layer.visible &&
          (layer.name === 'Line Art' ||
            layer.name === 'Guides' ||
            layer.name === 'Coloring'),
      )
      .sort((a, b) => a.order - b.order)
      .forEach((layer) => {
        context.globalAlpha = layer.opacity;
        context.drawImage(layer.canvas, 0, 0);
      });
  }

  return composite;
}

function colorsMatch(
  first: Uint8ClampedArray | number[],
  second: Uint8ClampedArray | number[],
  tolerance = 0,
): boolean {
  return (
    Math.abs(first[0] - second[0]) <= tolerance &&
    Math.abs(first[1] - second[1]) <= tolerance &&
    Math.abs(first[2] - second[2]) <= tolerance &&
    Math.abs(first[3] - second[3]) <= tolerance
  );
}

export function floodFillWithReference(
  targetCanvas: HTMLCanvasElement,
  referenceCanvas: HTMLCanvasElement,
  x: number,
  y: number,
  fillColor: string,
): void {
  const targetContext = targetCanvas.getContext('2d');
  const referenceContext = referenceCanvas.getContext('2d');
  if (!targetContext || !referenceContext) return;

  x = Math.floor(x);
  y = Math.floor(y);
  if (
    !Number.isFinite(x) ||
    !Number.isFinite(y) ||
    x < 0 ||
    x >= targetCanvas.width ||
    x >= referenceCanvas.width ||
    y < 0 ||
    y >= targetCanvas.height ||
    y >= referenceCanvas.height
  ) {
    return;
  }

  const targetData = targetContext.getImageData(
    0,
    0,
    targetCanvas.width,
    targetCanvas.height,
  );
  const referenceData = referenceContext.getImageData(
    0,
    0,
    referenceCanvas.width,
    referenceCanvas.height,
  );
  const startReferenceIndex = (y * referenceCanvas.width + x) * 4;
  const startColor = referenceData.data.slice(
    startReferenceIndex,
    startReferenceIndex + 4,
  );
  const isTransparent =
    fillColor === 'rgba(0,0,0,0)' || fillColor === 'transparent';
  const fillRgb = isTransparent ? { r: 0, g: 0, b: 0 } : hexToRgb(fillColor);
  const fillAlpha = isTransparent ? 0 : 255;
  const visited = new Set<number>();
  const stack: Point[] = [{ x, y }];

  while (stack.length > 0) {
    const point = stack.pop()!;
    if (
      point.x < 0 ||
      point.x >= targetCanvas.width ||
      point.y < 0 ||
      point.y >= targetCanvas.height
    ) {
      continue;
    }

    if (
      point.x >= referenceCanvas.width ||
      point.y >= referenceCanvas.height
    ) {
      continue;
    }

    const targetIndex = (point.y * targetCanvas.width + point.x) * 4;
    if (visited.has(targetIndex)) continue;
    visited.add(targetIndex);

    const referenceIndex =
      (point.y * referenceCanvas.width + point.x) * 4;
    const referenceColor = referenceData.data.slice(
      referenceIndex,
      referenceIndex + 4,
    );
    if (!colorsMatch(referenceColor, startColor)) continue;

    targetData.data[targetIndex] = fillRgb.r;
    targetData.data[targetIndex + 1] = fillRgb.g;
    targetData.data[targetIndex + 2] = fillRgb.b;
    targetData.data[targetIndex + 3] = fillAlpha;

    stack.push({ x: point.x + 1, y: point.y });
    stack.push({ x: point.x - 1, y: point.y });
    stack.push({ x: point.x, y: point.y + 1 });
    stack.push({ x: point.x, y: point.y - 1 });
  }

  targetContext.putImageData(targetData, 0, 0);
}

function calculateBounds(path: Point[]): Bounds {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  path.forEach((point) => {
    minX = Math.min(minX, Math.floor(point.x));
    maxX = Math.max(maxX, Math.ceil(point.x));
    minY = Math.min(minY, Math.floor(point.y));
    maxY = Math.max(maxY, Math.ceil(point.y));
  });

  return { minX, maxX, minY, maxY };
}

function isPointInPolygon(point: Point, polygon: Point[]): boolean {
  let inside = false;

  for (
    let index = 0, previous = polygon.length - 1;
    index < polygon.length;
    previous = index++
  ) {
    const currentPoint = polygon[index];
    const previousPoint = polygon[previous];
    if (
      (currentPoint.y > point.y) !== (previousPoint.y > point.y) &&
      point.x <
        ((previousPoint.x - currentPoint.x) *
          (point.y - currentPoint.y)) /
          (previousPoint.y - currentPoint.y) +
          currentPoint.x
    ) {
      inside = !inside;
    }
  }

  return inside;
}

function generateEncloseAndFillMask(
  path: Point[],
  width: number,
  height: number,
): Uint8Array {
  const bounds = calculateBounds(path);
  const mask = new Uint8Array(width * height);

  for (
    let y = Math.max(0, bounds.minY);
    y <= Math.min(height - 1, bounds.maxY);
    y++
  ) {
    for (
      let x = Math.max(0, bounds.minX);
      x <= Math.min(width - 1, bounds.maxX);
      x++
    ) {
      if (isPointInPolygon({ x, y }, path)) {
        mask[y * width + x] = 1;
      }
    }
  }

  return mask;
}

function generateBrushMask(
  path: Point[],
  brushSize: number,
  width: number,
  height: number,
): Uint8Array {
  const mask = new Uint8Array(width * height);
  const radius = Math.floor(brushSize / 2);

  for (let index = 0; index < path.length - 1; index++) {
    const start = path[index];
    const end = path[index + 1];
    const deltaX = end.x - start.x;
    const deltaY = end.y - start.y;
    const steps = Math.ceil(Math.sqrt(deltaX * deltaX + deltaY * deltaY));

    for (let step = 0; step <= steps; step++) {
      const progress = steps === 0 ? 0 : step / steps;
      const x = Math.round(start.x + deltaX * progress);
      const y = Math.round(start.y + deltaY * progress);

      for (let brushX = -radius; brushX <= radius; brushX++) {
        for (let brushY = -radius; brushY <= radius; brushY++) {
          if (brushX * brushX + brushY * brushY <= radius * radius) {
            const pixelX = x + brushX;
            const pixelY = y + brushY;
            if (
              pixelX >= 0 &&
              pixelX < width &&
              pixelY >= 0 &&
              pixelY < height
            ) {
              mask[pixelY * width + pixelX] = 1;
            }
          }
        }
      }
    }
  }

  return mask;
}

function fillCoveredRegions(
  activeCanvas: HTMLCanvasElement,
  sourceCanvas: HTMLCanvasElement,
  coveredPixels: Uint8Array,
  fillColor: string,
): void {
  const activeContext = activeCanvas.getContext('2d');
  const sourceContext = sourceCanvas.getContext('2d');
  if (!activeContext || !sourceContext) return;

  const sourceData = sourceContext.getImageData(
    0,
    0,
    sourceCanvas.width,
    sourceCanvas.height,
  );
  const activeData = activeContext.getImageData(
    0,
    0,
    activeCanvas.width,
    activeCanvas.height,
  );
  const fillRgb =
    fillColor === 'transparent'
      ? { r: 0, g: 0, b: 0 }
      : hexToRgb(fillColor);
  const fillAlpha = fillColor === 'transparent' ? 0 : 255;
  const width = sourceCanvas.width;
  const height = sourceCanvas.height;
  const pixelCount = width * height;
  const visited = new Uint8Array(pixelCount);
  const stack = new Uint32Array(pixelCount);
  const component = new Uint32Array(pixelCount);

  for (let startIndex = 0; startIndex < pixelCount; startIndex++) {
    if (coveredPixels[startIndex] === 0 || visited[startIndex] !== 0) continue;

    const rgbaIndex = startIndex * 4;
    const targetColor: RgbaColor = {
      r: sourceData.data[rgbaIndex],
      g: sourceData.data[rgbaIndex + 1],
      b: sourceData.data[rgbaIndex + 2],
      a: sourceData.data[rgbaIndex + 3],
    };
    let stackLength = 0;
    let componentLength = 0;
    let isFullyCovered = true;

    visited[startIndex] = 1;
    stack[stackLength++] = startIndex;

    while (stackLength > 0) {
      const pixelIndex = stack[--stackLength];
      component[componentLength++] = pixelIndex;
      if (coveredPixels[pixelIndex] === 0) {
        isFullyCovered = false;
      }

      const x = pixelIndex % width;
      const y = Math.floor(pixelIndex / width);
      const visitNeighbor = (neighborIndex: number) => {
        if (visited[neighborIndex] !== 0) return;

        const neighborRgbaIndex = neighborIndex * 4;
        if (
          sourceData.data[neighborRgbaIndex] !== targetColor.r ||
          sourceData.data[neighborRgbaIndex + 1] !== targetColor.g ||
          sourceData.data[neighborRgbaIndex + 2] !== targetColor.b ||
          sourceData.data[neighborRgbaIndex + 3] !== targetColor.a
        ) {
          return;
        }

        visited[neighborIndex] = 1;
        stack[stackLength++] = neighborIndex;
      };

      if (x > 0) visitNeighbor(pixelIndex - 1);
      if (x + 1 < width) visitNeighbor(pixelIndex + 1);
      if (y > 0) visitNeighbor(pixelIndex - width);
      if (y + 1 < height) visitNeighbor(pixelIndex + width);
    }

    if (!isFullyCovered) continue;

    for (let index = 0; index < componentLength; index++) {
      const pixelIndex = component[index];
      const x = pixelIndex % width;
      const y = Math.floor(pixelIndex / width);
      if (x >= activeCanvas.width || y >= activeCanvas.height) continue;

      const targetIndex = (y * activeCanvas.width + x) * 4;
      if (activeData.data[targetIndex + 3] !== 0) continue;

      activeData.data[targetIndex] = fillRgb.r;
      activeData.data[targetIndex + 1] = fillRgb.g;
      activeData.data[targetIndex + 2] = fillRgb.b;
      activeData.data[targetIndex + 3] = fillAlpha;
    }
  }

  activeContext.putImageData(activeData, 0, 0);
}

export function fillEncloseAndFillSelection(
  activeCanvas: HTMLCanvasElement,
  sourceCanvas: HTMLCanvasElement,
  path: Point[],
  fillColor: string,
): void {
  const enclosedPixels = generateEncloseAndFillMask(
    path,
    sourceCanvas.width,
    sourceCanvas.height,
  );
  fillCoveredRegions(activeCanvas, sourceCanvas, enclosedPixels, fillColor);
}

export function fillLeftoverPenSelection(
  activeCanvas: HTMLCanvasElement,
  sourceCanvas: HTMLCanvasElement,
  path: Point[],
  brushSize: number,
  fillColor: string,
): void {
  const brushPixels = generateBrushMask(
    path,
    brushSize,
    sourceCanvas.width,
    sourceCanvas.height,
  );
  fillCoveredRegions(activeCanvas, sourceCanvas, brushPixels, fillColor);
}

export function convertScreenToCanvas(
  canvas: HTMLCanvasElement | null,
  screenX: number,
  screenY: number,
  canvasSize: CanvasSize,
  pan: Point,
  zoom: number,
): Point {
  const rect = canvas?.getBoundingClientRect();
  if (!canvas || !rect || rect.width === 0 || rect.height === 0) {
    return { x: 0, y: 0 };
  }

  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const centerX = canvas.width / 2;
  const centerY = canvas.height / 2;
  const mouseX = (screenX - rect.left) * scaleX;
  const mouseY = (screenY - rect.top) * scaleY;
  const canvasX =
    (mouseX - centerX - pan.x * scaleX) / zoom +
    canvasSize.width / 2 -
    0.5;
  const canvasY =
    (mouseY - centerY - pan.y * scaleY) / zoom +
    canvasSize.height / 2 -
    0.5;

  return { x: canvasX, y: canvasY };
}
