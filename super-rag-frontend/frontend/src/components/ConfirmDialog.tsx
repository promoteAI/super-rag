import { createPortal } from 'react-dom';
import './ConfirmDialog.css';

interface ConfirmDialogProps {
  open: boolean;
  title?: string;
  description?: string;
  cancelText?: string;
  confirmText?: string;
  loading?: boolean;
  loadingText?: string;
  onCancel: () => void;
  onConfirm: () => void;
}

export default function ConfirmDialog({
  open,
  title = 'Are you absolutely sure?',
  description = 'This action cannot be undone. This will permanently delete collection and remove your documents from our servers.',
  cancelText = 'Cancel',
  confirmText = 'Continue',
  loading = false,
  loadingText = 'Deleting...',
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  if (!open) return null;

  return createPortal(
    <div className="confirm-dialog-backdrop" onMouseDown={onCancel}>
      <div className="confirm-dialog" onMouseDown={(e) => e.stopPropagation()}>
        <h2 className="confirm-dialog-title">{title}</h2>
        <p className="confirm-dialog-description">{description}</p>
        <div className="confirm-dialog-actions">
          <button
            type="button"
            className="confirm-dialog-btn cancel"
            onClick={onCancel}
            disabled={loading}
          >
            {cancelText}
          </button>
          <button
            type="button"
            className="confirm-dialog-btn danger"
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? loadingText : confirmText}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
