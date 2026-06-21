import type { Point } from '../../types';
import { parseHexColor } from './gapFillColors.ts';

interface FillRegion {
  pixels: Point[];
  predictedColor: string;
}

interface PaintRegion {
  pixels: Point[];
  color: string;
}

function paintRegions(
  imageData: ImageData,
  regions: PaintRegion[],
): boolean {
  const pixels = imageData.data;
  const { width, height } = imageData;
  let painted = false;

  for (const region of regions) {
    const rgb = parseHexColor(region.color);
    if (!rgb) {
      console.error(
        `GapFill received an invalid color: "${region.color}". The region was skipped.`,
      );
      continue;
    }

    const [red, green, blue] = rgb;

    for (const point of region.pixels) {
      if (
        point.x < 0 ||
        point.x >= width ||
        point.y < 0 ||
        point.y >= height
      ) {
        continue;
      }

      const pixelIndex = (point.y * width + point.x) * 4;
      pixels[pixelIndex] = red;
      pixels[pixelIndex + 1] = green;
      pixels[pixelIndex + 2] = blue;
      pixels[pixelIndex + 3] = 255;
      painted = true;
    }
  }

  return painted;
}

export function fillGapRegion(
  canvas: HTMLCanvasElement,
  region: FillRegion,
  color: string,
): void {
  // Implementation of Paper Sec. 4.1.4 and 4.1.5:
  // commit a corrected or accepted suggested color to the target gap.
  const context = canvas.getContext('2d');
  if (!context) return;

  const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
  if (paintRegions(imageData, [{ pixels: region.pixels, color }])) {
    context.putImageData(imageData, 0, 0);
  }
}

export function fillGapRegions(
  canvas: HTMLCanvasElement,
  regions: FillRegion[],
): void {
  // Implementation of Paper Sec. 4.1.5:
  // apply every accepted suggestion for sweep selection or Apply All.
  if (regions.length === 0) return;

  const context = canvas.getContext('2d');
  if (!context) return;

  const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
  const paintTargets = regions.map((region) => ({
    pixels: region.pixels,
    color: region.predictedColor,
  }));

  if (paintRegions(imageData, paintTargets)) {
    context.putImageData(imageData, 0, 0);
  }
}
