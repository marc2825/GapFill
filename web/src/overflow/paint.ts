import type { Point } from '../types';
import {
  parseHexColor,
  resolveGapFillFallbackRgb,
} from '../utils/GapFill/gapFillColors.ts';
import type { OverflowGap, OverflowOwnerRegion, RgbaColor } from './types';

interface PaintOverflowOwnerParams {
  canvas: HTMLCanvasElement;
  owner: OverflowOwnerRegion;
  linkedGaps: OverflowGap[];
  clickPoint: Point;
  fillColor: string;
}

export interface PaintOverflowOwnerResult {
  changed: boolean;
  propagatedGapIds: string[];
  propagatedRegions: Point[][];
  usedExistingOwnerColor: boolean;
}

function colorToRgba(color: string): RgbaColor {
  if (color === 'transparent' || color === 'rgba(0,0,0,0)') {
    return { r: 0, g: 0, b: 0, a: 0 };
  }

  const parsed = parseHexColor(color) ?? resolveGapFillFallbackRgb(color);
  return {
    r: parsed[0],
    g: parsed[1],
    b: parsed[2],
    a: 255,
  };
}

function rgbaAt(
  pixels: Uint8ClampedArray,
  width: number,
  height: number,
  point: Point,
): RgbaColor {
  const x = Math.round(point.x);
  const y = Math.round(point.y);
  if (x < 0 || y < 0 || x >= width || y >= height) {
    return { r: 0, g: 0, b: 0, a: 0 };
  }

  const index = (y * width + x) * 4;
  return {
    r: pixels[index],
    g: pixels[index + 1],
    b: pixels[index + 2],
    a: pixels[index + 3],
  };
}

function fillPoints(
  pixels: Uint8ClampedArray,
  width: number,
  height: number,
  points: Point[],
  color: RgbaColor,
): boolean {
  let changed = false;

  for (const point of points) {
    if (point.x < 0 || point.y < 0 || point.x >= width || point.y >= height) {
      continue;
    }

    const index = (point.y * width + point.x) * 4;
    if (
      pixels[index] === color.r &&
      pixels[index + 1] === color.g &&
      pixels[index + 2] === color.b &&
      pixels[index + 3] === color.a
    ) {
      continue;
    }

    pixels[index] = color.r;
    pixels[index + 1] = color.g;
    pixels[index + 2] = color.b;
    pixels[index + 3] = color.a;
    changed = true;
  }

  return changed;
}

export function paintOverflowOwner({
  canvas,
  owner,
  linkedGaps,
  clickPoint,
  fillColor,
}: PaintOverflowOwnerParams): PaintOverflowOwnerResult {
  const context = canvas.getContext('2d');
  if (!context) {
    return {
      changed: false,
      propagatedGapIds: [],
      propagatedRegions: [],
      usedExistingOwnerColor: false,
    };
  }

  const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
  const pixels = imageData.data;
  const ownerColor = rgbaAt(pixels, canvas.width, canvas.height, clickPoint);
  const usedExistingOwnerColor = ownerColor.a > 0;
  const paintColor = usedExistingOwnerColor
    ? ownerColor
    : colorToRgba(fillColor);

  let changed = false;
  if (!usedExistingOwnerColor) {
    changed = fillPoints(
      pixels,
      canvas.width,
      canvas.height,
      owner.pixels,
      paintColor,
    ) || changed;
  }

  const propagatedGapIds: string[] = [];
  const propagatedRegions: Point[][] = [];
  for (const gap of linkedGaps) {
    const gapChanged = fillPoints(
      pixels,
      canvas.width,
      canvas.height,
      gap.pixels,
      paintColor,
    );
    if (gapChanged) {
      changed = true;
      propagatedGapIds.push(gap.id);
      propagatedRegions.push(gap.pixels);
    }
  }

  if (changed) {
    context.putImageData(imageData, 0, 0);
  }

  return {
    changed,
    propagatedGapIds,
    propagatedRegions,
    usedExistingOwnerColor,
  };
}
