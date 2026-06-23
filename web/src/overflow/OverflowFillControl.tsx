import './OverflowFillControl.css';

interface OverflowFillControlProps {
  enabled: boolean;
  onToggle: () => void;
  likelihoodThreshold: number;
  onLikelihoodThresholdChange: (value: number) => void;
  status: string;
  linkedGapCount: number;
  propagationSuppressed: boolean;
}

function OverflowFillControl({
  enabled,
  onToggle,
  likelihoodThreshold,
  onLikelihoodThresholdChange,
  status,
  linkedGapCount,
  propagationSuppressed,
}: OverflowFillControlProps) {
  return (
    <div className="overflow-control">
      <div className="overflow-toggle-container">
        <label className="overflow-toggle-label">
          Overflow Fill
        </label>
        <button
          className={`overflow-toggle ${enabled ? 'active' : ''}`}
          onClick={onToggle}
          title="Bucket-fill a large owner region and propagate the same color to linked small gaps."
        >
          <span className="toggle-slider" />
          <span className="toggle-text">
            {enabled ? 'ON' : 'OFF'}
          </span>
        </button>
      </div>

      {enabled && (
        <div className="overflow-settings">
          <div className="overflow-threshold-control">
            <label>Owner Likelihood:</label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={likelihoodThreshold}
              onChange={(event) =>
                onLikelihoodThresholdChange(Number(event.target.value))
              }
            />
            <span>{Math.round(likelihoodThreshold * 100)}%</span>
          </div>

          <div className="overflow-status">
            {status}
          </div>

          <div className="overflow-hint">
            {linkedGapCount} linked gaps above threshold
          </div>

          {propagationSuppressed && (
            <div className="overflow-warning">
              Undo retry: propagation off
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default OverflowFillControl;
