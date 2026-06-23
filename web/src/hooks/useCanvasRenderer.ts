import { useEffect, useRef } from 'react';
import type { RefObject } from 'react';
import type { Layer, Point } from '../types';
import type { GapFillRegion } from '../types/GapFill';
import type { OverflowPropagationFlash } from '../overflow/types';
import {
  drawOverflowRegionBoundary,
  drawOverflowRegionFlash,
} from '../overflow/rendering';

interface CanvasRendererOptions {
  canvasRef: RefObject<HTMLCanvasElement | null>;
  overlayCanvasRef: RefObject<HTMLCanvasElement | null>;
  cursorCanvasRef: RefObject<HTMLCanvasElement | null>;
  minimapRef: RefObject<HTMLDivElement | null>;
  containerRef: RefObject<HTMLDivElement | null>;
  layers: Layer[];
  activeLayerId: string | null;
  canvasSize: { width: number; height: number };
  zoom: number;
  pan: Point;
  blackLightMode: boolean;
  gapFillMode: boolean;
  overflowFillMode: boolean;
  gaps: GapFillRegion[];
  precomputedGapCanvas: HTMLCanvasElement | null;
  highlightColor: string;
  scaledGapRadius: number;
  hoveredGap: GapFillRegion | null;
  overflowHighlightedRegions: Point[][];
  overflowPropagationFlash: OverflowPropagationFlash | null;
  isCtrlBPressed: boolean;
  swipeGaps: Set<string>;
  swipeMode: boolean;
  swipePath: Point[];
  swipeBrushSize: number;
  colorSelectionMode: boolean;
  encloseAndFillPath: Point[];
  leftoverPenPath: Point[];
  isDrawing: boolean;
  brushSize: number;
  selectedGapForColor: GapFillRegion | null;
  canvasMousePosition: Point | null;
  fixedMinimapPosition: Point | null;
  viewportSize: { width: number; height: number };
}

const CHECKERBOARD_CELL_SIZE = 20;
let checkerboardTile: HTMLCanvasElement | null = null;
const checkerboardPatterns =
  new WeakMap<CanvasRenderingContext2D, CanvasPattern>();

function getCheckerboardTile(): HTMLCanvasElement {
  if (checkerboardTile) return checkerboardTile;

  checkerboardTile = document.createElement('canvas');
  checkerboardTile.width = CHECKERBOARD_CELL_SIZE * 2;
  checkerboardTile.height = CHECKERBOARD_CELL_SIZE * 2;
  const context = checkerboardTile.getContext('2d');

  if (context) {
    context.fillStyle = '#606060';
    context.fillRect(0, 0, checkerboardTile.width, checkerboardTile.height);
    context.fillStyle = '#707070';
    context.fillRect(
      0,
      0,
      CHECKERBOARD_CELL_SIZE,
      CHECKERBOARD_CELL_SIZE,
    );
    context.fillRect(
      CHECKERBOARD_CELL_SIZE,
      CHECKERBOARD_CELL_SIZE,
      CHECKERBOARD_CELL_SIZE,
      CHECKERBOARD_CELL_SIZE,
    );
  }

  return checkerboardTile;
}

function getCheckerboardPattern(
  context: CanvasRenderingContext2D,
): CanvasPattern | null {
  const cachedPattern = checkerboardPatterns.get(context);
  if (cachedPattern) return cachedPattern;

  const pattern = context.createPattern(getCheckerboardTile(), 'repeat');
  if (pattern) {
    checkerboardPatterns.set(context, pattern);
  }
  return pattern;
}

function drawCheckerboard(
  context: CanvasRenderingContext2D,
  width: number,
  height: number,
): void {
  const pattern = getCheckerboardPattern(context);
  context.fillStyle = pattern || '#808080';
  context.fillRect(0, 0, width, height);
}

function drawBlackLightLayer(
  context: CanvasRenderingContext2D,
  layerCanvas: HTMLCanvasElement,
): void {
  const temporaryCanvas = document.createElement('canvas');
  temporaryCanvas.width = layerCanvas.width;
  temporaryCanvas.height = layerCanvas.height;
  const temporaryContext = temporaryCanvas.getContext('2d');
  if (!temporaryContext) return;

  temporaryContext.imageSmoothingEnabled = false;
  temporaryContext.drawImage(layerCanvas, 0, 0);
  const imageData = temporaryContext.getImageData(
    0,
    0,
    temporaryCanvas.width,
    temporaryCanvas.height,
  );

  for (let index = 0; index < imageData.data.length; index += 4) {
    if (imageData.data[index + 3] > 0) {
      imageData.data[index] = 0;
      imageData.data[index + 1] = 0;
      imageData.data[index + 2] = 0;
    }
  }

  temporaryContext.putImageData(imageData, 0, 0);
  context.drawImage(temporaryCanvas, 0, 0);
}

function drawBaseCanvas(options: CanvasRendererOptions): void {
  const canvas = options.canvasRef.current;
  if (!canvas) return;

  const context = canvas.getContext('2d');
  if (!context) return;

  context.imageSmoothingEnabled = false;
  drawCheckerboard(context, canvas.width, canvas.height);

  const centerX = canvas.width / 2;
  const centerY = canvas.height / 2;

  context.save();
  context.translate(centerX + options.pan.x, centerY + options.pan.y);
  context.scale(options.zoom, options.zoom);
  context.translate(
    -options.canvasSize.width / 2,
    -options.canvasSize.height / 2,
  );

  const hasContent = options.layers.some(
    (layer) => layer.visible && layer.name !== 'Background',
  );
  if (!hasContent) {
    context.strokeStyle = '#333333';
    context.lineWidth = 2 / options.zoom;
    context.strokeRect(
      0,
      0,
      options.canvasSize.width,
      options.canvasSize.height,
    );
  }

  [...options.layers]
    .sort((a, b) => a.order - b.order)
    .forEach((layer) => {
      if (!layer.visible) return;

      context.globalAlpha = layer.opacity;
      if (options.blackLightMode && layer.id === options.activeLayerId) {
        drawBlackLightLayer(context, layer.canvas);
      } else {
        context.drawImage(layer.canvas, 0, 0);
      }

      // Implementation of Paper Sec. 4.1.2: preserve Line Art above the suggested-color preview.
      if (
        layer.name === 'Coloring' &&
        options.gapFillMode &&
        options.precomputedGapCanvas
      ) {
        context.globalAlpha = 1;
        context.drawImage(options.precomputedGapCanvas, 0, 0);
      }
    });
  context.restore();
}

function drawGapOverlay(options: CanvasRendererOptions): void {
  const overlayCanvas = options.overlayCanvasRef.current;
  if (!overlayCanvas) return;

  const overlayContext = overlayCanvas.getContext('2d');
  if (!overlayContext) return;

  overlayContext.imageSmoothingEnabled = false;
  overlayContext.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
  overlayContext.globalCompositeOperation = 'source-over';

  const centerX = overlayCanvas.width / 2;
  const centerY = overlayCanvas.height / 2;

  overlayContext.save();
  overlayContext.translate(centerX + options.pan.x, centerY + options.pan.y);
  overlayContext.scale(options.zoom, options.zoom);
  overlayContext.translate(
    -options.canvasSize.width / 2,
    -options.canvasSize.height / 2,
  );

  // Implementation of Paper Sec. 4.1.1: draw one zoom-adjusted circle per detected gap.
  if (
    options.gapFillMode &&
    options.gaps.length > 0 &&
    !options.isCtrlBPressed
  ) {
    options.gaps.forEach((gap) => {
      const isHovered = options.hoveredGap?.id === gap.id;
      const isSwipeInProgress =
        options.swipeGaps.has(gap.id) && options.swipeMode;
      const shouldShowBlue =
        isSwipeInProgress && !options.colorSelectionMode;

      overlayContext.strokeStyle = shouldShowBlue
        ? '#0000FF'
        : isHovered
          ? '#0000FF'
          : options.highlightColor;
      const baseLineWidth = shouldShowBlue ? 6 : isHovered ? 3 : 2;
      overlayContext.lineWidth = baseLineWidth / Math.sqrt(options.zoom);
      overlayContext.beginPath();
      overlayContext.arc(
        gap.center.x,
        gap.center.y,
        options.scaledGapRadius,
        0,
        Math.PI * 2,
      );
      overlayContext.stroke();
    });
  }

  if (
    options.overflowFillMode &&
    options.overflowHighlightedRegions.length > 0 &&
    !options.isCtrlBPressed
  ) {
    for (const region of options.overflowHighlightedRegions) {
      drawOverflowRegionBoundary(
        overlayContext,
        region,
        options.highlightColor,
        Math.max(1 / options.zoom, 1.25 / Math.sqrt(options.zoom)),
      );
    }
  }

  if (
    options.overflowFillMode &&
    options.overflowPropagationFlash?.visible &&
    !options.isCtrlBPressed
  ) {
    for (const region of options.overflowPropagationFlash.regions) {
      drawOverflowRegionFlash(
        overlayContext,
        region,
        Math.max(1 / options.zoom, 1.4 / Math.sqrt(options.zoom)),
      );
    }
  }

  if (options.swipePath.length > 1) {
    overlayContext.strokeStyle = 'rgba(255, 255, 0, 0.3)';
    overlayContext.lineWidth = options.swipeBrushSize;
    overlayContext.lineCap = 'round';
    overlayContext.beginPath();
    overlayContext.moveTo(options.swipePath[0].x, options.swipePath[0].y);
    options.swipePath.slice(1).forEach((point) => {
      overlayContext.lineTo(point.x, point.y);
    });
    overlayContext.stroke();
  }

  if (options.encloseAndFillPath.length > 1 && !options.colorSelectionMode) {
    overlayContext.strokeStyle = '#FF00FF';
    overlayContext.lineWidth = 1 / options.zoom;
    const dashSize = 4 / options.zoom;
    overlayContext.setLineDash([dashSize, dashSize]);
    overlayContext.beginPath();
    overlayContext.moveTo(
      options.encloseAndFillPath[0].x,
      options.encloseAndFillPath[0].y,
    );
    options.encloseAndFillPath.slice(1).forEach((point) => {
      overlayContext.lineTo(point.x, point.y);
    });
    if (options.isDrawing) {
      overlayContext.stroke();
    } else {
      overlayContext.closePath();
      overlayContext.stroke();
    }
    overlayContext.setLineDash([]);
  }

  if (options.leftoverPenPath.length > 1 && !options.colorSelectionMode) {
    overlayContext.strokeStyle = 'rgba(0, 255, 0, 0.5)';
    overlayContext.lineWidth = options.brushSize;
    overlayContext.lineCap = 'round';
    overlayContext.beginPath();
    overlayContext.moveTo(
      options.leftoverPenPath[0].x,
      options.leftoverPenPath[0].y,
    );
    options.leftoverPenPath.slice(1).forEach((point) => {
      overlayContext.lineTo(point.x, point.y);
    });
    overlayContext.stroke();
  }

  overlayContext.restore();
}

function drawCursorLayer(options: CanvasRendererOptions): void {
  const cursorCanvas = options.cursorCanvasRef.current;
  if (!cursorCanvas) return;

  const context = cursorCanvas.getContext('2d');
  if (!context) return;

  context.imageSmoothingEnabled = false;
  context.clearRect(0, 0, cursorCanvas.width, cursorCanvas.height);
  context.globalCompositeOperation = 'source-over';

  const centerX = cursorCanvas.width / 2;
  const centerY = cursorCanvas.height / 2;

  context.save();
  context.translate(centerX + options.pan.x, centerY + options.pan.y);
  context.scale(options.zoom, options.zoom);
  context.translate(
    -options.canvasSize.width / 2,
    -options.canvasSize.height / 2,
  );

  // Implementation of Paper Sec. 4.1.4: connect the correction cursor to the selected gap.
  if (
    options.colorSelectionMode &&
    options.selectedGapForColor &&
    options.canvasMousePosition &&
    options.fixedMinimapPosition
  ) {
    const container = options.containerRef.current;
    if (container) {
      const minimapWidth = 320;
      const minimapHeight = 320;
      const minimapElement = options.minimapRef.current;
      let minimapCenterX: number;
      let minimapCenterY: number;

      if (minimapElement) {
        const minimapRect = minimapElement.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        minimapCenterX =
          minimapRect.left - containerRect.left + minimapWidth / 2;
        minimapCenterY =
          minimapRect.top - containerRect.top + minimapHeight / 2;
      } else {
        const minimapLeft = Math.max(
          10,
          options.fixedMinimapPosition.x - minimapWidth / 2,
        );
        const minimapTop = Math.max(
          10,
          options.fixedMinimapPosition.y - minimapHeight / 2,
        );
        minimapCenterX = minimapLeft + minimapWidth / 2;
        minimapCenterY = minimapTop + minimapHeight / 2;
      }

      const minimapCenterCanvasX =
        (minimapCenterX - centerX - options.pan.x) / options.zoom +
        options.canvasSize.width / 2;
      const minimapCenterCanvasY =
        (minimapCenterY - centerY - options.pan.y) / options.zoom +
        options.canvasSize.height / 2;
      const cursorDrawingX =
        (options.canvasMousePosition.x - centerX - options.pan.x) /
          options.zoom +
        options.canvasSize.width / 2;
      const cursorDrawingY =
        (options.canvasMousePosition.y - centerY - options.pan.y) /
          options.zoom +
        options.canvasSize.height / 2;

      context.strokeStyle = options.highlightColor;
      context.globalAlpha = 0.75;
      context.lineWidth = 1 / options.zoom;
      const dashSize = 5 / options.zoom;
      context.setLineDash([dashSize, dashSize]);
      context.beginPath();
      context.moveTo(cursorDrawingX, cursorDrawingY);
      context.lineTo(minimapCenterCanvasX, minimapCenterCanvasY);
      context.stroke();
      context.setLineDash([]);
      context.globalAlpha = 1;
    }
  }

  context.restore();
}

export function useCanvasRenderer(options: CanvasRendererOptions): void {
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    const frameId = window.requestAnimationFrame(() => {
      drawBaseCanvas(optionsRef.current);
    });
    return () => window.cancelAnimationFrame(frameId);
  }, [
    options.activeLayerId,
    options.blackLightMode,
    options.canvasSize,
    options.gapFillMode,
    options.layers,
    options.pan,
    options.precomputedGapCanvas,
    options.viewportSize,
    options.zoom,
  ]);

  useEffect(() => {
    const frameId = window.requestAnimationFrame(() => {
      drawGapOverlay(optionsRef.current);
    });
    return () => window.cancelAnimationFrame(frameId);
  }, [
    options.brushSize,
    options.canvasSize,
    options.colorSelectionMode,
    options.gapFillMode,
    options.overflowFillMode,
    options.leftoverPenPath,
    options.gaps,
    options.highlightColor,
    options.hoveredGap,
    options.isCtrlBPressed,
    options.isDrawing,
    options.encloseAndFillPath,
    options.pan,
    options.overflowHighlightedRegions,
    options.overflowPropagationFlash,
    options.scaledGapRadius,
    options.swipeBrushSize,
    options.swipeGaps,
    options.swipeMode,
    options.swipePath,
    options.viewportSize,
    options.zoom,
  ]);

  useEffect(() => {
    const frameId = window.requestAnimationFrame(() => {
      drawCursorLayer(optionsRef.current);
    });
    return () => window.cancelAnimationFrame(frameId);
  }, [
    options.canvasMousePosition,
    options.canvasSize,
    options.colorSelectionMode,
    options.fixedMinimapPosition,
    options.highlightColor,
    options.pan,
    options.selectedGapForColor,
    options.viewportSize,
    options.zoom,
  ]);
}
