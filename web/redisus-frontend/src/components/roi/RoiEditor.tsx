import { Plus, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { HEAL_ANALYZER_ROI_VERSION, buildHealAnalyzerRoiSelection, type HealAnalyzerRoiSelection } from '../../lib/heal-analyzer-roi';
import { createRoi, hasValidRois, normalizeRois } from '../../lib/roi';
import type { Roi } from '../../lib/types';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Modal } from '../ui/Modal';
import { WoundRoiCanvas } from './WoundRoiCanvas';

interface RoiEditorProps {
  open: boolean;
  imageUrl: string;
  initialRois: Roi[];
  onClose: () => void;
  onSave: (rois: Roi[]) => void;
}

const ROI_VERSION = '2026-05-contextual';

function createStableRoiId(index: number) {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `roi-${crypto.randomUUID()}`;
  }
  return `roi-${Date.now()}-${index}`;
}

function roiTool(roi: Roi): HealAnalyzerRoiSelection['tool'] {
  return roi.type === 'circle' ? 'circle' : roi.type === 'freehand' ? 'freehand' : 'polygon';
}

function roiToSelection(roi: Roi): HealAnalyzerRoiSelection {
  const selection = buildHealAnalyzerRoiSelection(roiTool(roi), roi.points, 1, 1);
  return {
    ...selection,
    version: roi.roiVersion || HEAL_ANALYZER_ROI_VERSION,
    confirmed: roi.points.length >= 3
  };
}

function selectionToRoi(selection: HealAnalyzerRoiSelection, index: number, previous?: Roi): Roi {
  const now = new Date().toISOString();
  return {
    id: previous?.id || createStableRoiId(index),
    label: previous?.label || `Ferida ${index + 1}`,
    type: selection.tool,
    points: selection.points,
    color: previous?.color || createRoi(index, selection.tool).color,
    createdAt: previous?.createdAt || now,
    updatedAt: now,
    normalized: true,
    roiVersion: ROI_VERSION
  };
}

export function RoiEditor({ open, imageUrl, initialRois, onClose, onSave }: RoiEditorProps) {
  const [draftRois, setDraftRois] = useState<Roi[]>(() => normalizeRois(initialRois));
  const [selectedId, setSelectedId] = useState<string>('');
  const [canvasKey, setCanvasKey] = useState(0);

  useEffect(() => {
    if (!open) return;
    const normalized = normalizeRois(initialRois);
    setDraftRois(normalized);
    setSelectedId(normalized[0]?.id || '');
    setCanvasKey(current => current + 1);
  }, [initialRois, open]);

  const selectedIndex = draftRois.findIndex(roi => roi.id === selectedId);
  const activeIndex = selectedIndex >= 0 ? selectedIndex : draftRois.length ? 0 : null;
  const activeRoi = activeIndex === null ? null : draftRois[activeIndex] || null;

  const savedSelections = useMemo(() => draftRois.map(roiToSelection), [draftRois]);
  const activeSelection = activeRoi ? roiToSelection(activeRoi) : null;
  const canSave = hasValidRois(draftRois);

  const addRoi = () => {
    const next = createRoi(draftRois.length);
    setDraftRois(current => [...current, next]);
    setSelectedId(next.id);
    setCanvasKey(current => current + 1);
  };

  const removeRoi = (id: string) => {
    const next = draftRois.filter(roi => roi.id !== id);
    setDraftRois(next);
    setSelectedId(next[0]?.id || '');
    setCanvasKey(current => current + 1);
  };

  const renameRoi = (id: string, label: string) => {
    setDraftRois(current => current.map(roi => (roi.id === id ? { ...roi, label, updatedAt: new Date().toISOString() } : roi)));
  };

  const handleConfirm = (selection: HealAnalyzerRoiSelection) => {
    setDraftRois(current => {
      const targetIndex = activeIndex ?? current.length;
      const nextRoi = selectionToRoi(selection, targetIndex, current[targetIndex]);
      if (!current[targetIndex]) {
        setSelectedId(nextRoi.id);
        return [...current, nextRoi];
      }
      return current.map((roi, index) => (index === targetIndex ? nextRoi : roi));
    });
  };

  const handleSelectionCleared = () => {
    if (!activeRoi) return;
    setDraftRois(current => current.map(roi => (roi.id === activeRoi.id ? { ...roi, points: [], updatedAt: new Date().toISOString() } : roi)));
  };

  const saveValidRois = () => {
    onSave(normalizeRois(draftRois).filter(roi => roi.points.length >= 3));
  };

  return (
    <Modal open={open} title="Editor de ROI" onClose={onClose} maxWidth="max-w-7xl">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <WoundRoiCanvas
          key={`${imageUrl}-${canvasKey}-${activeRoi?.id || 'new'}`}
          activeSavedSelectionIndex={activeIndex}
          confirmLabel={activeRoi?.points.length ? 'Atualizar ROI' : 'Salvar ROI'}
          imageSrc={imageUrl}
          initialSelection={activeSelection}
          savedSelections={savedSelections}
          onConfirm={handleConfirm}
          onSelectionCleared={handleSelectionCleared}
        />

        <aside className="space-y-4">
          <div className="rounded-2xl border border-heal-line bg-slate-50 p-3 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-heal-ink dark:text-white">ROIs</p>
                <p className="mt-1 text-xs text-heal-muted dark:text-zinc-400">Coordenadas normalizadas entre 0 e 1.</p>
              </div>
              <Button type="button" size="sm" variant="secondary" onClick={addRoi} aria-label="Nova ROI">
                <Plus className="h-4 w-4" />
              </Button>
            </div>

            <div className="mt-3 space-y-2">
              {draftRois.length ? (
                draftRois.map((roi, index) => (
                  <div
                    key={roi.id}
                    className={`rounded-xl border p-2 transition ${
                      roi.id === activeRoi?.id
                        ? 'border-heal-blue bg-blue-50 dark:bg-blue-950/30'
                        : 'border-heal-line bg-white dark:border-zinc-800 dark:bg-zinc-900'
                    }`}
                  >
                    <button type="button" className="w-full text-left" onClick={() => setSelectedId(roi.id)}>
                      <span className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: roi.color }} />
                        <span className="text-xs font-bold text-slate-700 dark:text-zinc-200">
                          {roi.label} - {roi.points.length} ponto(s)
                        </span>
                      </span>
                    </button>
                    <div className="mt-2 flex gap-2">
                      <Input value={roi.label} onChange={event => renameRoi(roi.id, event.target.value)} aria-label={`Nome da ROI ${index + 1}`} />
                      <Button type="button" variant="danger" size="sm" onClick={() => removeRoi(roi.id)} aria-label={`Excluir ROI ${index + 1}`}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <p className="rounded-xl border border-dashed border-heal-line bg-white px-3 py-4 text-center text-xs text-heal-muted dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
                  Desenhe e salve a primeira ROI na imagem.
                </p>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-50">
            Use uma ROI por ferida ou area clinicamente relevante. As coordenadas permanecem proporcionais a imagem e podem alimentar futuras mascaras supervisionadas.
          </div>

          <div className="flex gap-2">
            <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="button" className="flex-1" disabled={!canSave} onClick={saveValidRois}>
              Salvar ROI
            </Button>
          </div>
        </aside>
      </div>
    </Modal>
  );
}
