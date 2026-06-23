import React, { useRef } from 'react';
import type { ShortcutConfig } from '../types/shortcuts';
import './Toolbar.css';

interface ToolbarProps {
  activeTool: string;
  onToolChange: (toolId: string) => void;
  brushSize: number;
  onBrushSizeChange: (size: number) => void;
  brushColor: string;
  onBrushColorChange: (color: string) => void;
  previousColor: string;
  onRestorePreviousColor: () => void;
  blackLightMode: boolean;
  onBlackLightToggle: () => void;
  gapFillMode: boolean;
  overflowFillMode?: boolean;
  showEncloseAndFill?: boolean;
  showLeftoverPen?: boolean;
  showBucketTool?: boolean;
  showBlackLight?: boolean;
  shortcuts: ShortcutConfig;
}

interface Tool {
  id: string;
  name: string;
  icon: string;
}

const tools: Tool[] = [
  { id: 'move', name: 'Move', icon: '✋' },
  { id: 'zoom', name: 'Zoom', icon: '🔍' },
  { id: 'colorpicker', name: 'Color Picker', icon: '💉' },
  { id: 'fill', name: 'Paint Bucket', icon: '🪣' },
  { id: 'dot-pen', name: 'Dot Pen', icon: '✏️' },
  { id: 'eraser', name: 'Eraser', icon: '💧' },
  { id: 'separator', name: '', icon: '|' },
  { id: 'enclose-and-fill', name: 'Enclose and Fill', icon: '➰' },
  { id: 'leftover-pen', name: 'Leftover Pen', icon: '🖌️' },
];

const Toolbar: React.FC<ToolbarProps> = ({
  activeTool,
  onToolChange,
  brushSize,
  onBrushSizeChange,
  brushColor,
  onBrushColorChange,
  previousColor,
  onRestorePreviousColor,
  blackLightMode,
  onBlackLightToggle,
  gapFillMode,
  overflowFillMode = false,
  showEncloseAndFill = true,
  showLeftoverPen = true,
  showBucketTool = true,
  showBlackLight = true,
  shortcuts
}) => {
  const colorInputRef = useRef<HTMLInputElement>(null);
  
  const handleColorClick = () => {
    if (brushColor === 'transparent') {
      // If transparent is selected, restore the previous color
      onRestorePreviousColor();
    } else {
      // If a color is already selected, open the color picker
      colorInputRef.current?.click();
    }
  };

  // Implementation of Paper Sec. 5.1 Methodology:
  // this toolbar hosts the conventional paint-software tools used alongside GapFill,
  // including Paint Bucket, Dot Pen, Eraser, Enclose and Fill, Leftover Pen, and Black Light.
  return (
    <div className="toolbar">
      <div className="tool-buttons">
        {tools.map(tool => {
          if (tool.id === 'separator') {
            return <div key={tool.id} className="tool-separator">|</div>;
          }
          
          // Hide tools based on preset configuration
          if (tool.id === 'enclose-and-fill' && !showEncloseAndFill) {
            return null;
          }
          if (tool.id === 'leftover-pen' && !showLeftoverPen) {
            return null;
          }
          if (tool.id === 'fill' && !showBucketTool) {
            return null;
          }
          
          const toolId = tool.id;
          const toolsDisabled = gapFillMode || overflowFillMode;
          const isOverflowBucket = overflowFillMode && toolId === 'fill';
          return (
            <div key={tool.id} className="tool-button-wrapper">
              <button
                className={`tool-button ${(activeTool === toolId || isOverflowBucket) ? 'active' : ''} ${toolsDisabled ? 'disabled' : ''}`}
                onClick={() => !toolsDisabled && onToolChange(toolId)}
                title={
                  gapFillMode
                    ? 'Disabled in GapFill Mode'
                    : overflowFillMode
                      ? 'Paint Bucket is fixed in Overflow Fill'
                      : tool.name
                }
                disabled={toolsDisabled}
              >
                <span className="tool-icon">{tool.icon}</span>
              </button>
              {shortcuts[tool.id] && (
                <span className="tool-shortcut">{shortcuts[tool.id]}</span>
              )}
            </div>
          );
        })}
      </div>
      
      <div className={`tool-settings ${gapFillMode ? 'disabled' : ''}`}>
        <div className="setting-group">
          <label>Size:</label>
          <input
            type="range"
            min="1"
            max="50"
            value={brushSize}
            onChange={(e) => onBrushSizeChange(Number(e.target.value))}
            disabled={gapFillMode}
          />
          <span>{brushSize}px</span>
        </div>
        
        <div className="setting-group">
          <label>Color:</label>
          <div className="color-controls">
            <div 
              className="color-display"
              onClick={handleColorClick}
              style={{ 
                backgroundColor: brushColor === 'transparent' ? previousColor : brushColor,
                border: brushColor !== 'transparent' ? '2px solid #4CAF50' : '2px solid #ccc',
                backgroundImage: 'none'
              }}
              title={`Current color: ${brushColor === 'transparent' ? 'Transparent' : brushColor}. Click to ${brushColor === 'transparent' ? 'restore previous color' : 'open color picker'}.`}
            />
            <input
              ref={colorInputRef}
              type="color"
              value={brushColor === 'transparent' ? previousColor : brushColor}
              onChange={(e) => onBrushColorChange(e.target.value)}
              disabled={gapFillMode}
              style={{ 
                position: 'absolute',
                visibility: 'hidden',
                width: '1px',
                height: '1px',
                top: '40px',
                left: '0'
              }}
            />
            <button
              className={`transparent-button ${brushColor === 'transparent' ? 'active' : ''}`}
              onClick={() => {
                if (brushColor === 'transparent') {
                  onRestorePreviousColor();
                } else {
                  onBrushColorChange('transparent');
                }
              }}
              title={brushColor === 'transparent' ? 'Restore previous color' : 'Transparent (Eraser)'}
              disabled={gapFillMode}
            >
            </button>
          </div>
        </div>
        
        {showBlackLight && (
          <div className="switch-container">
            <label className="switch-label">
              Black Light
              <span className="shortcut-hint">({(shortcuts.blackLight && shortcuts.blackLight[0]) ? shortcuts.blackLight[0] : 'Ctrl+B'})</span>
            </label>
            <button
              className={`horizontal-switch ${blackLightMode ? 'active' : ''}`}
              onClick={onBlackLightToggle}
              title={`Black Light Mode (${(shortcuts.blackLight && shortcuts.blackLight[0]) ? shortcuts.blackLight[0] : 'Ctrl+B'})`}
              disabled={gapFillMode || overflowFillMode}
            >
              <div className="switch-track">
                <div className="switch-thumb"></div>
              </div>
              <span className="switch-text">{blackLightMode ? 'ON' : 'OFF'}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default Toolbar;
