import type { Point } from '../types';

export type OverflowGapKind = 'transparent' | 'guide';

export interface OverflowGap {
  id: string;
  center: Point;
  pixels: Point[];
  kind: OverflowGapKind;
}

export interface OverflowOwnerRegion {
  id: string;
  label: number;
  pixels: Point[];
  center: Point;
  boundingBox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  area: number;
}

export interface OverflowAssignment {
  gapId: string;
  ownerId: string;
  confidence: number;
}

export interface OverflowPrecomputeData {
  owners: OverflowOwnerRegion[];
  ownerLabels: Int32Array;
  width: number;
  height: number;
  assignments: OverflowAssignment[];
}

export interface RgbaColor {
  r: number;
  g: number;
  b: number;
  a: number;
}

export interface OverflowPropagationFlash {
  regions: Point[][];
  visible: boolean;
}

export interface LastOverflowPropagation {
  ownerId: string;
  gapIds: string[];
}
