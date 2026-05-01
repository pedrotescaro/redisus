import { useMemo, useRef, useState } from 'react';

import { createRoi, hasValidRois, normalizeRois } from '../../lib/roi';
import type { Roi, RoiPoint, RoiType } from '../../lib/types';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Modal } from '../ui/Modal';
import { RoiImageOverlay } from './RoiImageOverlay';
import { RoiToolbar } from './RoiToolbar';

interface RoiEditorProps {
  open: boolean;
  imageUrl: string;
  initialRois: Roi[];
  onClose: () => void;
  onSave: (rois: Roi[]) => void;
}

function pointFromEvent(event: React.PointerEvent<HTMLElement>, element: HTMLElement): RoiPoint {
  const rect = element.getBoundingClientRect();
  return {
    x: Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1),
    y: Math.min(Math.max((event.clientY - rect.top) / rect.height, 0), 1)
  };
}

export function RoiEditor({ open, imageUrl, initialRois, onClose, onSave }: RoiEditorProps) {
  const [draftRois, setDraftRois] = useState<Roi[]>(() => normalizeRois(initialRois));
  const [selectedId, setSelectedId] = useState<string>('');
  const [mode, setMode] = useState<RoiType>('polygon');
  const [isDrawing, setIsDrawing] = useState(false);
  const stageRef = useRef<HTMLDivElement>(null);

  const rois = useMemo(() => {
    const normalized = normalizeRois(draftRois);
    return normalized.length ? normalized : [createRoi(0, mode)];
  }, [draftRois, mode]);
  const selectedRoi = rois.find(roi => roi.id === selectedId) || rois[0];

  const commitRois = (updater: (current: Roi[]) => Roi[]) => {
    setDraftRois(current => updater(normalizeRois(current).length ? normalizeRois(current) : rois));
  };

  const addPoint = (event: React.PointerEvent<HTMLDivElement>) => {
    const element = stageRef.current;
    if (!element || !selectedRoi) return;
    const point = pointFromEvent(event, element);

    commitRois(current =>
      current.map(roi => (roi.id === selectedRoi.id ? { ...roi, type: mode, points: [...roi.points, point] } : roi))
    );
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (mode === 'freehand') setIsDrawing(true);
    addPoint(event);
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (mode !== 'freehand' || !isDrawing) return;
    addPoint(event);
  };

  const stopDrawing = () => setIsDrawing(false);

  const addRoi = () => {
    const next = createRoi(rois.length, mode);
    setDraftRois([...rois, next]);
    setSelectedId(next.id);
  };

  const undoPoint = () => {
    commitRois(current =>
      current.map(roi => (roi.id === selectedRoi.id ? { ...roi, points: roi.points.slice(0, -1) } : roi))
    );
  };

  const removeRoi = () => {
    const next = rois.filter(roi => roi.id !== selectedRoi.id);
    const fallback = next.length ? next : [createRoi(0, mode)];
    setDraftRois(fallback);
    setSelectedId(fallback[0].id);
  };

  const renameRoi = (id: string, label: string) => {
    commitRois(current => current.map(roi => (roi.id === id ? { ...roi, label } : roi)));
  };

  const canSave = hasValidRois(rois);

  return (
    <Modal open={open} title="Editor de ROI" onClose={onClose} maxWidth="max-w-5xl">
      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <div
          ref={stageRef}
          role="application"
          aria-label="Editor visual de ROI"
          className="relative aspect-[4/3] min-h-96 overflow-hidden rounded-lg border border-heal-line bg-slate-950"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={stopDrawing}
          onPointerLeave={stopDrawing}
        >
          <img src={imageUrl} alt="Foto da ferida para delimitação de ROI" className="h-full w-full object-contain" draggable={false} />
          <RoiImageOverlay rois={rois} />
        </div>

        <aside className="space-y-4">
          <RoiToolbar mode={mode} setMode={setMode} addRoi={addRoi} undoPoint={undoPoint} removeRoi={removeRoi} />
          <div className="rounded-lg border border-heal-line bg-slate-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
            <p className="text-sm font-semibold text-heal-ink dark:text-white">ROIs</p>
            <div className="mt-3 space-y-2">
              {rois.map(roi => (
                <button
                  key={roi.id}
                  type="button"
                  className={`w-full rounded-lg border p-2 text-left transition ${
                    roi.id === selectedRoi.id
                      ? 'border-heal-blue bg-blue-50 dark:bg-blue-950/30'
                      : 'border-heal-line bg-white dark:border-zinc-800 dark:bg-zinc-950'
                  }`}
                  onClick={() => setSelectedId(roi.id)}
                >
                  <span className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: roi.color }} />
                    <span className="text-xs font-bold text-slate-700 dark:text-zinc-200">
                      {roi.label} - {roi.points.length} ponto(s)
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </div>
          {selectedRoi ? (
            <Input label="Nome da ROI" value={selectedRoi.label} onChange={event => renameRoi(selectedRoi.id, event.target.value)} />
          ) : null}
          <p className="text-xs leading-5 text-slate-500 dark:text-zinc-400">
            As coordenadas são salvas normalizadas entre 0 e 1, evitando dependência do tamanho da tela.
          </p>
          <div className="flex gap-2">
            <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="button" className="flex-1" disabled={!canSave} onClick={() => onSave(rois.filter(roi => roi.points.length >= 3))}>
              Salvar ROI
            </Button>
          </div>
        </aside>
      </div>
    </Modal>
  );
}
