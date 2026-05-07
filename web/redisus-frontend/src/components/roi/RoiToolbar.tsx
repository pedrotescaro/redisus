import { Brush, MousePointer2, Plus, Trash2, Undo2 } from 'lucide-react';

import type { RoiType } from '../../lib/types';
import { Button } from '../ui/button';

interface RoiToolbarProps {
  mode: RoiType;
  setMode: (mode: RoiType) => void;
  addRoi: () => void;
  undoPoint: () => void;
  removeRoi: () => void;
}

export function RoiToolbar({ mode, setMode, addRoi, undoPoint, removeRoi }: RoiToolbarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        type="button"
        variant={mode === 'polygon' ? 'primary' : 'secondary'}
        icon={<MousePointer2 className="h-4 w-4" />}
        onClick={() => setMode('polygon')}
      >
        Pontos
      </Button>
      <Button
        type="button"
        variant={mode === 'freehand' ? 'primary' : 'secondary'}
        icon={<Brush className="h-4 w-4" />}
        onClick={() => setMode('freehand')}
      >
        Caneta fina
      </Button>
      <Button type="button" variant="secondary" icon={<Plus className="h-4 w-4" />} onClick={addRoi}>
        Nova ROI
      </Button>
      <Button type="button" variant="secondary" icon={<Undo2 className="h-4 w-4" />} onClick={undoPoint}>
        Desfazer ponto
      </Button>
      <Button type="button" variant="danger" icon={<Trash2 className="h-4 w-4" />} onClick={removeRoi}>
        Excluir ROI
      </Button>
    </div>
  );
}
