import type { Point } from '../../types';
import { UNASSIGNED_MATERIAL_COLOR } from './gapFillColors.ts';

const GREEDY_EXPANSION_RADIUS = 5;

function calculateBoundingBox(points: Point[]): {
  x: number;
  y: number;
  width: number;
  height: number;
} {
  if (points.length === 0) {
    return { x: 0, y: 0, width: 0, height: 0 };
  }

  let minX = points[0].x;
  let maxX = points[0].x;
  let minY = points[0].y;
  let maxY = points[0].y;

  for (const point of points) {
    minX = Math.min(minX, point.x);
    maxX = Math.max(maxX, point.x);
    minY = Math.min(minY, point.y);
    maxY = Math.max(maxY, point.y);
  }

  return {
    x: minX,
    y: minY,
    width: maxX - minX + 1,
    height: maxY - minY + 1,
  };
}

export function createOpaquePixelMask(
  width: number,
  height: number,
  canvases: Array<HTMLCanvasElement | undefined>,
): Uint8Array | undefined {
  const mask = new Uint8Array(width * height);
  const uniqueCanvases = new Set(
    canvases.filter((canvas) => canvas !== undefined),
  );

  if (uniqueCanvases.size === 0) return undefined;

  for (const canvas of uniqueCanvases) {
    const ctx = canvas.getContext('2d');
    if (!ctx) continue;

    const maskWidth = Math.min(width, canvas.width);
    const maskHeight = Math.min(height, canvas.height);
    const data = ctx.getImageData(0, 0, maskWidth, maskHeight).data;

    for (let y = 0; y < maskHeight; y++) {
      for (let x = 0; x < maskWidth; x++) {
        if (data[(y * maskWidth + x) * 4 + 3] > 0) {
          mask[y * width + x] = 1;
        }
      }
    }
  }

  return mask;
}

// Temporary greedy algorithm for color prediction (kept for fallback).
export function predictColorGreedy(
  pixels: Uint8ClampedArray,
  width: number,
  height: number,
  region: Point[],
  fallbackColor = UNASSIGNED_MATERIAL_COLOR,
  excludedPixels?: Uint8Array,
): string {
  const colorCounts = new Map<string, number>();
  const bounds = calculateBoundingBox(region);
  const startX = Math.max(0, bounds.x - GREEDY_EXPANSION_RADIUS);
  const startY = Math.max(0, bounds.y - GREEDY_EXPANSION_RADIUS);
  const endX = Math.min(
    width - 1,
    bounds.x + bounds.width - 1 + GREEDY_EXPANSION_RADIUS,
  );
  const endY = Math.min(
    height - 1,
    bounds.y + bounds.height - 1 + GREEDY_EXPANSION_RADIUS,
  );
  const localWidth = endX - startX + 1;
  const localHeight = endY - startY + 1;
  const regionMask = new Uint8Array(localWidth * localHeight);

  for (const point of region) {
    const localX = point.x - startX;
    const localY = point.y - startY;
    regionMask[localY * localWidth + localX] = 1;
  }

  for (let y = 0; y < localHeight; y++) {
    for (let x = 0; x < localWidth; x++) {
      const localIndex = y * localWidth + x;
      if (regionMask[localIndex] !== 0) continue;

      const sourceIndex = (startY + y) * width + startX + x;
      if (excludedPixels && excludedPixels[sourceIndex] !== 0) continue;

      const idx = sourceIndex * 4;
      const r = pixels[idx];
      const g = pixels[idx + 1];
      const b = pixels[idx + 2];
      const a = pixels[idx + 3];

      if (a > 0) {
        const colorKey = `${r},${g},${b}`;
        colorCounts.set(colorKey, (colorCounts.get(colorKey) || 0) + 1);
      }
    }
  }

  if (colorCounts.size === 0) {
    return fallbackColor;
  }

  let maxCount = 0;
  let mostFrequentColor = '';

  for (const [color, count] of colorCounts) {
    if (count > maxCount) {
      maxCount = count;
      mostFrequentColor = color;
    }
  }

  const [r, g, b] = mostFrequentColor.split(',').map(Number);
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}
