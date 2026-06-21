import React from 'react';
import type { Layer } from '../types';
import './LayerPanel.css';

interface LayerPanelProps {
  layers: Layer[];
  activeLayerId: string | null;
  onLayerToggleVisibility: (layerId: string) => void;
  fillMultiLayer: boolean;
  onFillMultiLayerChange: (value: boolean) => void;
}

const LayerPanel: React.FC<LayerPanelProps> = ({
  layers,
  activeLayerId,
  onLayerToggleVisibility,
  fillMultiLayer,
  onFillMultiLayerChange
}) => {
  return (
    <div className="layer-panel">
      {/* Implementation of Paper Sec. 5.1 Methodology:
          the study paint software exposes the layer stack and the
          "Reference Other Layers" option from this panel. */}
      {/* Reference other layers control */}
      <div className="reference-layers-control" style={{ marginBottom: '15px', padding: '8px' }}>
        <label className="checkbox-label" style={{ fontSize: '16px', fontWeight: 'bold', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={fillMultiLayer}
            onChange={(e) => onFillMultiLayerChange(e.target.checked)}
            style={{ marginRight: '8px', transform: 'scale(1.2)' }}
          />
          Reference Other Layers
        </label>
      </div>
      
      <div className="layer-panel-header">
        <h3>Layers</h3>
        {/* Layer add/delete/reorder functions disabled for user testing */}
        <button 
          className="add-layer-button" 
          disabled={true}
          style={{ opacity: 0.5, cursor: 'not-allowed' }}
        >
          + Add Layer
        </button>
      </div>
      
      <div className="layer-list">
        {[...layers]
          .sort((a, b) => b.order - a.order)
          .map((layer) => (
            <div
              key={layer.id}
              className={`layer-item ${layer.id === activeLayerId ? 'active' : ''}`}
              // Layer selection disabled for user testing
              style={{ cursor: 'not-allowed' }}
            >
              <button
                className="layer-visibility"
                onClick={(e) => {
                  e.stopPropagation();
                  onLayerToggleVisibility(layer.id);
                }}
              >
                {layer.visible ? '👁️' : '👁️‍🗨️'}
              </button>
              
              <span className="layer-name">{layer.name}</span>
              
              <div className="layer-controls">
                {/* Layer reorder/delete buttons disabled for user testing */}
                <button
                  className="layer-control"
                  disabled={true}
                  style={{ opacity: 0.5, cursor: 'not-allowed' }}
                >
                  ↑
                </button>
                <button
                  className="layer-control"
                  disabled={true}
                  style={{ opacity: 0.5, cursor: 'not-allowed' }}
                >
                  ↓
                </button>
                <button
                  className="layer-control delete"
                  disabled={true}
                  style={{ opacity: 0.5, cursor: 'not-allowed' }}
                >
                  🗑️
                </button>
              </div>
            </div>
          ))}
      </div>
    </div>
  );
};

export default LayerPanel;
