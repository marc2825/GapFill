import { useEffect, useRef, useState } from 'react';
import type { BrushSettings, Layer, Point } from './types';
import { useResizablePanels } from './components/ResizablePanels';
import { initializeModel } from './utils/GapFill/modelPreloader';
import type { ImagePreset } from './config/presets';
import { IMAGE_PRESETS } from './config/presets';
import { DEFAULT_SHORTCUTS } from './types/shortcuts';
import AppTopControls from './components/AppTopControls';
import AppWorkspace from './components/AppWorkspace';
import DescriptionDialog from './components/DescriptionDialog';
import useHistoryManager from './hooks/useHistoryManager';
import useInitialCanvasSetup from './hooks/useInitialCanvasSetup';
import useKeyboardShortcuts from './hooks/useKeyboardShortcuts';
import useLayerHandlers from './hooks/useLayerHandlers';
import useFileHandlers from './hooks/useFileHandlers';
import useSessionHandlers from './hooks/useSessionHandlers';
import usePresetHandlers from './hooks/usePresetHandlers';
import useGapFill from './hooks/GapFill/useGapFill';
import './App.css';

function App() {
  // Implementation of Paper Sec. 4.1 / 5.1:
  // This entry point orchestrates the study paint software by wiring the
  // paper's top-level UI (task controls + workspace) to the self-contained
  // implementations now colocated under src/components/* and src/utils/*.
  useResizablePanels();

  const [layers, setLayers] = useState<Layer[]>([]);
  const [activeLayerId, setActiveLayerId] = useState<string | null>(null);
  const [activeTool, setActiveTool] = useState<string>('move');
  const [brushSettings, setBrushSettings] = useState<BrushSettings>({
    size: 5,
    color: '#000000',
  });
  const [previousColor, setPreviousColor] = useState('#000000');
  const [blackLightMode, setBlackLightMode] = useState(false);
  const [overflowFillMode, setOverflowFillMode] = useState(false);
  const [overflowLikelihoodThreshold, setOverflowLikelihoodThreshold] =
    useState(0.15);
  const [overflowStatus, setOverflowStatus] =
    useState('Overflow Fill off');
  const [overflowLinkedGapCount, setOverflowLinkedGapCount] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 });
  const [referenceImage, setReferenceImage] = useState<string | null>(null);
  const [fillMultiLayer, setFillMultiLayer] = useState(true);
  const [canvasSize, setCanvasSize] = useState({ width: 800, height: 600 });
  const [selectedPreset, setSelectedPreset] = useState<string>(IMAGE_PRESETS[0]?.id || 'debug');
  const [currentPresetConfig, setCurrentPresetConfig] = useState<ImagePreset | null>(
    IMAGE_PRESETS[0] || null,
  );
  const [isStarted, setIsStarted] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);
  const [isPresetLoading, setIsPresetLoading] = useState(false);
  const [showDescription, setShowDescription] = useState(false);
  const shortcuts = DEFAULT_SHORTCUTS;
  const zoomStep = 0.1;

  const timerRef = useRef<number | null>(null);
  const isInitialMount = useRef(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const guidesInputRef = useRef<HTMLInputElement>(null);
  const coloringInputRef = useRef<HTMLInputElement>(null);
  const referenceInputRef = useRef<HTMLInputElement>(null);
  const canvasAreaRef = useRef<HTMLDivElement>(null);
  const isLoadingImageRef = useRef(false);
  const isLoadingGuidesRef = useRef(false);
  const isLoadingColoringRef = useRef(false);
  const manualFileLoadEpochRef = useRef(0);

  const {
    history,
    historyIndex,
    initializeHistory,
    addToHistory,
    undo,
    redo,
    resetHistory,
  } = useHistoryManager({
    layers,
    setLayers,
    isLoadingImageRef,
    isLoadingGuidesRef,
    isLoadingColoringRef,
  });

  const {
    handleLayerToggleVisibility,
    handleLayerUpdate,
  } = useLayerHandlers({
    layers,
    setLayers,
  });

  const {
    gapFillMode,
    setGapFillMode,
    gapFillThreshold,
    setGapFillThreshold,
    gapFillTool,
    setGapFillTool,
    swipeBrushSize,
    setSwipeBrushSize,
    highlightColor,
    setHighlightColor,
    currentGaps,
    setCurrentGaps,
    handleGapFillToggle,
    handleGapFillApplyAll,
  } = useGapFill({
    layers,
    activeLayerId,
    currentPresetConfig,
    onLayerUpdate: handleLayerUpdate,
    onAddToHistory: addToHistory,
  });

  const {
    handleImageLoad,
    handleGuidesLoad,
    handleColoringLoad,
    handleImageFileSelect,
    handleGuidesFileSelect,
    handleColoringFileSelect,
    handleReferenceImageSelect,
  } = useFileHandlers({
    fileInputRef,
    guidesInputRef,
    coloringInputRef,
    canvasSize,
    setCanvasSize,
    setPan,
    setZoom,
    setLayers,
    setReferenceImage,
    isLoadingImageRef,
    isLoadingGuidesRef,
    isLoadingColoringRef,
    manualFileLoadEpochRef,
  });

  const { handleStart, handleDone, stopTimer } = useSessionHandlers({
    isStarted,
    isDone,
    currentPresetConfig,
    layers,
    canvasSize,
    timerRef,
    setIsStarted,
    setIsDone,
    setTimeRemaining,
  });

  const { handlePresetChange } = usePresetHandlers({
    setSelectedPreset,
    setCurrentPresetConfig,
    setIsStarted,
    setIsDone,
    setTimeRemaining,
    stopTimer,
    setLayers,
    setReferenceImage,
    resetHistory,
    setPan,
    setZoom,
    setCanvasSize,
    setBlackLightMode,
    setGapFillMode,
    setActiveLayerId,
    setIsPresetLoading,
    isLoadingImageRef,
    isLoadingGuidesRef,
    isLoadingColoringRef,
    manualFileLoadEpochRef,
  });

  useInitialCanvasSetup({
    layers,
    canvasSize,
    isPresetLoading,
    setLayers,
    setActiveLayerId,
    initializeHistory,
  });

  useKeyboardShortcuts({
    zoom,
    zoomStep,
    blackLightMode,
    gapFillMode,
    overflowFillMode,
    setBlackLightMode,
    setZoom,
    onUndo: undo,
    onRedo: redo,
  });

  useEffect(() => {
    if (!isInitialMount.current || !currentPresetConfig) return undefined;

    const timer = window.setTimeout(() => {
      if (isInitialMount.current) {
        isInitialMount.current = false;
        handlePresetChange(currentPresetConfig);
      }
    }, 100);

    return () => window.clearTimeout(timer);
  }, [currentPresetConfig, handlePresetChange]);

  useEffect(() => {
    void initializeModel();
  }, []);

  useEffect(() => {
    return stopTimer;
  }, [stopTimer]);

  return (
    <div className="app">
      {/* Implementation of Paper Sec. 4.1 User Interface / Sec. 5.1 Methodology:
          task preset selection, undo/redo, task description, timer, Start/Done,
          and debug asset loading are grouped in the study's top control bar. */}
      <AppTopControls
        selectedPreset={selectedPreset}
        onPresetChange={handlePresetChange}
        onImageLoad={handleImageLoad}
        onGuidesLoad={handleGuidesLoad}
        onColoringLoad={handleColoringLoad}
        onUndo={undo}
        onRedo={redo}
        historyIndex={historyIndex}
        historyLength={history.length}
        shortcuts={shortcuts}
        fileInputRef={fileInputRef}
        guidesInputRef={guidesInputRef}
        coloringInputRef={coloringInputRef}
        referenceInputRef={referenceInputRef}
        onImageFileSelect={handleImageFileSelect}
        onGuidesFileSelect={handleGuidesFileSelect}
        onColoringFileSelect={handleColoringFileSelect}
        onReferenceImageSelect={handleReferenceImageSelect}
        timeRemaining={timeRemaining}
        onOpenDescription={() => setShowDescription(true)}
        isStarted={isStarted}
        isDone={isDone}
        onStart={handleStart}
        onDone={handleDone}
      />

      {/* Implementation of Paper Sec. 4.1 User Interface:
          the main three-pane work area is assembled here. AppWorkspace delegates the
          concrete painting, GapFill, reference, and layer UI to local components. */}
      <AppWorkspace
        selectedPreset={selectedPreset}
        currentPresetConfig={currentPresetConfig}
        activeTool={activeTool}
        onToolChange={setActiveTool}
        brushSettings={brushSettings}
        onBrushSizeChange={(size) => setBrushSettings({ ...brushSettings, size })}
        onBrushColorChange={(color) => {
          if (color === 'transparent' && brushSettings.color !== 'transparent') {
            setPreviousColor(brushSettings.color);
          } else if (color !== 'transparent' && brushSettings.color === 'transparent') {
            setPreviousColor(color);
          }
          setBrushSettings({ ...brushSettings, color });
        }}
        previousColor={previousColor}
        onRestorePreviousColor={() => {
          if (brushSettings.color === 'transparent') {
            setBrushSettings({ ...brushSettings, color: previousColor });
          }
        }}
        blackLightMode={blackLightMode}
        onBlackLightToggle={() => {
          if (!gapFillMode && !overflowFillMode) {
            setBlackLightMode(!blackLightMode);
          }
        }}
        gapFillMode={gapFillMode}
        overflowFillMode={overflowFillMode}
        overflowLikelihoodThreshold={overflowLikelihoodThreshold}
        overflowStatus={overflowStatus}
        overflowLinkedGapCount={overflowLinkedGapCount}
        onOverflowFillToggle={() => {
          setOverflowFillMode((currentMode) => {
            const nextMode = !currentMode;
            if (nextMode) {
              setGapFillMode(false);
              setActiveTool('fill');
            }
            return nextMode;
          });
        }}
        onOverflowLikelihoodThresholdChange={setOverflowLikelihoodThreshold}
        onOverflowStatusChange={setOverflowStatus}
        onOverflowLinkedGapCountChange={setOverflowLinkedGapCount}
        shortcuts={shortcuts}
        gapFillThreshold={gapFillThreshold}
        onGapFillToggle={() => {
          if (!gapFillMode) {
            setOverflowFillMode(false);
          }
          handleGapFillToggle();
        }}
        onGapFillThresholdChange={setGapFillThreshold}
        onGapFillApplyAll={handleGapFillApplyAll}
        gapCount={currentGaps.length}
        gapFillTool={gapFillTool}
        onGapFillToolChange={setGapFillTool}
        swipeBrushSize={swipeBrushSize}
        onSwipeBrushSizeChange={setSwipeBrushSize}
        highlightColor={highlightColor}
        onHighlightColorChange={setHighlightColor}
        layers={layers}
        activeLayerId={activeLayerId}
        onLayerToggleVisibility={handleLayerToggleVisibility}
        onLayerUpdate={handleLayerUpdate}
        zoom={zoom}
        pan={pan}
        zoomStep={zoomStep}
        onZoomChange={setZoom}
        onPanChange={setPan}
        onAddToHistory={addToHistory}
        historyIndex={historyIndex}
        onColorPick={(color: string) => setBrushSettings({ ...brushSettings, color })}
        fillMultiLayer={fillMultiLayer}
        onFillMultiLayerChange={setFillMultiLayer}
        canvasSize={canvasSize}
        onGapsChange={setCurrentGaps}
        isStarted={isStarted}
        isDone={isDone}
        referenceImage={referenceImage}
        canvasAreaRef={canvasAreaRef}
      />

      <DescriptionDialog
        isOpen={showDescription}
        description={currentPresetConfig?.description}
        onClose={() => setShowDescription(false)}
      />
    </div>
  );
}

export default App;
