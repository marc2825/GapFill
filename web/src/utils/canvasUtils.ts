import type { Point } from '../types';

interface RgbColor {
  r: number;
  g: number;
  b: number;
}

interface ParsedHexColor extends RgbColor {
  a: number;
}

function parseHexColor(hex: string): ParsedHexColor | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})?$/i.exec(hex);
  if (!result) return null;

  return {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16),
    a: result[4] ? parseInt(result[4], 16) / 255 : 1,
  };
}

export function createCanvas(width: number, height: number): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

export function getPixelColor(canvas: HTMLCanvasElement, x: number, y: number): string {
  const ctx = canvas.getContext('2d');
  if (!ctx) return 'rgba(0,0,0,0)';

  const pixelX = Math.floor(x);
  const pixelY = Math.floor(y);
  if (
    !Number.isFinite(pixelX) ||
    !Number.isFinite(pixelY) ||
    pixelX < 0 ||
    pixelX >= canvas.width ||
    pixelY < 0 ||
    pixelY >= canvas.height
  ) {
    return 'rgba(0,0,0,0)';
  }

  const pixel = ctx.getImageData(pixelX, pixelY, 1, 1).data;
  return `rgba(${pixel[0]},${pixel[1]},${pixel[2]},${pixel[3] / 255})`;
}

export function floodFill(
  canvas: HTMLCanvasElement,
  startX: number,
  startY: number,
  fillColor: string,
  tolerance: number = 0
): void {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  startX = Math.floor(startX);
  startY = Math.floor(startY);
  if (
    !Number.isFinite(startX) ||
    !Number.isFinite(startY) ||
    startX < 0 ||
    startX >= canvas.width ||
    startY < 0 ||
    startY >= canvas.height
  ) {
    return;
  }

  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const pixels = imageData.data;
  const width = canvas.width;
  const height = canvas.height;

  const startIdx = (startY * width + startX) * 4;
  const startR = pixels[startIdx];
  const startG = pixels[startIdx + 1];
  const startB = pixels[startIdx + 2];
  const startA = pixels[startIdx + 3];

  // Parse rgba() format or use hexToRgba for hex colors
  let fillRGBA;
  if (fillColor.startsWith('rgba(')) {
    const match = fillColor.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)/);
    if (match) {
      fillRGBA = {
        r: parseInt(match[1]),
        g: parseInt(match[2]),
        b: parseInt(match[3]),
        a: parseFloat(match[4])
      };
    } else {
      fillRGBA = { r: 0, g: 0, b: 0, a: 0 };
    }
  } else {
    fillRGBA = hexToRgba(fillColor);
  }
  
  // If the target color is the same as fill color, don't fill
  if (
    Math.abs(startR - fillRGBA.r) <= tolerance &&
    Math.abs(startG - fillRGBA.g) <= tolerance &&
    Math.abs(startB - fillRGBA.b) <= tolerance &&
    Math.abs(startA - fillRGBA.a * 255) <= tolerance
  ) {
    return;
  }

  const visited = new Set<number>();
  const stack: Point[] = [{ x: startX, y: startY }];

  while (stack.length > 0) {
    const { x, y } = stack.pop()!;
    
    if (x < 0 || x >= width || y < 0 || y >= height) continue;
    
    const idx = (y * width + x) * 4;
    if (visited.has(idx)) continue;
    visited.add(idx);

    const r = pixels[idx];
    const g = pixels[idx + 1];
    const b = pixels[idx + 2];
    const a = pixels[idx + 3];

    // Check if this pixel matches the starting color within tolerance
    const colorDiff = Math.abs(r - startR) + Math.abs(g - startG) + 
                      Math.abs(b - startB) + Math.abs(a - startA);

    if (colorDiff <= tolerance * 4) {
      pixels[idx] = fillRGBA.r;
      pixels[idx + 1] = fillRGBA.g;
      pixels[idx + 2] = fillRGBA.b;
      pixels[idx + 3] = fillRGBA.a * 255;

      stack.push({ x: x + 1, y });
      stack.push({ x: x - 1, y });
      stack.push({ x, y: y + 1 });
      stack.push({ x, y: y - 1 });
    }
  }

  ctx.putImageData(imageData, 0, 0);
}

export function hexToRgb(
  hex: string,
  fallback: RgbColor = { r: 0, g: 0, b: 0 },
): RgbColor {
  if (hex === 'transparent') {
    return { r: 0, g: 0, b: 0 };
  }

  const parsed = parseHexColor(hex);
  return parsed
    ? { r: parsed.r, g: parsed.g, b: parsed.b }
    : fallback;
}

function hexToRgba(hex: string): { r: number; g: number; b: number; a: number } {
  if (hex === 'transparent') {
    return { r: 0, g: 0, b: 0, a: 0 };
  }

  return parseHexColor(hex) || { r: 0, g: 0, b: 0, a: 1 };
}
