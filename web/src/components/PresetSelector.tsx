import React from 'react';
import type { ImagePreset } from '../config/presets';
import { IMAGE_PRESETS } from '../config/presets';
import './PresetSelector.css';

interface PresetSelectorProps {
  selectedPreset: string;
  onPresetChange: (preset: ImagePreset) => void;
}

const PresetSelector: React.FC<PresetSelectorProps> = ({ selectedPreset, onPresetChange }) => {
  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const preset = IMAGE_PRESETS.find(p => p.id === e.target.value);
    if (preset) {
      onPresetChange(preset);
    }
  };

  // Helper function to determine if we should add a separator before this preset
  const shouldAddSeparator = (currentPreset: ImagePreset, index: number): boolean => {
    if (index === 0) return false;
    
    const prevPreset = IMAGE_PRESETS[index - 1];
    
    // Extract category from preset names
    const getCategory = (name: string): string => {
      if (name.includes('[Practice]')) return 'Practice';
      if (name.includes('[Task A]')) return 'Task A';
      if (name.includes('[Task B-1]')) return 'Task B-1';
      if (name.includes('[Task B-2]')) return 'Task B-2';
      if (name.includes('[Task C')) return 'Task C';
      return 'Other';
    };
    
    const prevCategory = getCategory(prevPreset.name);
    const currentCategory = getCategory(currentPreset.name);
    
    return prevCategory !== currentCategory;
  };

  return (
    <div className="preset-selector">
      <select 
        value={selectedPreset} 
        onChange={handleChange}
        className="preset-dropdown"
      >
        {IMAGE_PRESETS.map((preset, index) => (
          <React.Fragment key={preset.id}>
            {shouldAddSeparator(preset, index) && (
              <option disabled className="preset-separator">
                ──────────────
              </option>
            )}
            <option value={preset.id}>
              {preset.name}
            </option>
          </React.Fragment>
        ))}
      </select>
    </div>
  );
};

export default PresetSelector;