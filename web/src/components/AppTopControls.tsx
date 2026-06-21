import type { ChangeEvent, RefObject } from 'react';
import PresetSelector from './PresetSelector';
import type { ImagePreset } from '../config/presets';
import type { ShortcutConfig } from '../types/shortcuts';

interface AppTopControlsProps {
  selectedPreset: string;
  onPresetChange: (preset: ImagePreset) => void;
  onImageLoad: () => void;
  onGuidesLoad: () => void;
  onColoringLoad: () => void;
  onUndo: () => Promise<void> | void;
  onRedo: () => Promise<void> | void;
  historyIndex: number;
  historyLength: number;
  shortcuts: ShortcutConfig;
  fileInputRef: RefObject<HTMLInputElement | null>;
  guidesInputRef: RefObject<HTMLInputElement | null>;
  coloringInputRef: RefObject<HTMLInputElement | null>;
  referenceInputRef: RefObject<HTMLInputElement | null>;
  onImageFileSelect: (e: ChangeEvent<HTMLInputElement>) => void;
  onGuidesFileSelect: (e: ChangeEvent<HTMLInputElement>) => void;
  onColoringFileSelect: (e: ChangeEvent<HTMLInputElement>) => void;
  onReferenceImageSelect: (e: ChangeEvent<HTMLInputElement>) => void;
  timeRemaining: number | null;
  onOpenDescription: () => void;
  isStarted: boolean;
  isDone: boolean;
  onStart: () => void;
  onDone: () => void;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function AppTopControls({
  selectedPreset,
  onPresetChange,
  onImageLoad,
  onGuidesLoad,
  onColoringLoad,
  onUndo,
  onRedo,
  historyIndex,
  historyLength,
  shortcuts,
  fileInputRef,
  guidesInputRef,
  coloringInputRef,
  referenceInputRef,
  onImageFileSelect,
  onGuidesFileSelect,
  onColoringFileSelect,
  onReferenceImageSelect,
  timeRemaining,
  onOpenDescription,
  isStarted,
  isDone,
  onStart,
  onDone,
}: AppTopControlsProps) {
  return (
    <div className="top-controls">
      {/* Implementation of Paper Sec. 4.1 User Interface / Sec. 5.1 Methodology:
          preset switching and study asset loading live in the top-left group. */}
      <div className="left-controls">
        <PresetSelector
          selectedPreset={selectedPreset}
          onPresetChange={onPresetChange}
        />
        {selectedPreset === 'debug' ? (
          <div className="debug-file-controls">
            <button onClick={onImageLoad} className="control-button">
              📁 Load Line Art
            </button>
            <button onClick={onGuidesLoad} className="control-button">
              🗺️ Load Guides
            </button>
            <button onClick={onColoringLoad} className="control-button">
              🎨 Load Coloring
            </button>
            <button className="control-button" disabled>
              💾 Save Image
            </button>
          </div>
        ) : (
          <button className="control-button" disabled>
            💾 Save Image
          </button>
        )}
      </div>

      {/* Implementation of Paper Sec. 4.1 User Interface:
          undo/redo are exposed as persistent central controls. */}
      <div className="center-controls">
        <div className="history-controls">
          <div className="history-button-wrapper">
            <button
              onClick={onUndo}
              disabled={historyIndex <= 0}
              className="history-button"
              title={`Undo (${shortcuts.undo})`}
            >
              <span className="history-arrow">←</span>
              <span className="history-label">Undo</span>
            </button>
            <span className="shortcut-label">{shortcuts.undo}</span>
          </div>
          <div className="history-button-wrapper">
            <button
              onClick={onRedo}
              disabled={historyIndex >= historyLength - 1}
              className="history-button"
              title={`Redo (${shortcuts.redo})`}
            >
              <span className="history-arrow">→</span>
              <span className="history-label">Redo</span>
            </button>
            <span className="shortcut-label">{shortcuts.redo}</span>
          </div>
        </div>
      </div>

      <div className="file-controls">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={onImageFileSelect}
          style={{ display: 'none' }}
        />
        <input
          ref={guidesInputRef}
          type="file"
          accept="image/*"
          onChange={onGuidesFileSelect}
          style={{ display: 'none' }}
        />
        <input
          ref={coloringInputRef}
          type="file"
          accept="image/*"
          onChange={onColoringFileSelect}
          style={{ display: 'none' }}
        />
      </div>

      {/* Implementation of Paper Sec. 5.1 Methodology:
          timer, task description, reference image access, and Start/Done are the
          task-management controls that turn the app into the study paint software. */}
      <div className="reference-image-control">
        {selectedPreset !== 'debug' && timeRemaining !== null && (
          <div className="timer-display">
            ⏱️ {formatTime(timeRemaining)}
          </div>
        )}
        <button
          className="control-button info-button"
          onClick={onOpenDescription}
          title="Task Description"
        >
          💬 Description
        </button>

        {selectedPreset === 'debug' && (
          <button
            onClick={() => referenceInputRef.current?.click()}
            className="control-button"
          >
            🖼️ Reference Image
          </button>
        )}

        {selectedPreset !== 'debug' && (
          <div className="non-debug-buttons">
            <button
              onClick={onStart}
              className={`control-button start-button ${isStarted ? 'started' : ''}`}
              disabled={isStarted}
            >
              ▶️ Start
            </button>
            <button
              onClick={onDone}
              className={`control-button done-button ${isDone ? 'done' : ''}`}
              disabled={!isStarted || isDone}
            >
              ✅ Done!
            </button>
          </div>
        )}
        <input
          ref={referenceInputRef}
          type="file"
          accept="image/*"
          onChange={onReferenceImageSelect}
          style={{ display: 'none' }}
        />
      </div>
    </div>
  );
}

export default AppTopControls;
