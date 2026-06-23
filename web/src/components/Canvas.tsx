import { useLayoutEffect, useRef, useState, type FC } from 'react';
import type { AddToHistory, BrushSettings, Layer, Point } from '../types';
import type { GapFillRegion } from '../types/GapFill';
import { useCanvasInteractions } from '../hooks/useCanvasInteractions';
import { useCanvasRenderer } from '../hooks/useCanvasRenderer';
import { useGapDetection } from '../hooks/GapFill/useGapDetection';
import { useOverflowFill } from '../overflow/useOverflowFill';
import { GapMagnifier } from './GapFill/GapMagnifier';
import './Canvas.css';

interface CanvasProps {
  layers: Layer[];
  activeLayerId: string | null;
  activeTool: string;
  brushSettings: BrushSettings;
  gapFillMode: boolean;
  overflowFillMode: boolean;
  overflowLikelihoodThreshold: number;
  onOverflowStatusChange: (status: string) => void;
  onOverflowLinkedGapCountChange: (count: number) => void;
  gapFillThreshold: number;
  gapFillTool: string;
  swipeBrushSize: number;
  blackLightMode: boolean;
  zoom: number;
  pan: Point;
  zoomStep: number;
  onZoomChange: (zoom: number) => void;
  onPanChange: (pan: Point) => void;
  onLayerUpdate: (layerId: string, canvas: HTMLCanvasElement) => void;
  onAddToHistory: AddToHistory;
  onToolChange: (tool: string) => void;
  onColorPick: (color: string) => void;
  fillMultiLayer: boolean;
  canvasSize: { width: number; height: number };
  highlightColor: string;
  onGapsChange?: (gaps: GapFillRegion[]) => void;
  historyIndex: number;
  disabled?: boolean;
  isStarted?: boolean;
}

const Canvas: FC<CanvasProps> = ({
  layers,
  activeLayerId,
  activeTool,
  brushSettings,
  gapFillMode,
  overflowFillMode,
  overflowLikelihoodThreshold,
  onOverflowStatusChange,
  onOverflowLinkedGapCountChange,
  gapFillThreshold,
  gapFillTool,
  swipeBrushSize,
  blackLightMode,
  zoom,
  pan,
  zoomStep,
  onZoomChange,
  onPanChange,
  onLayerUpdate,
  onAddToHistory,
  onToolChange,
  onColorPick,
  fillMultiLayer,
  canvasSize,
  highlightColor,
  onGapsChange,
  historyIndex,
  disabled = false,
  isStarted = true,
}) => {
  // Implementation of Paper Sec. 4.1 implementation map:
  // 4.1.1-4.1.2 detection and suggested-color overlay: useGapDetection.
  // 4.1.1 circle and 4.1.4 connector rendering: useCanvasRenderer.
  // 4.1.3 fixed 5x local view: GapMagnifier.
  // 4.1.4 correction and 4.1.5 sweep interactions: useCanvasInteractions.
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const cursorCanvasRef = useRef<HTMLCanvasElement>(null);
  const minimapCanvasRef = useRef<HTMLCanvasElement>(null);
  const minimapRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewportSize, setViewportSize] = useState({ width: 1, height: 1 });

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const updateViewportSize = () => {
      const nextSize = {
        width: Math.max(1, Math.floor(container.clientWidth)),
        height: Math.max(1, Math.floor(container.clientHeight)),
      };
      setViewportSize((currentSize) =>
        currentSize.width === nextSize.width &&
        currentSize.height === nextSize.height
          ? currentSize
          : nextSize,
      );
    };

    updateViewportSize();
    const resizeObserver = new ResizeObserver(updateViewportSize);
    resizeObserver.observe(container);

    return () => resizeObserver.disconnect();
  }, []);

  const baseGapRadius = 12;
  const scaledGapRadius = baseGapRadius / Math.sqrt(zoom);
  const {
    gaps,
    precomputedGapCanvas,
    error: gapDetectionError,
  } = useGapDetection({
    layers,
    activeLayerId,
    gapFillMode,
    gapFillThreshold,
    fallbackColor: brushSettings.color,
    onGapsChange,
  });
  const overflowFill = useOverflowFill({
    layers,
    activeLayerId,
    enabled: overflowFillMode,
    gapThreshold: gapFillThreshold,
    likelihoodThreshold: overflowLikelihoodThreshold,
    brushSettings,
    historyIndex,
    onLayerUpdate,
    onAddToHistory,
    onStatusChange: onOverflowStatusChange,
    onLinkedGapCountChange: onOverflowLinkedGapCountChange,
  });
  const interaction = useCanvasInteractions({
    canvasRef,
    minimapCanvasRef,
    minimapRef,
    containerRef,
    layers,
    activeLayerId,
    activeTool,
    brushSettings,
    gapFillMode,
    overflowFillMode,
    onOverflowHover: overflowFill.handleHover,
    onOverflowBucketFill: overflowFill.handleBucketFill,
    onOverflowStandardBucketFill: overflowFill.handleStandardBucketFill,
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
  });

  useCanvasRenderer({
    canvasRef,
    overlayCanvasRef,
    cursorCanvasRef,
    minimapRef,
    containerRef,
    layers,
    activeLayerId,
    canvasSize,
    zoom,
    pan,
    blackLightMode,
    gapFillMode,
    overflowFillMode,
    gaps,
    precomputedGapCanvas,
    highlightColor,
    scaledGapRadius,
    hoveredGap: interaction.hoveredGap,
    overflowHighlightedRegions: overflowFill.highlightedRegions,
    overflowPropagationFlash: overflowFill.propagationFlash,
    isCtrlBPressed: interaction.isCtrlBPressed,
    swipeGaps: interaction.swipeGaps,
    swipeMode: interaction.swipeMode,
    swipePath: interaction.swipePath,
    swipeBrushSize,
    colorSelectionMode: interaction.colorSelectionMode,
    encloseAndFillPath: interaction.encloseAndFillPath,
    leftoverPenPath: interaction.leftoverPenPath,
    isDrawing: interaction.isDrawing,
    brushSize: brushSettings.size,
    selectedGapForColor: interaction.selectedGapForColor,
    canvasMousePosition: interaction.canvasMousePosition,
    fixedMinimapPosition: interaction.fixedMinimapPosition,
    viewportSize,
  });

  const isMinimapVisible =
    gapFillMode &&
    gapFillTool === 'special' &&
    !interaction.isSpacePressed &&
    Boolean(interaction.hoveredGap || interaction.colorSelectionMode);

  return (
    <div
      className={`canvas-container ${isMinimapVisible ? 'minimap-active' : ''} ${interaction.colorSelectionMode ? 'color-selection-mode' : ''} ${disabled ? 'canvas-disabled' : ''} ${disabled && !isStarted ? 'not-started' : ''}`}
      ref={containerRef}
      data-tool={activeTool}
      data-gapfill={gapFillMode}
      data-overflow-fill={overflowFillMode}
      data-gapfill-tool={gapFillTool}
      data-swipe-mode={
        interaction.swipeMode && !interaction.colorSelectionMode
      }
      data-space-pressed={interaction.isSpacePressed}
      data-z-pressed={interaction.isZKeyPressed}
      data-disabled={disabled}
    >
      <canvas
        ref={canvasRef}
        width={viewportSize.width}
        height={viewportSize.height}
        className="main-canvas"
        style={{
          imageRendering: zoom > 4 ? 'pixelated' : 'auto',
          touchAction: 'none',
        }}
        onPointerDown={interaction.handlePointerDown}
        onPointerMove={interaction.handlePointerMove}
        onPointerUp={interaction.handlePointerUp}
        onPointerCancel={interaction.handlePointerCancel}
        onContextMenu={interaction.handleRightClick}
      />

      {overflowFillMode && overflowFill.propagationSuppressed && (
        <div className="overflow-retry-badge">
          Undo retry: propagation off
        </div>
      )}
      <canvas
        ref={overlayCanvasRef}
        width={viewportSize.width}
        height={viewportSize.height}
        className="overlay-canvas"
        style={{
          pointerEvents: 'none',
          imageRendering: zoom > 4 ? 'pixelated' : 'auto',
        }}
      />
      <canvas
        ref={cursorCanvasRef}
        width={viewportSize.width}
        height={viewportSize.height}
        className="cursor-canvas"
        style={{
          pointerEvents: 'none',
          imageRendering: zoom > 4 ? 'pixelated' : 'auto',
        }}
      />

      {gapFillMode &&
        gapFillTool !== 'move' &&
        !interaction.isSpacePressed &&
        (interaction.hoveredGap || interaction.colorSelectionMode) && (
          <GapMagnifier
            layers={layers}
            gaps={gaps}
            hoveredGap={interaction.hoveredGap}
            selectedGap={interaction.selectedGapForColor}
            colorSelectionMode={interaction.colorSelectionMode}
            temporaryColor={interaction.tempGapColor}
            highlightColor={highlightColor}
            canvasMousePosition={interaction.canvasMousePosition}
            fixedPosition={interaction.fixedMinimapPosition}
            canvasRef={minimapCanvasRef}
            minimapRef={minimapRef}
            onCancel={interaction.cancelColorSelection}
          />
        )}

      <input
        type="color"
        value={interaction.tempGapColor}
        onChange={(event) =>
          interaction.setTempGapColor(event.target.value)
        }
        style={{
          position: 'absolute',
          visibility: 'hidden',
          width: '1px',
          height: '1px',
          pointerEvents: 'none',
        }}
      />

      {interaction.colorPickerInfo && (
        <div
          className="color-picker-popup"
          style={{
            left: Math.min(
              interaction.colorPickerInfo.x + 10,
              window.innerWidth - 150,
            ),
            top: Math.max(interaction.colorPickerInfo.y - 40, 10),
          }}
        >
          <div className="color-picker-popup-content">
            <div
              className="color-picker-preview"
              style={{
                backgroundColor: interaction.colorPickerInfo.color,
              }}
            />
            <span className="color-picker-text">
              {interaction.colorPickerInfo.color}
            </span>
          </div>
        </div>
      )}

      {gapFillMode && gapDetectionError && (
        <div className="gapfill-error" role="alert">
          <strong>GapFill unavailable</strong>
          <span>{gapDetectionError}</span>
        </div>
      )}

      {gapFillMode && !gapDetectionError && (
        <div
          className="gapfill-indicator"
          style={{ color: highlightColor, borderColor: highlightColor }}
        >
          Predicted Colors Active
        </div>
      )}
    </div>
  );
};

export default Canvas;
