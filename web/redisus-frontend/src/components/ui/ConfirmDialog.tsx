import { AlertTriangle } from 'lucide-react';

import { Button } from './Button';
import { Modal } from './Modal';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onClose: () => void;
}

export function ConfirmDialog({ open, title, description, confirmLabel = 'Confirmar', onConfirm, onClose }: ConfirmDialogProps) {
  return (
    <Modal open={open} title={title} onClose={onClose}>
      <div className="flex gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-red-50 text-heal-danger">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <p className="text-sm leading-6 text-heal-muted dark:text-zinc-400">{description}</p>
      </div>
      <div className="mt-6 flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cancelar
        </Button>
        <Button
          type="button"
          variant="danger"
          onClick={() => {
            onConfirm();
            onClose();
          }}
        >
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
