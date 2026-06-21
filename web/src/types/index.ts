export interface Point {
  x: number;
  y: number;
}

export interface Layer {
  id: string;
  name: string;
  canvas: HTMLCanvasElement;
  visible: boolean;
  opacity: number;
  order: number;
}

export type AddToHistory = (
  changedLayerIds?: readonly string[],
  sourceLayers?: Layer[],
) => void;

export interface BrushSettings {
  size: number;
  color: string;
}
