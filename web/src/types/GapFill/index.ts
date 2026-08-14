import type { Point } from '..';

export interface GapFillRegion {
  id: string;
  center: Point;
  pixels: Point[];
  predictedColor: string;
  predictionProvenance: 'learned' | 'fallback';
  learnedConfidence: number | null;
  fallbackReason?: string;
}
