/* eslint-disable @next/next/no-img-element */
import type { ChangeEvent, ReactNode, RefObject } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  AlertTriangle,
  BadgeCheck,
  CheckCircle2,
  ClipboardList,
  FileImage,
  History,
  ImagePlus,
  Info,
  LoaderCircle,
  RefreshCcw,
  Save,
  ScanSearch,
  ShieldAlert,
  Sparkles,
  Target,
  Trash2,
  UserRound
} from 'lucide-react';

import { useAuth } from '../../app/providers/AuthProvider';
import { WoundRoiCanvas } from '../roi/WoundRoiCanvas';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/button';
import { Card } from '../ui/Card';
import { Input } from '../ui/input';
import { Modal } from '../ui/Modal';
import { PageHeader } from '../ui/PageHeader';
import { formatDate } from '../../lib/date';
import type { ClinicalAnalysisAlert, ClinicalAnalysisResult, Evaluation, Patient, Roi } from '../../lib/types';
import { cn } from '../../lib/utils';
import { buildClinicalAnalysisResult } from '../../services/heal-analyzer/woundAnalysisService';
import {
  loadClinicalAnalysisContext,
  saveAssessmentImageRois,
  saveClinicalAnalysisResult,
  type ClinicalAnalysisContext
} from '../../services/heal-analyzer/clinicalContextService';
import { analyzerSelectionToRoi, ensureClinicalRois, roisToAnalyzerSelections } from '../../services/heal-analyzer/roiProcessingService';

type MobilePanel = 'context' | 'roi' | 'result';

const emptyContext: ClinicalAnalysisContext = {
  patient: null,
  assessment: null,
  history: [],
  mode: 'standalone'
};

function firstAssessmentImage(assessment: Evaluation | null) {
  return assessment?.images?.[0] || null;
}

function getAge(birthDate?: string) {
  if (!birthDate) return null;
  const birth = new Date(birthDate);
  if (Number.isNaN(birth.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const monthDelta = today.getMonth() - birth.getMonth();
  if (monthDelta < 0 || (monthDelta === 0 && today.getDate() < birth.getDate())) age -= 1;
  return age >= 0 && age < 130 ? age : null;
}

function resultStatusLabel(result: ClinicalAnalysisResult | null, hasImage: boolean, hasRoi: boolean, loading: boolean, linked: boolean) {
  if (loading) return { label: 'Processando', tone: 'border-sky-200 bg-sky-50 text-sky-700' };
  if (result && !result.canAnalyze) return { label: 'Analise bloqueada', tone: 'border-amber-200 bg-amber-50 text-amber-800' };
  if (result) return { label: 'Analise limitada', tone: 'border-emerald-200 bg-emerald-50 text-emerald-700' };
  if (!hasImage) return { label: 'Aguardando imagem', tone: 'border-slate-200 bg-slate-50 text-slate-600' };
  if (!hasRoi) return { label: 'ROI pendente', tone: 'border-amber-200 bg-amber-50 text-amber-700' };
  if (linked) return { label: 'Avaliacao vinculada', tone: 'border-blue-200 bg-blue-50 text-blue-700' };
  return { label: 'Pronto para analise', tone: 'border-teal-200 bg-teal-50 text-teal-700' };
}

export function AnalyzerWorkbench() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const roiFeedbackTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [activeMobilePanel, setActiveMobilePanel] = useState<MobilePanel>('context');
  const [context, setContext] = useState<ClinicalAnalysisContext>(emptyContext);
  const [contextLoading, setContextLoading] = useState(false);
  const [patientIdInput, setPatientIdInput] = useState(searchParams.get('patientId') || '');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [linkedImageId, setLinkedImageId] = useState('');
  const [rois, setRois] = useState<Roi[]>([]);
  const [editingRoiIndex, setEditingRoiIndex] = useState<number | null>(null);
  const [roiEditorKey, setRoiEditorKey] = useState(0);
  const [roiFeedback, setRoiFeedback] = useState('');
  const [analysis, setAnalysis] = useState<ClinicalAnalysisResult | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const queryPatientId = searchParams.get('patientId') || '';
  const queryAssessmentId = searchParams.get('assessmentId') || '';

  useEffect(() => {
    return () => {
      if (previewUrl?.startsWith('blob:')) URL.revokeObjectURL(previewUrl);
      if (roiFeedbackTimeoutRef.current) clearTimeout(roiFeedbackTimeoutRef.current);
    };
  }, [previewUrl]);

  useEffect(() => {
    if (!user || !queryPatientId) return;
    setContextLoading(true);
    setError('');
    void loadClinicalAnalysisContext({ uid: user.uid, patientId: queryPatientId, assessmentId: queryAssessmentId })
      .then(nextContext => {
        const image = firstAssessmentImage(nextContext.assessment);
        setContext(nextContext);
        setPatientIdInput(queryPatientId);
        setSelectedFile(null);
        setPreviewUrl(image?.downloadURL || null);
        setLinkedImageId(image?.id || '');
        setRois(ensureClinicalRois(image?.rois || []));
        setEditingRoiIndex(null);
        setAnalysis(null);
        setActiveMobilePanel(image ? 'roi' : 'context');
      })
      .catch(loadError => setError(loadError instanceof Error ? loadError.message : 'Nao foi possivel carregar a avaliacao.'))
      .finally(() => setContextLoading(false));
  }, [queryAssessmentId, queryPatientId, user]);

  const linkedAssessment = Boolean(context.assessment);
  const hasImage = Boolean(previewUrl || selectedFile);
  const hasRoi = rois.some(roi => roi.points.length >= 3);
  const imageSource: File | string | null = selectedFile || (previewUrl && !previewUrl.startsWith('blob:') ? previewUrl : null);
  const assessmentImage = firstAssessmentImage(context.assessment);
  const status = resultStatusLabel(analysis, hasImage, hasRoi, analysisLoading, linkedAssessment);
  const savedSelections = useMemo(() => roisToAnalyzerSelections(rois), [rois]);
  const activeEditorSelection = editingRoiIndex !== null ? savedSelections[editingRoiIndex] || null : null;

  const showRoiFeedback = (message: string) => {
    setRoiFeedback(message);
    if (roiFeedbackTimeoutRef.current) clearTimeout(roiFeedbackTimeoutRef.current);
    roiFeedbackTimeoutRef.current = setTimeout(() => setRoiFeedback(''), 2600);
  };

  const resetResult = () => {
    setAnalysis(null);
    setError('');
    setNotice('');
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.currentTarget.value = '';
    if (!file) return;

    if (previewUrl?.startsWith('blob:')) URL.revokeObjectURL(previewUrl);
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
    setLinkedImageId('');
    setRois([]);
    setEditingRoiIndex(null);
    setRoiEditorKey(current => current + 1);
    setContext(current => ({ ...current, assessment: null, mode: 'standalone' }));
    resetResult();
    setActiveMobilePanel('roi');
  };

  const loadPatientContext = async () => {
    if (!user || !patientIdInput.trim()) return;
    setContextLoading(true);
    setError('');
    try {
      const nextContext = await loadClinicalAnalysisContext({ uid: user.uid, patientId: patientIdInput.trim() });
      setContext({ ...nextContext, assessment: null, mode: 'standalone' });
      setNotice(nextContext.patient ? 'Paciente e historico carregados para analise contextual.' : 'Paciente nao encontrado para o usuario logado.');
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Nao foi possivel carregar o paciente.');
    } finally {
      setContextLoading(false);
    }
  };

  const restoreAssessmentRois = () => {
    const nextRois = ensureClinicalRois(assessmentImage?.rois || []);
    setRois(nextRois);
    setEditingRoiIndex(null);
    setRoiEditorKey(current => current + 1);
    resetResult();
    showRoiFeedback(nextRois.length ? 'ROI da avaliacao reutilizada.' : 'A avaliacao nao possui ROI salva.');
  };

  const handleRoiConfirmed = (selection: Parameters<typeof analyzerSelectionToRoi>[0]) => {
    resetResult();
    setRois(current => {
      if (editingRoiIndex === null) return [...current, analyzerSelectionToRoi(selection, current.length)];
      return current.map((roi, index) => (index === editingRoiIndex ? analyzerSelectionToRoi(selection, index, roi) : roi));
    });
    setEditingRoiIndex(null);
    setRoiEditorKey(current => current + 1);
    showRoiFeedback('ROI salva no Analyzer.');
  };

  const removeRoi = (index: number) => {
    setRois(current => current.filter((_, currentIndex) => currentIndex !== index));
    setEditingRoiIndex(current => {
      if (current === null || current === index) return null;
      return current > index ? current - 1 : current;
    });
    setRoiEditorKey(current => current + 1);
    resetResult();
  };

  const clearRois = () => {
    if (rois.length && !window.confirm('Limpar todas as ROIs do Analyzer?')) return;
    setRois([]);
    setEditingRoiIndex(null);
    setRoiEditorKey(current => current + 1);
    resetResult();
  };

  const saveRoisToAssessment = async () => {
    if (!user || !context.assessment || !linkedImageId) {
      setNotice('ROIs mantidas nesta analise. Para persistir no historico, use uma avaliacao vinculada.');
      return;
    }

    try {
      await saveAssessmentImageRois({
        uid: user.uid,
        assessment: context.assessment,
        imageId: linkedImageId,
        rois,
        updatedBy: user.uid
      });
      const nextAssessment: Evaluation = {
        ...context.assessment,
        images: context.assessment.images.map(image => (image.id === linkedImageId ? { ...image, rois } : image))
      };
      setContext(current => ({ ...current, assessment: nextAssessment }));
      setNotice('ROI salva na avaliacao com rastreabilidade.');
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Nao foi possivel salvar a ROI na avaliacao.');
    }
  };

  const requestAnalysis = () => {
    if (!hasImage || !imageSource) {
      setError('Selecione uma imagem para iniciar.');
      setActiveMobilePanel('context');
      return;
    }
    if (!hasRoi) {
      setError('Crie uma ROI manual antes da analise. O HEAL Analyzer nao classifica imagem inteira como ferida.');
      setActiveMobilePanel('roi');
      return;
    }
    if (context.patient || context.assessment) {
      setConfirmOpen(true);
      return;
    }
    void runAnalysis();
  };

  const runAnalysis = async () => {
    if (!user || !imageSource) return;
    setConfirmOpen(false);
    setAnalysisLoading(true);
    setError('');
    setNotice('');
    setActiveMobilePanel('result');

    try {
      const result = await buildClinicalAnalysisResult({
        mode: context.assessment ? 'assessment_context' : 'standalone',
        patient: context.patient,
        assessment: context.assessment,
        history: context.history,
        image: imageSource,
        imageId: linkedImageId || selectedFile?.name,
        rois,
        createdBy: user.uid
      });
      setAnalysis(result);

      try {
        await saveClinicalAnalysisResult({ uid: user.uid, result });
        setNotice('Analise assistiva gerada e salva com sucesso.');
      } catch (saveError) {
        setNotice(saveError instanceof Error ? `Analise gerada, mas nao salva: ${saveError.message}` : 'Analise gerada, mas nao salva.');
      }
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : 'Falha ao gerar analise assistiva.');
    } finally {
      setAnalysisLoading(false);
    }
  };

  return (
    <>
      <PageHeader
        title="HEAL Analyzer"
        description="Analise assistiva de feridas e ROI"
        action={
          <div className="flex flex-wrap gap-2 items-center">
            <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold ${status.tone}`}>
              {analysisLoading ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
              {status.label}
            </span>
            <Badge tone={linkedAssessment ? 'blue' : 'slate'} dot>
              {linkedAssessment ? 'Avaliacao vinculada' : 'Analise avulsa'}
            </Badge>
          </div>
        }
      />

      <div className="p-4 sm:p-6 flex-grow space-y-5">

        {notice ? <Notice tone="success" message={notice} /> : null}
        {error ? <Notice tone="error" message={error} /> : null}

        <MobileAnalyzerTabs activePanel={activeMobilePanel} onChange={setActiveMobilePanel} roiCount={rois.length} />

        <div className="grid gap-6 lg:grid-cols-[310px_minmax(0,1fr)] xl:grid-cols-[310px_minmax(0,1fr)_390px]">
          <ContextPanel
            className={cn(activeMobilePanel === 'context' ? 'block' : 'hidden lg:block')}
            assessment={context.assessment}
            contextLoading={contextLoading}
            fileInputRef={fileInputRef}
            hasImage={hasImage}
            linkedAssessment={linkedAssessment}
            onAnalyze={requestAnalysis}
            onFileChange={handleFileChange}
            onLoadPatient={() => void loadPatientContext()}
            onRestoreAssessmentRois={restoreAssessmentRois}
            onSaveRois={() => void saveRoisToAssessment()}
            onSelectImage={() => fileInputRef.current?.click()}
            patient={context.patient}
            patientIdInput={patientIdInput}
            previewUrl={previewUrl}
            roiCount={rois.length}
            selectedFile={selectedFile}
            setPatientIdInput={setPatientIdInput}
          />

          <div className={cn(activeMobilePanel === 'roi' ? 'block' : 'hidden lg:block')}>
            <RoiWorkspace
              editingRoiIndex={editingRoiIndex}
              hasImage={hasImage}
              previewUrl={previewUrl}
              roiFeedback={roiFeedback}
              rois={rois}
              onClearRois={clearRois}
              onEditRoi={setEditingRoiIndex}
              onNewRoi={() => {
                setEditingRoiIndex(null);
                setRoiEditorKey(current => current + 1);
              }}
              onRemoveRoi={removeRoi}
            >
              {previewUrl ? (
                <WoundRoiCanvas
                  key={`${previewUrl}-${roiEditorKey}-${editingRoiIndex ?? 'new'}`}
                  activeSavedSelectionIndex={editingRoiIndex}
                  confirmLabel={editingRoiIndex !== null ? `Atualizar ROI ${editingRoiIndex + 1}` : rois.length ? 'Salvar nova ROI' : 'Salvar primeira ROI'}
                  disabled={analysisLoading}
                  imageSrc={previewUrl}
                  initialSelection={activeEditorSelection}
                  savedSelections={savedSelections}
                  onConfirm={handleRoiConfirmed}
                  onSelectionCleared={() => {
                    setEditingRoiIndex(null);
                    resetResult();
                  }}
                />
              ) : (
                <EmptyCanvasPanel />
              )}
            </RoiWorkspace>
          </div>

          <div className={cn(activeMobilePanel === 'result' ? 'block' : 'hidden lg:block', 'lg:col-span-2 xl:col-span-1')}>
            <ClinicalResultPanel
              analysis={analysis}
              loading={analysisLoading}
              hasImage={hasImage}
              hasRoi={hasRoi}
              onEditRoi={() => setActiveMobilePanel('roi')}
              onRunAnalysis={requestAnalysis}
              onSelectImage={() => fileInputRef.current?.click()}
            />
          </div>
        </div>
      </div>

      <Modal open={confirmOpen} title="Analise assistiva com dados clinicos" onClose={() => setConfirmOpen(false)} size="lg">
        <div className="space-y-5">
          <div className="flex gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-heal-blue ring-1 ring-blue-100">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <p className="text-sm leading-6 text-slate-600 dark:text-zinc-300">
              O HEAL Analyzer utilizara apenas a ROI marcada, dados da avaliacao e historico do paciente para gerar uma analise assistiva. Se a ROI nao parecer conter ferida, a classificacao clinica sera bloqueada.
            </p>
          </div>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button type="button" variant="secondary" onClick={() => setConfirmOpen(false)}>
              Cancelar
            </Button>
            <Button type="button" onClick={() => void runAnalysis()} isLoading={analysisLoading}>
              Iniciar analise
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

function Notice({ tone, message }: { tone: 'success' | 'error'; message: string }) {
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'rounded-xl border px-4 py-3 text-sm font-bold',
        tone === 'error' ? 'border-red-200 bg-red-50 text-red-700' : 'border-emerald-200 bg-emerald-50 text-emerald-800'
      )}
    >
      {message}
    </div>
  );
}

function ContextPanel({
  assessment,
  className,
  contextLoading,
  fileInputRef,
  hasImage,
  linkedAssessment,
  onAnalyze,
  onFileChange,
  onLoadPatient,
  onRestoreAssessmentRois,
  onSaveRois,
  onSelectImage,
  patient,
  patientIdInput,
  previewUrl,
  roiCount,
  selectedFile,
  setPatientIdInput
}: {
  assessment: Evaluation | null;
  className?: string;
  contextLoading: boolean;
  fileInputRef: RefObject<HTMLInputElement>;
  hasImage: boolean;
  linkedAssessment: boolean;
  onAnalyze: () => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onLoadPatient: () => void;
  onRestoreAssessmentRois: () => void;
  onSaveRois: () => void;
  onSelectImage: () => void;
  patient: Patient | null;
  patientIdInput: string;
  previewUrl: string | null;
  roiCount: number;
  selectedFile: File | null;
  setPatientIdInput: (value: string) => void;
}) {
  const patientAge = getAge(patient?.birthDate);

  return (
    <aside className={cn('space-y-4 lg:sticky lg:top-24 lg:self-start', className)}>
      <Card padding="sm">
        <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={onFileChange} />
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-blue">Imagem</p>
        <div className="mt-3 overflow-hidden rounded-2xl border border-heal-line bg-heal-canvas dark:border-zinc-800 dark:bg-zinc-950">
          {previewUrl ? (
            <img src={previewUrl} alt="Imagem da ferida para analise assistiva" className="h-40 w-full object-cover" />
          ) : (
            <div className="flex h-40 flex-col items-center justify-center px-4 text-center">
              <FileImage className="h-8 w-8 text-heal-blue" />
              <p className="mt-3 text-sm font-black text-heal-ink dark:text-white">Selecione uma imagem para iniciar.</p>
            </div>
          )}
        </div>
        <div className="mt-4 flex flex-col gap-3">
          <Button type="button" variant="secondary" className="w-full justify-center" onClick={onSelectImage}>
            <ImagePlus className="h-4 w-4" />
            {previewUrl ? 'Trocar imagem avulsa' : 'Selecionar imagem'}
          </Button>
          <Button type="button" className="w-full justify-center" onClick={onAnalyze} disabled={!hasImage || !roiCount || contextLoading}>
            {contextLoading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <ScanSearch className="h-4 w-4" />}
            Iniciar analise
          </Button>
          {!roiCount ? (
            <p className="rounded-xl bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
              ROI obrigatoria: marque somente a area da ferida antes de iniciar. Nao inclua rosto, roupa, fundo, maos ou grandes areas de pele saudavel.
            </p>
          ) : null}
        </div>
      </Card>

      <Card padding="sm">
        <div className="flex items-center gap-2">
          <UserRound className="h-4 w-4 text-heal-blue" />
          <p className="text-sm font-black text-heal-ink dark:text-white">Paciente vinculado</p>
        </div>
        {patient ? (
          <div className="mt-3 space-y-2 text-sm">
            <p className="font-black text-heal-ink dark:text-white">{patient.name}</p>
            <p className="text-heal-muted dark:text-zinc-400">ID: {patient.id}</p>
            <p className="text-heal-muted dark:text-zinc-400">Status: {patient.archived ? 'Arquivado' : 'Ativo'}</p>
            <p className="text-heal-muted dark:text-zinc-400">Idade: {patientAge === null ? 'Nao informada' : `${patientAge} anos`}</p>
          </div>
        ) : (
          <p className="mt-3 text-sm leading-6 text-heal-muted dark:text-zinc-400">
            Analise visual disponivel. Para analise contextual, vincule um paciente.
          </p>
        )}
        <div className="mt-3 flex gap-2">
          <Input className="flex-1" placeholder="ID do paciente" value={patientIdInput} onChange={event => setPatientIdInput(event.target.value)} />
          <Button type="button" variant="secondary" onClick={onLoadPatient} disabled={!patientIdInput.trim() || contextLoading} aria-label="Carregar paciente">
            {contextLoading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
          </Button>
        </div>
      </Card>

      <Card padding="sm">
        <div className="flex items-center gap-2">
          <ClipboardList className="h-4 w-4 text-heal-blue" />
          <p className="text-sm font-black text-heal-ink dark:text-white">Avaliacao vinculada</p>
        </div>
        {assessment ? (
          <div className="mt-3 space-y-2 text-sm text-heal-muted dark:text-zinc-400">
            <p><span className="font-bold text-heal-ink dark:text-white">Data:</span> {formatDate(assessment.date)}</p>
            <p><span className="font-bold text-heal-ink dark:text-white">Regiao:</span> {assessment.woundLocation || 'Nao informada'}</p>
            <p><span className="font-bold text-heal-ink dark:text-white">Lesao:</span> {assessment.woundEtiology || 'Nao informada'}</p>
            <p><span className="font-bold text-heal-ink dark:text-white">Dor:</span> {assessment.painLevel}/10</p>
            <p><span className="font-bold text-heal-ink dark:text-white">Exsudato:</span> {[assessment.exudateAmount, assessment.exudateType].filter(Boolean).join(' / ') || 'Nao informado'}</p>
          </div>
        ) : (
          <p className="mt-3 text-sm leading-6 text-heal-muted dark:text-zinc-400">
            Use o botao Analisar no historico ou informe um paciente para contexto parcial.
          </p>
        )}
        <div className="mt-4 grid gap-2">
          <Button type="button" variant="secondary" onClick={onRestoreAssessmentRois} disabled={!linkedAssessment}>
            <Target className="h-4 w-4" />
            Usar ROI da avaliacao
          </Button>
          <Button type="button" variant="secondary" onClick={onSaveRois} disabled={!roiCount}>
            <Save className="h-4 w-4" />
            Salvar ROI
          </Button>
        </div>
      </Card>

      {selectedFile ? (
        <Card padding="sm">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-muted">Arquivo atual</p>
          <p className="mt-2 truncate text-sm font-black text-heal-ink dark:text-white" title={selectedFile.name}>{selectedFile.name}</p>
        </Card>
      ) : null}

      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/20 dark:bg-amber-500/10">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 text-amber-600 dark:text-amber-300" />
          <p className="text-sm leading-6 text-amber-900 dark:text-amber-50">
            Resultado assistivo. Nao substitui avaliacao clinica profissional.
          </p>
        </div>
      </div>
    </aside>
  );
}

function RoiWorkspace({
  children,
  editingRoiIndex,
  hasImage,
  onClearRois,
  onEditRoi,
  onNewRoi,
  onRemoveRoi,
  previewUrl,
  roiFeedback,
  rois
}: {
  children: ReactNode;
  editingRoiIndex: number | null;
  hasImage: boolean;
  onClearRois: () => void;
  onEditRoi: (index: number) => void;
  onNewRoi: () => void;
  onRemoveRoi: (index: number) => void;
  previewUrl: string | null;
  roiFeedback: string;
  rois: Roi[];
}) {
  return (
    <section className="space-y-4">
      <Card padding="sm">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-muted">Canvas ROI</p>
            <h2 className="mt-1 text-xl font-black text-heal-ink dark:text-white">Imagem e regioes marcadas</h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {roiFeedback ? (
              <span className="inline-flex items-center gap-2 rounded-full border border-heal-teal/20 bg-heal-tealSoft px-3 py-1.5 text-xs font-black text-heal-teal">
                <BadgeCheck className="h-3.5 w-3.5" />
                {roiFeedback}
              </span>
            ) : null}
            <Badge tone={rois.length ? 'teal' : 'slate'}>{rois.length ? `${rois.length} ROI(s)` : 'Nenhuma ROI'}</Badge>
            {hasImage ? (
              <Button type="button" variant="secondary" size="sm" onClick={onNewRoi}>
                Nova ROI
              </Button>
            ) : null}
            {rois.length ? (
              <Button type="button" variant="secondary" size="sm" onClick={onClearRois}>
                Limpar
              </Button>
            ) : null}
          </div>
        </div>
        {rois.length ? (
          <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
            {rois.map((roi, index) => (
              <div
                key={roi.id}
                className={cn(
                  'inline-flex shrink-0 items-center gap-2 rounded-full border px-2 py-1',
                  editingRoiIndex === index
                    ? 'border-heal-blue/30 bg-heal-softBlue text-heal-blue'
                    : 'border-heal-line bg-heal-canvas text-heal-ink dark:border-zinc-800 dark:bg-zinc-950 dark:text-white'
                )}
              >
                <button type="button" onClick={() => onEditRoi(index)} className="rounded-full px-2 py-1 text-xs font-black">
                  {roi.label || `ROI ${index + 1}`} - {roi.points.length} pontos
                </button>
                <button type="button" onClick={() => onRemoveRoi(index)} className="rounded-full p-1 text-heal-muted transition hover:bg-white hover:text-heal-danger dark:hover:bg-zinc-900" aria-label={`Remover ROI ${index + 1}`}>
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        ) : previewUrl ? (
          <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-800">
            Marque somente a area da ferida. Evite incluir rosto, roupa, fundo, maos, instrumentos ou grandes areas de pele saudavel.
          </p>
        ) : null}
      </Card>
      {children}
    </section>
  );
}

function EmptyCanvasPanel() {
  return (
    <Card padding="lg" className="flex min-h-[520px] items-center justify-center text-center border-dashed">
      <div className="max-w-sm">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue">
          <FileImage className="h-7 w-7" />
        </div>
        <h2 className="mt-5 text-xl font-black text-heal-ink dark:text-white">Selecione uma imagem para iniciar</h2>
        <p className="mt-2 text-sm leading-6 text-heal-muted dark:text-zinc-400">O canvas de ROI aparece aqui assim que a foto da ferida for carregada.</p>
      </div>
    </Card>
  );
}

function ClinicalResultPanel({
  analysis,
  hasImage,
  hasRoi,
  loading,
  onEditRoi,
  onSelectImage,
  onRunAnalysis
}: {
  analysis: ClinicalAnalysisResult | null;
  hasImage: boolean;
  hasRoi: boolean;
  loading: boolean;
  onEditRoi: () => void;
  onSelectImage: () => void;
  onRunAnalysis: () => void;
}) {
  return (
    <aside className="2xl:sticky 2xl:top-24 2xl:self-start">
      <Card>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-muted">Resultado</p>
            <h2 className="mt-2 text-xl font-black text-heal-ink dark:text-white">Analise clinica assistiva</h2>
          </div>
          {loading ? <LoaderCircle className="h-5 w-5 animate-spin text-heal-blue" /> : <Sparkles className="h-5 w-5 text-heal-blue" />}
        </div>

        {!analysis ? (
          <div className="mt-4 rounded-2xl border border-dashed border-heal-line bg-heal-canvas p-6 text-center dark:border-zinc-800 dark:bg-zinc-950">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-heal-blue shadow-sm dark:bg-zinc-900">
              {loading ? <LoaderCircle className="h-6 w-6 animate-spin" /> : <ClipboardList className="h-6 w-6" />}
            </div>
            <p className="mt-4 text-lg font-black text-heal-ink dark:text-white">Resultado ainda nao gerado</p>
            <p className="mx-auto mt-2 max-w-[280px] text-sm leading-6 text-heal-muted dark:text-zinc-400">
              {hasImage && hasRoi
                ? 'Dados prontos para analisar imagem, ROI e contexto disponivel.'
                : hasImage
                  ? 'Marque a ROI para permitir a analise segura.'
                  : 'Selecione uma imagem para iniciar.'}
            </p>
            <Button type="button" className="mt-5 w-full justify-center" onClick={onRunAnalysis} disabled={!hasImage || !hasRoi || loading}>
              {loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <ScanSearch className="h-4 w-4" />}
              Iniciar analise
            </Button>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {!analysis.canAnalyze ? (
              <BlockedAnalysisCard analysis={analysis} onEditRoi={onEditRoi} onSelectImage={onSelectImage} />
            ) : null}

            <ResultSection title="Resumo da analise" icon={<ClipboardList className="h-4 w-4" />}>
              <div className="grid gap-2 text-sm text-heal-muted dark:text-zinc-400">
                <Metric label="Paciente" value={analysis.clinicalContext.patientName || 'Nao vinculado'} />
                <Metric label="Data da avaliacao" value={analysis.assessmentId ? analysis.clinicalContext.woundRegion ? 'Vinculada' : 'Vinculada, dados parciais' : 'Avulsa'} />
                <Metric label="Regiao" value={analysis.clinicalContext.woundRegion || 'Nao informada'} />
                <Metric label="ROIs avaliadas" value={`${analysis.roisUsed.length}`} />
                <Metric label="Qualidade da imagem" value={`${analysis.imageQuality.status} (${analysis.imageQuality.score}/100)`} />
                <Metric label="Validade da ROI" value={analysis.roiValidation.isValid ? `${Math.round(analysis.roiValidation.woundLikelihood * 100)}%` : 'Bloqueada'} />
                <Metric label="Classificacao tecidual" value={analysis.tissueClassification.enabled ? 'Habilitada' : 'Indisponivel'} />
              </div>
            </ResultSection>

            <ResultSection title="Dados considerados" icon={<Info className="h-4 w-4" />}>
              <TagList items={analysis.consideredData} />
            </ResultSection>

            <ResultSection title="Validacao da ROI" icon={<Target className="h-4 w-4" />}>
              <div className="space-y-3">
                <p className="text-sm leading-6 text-heal-muted dark:text-zinc-400">{analysis.roiValidation.reason}</p>
                {analysis.roiValidation.issues.length ? <TagList items={analysis.roiValidation.issues.map(issue => `Gate ROI: ${issue}`)} /> : null}
                <p className="text-sm leading-6 text-heal-muted dark:text-zinc-400">
                  Filtros aplicados antes da analise: {analysis.imageQuality.preprocessing.join(', ') || 'nao aplicados'}.
                </p>
              </div>
            </ResultSection>

            {analysis.canAnalyze ? (
              <ResultSection title="Segmentacao" icon={<ScanSearch className="h-4 w-4" />}>
                <div className="space-y-3">
                  {analysis.segmentation.overlayUrl ? (
                    <img src={analysis.segmentation.overlayUrl} alt="Mascara da ROI sobreposta ao recorte analisado" className="max-h-56 w-full rounded-xl object-contain bg-slate-950" />
                  ) : null}
                  <div className="grid gap-2 text-sm text-heal-muted dark:text-zinc-400">
                    <Metric label="Metodo" value={analysis.segmentation.method === 'manual_roi_mask' ? 'Mascara manual da ROI' : 'Modelo treinado'} />
                    <Metric label="Area estimada" value={analysis.segmentation.areaPixels ? `${analysis.segmentation.areaPixels} px` : 'Nao disponivel'} />
                    <Metric label="Confianca" value={analysis.segmentation.confidence !== undefined ? `${Math.round(analysis.segmentation.confidence * 100)}%` : 'Nao disponivel'} />
                  </div>
                  {analysis.segmentation.reason ? <p className="text-sm leading-6 text-amber-800 dark:text-amber-100">{analysis.segmentation.reason}</p> : null}
                </div>
              </ResultSection>
            ) : null}

            <ResultSection title="Classificacao visual" icon={<ShieldAlert className="h-4 w-4" />}>
              {analysis.tissueClassification.enabled ? (
                <TissueClassificationList classes={analysis.tissueClassification.classes} />
              ) : (
                <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-900 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-50">
                  {analysis.tissueClassification.reason}
                </p>
              )}
            </ResultSection>

            <ResultSection title="Achados visuais nao diagnosticos" icon={<Target className="h-4 w-4" />}>
              <div className="space-y-3">
                <ColorBreakdown colors={analysis.visualFindings.dominantColors} />
                <TagList items={analysis.visualFindings.tissueHints.length ? analysis.visualFindings.tissueHints : ['Sem achados visuais suficientes na ROI.']} />
              </div>
            </ResultSection>

            <ResultSection title="Contexto clinico" icon={<UserRound className="h-4 w-4" />}>
              <p className="text-sm leading-6 text-heal-muted dark:text-zinc-400">
                Dor {analysis.clinicalContext.painLevel ?? 'nao informada'}/10, lesao {analysis.clinicalContext.woundType || 'nao informada'} em {analysis.clinicalContext.woundRegion || 'regiao nao informada'}, exsudato {analysis.clinicalContext.exudate || 'nao informado'}. A interpretacao e limitada pelos dados preenchidos e pela qualidade da imagem.
              </p>
              {analysis.aiInference.summary ? (
                <p className="mt-3 rounded-xl bg-heal-canvas px-3 py-2 text-sm leading-6 text-heal-muted dark:bg-zinc-950 dark:text-zinc-400">
                  IA visual: {analysis.aiInference.summary}
                </p>
              ) : null}
            </ResultSection>

            <ResultSection title="Comparacao evolutiva" icon={<History className="h-4 w-4" />}>
              <p className="text-sm leading-6 text-heal-muted dark:text-zinc-400">{analysis.evolution.summary}</p>
              {analysis.evolution.previousAssessmentDate ? (
                <p className="mt-2 text-xs font-bold text-heal-muted dark:text-zinc-500">
                  Referencia anterior: {formatDate(analysis.evolution.previousAssessmentDate)}
                </p>
              ) : null}
            </ResultSection>

            <ResultSection title="Alertas clinicos" icon={<AlertTriangle className="h-4 w-4" />}>
              <AlertList alerts={analysis.alerts} />
            </ResultSection>

            <ResultSection title="Recomendacoes assistivas" icon={<CheckCircle2 className="h-4 w-4" />}>
              <TagList items={analysis.recommendations} />
            </ResultSection>

            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-50">
              <ShieldAlert className="mr-2 inline h-4 w-4" />
              {analysis.disclaimer}
            </div>
          </div>
        )}
      </Card>
    </aside>
  );
}

function BlockedAnalysisCard({
  analysis,
  onEditRoi,
  onSelectImage
}: {
  analysis: ClinicalAnalysisResult;
  onEditRoi: () => void;
  onSelectImage: () => void;
}) {
  return (
    <section className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-50">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700 dark:text-amber-200" />
        <div>
          <p className="text-sm font-black">Imagem nao adequada para analise de ferida</p>
          <p className="mt-2 text-sm leading-6">
            {analysis.blockedReason ||
              'O HEAL Analyzer nao identificou uma ferida visivel na ROI marcada. Revise a imagem ou marque corretamente a regiao da ferida.'}
          </p>
        </div>
      </div>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <Button type="button" variant="secondary" className="justify-center" onClick={onEditRoi}>
          <Target className="h-4 w-4" />
          Editar ROI
        </Button>
        <Button type="button" variant="secondary" className="justify-center" onClick={onSelectImage}>
          <ImagePlus className="h-4 w-4" />
          Trocar imagem
        </Button>
      </div>
    </section>
  );
}

function tissueLabel(label: ClinicalAnalysisResult['tissueClassification']['classes'][number]['label']) {
  if (label === 'granulation') return 'Granulacao';
  if (label === 'slough_fibrin') return 'Esfacelo/fibrina';
  if (label === 'necrosis') return 'Necrose';
  if (label === 'epithelial') return 'Epitelizacao';
  return 'Indeterminado';
}

function TissueClassificationList({ classes }: { classes: ClinicalAnalysisResult['tissueClassification']['classes'] }) {
  return (
    <div className="space-y-2">
      {classes.map(item => (
        <div key={item.label} className="rounded-xl border border-heal-line bg-heal-canvas px-3 py-2 text-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-center justify-between gap-3">
            <span className="font-bold text-heal-ink dark:text-white">{tissueLabel(item.label)}</span>
            <span className="text-heal-muted dark:text-zinc-400">{item.percentage}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-white dark:bg-zinc-950">
            <div className="h-full rounded-full bg-heal-teal" style={{ width: `${item.percentage}%` }} />
          </div>
          <p className="mt-2 text-xs text-heal-muted dark:text-zinc-400">Confianca: {Math.round(item.confidence * 100)}%</p>
        </div>
      ))}
    </div>
  );
}

function ResultSection({ children, icon, title }: { children: ReactNode; icon: ReactNode; title: string }) {
  return (
    <Card padding="sm" className="bg-heal-canvas dark:bg-zinc-950 border-heal-line/60 dark:border-zinc-800/60 shadow-none">
      <div className="mb-3 flex items-center gap-2 text-heal-ink dark:text-white">
        {icon}
        <p className="text-sm font-black">{title}</p>
      </div>
      {children}
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl bg-heal-canvas px-3 py-2 dark:bg-zinc-900">
      <span>{label}</span>
      <span className="text-right font-bold text-heal-ink dark:text-white">{value}</span>
    </div>
  );
}

function ColorBreakdown({ colors }: { colors: ClinicalAnalysisResult['visualFindings']['dominantColors'] }) {
  if (!colors.length) return <p className="text-sm text-heal-muted dark:text-zinc-400">Sem cores dominantes calculadas.</p>;
  return (
    <div className="space-y-2">
      {colors.slice(0, 4).map(color => (
        <div key={color.label} className="flex items-center justify-between gap-3 rounded-xl bg-heal-canvas px-3 py-2 text-sm dark:bg-zinc-900">
          <span className="inline-flex items-center gap-2 text-heal-muted dark:text-zinc-400">
            <span className="h-3 w-3 rounded-full" style={{ backgroundColor: color.hex }} />
            {color.label}
          </span>
          <span className="font-bold text-heal-ink dark:text-white">{color.percentage}%</span>
        </div>
      ))}
    </div>
  );
}

function AlertList({ alerts }: { alerts: ClinicalAnalysisAlert[] }) {
  if (!alerts.length) return <p className="text-sm text-heal-muted dark:text-zinc-400">Nenhum alerta clinico assistivo foi gerado com os dados atuais.</p>;
  return (
    <div className="space-y-2">
      {alerts.map(alert => (
        <div
          key={`${alert.title}-${alert.message}`}
          className={cn(
            'rounded-xl border px-3 py-2 text-sm leading-6',
            alert.severity === 'high'
              ? 'border-red-200 bg-red-50 text-red-800'
              : alert.severity === 'medium'
                ? 'border-amber-200 bg-amber-50 text-amber-800'
                : 'border-sky-200 bg-sky-50 text-sky-800'
          )}
        >
          <p className="font-black">{alert.title}</p>
          <p>{alert.message}</p>
        </div>
      ))}
    </div>
  );
}

function TagList({ items }: { items: string[] }) {
  return (
    <div className="space-y-2">
      {items.map(item => (
        <p key={item} className="rounded-xl border border-heal-line bg-heal-canvas px-3 py-2 text-sm leading-6 text-heal-muted dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
          {item}
        </p>
      ))}
    </div>
  );
}

function MobileAnalyzerTabs({ activePanel, onChange, roiCount }: { activePanel: MobilePanel; onChange: (panel: MobilePanel) => void; roiCount: number }) {
  const tabs: Array<{ id: MobilePanel; label: string }> = [
    { id: 'context', label: 'Contexto' },
    { id: 'roi', label: `ROI${roiCount ? ` (${roiCount})` : ''}` },
    { id: 'result', label: 'Resultado' }
  ];

  return (
    <div className="flex gap-2 overflow-x-auto rounded-2xl border border-heal-line bg-white p-1 shadow-soft dark:border-zinc-800 dark:bg-zinc-900 lg:hidden">
      {tabs.map(tab => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={cn(
            'h-10 min-w-28 rounded-xl px-4 text-sm font-black transition',
            activePanel === tab.id
              ? 'bg-heal-blue text-white shadow-sm'
              : 'text-heal-muted hover:bg-heal-canvas hover:text-heal-ink dark:hover:bg-zinc-800 dark:hover:text-white'
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
