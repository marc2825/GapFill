import type { Point } from '../types';

export function drawOverflowRegionBoundary(
  context: CanvasRenderingContext2D,
  pixels: Point[],
  color: string,
  lineWidth: number,
): void {
  if (pixels.length === 0) return;

  const pixelSet = new Set(pixels.map((point) => `${point.x},${point.y}`));
  context.save();
  context.strokeStyle = color;
  context.lineWidth = lineWidth;
  context.beginPath();

  for (const { x, y } of pixels) {
    if (!pixelSet.has(`${x},${y - 1}`)) {
      context.moveTo(x, y);
      context.lineTo(x + 1, y);
    }
    if (!pixelSet.has(`${x + 1},${y}`)) {
      context.moveTo(x + 1, y);
      context.lineTo(x + 1, y + 1);
    }
    if (!pixelSet.has(`${x},${y + 1}`)) {
      context.moveTo(x + 1, y + 1);
      context.lineTo(x, y + 1);
    }
    if (!pixelSet.has(`${x - 1},${y}`)) {
      context.moveTo(x, y + 1);
      context.lineTo(x, y);
    }
  }

  context.stroke();
  context.restore();
}

export function drawOverflowRegionFlash(
  context: CanvasRenderingContext2D,
  pixels: Point[],
  lineWidth: number,
): void {
  if (pixels.length === 0) return;

  context.save();
  context.fillStyle = 'rgba(0, 180, 255, 0.35)';
  for (const point of pixels) {
    context.fillRect(point.x, point.y, 1, 1);
  }
  context.restore();

  drawOverflowRegionBoundary(context, pixels, '#00B4FF', lineWidth);
}
