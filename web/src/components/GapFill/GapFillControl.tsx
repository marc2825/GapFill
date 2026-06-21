import React, { useState } from 'react';
import './GapFillControl.css';

interface GapFillControlProps {
  gapFillMode: boolean;
  onGapFillToggle: () => void;
  gapFillThreshold: number;
  onThresholdChange: (value: number) => void;
  onApplyAll: () => Promise<void> | void;
  gapCount: number;
  gapFillTool: string;
  onGapFillToolChange: (tool: string) => void;
  swipeBrushSize: number;
  onSwipeBrushSizeChange: (size: number) => void;
  highlightColor: string;
  onHighlightColorChange: (color: string) => void;
  isLocked?: boolean;
  enableGapThreshold?: boolean;
  enableHighlightColor?: boolean;
}

const GapFillControl: React.FC<GapFillControlProps> = ({
  gapFillMode,
  onGapFillToggle,
  gapFillThreshold,
  onThresholdChange,
  onApplyAll,
  gapCount,
  gapFillTool,
  onGapFillToolChange,
  swipeBrushSize,
  onSwipeBrushSizeChange,
  highlightColor,
  onHighlightColorChange,
  isLocked = false,
  enableGapThreshold = true,
  enableHighlightColor = true
}) => {
  const [isApplyingAll, setIsApplyingAll] = useState(false);

  // Implementation of Paper Sec. 4.1: the on-demand toggle activates the GapFill interface.
  return (
    <div className="gapfill-control">
      <div className="gapfill-toggle-container">
        <label className="gapfill-toggle-label">
          GapFill Mode
        </label>
        <button
          className={`gapfill-toggle ${gapFillMode ? 'active' : ''} ${isLocked ? 'locked' : ''}`}
          onClick={onGapFillToggle}
          disabled={isLocked}
          title={isLocked ? 'Gap Fill Mode is locked for this preset' : ''}
        >
          <span className="toggle-slider" />
          <span className="toggle-text">
            {gapFillMode ? 'ON' : 'OFF'}
          </span>
        </button>
      </div>
      
      {gapFillMode && (
        <div className="gapfill-settings">
          {/* Implementation of Paper Sec. 4.1.1: user-adjustable maximum gap threshold (pixel count). */}
          {enableGapThreshold && (
            <div className="threshold-control">
              <label>Gap Threshold:</label>
              <input
                type="range"
                min="1"
                max="50"
                value={gapFillThreshold}
                onChange={(e) => onThresholdChange(Number(e.target.value))}
              />
              <span>{gapFillThreshold} pixels</span>
            </div>
          )}

          <div className="gapfill-tools">
            <label>Tools:</label>
            <div className="gapfill-tool-rows">
              <div className="gapfill-tool-buttons-row">
                <button
                  className={`gapfill-tool-button ${gapFillTool === 'move' ? 'active' : ''}`}
                  onClick={() => onGapFillToolChange('move')}
                  title="Move Tool"
                >
                  ✋
                </button>
                <button
                  className={`gapfill-tool-button ${gapFillTool === 'zoom' ? 'active' : ''}`}
                  onClick={() => onGapFillToolChange('zoom')}
                  title="Zoom Tool"
                >
                  🔍
                </button>
              </div>
              <div className="gapfill-tool-buttons-row">
                <button
                  className={`gapfill-tool-button special ${gapFillTool === 'special' ? 'active' : ''}`}
                  onClick={() => onGapFillToolChange('special')}
                  title="GapFill Tool"
                >
                  🔧
                </button>
              </div>
            </div>
          </div>

          {/* Implementation of Paper Sec. 4.1.5: width of the translucent sweep selection stroke. */}
          <div className="swipe-size-control">
            <label>Swipe Size:</label>
            <input
              type="range"
              min="10"
              max="100"
              value={swipeBrushSize}
              onChange={(e) => onSwipeBrushSizeChange(Number(e.target.value))}
            />
            <span>{swipeBrushSize}px</span>
          </div>

          {enableHighlightColor && (
            <div className="highlight-color-control">
              <label>Highlight Color:</label>
              <input
                type="color"
                value={highlightColor}
                onChange={(e) => onHighlightColorChange(e.target.value)}
                style={{ 
                  position: 'relative',
                  zIndex: 1000,
                  marginLeft: '5px'
                }}
              />
            </div>
          )}

          {/* Implementation of Paper Sec. 4.1.5: one-click application of all suggestions. */}
          <button
            className={`apply-all-button ${gapCount === 0 || isApplyingAll ? 'disabled' : ''}`}
            onClick={async () => {
              if (gapCount === 0 || isApplyingAll) return;

              setIsApplyingAll(true);
              try {
                await onApplyAll();
              } finally {
                setIsApplyingAll(false);
              }
            }}
            disabled={gapCount === 0 || isApplyingAll}
          >
            {isApplyingAll ? 'Applying...' : 'Apply All'}
          </button>

          <div className="gapfill-hint">
            Ctrl+B: Hide circle display
          </div>
        </div>
      )}
    </div>
  );
};

export default GapFillControl;
