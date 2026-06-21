interface DescriptionDialogProps {
  isOpen: boolean;
  description?: string;
  onClose: () => void;
}

function DescriptionDialog({ isOpen, description, onClose }: DescriptionDialogProps) {
  if (!isOpen) {
    return null;
  }

  // Implementation of Paper Sec. 5.1 Methodology:
  // each preset can expose its task instructions through this lightweight dialog.
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content description-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>💬 Task Description</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {description ? (
            <p className="description-text">{description}</p>
          ) : (
            <p className="description-text">No description available for this task.</p>
          )}
        </div>
        <div className="modal-footer">
          <button className="modal-button" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default DescriptionDialog;
