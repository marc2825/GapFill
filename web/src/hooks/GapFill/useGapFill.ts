import { useCallback, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { AddToHistory, Layer } from '../../types';
import type { GapFillRegion } from '../../types/GapFill';
import type { ImagePreset } from '../../config/presets';
import { fillGapRegions } from '../../utils/GapFill/gapFillApplication';

interface UseGapFillParams {
  layers: Layer[];
  activeLayerId: string | null;
  currentPresetConfig: ImagePreset | null;
  onLayerUpdate: (layerId: string, canvas: HTMLCanvasElement) => void;
  onAddToHistory: AddToHistory;
}

interface UseGapFillResult {
  gapFillMode: boolean;
  setGapFillMode: Dispatch<SetStateAction<boolean>>;
  gapFillThreshold: number;
  setGapFillThreshold: Dispatch<SetStateAction<number>>;
  gapFillTool: string;
  setGapFillTool: Dispatch<SetStateAction<string>>;
  swipeBrushSize: number;
  setSwipeBrushSize: Dispatch<SetStateAction<number>>;
  highlightColor: string;
  setHighlightColor: Dispatch<SetStateAction<string>>;
  currentGaps: GapFillRegion[];
  setCurrentGaps: Dispatch<SetStateAction<GapFillRegion[]>>;
  handleGapFillToggle: () => void;
  handleGapFillApplyAll: () => Promise<void>;
}

function useGapFill({
  layers,
  activeLayerId,
  currentPresetConfig,
  onLayerUpdate,
  onAddToHistory,
}: UseGapFillParams): UseGapFillResult {
  // State for the GapFill control panel.
  // Pointer interactions are handled in useCanvasInteractions.ts.
  const [gapFillMode, setGapFillMode] = useState(false);
  const [gapFillThreshold, setGapFillThreshold] = useState(30);
  const [gapFillTool, setGapFillTool] = useState('special');
  const [swipeBrushSize, setSwipeBrushSize] = useState(30);
  const [highlightColor, setHighlightColor] = useState('#FF0000');
  const [currentGaps, setCurrentGaps] = useState<GapFillRegion[]>([]);

  const handleGapFillToggle = useCallback(() => {
    if (!currentPresetConfig?.lockGapFillMode) {
      setGapFillMode((currentMode) => !currentMode);
    }
  }, [currentPresetConfig?.lockGapFillMode]);

  const handleGapFillApplyAll = useCallback(async () => {
    if (!activeLayerId || currentGaps.length === 0) return;

    const activeLayer = layers.find((layer) => layer.id === activeLayerId);
    if (!activeLayer) return;

    // Implementation of Paper Sec. 4.1.5:
    // commit every currently detected gap with its suggested color in one operation when the user presses Apply All.
    fillGapRegions(activeLayer.canvas, currentGaps);

    onLayerUpdate(activeLayerId, activeLayer.canvas);
    onAddToHistory([activeLayerId]);
  }, [activeLayerId, currentGaps, layers, onAddToHistory, onLayerUpdate]);

  return {
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
  };
}

export default useGapFill;
