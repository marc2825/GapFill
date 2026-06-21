import GapFillControl from './GapFillControl';
import type { ImagePreset } from '../../config/presets';

interface GapFillPanelProps {
  selectedPreset: string;
  currentPresetConfig: ImagePreset | null;
  gapFillMode: boolean;
  onGapFillToggle: () => void;
  gapFillThreshold: number;
  onGapFillThresholdChange: (threshold: number) => void;
  onGapFillApplyAll: () => Promise<void> | void;
  gapCount: number;
  gapFillTool: string;
  onGapFillToolChange: (tool: string) => void;
  swipeBrushSize: number;
  onSwipeBrushSizeChange: (size: number) => void;
  highlightColor: string;
  onHighlightColorChange: (color: string) => void;
}

function GapFillPanel({
  selectedPreset,
  currentPresetConfig,
  gapFillMode,
  onGapFillToggle,
  gapFillThreshold,
  onGapFillThresholdChange,
  onGapFillApplyAll,
  gapCount,
  gapFillTool,
  onGapFillToolChange,
  swipeBrushSize,
  onSwipeBrushSizeChange,
  highlightColor,
  onHighlightColorChange,
}: GapFillPanelProps) {
  if (currentPresetConfig?.enableGapFillMode === false) {
    return null;
  }

  // Implementation of Paper Sec. 4.1 User Interface:
  // GapFillControl renders the actual controls;
  // this panel decides whether they should be shown for the active preset.
  return (
    <GapFillControl
      key={`gapfill-${selectedPreset}`}
      gapFillMode={gapFillMode}
      onGapFillToggle={onGapFillToggle}
      gapFillThreshold={gapFillThreshold}
      onThresholdChange={onGapFillThresholdChange}
      onApplyAll={onGapFillApplyAll}
      gapCount={gapCount}
      gapFillTool={gapFillTool}
      onGapFillToolChange={onGapFillToolChange}
      swipeBrushSize={swipeBrushSize}
      onSwipeBrushSizeChange={onSwipeBrushSizeChange}
      highlightColor={highlightColor}
      onHighlightColorChange={onHighlightColorChange}
      isLocked={currentPresetConfig?.lockGapFillMode}
      enableGapThreshold={currentPresetConfig?.enableGapThreshold}
      enableHighlightColor={currentPresetConfig?.enableHighlightColor}
    />
  );
}

export default GapFillPanel;
