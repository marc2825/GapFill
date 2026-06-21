import { useCallback, useEffect, useRef, useState, type MouseEvent as ReactMouseEvent, type PointerEvent as ReactPointerEvent, type RefObject } from 'react';
import type { AddToHistory, BrushSettings, Layer, Point } from '../types';
import type { GapFillRegion } from '../types/GapFill';
import { fillGapRegion, fillGapRegions } from '../utils/GapFill/gapFillApplication';
import { floodFill, getPixelColor } from '../utils/canvasUtils';
import { convertScreenToCanvas, createCompositeCanvas, createFillReferenceCanvas, fillEncloseAndFillSelection, fillLeftoverPenSelection, floodFillWithReference, rgbaStringToHex } from '../utils/canvasToolUtils';
import { useCanvasNavigation } from './useCanvasNavigation';

interface UseCanvasInteractionsOptions {
  canvasRef: RefObject<HTMLCanvasElement | null>;
  minimapCanvasRef: RefObject<HTMLCanvasElement | null>;
  minimapRef: RefObject<HTMLDivElement | null>;
  containerRef: RefObject<HTMLDivElement | null>;
  layers: Layer[];
  activeLayerId: string | null;
  activeTool: string;
  brushSettings: BrushSettings;
  gapFillMode: boolean;
  gapFillTool: string;
  gaps: GapFillRegion[];
  scaledGapRadius: number;
  swipeBrushSize: number;
  zoom: number;
  pan: Point;
  zoomStep: number;
  canvasSize: { width: number; height: number };
  fillMultiLayer: boolean;
  disabled: boolean;
  onZoomChange: (zoom: number) => void;
  onPanChange: (pan: Point) => void;
  onLayerUpdate: (layerId: string, canvas: HTMLCanvasElement) => void;
  onAddToHistory: AddToHistory;
  onToolChange: (tool: string) => void;
  onColorPick: (color: string) => void;
}

export interface CanvasInteractionState {
  isDrawing: boolean;
  hoveredGap: GapFillRegion | null;
  colorSelectionMode: boolean;
  selectedGapForColor: GapFillRegion | null;
  tempGapColor: string;
  swipeGaps: Set<string>;
  colorPickerInfo: { x: number; y: number; color: string } | null;
  fixedMinimapPosition: Point | null;
  swipeMode: boolean;
  swipePath: Point[];
  isCtrlBPressed: boolean;
  encloseAndFillPath: Point[];
  leftoverPenPath: Point[];
  isSpacePressed: boolean;
  canvasMousePosition: Point | null;
  isZKeyPressed: boolean;
  setTempGapColor: (color: string) => void;
  cancelColorSelection: () => void;
  handlePointerDown: (
    event: ReactPointerEvent<HTMLCanvasElement>,
  ) => void;
  handlePointerMove: (
    event: ReactPointerEvent<HTMLCanvasElement>,
  ) => void;
  handlePointerUp: (
    event: ReactPointerEvent<HTMLCanvasElement>,
  ) => void;
  handlePointerCancel: (
    event: ReactPointerEvent<HTMLCanvasElement>,
  ) => void;
  handleRightClick: (event: ReactMouseEvent<HTMLCanvasElement>) => void;
}

export function useCanvasInteractions({
  canvasRef,
  minimapCanvasRef,
  minimapRef,
  containerRef,
  layers,
  activeLayerId,
  activeTool,
  brushSettings,
  gapFillMode,
  gapFillTool,
  gaps,
  scaledGapRadius,
  swipeBrushSize,
  zoom,
  pan,
  zoomStep,
  canvasSize,
  fillMultiLayer,
  disabled,
  onZoomChange,
  onPanChange,
  onLayerUpdate,
  onAddToHistory,
  onToolChange,
  onColorPick,
}: UseCanvasInteractionsOptions): CanvasInteractionState {
  const [isDrawing, setIsDrawing] = useState(false);
  const [lastPoint, setLastPoint] = useState<Point | null>(null);
  const [hoveredGap, setHoveredGap] = useState<GapFillRegion | null>(null);
  const [colorSelectionMode, setColorSelectionMode] = useState(false);
  const [selectedGapForColor, setSelectedGapForColor] =
    useState<GapFillRegion | null>(null);
  const [tempGapColor, setTempGapColor] = useState('#000000');
  const [swipeGaps, setSwipeGaps] = useState<Set<string>>(new Set());
  const [colorPickerInfo, setColorPickerInfo] = useState<{
    x: number;
    y: number;
    color: string;
  } | null>(null);
  const colorPickerTimerRef = useRef<number | null>(null);
  const [fixedMinimapPosition, setFixedMinimapPosition] =
    useState<Point | null>(null);
  const [swipeMode, setSwipeMode] = useState(false);
  const [swipePath, setSwipePath] = useState<Point[]>([]);
  const [isPanning, setIsPanning] = useState(false);
  const [lastPanPoint, setLastPanPoint] = useState<Point | null>(null);
  const [encloseAndFillPath, setEncloseAndFillPath] = useState<Point[]>([]);
  const [leftoverPenPath, setLeftoverPenPath] = useState<Point[]>([]);
  const [canvasMousePosition, setCanvasMousePosition] =
    useState<Point | null>(null);
  const [screenMousePosition, setScreenMousePosition] =
    useState<Point | null>(null);
  const [isZooming, setIsZooming] = useState(false);
  const [zoomStartPoint, setZoomStartPoint] = useState<Point | null>(null);
  const [initialZoomValue, setInitialZoomValue] = useState(1);
  const [initialPanValue, setInitialPanValue] = useState<Point>({
    x: 0,
    y: 0,
  });
  const { isCtrlBPressed, isSpacePressed, isZKeyPressed } =
    useCanvasNavigation({
      canvasRef,
      containerRef,
      gapFillMode,
      screenMousePosition,
      zoom,
      pan,
      zoomStep,
      canvasSize,
      onZoomChange,
      onPanChange,
      onToolChange,
    });

  const screenToCanvas = (x: number, y: number): Point =>
    convertScreenToCanvas(
      canvasRef.current,
      x,
      y,
      canvasSize,
      pan,
      zoom,
    );

  const showColorPickerInfo = (
    color: string,
    screenX: number,
    screenY: number,
  ) => {
    if (colorPickerTimerRef.current !== null) {
      window.clearTimeout(colorPickerTimerRef.current);
    }

    onColorPick(color);
    setColorPickerInfo({ x: screenX, y: screenY, color });
    colorPickerTimerRef.current = window.setTimeout(() => {
      setColorPickerInfo(null);
      colorPickerTimerRef.current = null;
    }, 2000);
  };

  useEffect(() => {
    return () => {
      if (colorPickerTimerRef.current !== null) {
        window.clearTimeout(colorPickerTimerRef.current);
      }
    };
  }, []);

  const cancelColorSelection = useCallback(() => {
    setColorSelectionMode(false);
    setSelectedGapForColor(null);
    setCanvasMousePosition(null);
    setIsDrawing(false);
    setFixedMinimapPosition(null);
    setHoveredGap(null);
  }, []);

  const isOverColorSelectionCancel = (clientX: number, clientY: number) => {
    const cancelButton = minimapRef.current?.querySelector<HTMLElement>(
      '[data-color-selection-cancel]',
    );
    if (!cancelButton) return false;

    const rect = cancelButton.getBoundingClientRect();
    return (
      clientX >= rect.left &&
      clientX <= rect.right &&
      clientY >= rect.top &&
      clientY <= rect.bottom
    );
  };

  const resetPointerInteraction = useCallback(() => {
    setIsDrawing(false);
    setLastPoint(null);
    setIsPanning(false);
    setLastPanPoint(null);
    setIsZooming(false);
    setZoomStartPoint(null);
    setInitialZoomValue(1);
    setInitialPanValue({ x: 0, y: 0 });
    setSwipeMode(false);
    setSwipePath([]);
    setSwipeGaps(new Set());
    setEncloseAndFillPath([]);
    setLeftoverPenPath([]);
  }, []);

  useEffect(() => {
    if (disabled) {
      resetPointerInteraction();
      cancelColorSelection();
    }
  }, [cancelColorSelection, disabled, resetPointerInteraction]);

  useEffect(() => {
    if (gapFillMode && gapFillTool !== 'special') {
      setHoveredGap(null);
    }
  }, [gapFillMode, gapFillTool]);

  const fillPathSelection = (
    path: Point[],
    mode: 'enclose-and-fill' | 'leftover-pen',
  ) => {
    if (!activeLayerId) return;
    const activeLayer = layers.find((layer) => layer.id === activeLayerId);
    if (!activeLayer) return;

    const sourceCanvas = fillMultiLayer
      ? createFillReferenceCanvas(layers, canvasSize)
      : activeLayer.canvas;
    if (mode === 'enclose-and-fill') {
      fillEncloseAndFillSelection(
        activeLayer.canvas,
        sourceCanvas,
        path,
        brushSettings.color,
      );
    } else {
      fillLeftoverPenSelection(
        activeLayer.canvas,
        sourceCanvas,
        path,
        brushSettings.size,
        brushSettings.color,
      );
    }
    onLayerUpdate(activeLayerId, activeLayer.canvas);
    onAddToHistory([activeLayerId]);
  };

  const handleRightClick = (
    event: ReactMouseEvent<HTMLCanvasElement>,
  ) => {
    event.preventDefault();
    if (disabled) return;

    const point = screenToCanvas(event.clientX, event.clientY);
    const compositeCanvas = createCompositeCanvas(layers, canvasSize);
    const color = getPixelColor(
      compositeCanvas,
      Math.round(point.x),
      Math.round(point.y),
    );
    if (color !== 'rgba(0,0,0,0)') {
      showColorPickerInfo(
        rgbaStringToHex(color),
        event.clientX,
        event.clientY,
      );
    }
  };

  const handlePointerDown = (
    event: ReactPointerEvent<HTMLCanvasElement>,
  ) => {
    if (disabled || !event.isPrimary) return;
    const point = screenToCanvas(event.clientX, event.clientY);

    if (event.button === 2) {
      event.preventDefault();
      return;
    }

    event.currentTarget.setPointerCapture(event.pointerId);

    if (
      isSpacePressed ||
      (activeTool === 'move' && !gapFillMode && !isZKeyPressed) ||
      (gapFillMode &&
        gapFillTool === 'move' &&
        !isSpacePressed &&
        !isZKeyPressed)
    ) {
      setIsPanning(true);
      setLastPanPoint({ x: event.clientX, y: event.clientY });
      return;
    }

    if (
      isZKeyPressed ||
      (activeTool === 'zoom' && !gapFillMode && !isSpacePressed) ||
      (gapFillMode && gapFillTool === 'zoom' && !isSpacePressed)
    ) {
      setIsZooming(true);
      setZoomStartPoint({ x: event.clientX, y: event.clientY });
      setInitialZoomValue(zoom);
      setInitialPanValue(pan);
      const newZoom = Math.min(zoom * 1.2, 5);
      const rect = containerRef.current?.getBoundingClientRect();

      if (rect) {
        const clickX = event.clientX - rect.left - rect.width / 2;
        const clickY = event.clientY - rect.top - rect.height / 2;
        const scaleFactor = newZoom / zoom;
        onPanChange({
          x: clickX - (clickX - pan.x) * scaleFactor,
          y: clickY - (clickY - pan.y) * scaleFactor,
        });
      }
      onZoomChange(newZoom);
      return;
    }

    if (gapFillMode && gapFillTool === 'special') {
      const clickedGap = gaps.find((gap) => {
        const deltaX = gap.center.x - point.x;
        const deltaY = gap.center.y - point.y;
        return (
          Math.sqrt(deltaX * deltaX + deltaY * deltaY) <= scaledGapRadius
        );
      });

      if (clickedGap) {
        if (canvasMousePosition) {
          setFixedMinimapPosition(canvasMousePosition);
        }
        setSelectedGapForColor(clickedGap);
        setTempGapColor(clickedGap.predictedColor);
        setIsDrawing(true);
        setColorSelectionMode(true);
      } else {
        setSwipeMode(true);
        setSwipePath([point]);
        setSwipeGaps(new Set());
      }
      return;
    }

    if (gapFillMode) return;

    if (activeTool === 'enclose-and-fill' && !colorSelectionMode) {
      setEncloseAndFillPath([point]);
      setIsDrawing(true);
      return;
    }

    if (activeTool === 'leftover-pen' && !colorSelectionMode) {
      setLeftoverPenPath([point]);
      setIsDrawing(true);
      return;
    }

    setIsDrawing(true);
    setLastPoint(point);

    if (activeTool === 'fill' && activeLayerId) {
      const activeLayer = layers.find((layer) => layer.id === activeLayerId);
      if (activeLayer) {
        const fillColor =
          brushSettings.color === 'transparent'
            ? 'rgba(0,0,0,0)'
            : brushSettings.color;
        if (fillMultiLayer) {
          floodFillWithReference(
            activeLayer.canvas,
            createCompositeCanvas(layers, canvasSize),
            Math.round(point.x),
            Math.round(point.y),
            fillColor,
          );
        } else {
          floodFill(
            activeLayer.canvas,
            Math.round(point.x),
            Math.round(point.y),
            fillColor,
          );
        }
        onLayerUpdate(activeLayerId, activeLayer.canvas);
        onAddToHistory([activeLayerId]);
      }
    }

    if (activeTool === 'colorpicker') {
      const color = getPixelColor(
        createCompositeCanvas(layers, canvasSize),
        Math.round(point.x),
        Math.round(point.y),
      );
      if (color !== 'rgba(0,0,0,0)') {
        showColorPickerInfo(
          rgbaStringToHex(color),
          event.clientX,
          event.clientY,
        );
      }
    }
  };

  const handlePointerMove = (
    event: ReactPointerEvent<HTMLCanvasElement>,
  ) => {
    if (!event.isPrimary) return;
    const point = screenToCanvas(event.clientX, event.clientY);
    setScreenMousePosition({ x: event.clientX, y: event.clientY });

    if (disabled && (isDrawing || isPanning || isZooming)) return;

    const canvasRect = canvasRef.current?.getBoundingClientRect();
    if (canvasRect) {
      setCanvasMousePosition({
        x: event.clientX - canvasRect.left,
        y: event.clientY - canvasRect.top,
      });
    }

    if (isZooming && zoomStartPoint) {
      const deltaX = event.clientX - zoomStartPoint.x;
      const deltaY = event.clientY - zoomStartPoint.y;
      if (Math.sqrt(deltaX * deltaX + deltaY * deltaY) > 5) {
        const dragMultiplier = 1 + deltaX * 0.005;
        const newZoom = Math.max(
          0.1,
          Math.min(20, initialZoomValue * 1.2 * dragMultiplier),
        );
        const rect = containerRef.current?.getBoundingClientRect();
        if (rect) {
          const startX =
            zoomStartPoint.x - rect.left - rect.width / 2;
          const startY =
            zoomStartPoint.y - rect.top - rect.height / 2;
          const scaleFactor = newZoom / initialZoomValue;
          onPanChange({
            x:
              startX -
              (startX - initialPanValue.x) * scaleFactor,
            y:
              startY -
              (startY - initialPanValue.y) * scaleFactor,
          });
        }
        onZoomChange(newZoom);
      }
      return;
    }

    if (isPanning && lastPanPoint) {
      onPanChange({
        x: pan.x + event.clientX - lastPanPoint.x,
        y: pan.y + event.clientY - lastPanPoint.y,
      });
      setLastPanPoint({ x: event.clientX, y: event.clientY });
      return;
    }

    if (
      activeTool === 'enclose-and-fill' &&
      isDrawing &&
      !colorSelectionMode
    ) {
      setEncloseAndFillPath((currentPath) => [...currentPath, point]);
      return;
    }

    if (
      activeTool === 'leftover-pen' &&
      isDrawing &&
      !colorSelectionMode
    ) {
      setLeftoverPenPath((currentPath) => [...currentPath, point]);
      return;
    }

    // Implementation of Paper Sec. 4.1.4: the pixel under the cursor dynamically replaces
    // the selected gap's temporary fill color.
    if (colorSelectionMode && selectedGapForColor && activeLayerId) {
      const minimapElement = minimapRef.current;
      const minimapCanvas = minimapCanvasRef.current;
      if (minimapElement && minimapCanvas) {
        const minimapRect = minimapElement.getBoundingClientRect();
        const isOverMinimap =
          event.clientX >= minimapRect.left &&
          event.clientX <= minimapRect.right &&
          event.clientY >= minimapRect.top &&
          event.clientY <= minimapRect.bottom;

        if (isOverMinimap) {
          const rect = minimapCanvas.getBoundingClientRect();
          const x = event.clientX - rect.left;
          const y = event.clientY - rect.top;
          const context = minimapCanvas.getContext('2d');
          if (
            context &&
            x >= 0 &&
            x < minimapCanvas.width &&
            y >= 0 &&
            y < minimapCanvas.height
          ) {
            try {
              const [r, g, b, a] = context.getImageData(
                Math.floor(x),
                Math.floor(y),
                1,
                1,
              ).data;
              setTempGapColor(
                a > 0
                  ? `#${r.toString(16).padStart(2, '0')}${g
                      .toString(16)
                      .padStart(2, '0')}${b
                      .toString(16)
                      .padStart(2, '0')}`
                  : 'transparent',
              );
              return;
            } catch (error) {
              console.warn('Failed to get color from minimap:', error);
            }
          }
        }
      }

      const color = getPixelColor(
        createCompositeCanvas(layers, canvasSize),
        Math.round(point.x),
        Math.round(point.y),
      );
      setTempGapColor(
        color === 'rgba(0,0,0,0)'
          ? 'transparent'
          : rgbaStringToHex(color),
      );
      return;
    }

    // Implementation of Paper Sec. 4.1.5: collect every circular highlight crossed by the
    // translucent sweep stroke.
    if (
      gapFillMode &&
      gapFillTool === 'special' &&
      swipeMode &&
      !colorSelectionMode
    ) {
      setSwipePath((currentPath) => [...currentPath, point]);
      const brushRadius = swipeBrushSize / 2;
      const intersectingGapIds = gaps
        .filter((gap) => {
          const deltaX = gap.center.x - point.x;
          const deltaY = gap.center.y - point.y;
          return (
            Math.sqrt(deltaX * deltaX + deltaY * deltaY) <=
            brushRadius + scaledGapRadius
          );
        })
        .map((gap) => gap.id);
      if (intersectingGapIds.length > 0) {
        setSwipeGaps((currentGaps) => {
          const nextGaps = new Set(currentGaps);
          intersectingGapIds.forEach((gapId) => nextGaps.add(gapId));
          return nextGaps;
        });
      }
      return;
    }

    // Implementation of Paper Sec. 4.1.3: hovering a circle selects the fixed 5x magnifier.
    if (
      gapFillMode &&
      gapFillTool === 'special' &&
      !swipeMode
    ) {
      const overGap =
        gaps.find((gap) => {
          const deltaX = gap.center.x - point.x;
          const deltaY = gap.center.y - point.y;
          return (
            Math.sqrt(deltaX * deltaX + deltaY * deltaY) <=
            scaledGapRadius
          );
        }) || null;
      setHoveredGap(overGap);
    }

    if (!isDrawing || !activeLayerId) return;
    const activeLayer = layers.find((layer) => layer.id === activeLayerId);
    const context = activeLayer?.canvas.getContext('2d');
    if (!activeLayer || !context) return;

    if (activeTool === 'dot-pen' || activeTool === 'eraser') {
      const isTransparent = brushSettings.color === 'transparent';
      context.globalCompositeOperation =
        activeTool === 'eraser' || isTransparent
          ? 'destination-out'
          : 'source-over';
      context.fillStyle = isTransparent ? '#000000' : brushSettings.color;
      context.imageSmoothingEnabled = false;
      const size = Math.max(1, Math.floor(brushSettings.size));
      const halfSize = Math.floor(size / 2);

      if (lastPoint) {
        const deltaX = Math.abs(point.x - lastPoint.x);
        const deltaY = Math.abs(point.y - lastPoint.y);
        const steps = Math.max(deltaX, deltaY);
        for (let index = 0; index <= steps; index++) {
          const progress = steps === 0 ? 0 : index / steps;
          const x = Math.floor(
            lastPoint.x + (point.x - lastPoint.x) * progress,
          );
          const y = Math.floor(
            lastPoint.y + (point.y - lastPoint.y) * progress,
          );
          context.fillRect(
            x - halfSize,
            y - halfSize,
            size,
            size,
          );
        }
      } else {
        context.fillRect(
          Math.floor(point.x) - halfSize,
          Math.floor(point.y) - halfSize,
          size,
          size,
        );
      }

      setLastPoint(point);
      onLayerUpdate(activeLayerId, activeLayer.canvas);
    }
  };

  const handlePointerUp = (
    event: ReactPointerEvent<HTMLCanvasElement>,
  ) => {
    if (!event.isPrimary) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (disabled) {
      resetPointerInteraction();
      cancelColorSelection();
      return;
    }

    if (isZooming) {
      setIsZooming(false);
      setZoomStartPoint(null);
      setInitialZoomValue(1);
      setInitialPanValue({ x: 0, y: 0 });
    }
    setIsPanning(false);
    setLastPanPoint(null);

    // The main canvas owns pointer capture during the drag, so the cancel
    // button cannot receive pointerup directly. Check its bounds before
    // committing the selected color.
    if (
      colorSelectionMode &&
      isOverColorSelectionCancel(event.clientX, event.clientY)
    ) {
      cancelColorSelection();
      return;
    }

    // Implementation of Paper Sec. 4.1.4: release commits the chosen color.
    if (colorSelectionMode && selectedGapForColor && activeLayerId) {
      const activeLayer = layers.find((layer) => layer.id === activeLayerId);
      if (tempGapColor !== 'transparent' && activeLayer) {
        fillGapRegion(
          activeLayer.canvas,
          selectedGapForColor,
          tempGapColor,
        );
        onLayerUpdate(activeLayerId, activeLayer.canvas);
        onAddToHistory([activeLayerId]);
      }
      cancelColorSelection();
      return;
    }

    // Implementation of Paper Sec. 4.1.5: release applies all selected suggestions together.
    if (
      gapFillMode &&
      gapFillTool === 'special' &&
      swipeMode &&
      !colorSelectionMode
    ) {
      if (activeLayerId && swipeGaps.size > 0) {
        const activeLayer = layers.find(
          (layer) => layer.id === activeLayerId,
        );
        if (activeLayer) {
          const selectedGaps = gaps.filter((gap) => swipeGaps.has(gap.id));
          fillGapRegions(activeLayer.canvas, selectedGaps);
          onLayerUpdate(activeLayerId, activeLayer.canvas);
          onAddToHistory([activeLayerId]);
        }
      }
      setSwipeMode(false);
      setSwipePath([]);
      setSwipeGaps(new Set());
      setIsDrawing(false);
      return;
    }

    if (
      activeTool === 'enclose-and-fill' &&
      isDrawing &&
      encloseAndFillPath.length > 2 &&
      !colorSelectionMode
    ) {
      fillPathSelection(encloseAndFillPath, 'enclose-and-fill');
      setEncloseAndFillPath([]);
      setIsDrawing(false);
      return;
    }

    if (
      activeTool === 'leftover-pen' &&
      isDrawing &&
      leftoverPenPath.length > 1 &&
      !colorSelectionMode
    ) {
      fillPathSelection(leftoverPenPath, 'leftover-pen');
      setLeftoverPenPath([]);
      setIsDrawing(false);
      return;
    }

    const wasDrawing = isDrawing;
    setIsDrawing(false);
    setLastPoint(null);
    setEncloseAndFillPath([]);
    setLeftoverPenPath([]);
    if (
      wasDrawing &&
      (activeTool === 'dot-pen' ||
        activeTool === 'eraser' ||
        activeTool === 'leftover-pen')
    ) {
      onAddToHistory(activeLayerId ? [activeLayerId] : undefined);
    }
  };

  const handlePointerCancel = (
    event: ReactPointerEvent<HTMLCanvasElement>,
  ) => {
    if (!event.isPrimary) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    resetPointerInteraction();
    cancelColorSelection();
  };

  return {
    isDrawing,
    hoveredGap,
    colorSelectionMode,
    selectedGapForColor,
    tempGapColor,
    swipeGaps,
    colorPickerInfo,
    fixedMinimapPosition,
    swipeMode,
    swipePath,
    isCtrlBPressed,
    encloseAndFillPath,
    leftoverPenPath,
    isSpacePressed,
    canvasMousePosition,
    isZKeyPressed,
    setTempGapColor,
    cancelColorSelection,
    handlePointerDown,
    handlePointerMove,
    handlePointerUp,
    handlePointerCancel,
    handleRightClick,
  };
}
