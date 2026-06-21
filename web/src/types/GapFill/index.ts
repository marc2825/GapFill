import type { Point } from '..';

export interface GapFillRegion {
  id: string;
  center: Point;
  pixels: Point[];
  predictedColor: string;
}
