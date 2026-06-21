import type { RefObject } from 'react';
import Toolbar from './Toolbar';
import LayerPanel from './LayerPanel';
import ReferenceCanvas from './ReferenceCanvas';
import Canvas from './Canvas';
import type { AddToHistory, BrushSettings, Layer, Point } from '../types';
import type { GapFillRegion } from '../types/GapFill';
import type { ImagePreset } from '../config/presets';
import type { ShortcutConfig } from '../types/shortcuts';
import GapFillPanel from './GapFill/GapFillPanel';

interface AppWorkspaceProps {
  selectedPreset: string;
  currentPresetConfig: ImagePreset | null;
  activeTool: string;
  onToolChange: (toolId: string) => void;
  brushSettings: BrushSettings;
  onBrushSizeChange: (size: number) => void;
  onBrushColorChange: (color: string) => void;
  previousColor: string;
  onRestorePreviousColor: () => void;
  blackLightMode: boolean;
  onBlackLightToggle: () => void;
  gapFillMode: boolean;
  shortcuts: ShortcutConfig;

  gapFillThreshold: number;
  onGapFillToggle: () => void;
  onGapFillThresholdChange: (threshold: number) => void;
  onGapFillApplyAll: () => Promise<void> | void;
  gapCount: number;
  gapFillTool: string;
  onGapFillToolChange: (tool: string) => void;
  swipeBrushSize: number;
  onSwipeBrushSizeChange: (size: number) => void;
  highlightColor: string;
  onHighlightColorChange: (color: string) => void;

  layers: Layer[];
  activeLayerId: string | null;
  onLayerToggleVisibility: (layerId: string) => void;
  onLayerUpdate: (layerId: string, canvas: HTMLCanvasElement) => void;

  zoom: number;
  pan: Point;
  zoomStep: number;
  onZoomChange: (zoom: number) => void;
  onPanChange: (pan: Point) => void;
  onAddToHistory: AddToHistory;
  onColorPick: (color: string) => void;
  fillMultiLayer: boolean;
  onFillMultiLayerChange: (enabled: boolean) => void;
  canvasSize: { width: number; height: number };
  onGapsChange: (gaps: GapFillRegion[]) => void;
  isStarted: boolean;
  isDone: boolean;
  referenceImage: string | null;
  canvasAreaRef: RefObject<HTMLDivElement | null>;
}

function AppWorkspace({
  selectedPreset,
  currentPresetConfig,
  activeTool,
  onToolChange,
  brushSettings,
  onBrushSizeChange,
  onBrushColorChange,
  previousColor,
  onRestorePreviousColor,
  blackLightMode,
  onBlackLightToggle,
  gapFillMode,
  shortcuts,
  gapFillThreshold,
  onGapFillToggle,
  onGapFillThresholdChange,
  onGapFillApplyAll,
  gapCount,
  gapFillTool,
  onGapFillToolChange,
  swipeBrushSize,
  onSwipeBrushSizeChange,
  highlightColor,
  onHighlightColorChange,
  layers,
  activeLayerId,
  onLayerToggleVisibility,
  onLayerUpdate,
  zoom,
  pan,
  zoomStep,
  onZoomChange,
  onPanChange,
  onAddToHistory,
  onColorPick,
  fillMultiLayer,
  onFillMultiLayerChange,
  canvasSize,
  onGapsChange,
  isStarted,
  isDone,
  referenceImage,
  canvasAreaRef,
}: AppWorkspaceProps) {
  return (
    <>
      {/* Implementation of Paper Sec. 4.1 User Interface:
          the conventional paint tools (move/zoom/picker/bucket/Dot Pen/eraser plus
          Black Light, Enclose and Fill, and Leftover Pen) are surfaced via Toolbar. */}
      <Toolbar
        activeTool={activeTool}
        onToolChange={onToolChange}
        brushSize={brushSettings.size}
        onBrushSizeChange={onBrushSizeChange}
        brushColor={brushSettings.color}
        onBrushColorChange={onBrushColorChange}
        previousColor={previousColor}
        onRestorePreviousColor={onRestorePreviousColor}
        blackLightMode={blackLightMode}
        onBlackLightToggle={onBlackLightToggle}
        gapFillMode={gapFillMode}
        showEncloseAndFill={currentPresetConfig?.enableEncloseAndFill !== false}
        showLeftoverPen={currentPresetConfig?.enableLeftoverPen !== false}
        showBucketTool={currentPresetConfig?.enableBucketTool !== false}
        showBlackLight={currentPresetConfig?.enableBlackLight !== false}
        shortcuts={shortcuts}
      />

      <div className="main-container">
        <div className="left-panel resizable-panel">
          <div className="panel-content">
            {/* Implementation of Paper Sec. 4.1 User Interface:
                dedicated GapFill-side controls (mode, threshold, tool, highlight,
                Apply All) live in the left panel. */}
            <GapFillPanel
              selectedPreset={selectedPreset}
              currentPresetConfig={currentPresetConfig}
              gapFillMode={gapFillMode}
              onGapFillToggle={onGapFillToggle}
              gapFillThreshold={gapFillThreshold}
              onGapFillThresholdChange={onGapFillThresholdChange}
              onGapFillApplyAll={onGapFillApplyAll}
              gapCount={gapCount}
              gapFillTool={gapFillTool}
              onGapFillToolChange={onGapFillToolChange}
              swipeBrushSize={swipeBrushSize}
              onSwipeBrushSizeChange={onSwipeBrushSizeChange}
              highlightColor={highlightColor}
              onHighlightColorChange={onHighlightColorChange}
            />
          </div>
          <div className="resize-handle resize-handle-right"></div>
        </div>

        <div className="canvas-area" ref={canvasAreaRef}>
          {/* Implementation of Paper Sec. 4.1 User Interface / Sec. 5.1 Methodology:
              components/Canvas.tsx is the actual paint software implementation
              used in the study, including Dot Pen, zoom/pan, Paint Bucket,
              Enclose and Fill, Leftover Pen, gap detection, hover magnification, in-circle color-pick,
              sweep-to-apply, and the disabled state before Start / after Done. */}
          <Canvas
            layers={layers}
            activeLayerId={activeLayerId}
            activeTool={activeTool}
            brushSettings={brushSettings}
            gapFillMode={gapFillMode}
            gapFillThreshold={gapFillThreshold}
            gapFillTool={gapFillTool}
            swipeBrushSize={swipeBrushSize}
            blackLightMode={blackLightMode}
            zoom={zoom}
            pan={pan}
            zoomStep={zoomStep}
            onZoomChange={onZoomChange}
            onPanChange={onPanChange}
            onLayerUpdate={onLayerUpdate}
            onAddToHistory={onAddToHistory}
            onToolChange={onToolChange}
            onColorPick={onColorPick}
            fillMultiLayer={fillMultiLayer}
            canvasSize={canvasSize}
            highlightColor={highlightColor}
            onGapsChange={onGapsChange}
            disabled={selectedPreset !== 'debug' && (!isStarted || isDone)}
            isStarted={isStarted}
          />
        </div>

        <div className="right-panel resizable-panel">
          <div className="resize-handle resize-handle-left"></div>
          <div className="panel-content">
            {/* Implementation of Paper Sec. 4.1 User Interface / Sec. 5.1 Methodology:
                the right panel hosts the reference image and layer stack used by the
                experiment tasks and by the refactored production-style workspace. */}
            {referenceImage && (
              <ReferenceCanvas
                referenceImage={referenceImage}
                onColorPick={onColorPick}
              />
            )}

            <LayerPanel
              layers={layers}
              activeLayerId={activeLayerId}
              onLayerToggleVisibility={onLayerToggleVisibility}
              fillMultiLayer={fillMultiLayer}
              onFillMultiLayerChange={onFillMultiLayerChange}
            />
          </div>
        </div>
      </div>
    </>
  );
}

export default AppWorkspace;
