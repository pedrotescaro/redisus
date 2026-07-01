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
  UserRound,
  BrainCircuit
} from 'lucide-react';

import { MarkdownRenderer } from '../ui/MarkdownRenderer';
import { subscribePatients } from '../../features/patients/patientService';
import { subscribeEvaluations } from '../../features/evaluations/evaluationService';

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
  if (loading) return { label: 'Processando', tone: 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/50 dark:bg-sky-950/20 dark:text-sky-300' };
  if (result && !result.canAnalyze) return { label: 'Análise bloqueada', tone: 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300' };
  if (result) return { label: 'Análise limitada', tone: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-300' };
  if (!hasImage) return { label: 'Aguardando imagem', tone: 'border-slate-200 bg-slate-50 text-slate-600 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400' };
  if (!hasRoi) return { label: 'ROI pendente', tone: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300' };
  if (linked) return { label: 'Avaliação vinculada', tone: 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-300' };
  return { label: 'Pronto para análise', tone: 'border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-900/50 dark:bg-teal-950/20 dark:text-teal-300' };
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
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [patients, setPatients] = useState<Patient[]>([]);

  useEffect(() => {
    if (!user) return;
    const unPatients = subscribePatients(user.uid, next => {
      setPatients(next.filter(p => !p.archived));
    });
    return () => unPatients();
  }, [user]);

  const [patientEvaluations, setPatientEvaluations] = useState<Evaluation[]>([]);

  useEffect(() => {
    if (!user || !context.patient) {
      setPatientEvaluations([]);
      return;
    }
    const unSub = subscribeEvaluations(user.uid, context.patient.id, next => {
      setPatientEvaluations(next);
    });
    return () => unSub();
  }, [user, context.patient]);

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
    if (rois.length) {
      setClearConfirmOpen(true);
    } else {
      executeClearRois();
    }
  };

  const executeClearRois = () => {
    setRois([]);
    setEditingRoiIndex(null);
    setRoiEditorKey(current => current + 1);
    resetResult();
    setClearConfirmOpen(false);
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
    <div className="flex flex-col xl:flex-row min-h-screen min-w-0 bg-white dark:bg-[#0c0c0e]">
      {/* Coluna Central / Esquerda */}
      <div className="flex-grow w-full border-r border-heal-line dark:border-zinc-800/60 min-h-screen flex flex-col min-w-0">
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

        <div className="p-4 sm:py-6 sm:pl-6 sm:pr-3 flex-grow space-y-5 xl:h-[calc(100vh-80px)] xl:overflow-y-auto">
          {notice ? <Notice tone="success" message={notice} /> : null}
          {error ? <Notice tone="error" message={error} /> : null}

          <MobileAnalyzerTabs activePanel={activeMobilePanel} onChange={setActiveMobilePanel} roiCount={rois.length} />

          {/* Workspace do Canvas ROI */}
          <div className={cn(activeMobilePanel === 'roi' ? 'block' : 'hidden xl:block')}>
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

          {/* Grid de Contexto e Inputs (Imagem, Paciente, Avaliação) */}
          <div className={cn(activeMobilePanel === 'context' ? 'grid' : 'hidden xl:grid', 'grid-cols-1 md:grid-cols-3 gap-6')}>
            {/* Card 1: Imagem */}
            <Card padding="sm" className="flex flex-col justify-between">
              <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-blue">Imagem</p>
                <div className="mt-3 overflow-hidden rounded-2xl border border-heal-line bg-heal-canvas dark:border-zinc-800 dark:bg-zinc-950">
                  {previewUrl ? (
                    <img src={previewUrl} alt="Imagem da ferida para análise assistiva" className="h-32 w-full object-cover" />
                  ) : (
                    <div className="flex h-32 flex-col items-center justify-center px-4 text-center">
                      <FileImage className="h-6 w-6 text-heal-blue" />
                      <p className="mt-2 text-xs font-black text-heal-ink dark:text-white">Selecione uma imagem para iniciar.</p>
                    </div>
                  )}
                </div>
              </div>
              <div className="mt-4 flex flex-col gap-2.5">
                <Button type="button" variant="secondary" className="w-full justify-center text-xs" onClick={() => fileInputRef.current?.click()}>
                  <ImagePlus className="h-3.5 w-3.5" />
                  Selecionar imagem
                </Button>
                <Button type="button" className="w-full justify-center text-xs" onClick={requestAnalysis} disabled={!hasImage || !rois.length || contextLoading}>
                  {contextLoading ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <ScanSearch className="h-3.5 w-3.5" />}
                  Iniciar análise
                </Button>
                {!rois.length ? (
                  <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[10px] leading-relaxed text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300">
                    ROI obrigatória: marque somente a área da ferida antes de iniciar. Não inclua rosto, roupa, fundo, mãos ou grandes áreas de pele saudável.
                  </p>
                ) : null}
              </div>
            </Card>

            {/* Card 2: Paciente Vinculado */}
            <Card padding="sm" className="flex flex-col justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <UserRound className="h-4 w-4 text-heal-blue" />
                  <p className="text-sm font-black text-heal-ink dark:text-white">Paciente vinculado</p>
                </div>
                {context.patient ? (
                  <div className="mt-3 space-y-1.5 text-xs text-heal-muted dark:text-zinc-400">
                    <p className="font-black text-heal-ink dark:text-white">{context.patient.name}</p>
                    <p>ID: {context.patient.id}</p>
                    <p>Status: {context.patient.archived ? 'Arquivado' : 'Ativo'}</p>
                    <p>Idade: {getAge(context.patient.birthDate) === null ? 'Não informada' : `${getAge(context.patient.birthDate)} anos`}</p>
                  </div>
                ) : (
                  <p className="mt-3 text-xs leading-relaxed text-heal-muted dark:text-zinc-400">
                    Análise visual disponível. Para análise contextual, vincule um paciente.
                  </p>
                )}
              </div>
              <div className="mt-4">
                <select
                  className="w-full rounded-xl border border-heal-line bg-white px-3 py-2 text-xs font-semibold text-heal-ink dark:border-zinc-800 dark:bg-zinc-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-heal-blue"
                  value={patientIdInput}
                  onChange={async (event) => {
                    const selectedId = event.target.value;
                    setPatientIdInput(selectedId);
                    if (selectedId && user) {
                      setContextLoading(true);
                      setError('');
                      try {
                        const nextContext = await loadClinicalAnalysisContext({ uid: user.uid, patientId: selectedId });
                        setContext({ ...nextContext, assessment: null, mode: 'standalone' });
                        setNotice(nextContext.patient ? 'Paciente e histórico carregados para análise.' : 'Paciente não encontrado.');
                      } catch (loadError) {
                        setError(loadError instanceof Error ? loadError.message : 'Não foi possível carregar o paciente.');
                      } finally {
                        setContextLoading(false);
                      }
                    } else {
                      setContext(current => ({ ...current, patient: null, history: [] }));
                    }
                  }}
                >
                  <option value="">-- Selecione um paciente --</option>
                  {patients.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
            </Card>

            {/* Card 3: Avaliação Vinculada e Disclaimer */}
            <div className="flex flex-col gap-4">
              <Card padding="sm" className="flex-1 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <ClipboardList className="h-4 w-4 text-heal-blue" />
                    <p className="text-sm font-black text-heal-ink dark:text-white">Avaliação vinculada</p>
                  </div>
                  {context.assessment ? (
                    <div className="mt-3 space-y-1.5 text-xs text-heal-muted dark:text-zinc-400">
                      <p><span className="font-bold text-heal-ink dark:text-white">Data:</span> {formatDate(context.assessment.date)}</p>
                      <p><span className="font-bold text-heal-ink dark:text-white">Região:</span> {context.assessment.woundLocation || 'Não informada'}</p>
                      <p><span className="font-bold text-heal-ink dark:text-white">Lesão:</span> {context.assessment.woundEtiology || 'Não informada'}</p>
                      <p><span className="font-bold text-heal-ink dark:text-white">Dor:</span> {context.assessment.painLevel}/10</p>
                      <p><span className="font-bold text-heal-ink dark:text-white">Exsudato:</span> {[context.assessment.exudateAmount, context.assessment.exudateType].filter(Boolean).join(' / ') || 'Não informado'}</p>
                    </div>
                  ) : (
                    <p className="mt-3 text-xs leading-relaxed text-heal-muted dark:text-zinc-400">
                      Use o botão Analisar no histórico ou informe um paciente para contexto parcial.
                    </p>
                  )}
                  {context.patient && (
                    <div className="mt-3">
                      {patientEvaluations.length > 0 ? (
                        <select
                          className="w-full rounded-xl border border-heal-line bg-white px-3 py-2 text-xs font-semibold text-heal-ink dark:border-zinc-800 dark:bg-zinc-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-heal-blue"
                          value={context.assessment?.id || ''}
                          onChange={async (event) => {
                            const selectedAssessmentId = event.target.value;
                            if (selectedAssessmentId && user) {
                              setContextLoading(true);
                              setError('');
                              try {
                                const nextContext = await loadClinicalAnalysisContext({
                                  uid: user.uid,
                                  patientId: context.patient!.id,
                                  assessmentId: selectedAssessmentId
                                });
                                setContext({ ...nextContext, mode: 'assessment_context' });

                                const image = firstAssessmentImage(nextContext.assessment);
                                setPreviewUrl(image?.downloadURL || null);
                                setLinkedImageId(image?.id || '');
                                setRois(ensureClinicalRois(image?.rois || []));
                                setEditingRoiIndex(null);
                                setAnalysis(null);
                              } catch (loadError) {
                                setError(loadError instanceof Error ? loadError.message : 'Não foi possível carregar a avaliação.');
                              } finally {
                                setContextLoading(false);
                              }
                            } else {
                              setContext(current => ({ ...current, assessment: null, mode: 'standalone' }));
                              setPreviewUrl(null);
                              setLinkedImageId('');
                              setRois([]);
                            }
                          }}
                        >
                          <option value="">-- Selecione uma avaliação --</option>
                          {patientEvaluations.map(e => (
                            <option key={e.id} value={e.id}>
                              {formatDate(e.date)} - {e.woundLocation || 'Sem região'}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <p className="text-[10px] text-amber-600 dark:text-amber-400 font-semibold bg-amber-500/10 px-2.5 py-1.5 rounded-lg border border-amber-500/20">
                          Nenhuma avaliação encontrada para este paciente.
                        </p>
                      )}
                    </div>
                  )}
                </div>
                <div className="mt-4 flex flex-col gap-2">
                  <Button type="button" variant="secondary" className="justify-center text-[10px] px-1 h-9" onClick={restoreAssessmentRois} disabled={!linkedAssessment}>
                    <Target className="h-3.5 w-3.5" />
                    Usar ROI da avaliação
                  </Button>
                  <Button type="button" variant="secondary" className="justify-center text-[10px] px-1 h-9" onClick={() => void saveRoisToAssessment()} disabled={!rois.length}>
                    <Save className="h-3.5 w-3.5" />
                    Salvar ROI
                  </Button>
                </div>
              </Card>

              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 dark:border-amber-900/50 dark:bg-amber-950/20">
                <div className="flex items-start gap-2.5">
                  <ShieldAlert className="mt-0.5 h-4.5 w-4.5 text-amber-700 dark:text-amber-300 shrink-0" />
                  <p className="text-[10px] leading-relaxed text-amber-900 dark:text-amber-200 font-medium">
                    Resultado assistivo. Não substitui avaliação clínica profissional.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Coluna Lateral Direita (Resultado) */}
      <aside className={cn(activeMobilePanel === 'result' ? 'block' : 'hidden xl:block', 'w-full xl:w-[390px] p-4 sm:py-5 sm:pr-5 sm:pl-3 shrink-0 min-h-screen xl:h-screen xl:overflow-y-auto')}>
        <ClinicalResultPanel
          analysis={analysis}
          loading={analysisLoading}
          hasImage={hasImage}
          hasRoi={hasRoi}
          patient={context.patient}
          onEditRoi={() => setActiveMobilePanel('roi')}
          onRunAnalysis={requestAnalysis}
          onSelectImage={() => fileInputRef.current?.click()}
        />
      </aside>

      <Modal open={confirmOpen} title="Análise assistiva com dados clínicos" onClose={() => setConfirmOpen(false)} size="lg">
        <div className="space-y-5">
          <div className="flex gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-heal-blue ring-1 ring-blue-100">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <p className="text-sm leading-6 text-slate-600 dark:text-zinc-300">
              O HEAL Analyzer utilizará apenas a ROI marcada, dados da avaliação e histórico do paciente para gerar uma análise assistiva. Se a ROI não parecer conter ferida, a classificação clínica será bloqueada.
            </p>
          </div>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button type="button" variant="secondary" onClick={() => setConfirmOpen(false)}>
              Cancelar
            </Button>
            <Button type="button" onClick={() => void runAnalysis()} isLoading={analysisLoading}>
              Iniciar análise
            </Button>
          </div>
        </div>
      </Modal>

      <Modal open={clearConfirmOpen} title="Limpar todas as ROIs" onClose={() => setClearConfirmOpen(false)} size="sm">
        <div className="space-y-5">
          <div className="flex gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-red-500/10 text-heal-danger ring-1 ring-red-500/20">
              <Trash2 className="h-5 w-5" />
            </div>
            <p className="text-sm leading-6 text-slate-600 dark:text-zinc-300">
              Tem certeza que deseja limpar todas as ROIs do Analyzer? Esta ação não pode ser desfeita.
            </p>
          </div>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button type="button" variant="secondary" onClick={() => setClearConfirmOpen(false)}>
              Cancelar
            </Button>
            <Button type="button" variant="danger" onClick={executeClearRois}>
              Limpar tudo
            </Button>
          </div>
        </div>
      </Modal>
    </div>
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
      {children}
      <Card padding="sm" className="border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e]">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-muted">Canvas ROI</p>
            <h2 className="mt-1 text-xl font-black text-heal-ink dark:text-white">Imagem e regiões marcadas</h2>
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
          <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300">
            Marque somente a área da ferida. Evite incluir rosto, roupa, fundo, mãos, instrumentos ou grandes áreas de pele saudável.
          </p>
        ) : null}
      </Card>
    </section>
  );
}

function EmptyCanvasPanel() {
  return (
    <Card className="flex h-full min-h-[380px] flex-col items-center justify-center p-8 text-center bg-white dark:bg-[#0c0c0e]">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40 shadow-sm transition-transform duration-300 hover:scale-105 mb-6">
        <FileImage className="h-8 w-8 animate-pulse text-heal-blue" />
      </div>
      <h2 className="text-2xl font-black text-heal-ink dark:text-white tracking-tight mb-3">Selecione uma imagem para iniciar</h2>
      <p className="max-w-sm text-sm leading-relaxed text-heal-muted dark:text-zinc-400">
        O canvas de ROI aparecerá aqui assim que a foto da ferida for carregada para que você possa desenhar as marcações.
      </p>
    </Card>
  );
}

function ClinicalResultPanel({
  analysis,
  hasImage,
  hasRoi,
  loading,
  patient,
  onEditRoi,
  onSelectImage,
  onRunAnalysis
}: {
  analysis: ClinicalAnalysisResult | null;
  hasImage: boolean;
  hasRoi: boolean;
  loading: boolean;
  patient: Patient | null;
  onEditRoi: () => void;
  onSelectImage: () => void;
  onRunAnalysis: () => void;
}) {
  const [aiAnalysis, setAiAnalysis] = useState<string | null>(null);
  const [loadingAiAnalysis, setLoadingAiAnalysis] = useState(false);
  const [aiAnalysisError, setAiAnalysisError] = useState<string | null>(null);
  const [resultTab, setResultTab] = useState<'neural' | 'generative'>('neural');

  const handleGenerateAiAnalysis = () => {
    if (!analysis) return;
    setLoadingAiAnalysis(true);
    setAiAnalysisError(null);

    const apiKey = import.meta.env.VITE_GROQ_API_KEY || '';
    const model = import.meta.env.VITE_AI_MODEL || 'llama-3.1-8b-instant';

    const userPrompt = `Analise o seguinte resultado técnico gerado pelo HEAL Analyzer (modelo de visão computacional de segmentação de feridas) para o paciente ${patient?.name || 'não informado'}.

Dados Técnicos do Analyzer:
- Região da lesão: ${analysis.clinicalContext.woundRegion || 'Não informada'}
- Qualidade da imagem: ${analysis.imageQuality.status} (Score: ${analysis.imageQuality.score}/100)
- Área estimada da lesão: ${analysis.segmentation.areaPixels ? `${analysis.segmentation.areaPixels} pixels` : 'Não calculada'}
- Validade da ROI (Wound Likelihood): ${Math.round(analysis.roiValidation.woundLikelihood * 100)}%
- Classificação Tecidual (Proporções no Leito):
  ${analysis.tissueClassification.classes.map(c => {
    const labelMap: Record<string, string> = {
      granulation: 'Granulação',
      slough_fibrin: 'Esfacelo / Fibrina',
      necrosis: 'Necrose',
      epithelial: 'Epitelização',
      unknown: 'Não identificado'
    };
    return `* ${labelMap[c.label] || c.label}: ${Math.round(c.percentage * 100)}%`;
  }).join('\n') || 'Indisponível'}
- Achados Visuais (Pistas de Tecido): ${analysis.visualFindings.tissueHints.join(', ') || 'Nenhum'}
- Contexto Clínico: Dor ${analysis.clinicalContext.painLevel ?? 'não informada'}/10, Exsudato: ${analysis.clinicalContext.exudate || 'Não informado'}
- Alertas Clínicos Detectados: ${analysis.alerts.map(a => `* [${a.severity}] ${a.title}: ${a.message}`).join('\n') || 'Nenhum'}
- Recomendações Técnicas: ${analysis.recommendations.join(', ') || 'Nenhuma'}

Por favor, como especialista em estomaterapia, gere um Parecer Clínico Generativo contendo:
1. DIAGNÓSTICO DO LEITO: Interprete o percentual de tecidos (granulação, esfacelo, necrose) e o que isso indica sobre a fase de cicatrização.
2. SINAIS DE ALERTA: Avalie se há suspeitas de infecção (baseado nos alertas de dor, exsudato ou pistas visuais).
3. DIRETRIZES DE TRATAMENTO: Sugira o tipo de cobertura ou curativo ideal baseado no tecido e exsudato.`;

    fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: 'system', content: 'Você é um clínico especialista em estomaterapia e cicatrização de feridas crônicas.' },
          { role: 'user', content: userPrompt }
        ]
      })
    })
    .then(async response => {
      if (!response.ok) throw new Error(`Erro: ${response.status}`);
      const data = await response.json();
      const text = data.choices?.[0]?.message?.content;
      if (!text) throw new Error('Retorno vazio.');
      setAiAnalysis(text);
    })
    .catch(err => {
      console.error(err);
      setAiAnalysisError('Falha ao gerar parecer por IA. Verifique sua chave de API ou conexão.');
    })
    .finally(() => {
      setLoadingAiAnalysis(false);
    });
  };

  useEffect(() => {
    if (analysis) {
      setResultTab('neural');
      handleGenerateAiAnalysis();
    } else {
      setAiAnalysis(null);
      setAiAnalysisError(null);
    }
  }, [analysis]);

  return (
    <div className="w-full">
      <Card className="border-heal-line/75 dark:border-zinc-800/80 bg-white dark:bg-[#0c0c0e]">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-heal-muted">Resultado</p>
            <h2 className="mt-2 text-xl font-black text-heal-ink dark:text-white">Análise clínica assistiva</h2>
          </div>
          {loading ? <LoaderCircle className="h-5 w-5 animate-spin text-heal-blue" /> : <Sparkles className="h-5 w-5 text-heal-blue" />}
        </div>

        {/* Switcher Tabs */}
        {analysis && (
          <div className="flex w-full border-b border-heal-line/60 dark:border-zinc-800/60 bg-transparent select-none mt-4 mb-4">
            <button
              type="button"
              className={`relative flex-1 pb-3 text-xs font-bold transition-colors text-center cursor-pointer border-0 bg-transparent ${
                resultTab === 'neural' ? 'text-heal-blue' : 'text-heal-muted hover:text-heal-ink dark:hover:text-white'
              }`}
              onClick={() => setResultTab('neural')}
            >
              IA Treinada (Rede Neural)
              {resultTab === 'neural' && <div className="absolute bottom-0 left-1/4 right-1/4 h-0.5 rounded-full bg-heal-blue" />}
            </button>
            <button
              type="button"
              className={`relative flex-1 pb-3 text-xs font-bold transition-colors text-center cursor-pointer border-0 bg-transparent ${
                resultTab === 'generative' ? 'text-heal-blue' : 'text-heal-muted hover:text-heal-ink dark:hover:text-white'
              }`}
              onClick={() => setResultTab('generative')}
            >
              <div className="inline-flex items-center gap-1.5 justify-center">
                <span>IA Generativa (Llama 3.1)</span>
                {loadingAiAnalysis && <LoaderCircle className="h-3 w-3 animate-spin text-heal-blue" />}
              </div>
              {resultTab === 'generative' && <div className="absolute bottom-0 left-1/4 right-1/4 h-0.5 rounded-full bg-heal-blue" />}
            </button>
          </div>
        )}

        {!analysis ? (
          <div className="mt-4 rounded-2xl border border-dashed border-heal-line bg-heal-canvas p-6 text-center dark:border-zinc-800 dark:bg-zinc-950">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-heal-blue shadow-sm dark:bg-zinc-900">
              {loading ? <LoaderCircle className="h-6 w-6 animate-spin" /> : <ClipboardList className="h-6 w-6" />}
            </div>
            <p className="mt-4 text-lg font-black text-heal-ink dark:text-white">Resultado ainda não gerado</p>
            <p className="mx-auto mt-2 max-w-[280px] text-sm leading-6 text-heal-muted dark:text-zinc-400">
              {hasImage && hasRoi
                ? 'Dados prontos para analisar imagem, ROI e contexto disponível.'
                : hasImage
                  ? 'Marque a ROI para permitir a análise segura.'
                  : 'Selecione uma imagem para iniciar.'}
            </p>
            <Button type="button" className="mt-5 w-full justify-center" onClick={onRunAnalysis} disabled={!hasImage || !hasRoi || loading}>
              {loading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <ScanSearch className="h-4 w-4" />}
              Iniciar análise
            </Button>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {!analysis.canAnalyze ? (
              <BlockedAnalysisCard analysis={analysis} onEditRoi={onEditRoi} onSelectImage={onSelectImage} />
            ) : null}

            {resultTab === 'neural' ? (
              <>
                <ResultSection title="Resumo da análise" icon={<ClipboardList className="h-4 w-4" />}>
                  <div className="grid gap-0.5">
                    <Metric label="Paciente" value={analysis.clinicalContext.patientName || 'Não vinculado'} />
                    <Metric label="Data da avaliação" value={analysis.assessmentId ? analysis.clinicalContext.woundRegion ? 'Vinculada' : 'Vinculada, dados parciais' : 'Avulsa'} />
                    <Metric label="Região" value={analysis.clinicalContext.woundRegion || 'Não informada'} />
                    <Metric label="ROIs avaliadas" value={`${analysis.roisUsed.length}`} />
                    <Metric label="Qualidade da imagem" value={`${analysis.imageQuality.status} (${analysis.imageQuality.score}/100)`} />
                    <Metric label="Validade da ROI" value={analysis.roiValidation.isValid ? `${Math.round(analysis.roiValidation.woundLikelihood * 100)}%` : 'Bloqueada'} />
                    <Metric label="Classificação tecidual" value={analysis.tissueClassification.enabled ? 'Habilitada' : 'Indisponível'} />
                  </div>
                </ResultSection>

                <ResultSection title="Dados considerados" icon={<Info className="h-4 w-4" />}>
                  <TagList items={analysis.consideredData} />
                </ResultSection>

                <ResultSection title="Validação da ROI" icon={<Target className="h-4 w-4" />}>
                  <div className="space-y-3">
                    <p className="text-xs leading-relaxed text-heal-muted dark:text-zinc-400">{analysis.roiValidation.reason}</p>
                    {analysis.roiValidation.issues.length ? <TagList items={analysis.roiValidation.issues.map(issue => `Gate ROI: ${issue}`)} /> : null}
                    <p className="text-[11px] leading-relaxed text-heal-muted dark:text-zinc-450">
                      Filtros aplicados antes da análise: {analysis.imageQuality.preprocessing.join(', ') || 'não aplicados'}.
                    </p>
                  </div>
                </ResultSection>

                {analysis.canAnalyze ? (
                  <ResultSection title="Segmentação" icon={<ScanSearch className="h-4 w-4" />}>
                    <div className="space-y-3">
                      {analysis.segmentation.overlayUrl ? (
                        <img src={analysis.segmentation.overlayUrl} alt="Mascara da ROI sobreposta ao recorte analisado" className="max-h-56 w-full rounded-xl object-contain bg-slate-950" />
                      ) : null}
                      <div className="grid gap-0.5">
                        <Metric label="Método" value={analysis.segmentation.method === 'manual_roi_mask' ? 'Máscara manual da ROI' : 'Modelo treinado'} />
                        <Metric label="Área estimada" value={analysis.segmentation.areaPixels ? `${analysis.segmentation.areaPixels} px` : 'Não disponível'} />
                        <Metric label="Confiança" value={analysis.segmentation.confidence !== undefined ? `${Math.round(analysis.segmentation.confidence * 100)}%` : 'Não disponível'} />
                      </div>
                      {analysis.segmentation.reason ? <p className="text-xs leading-relaxed text-amber-800 dark:text-amber-100">{analysis.segmentation.reason}</p> : null}
                    </div>
                  </ResultSection>
                ) : null}

                <ResultSection title="Classificação visual" icon={<ShieldAlert className="h-4 w-4" />}>
                  {analysis.tissueClassification.enabled ? (
                    <TissueClassificationList classes={analysis.tissueClassification.classes} />
                  ) : (
                    <p className="rounded-xl border border-amber-200 bg-amber-550/5 px-3 py-2 text-xs leading-relaxed text-amber-900 dark:border-amber-550/20 dark:bg-amber-500/5 dark:text-amber-200">
                      {analysis.tissueClassification.reason}
                    </p>
                  )}
                </ResultSection>

                <ResultSection title="Achados visuais não diagnósticos" icon={<Target className="h-4 w-4" />}>
                  <div className="space-y-3">
                    <ColorBreakdown colors={analysis.visualFindings.dominantColors} />
                    <TagList items={analysis.visualFindings.tissueHints.length ? analysis.visualFindings.tissueHints : ['Sem achados visuais suficientes na ROI.']} />
                  </div>
                </ResultSection>

                <ResultSection title="Contexto clínico" icon={<UserRound className="h-4 w-4" />}>
                  <p className="text-xs leading-relaxed text-heal-muted dark:text-zinc-400">
                    Dor {analysis.clinicalContext.painLevel ?? 'não informada'}/10, lesão {analysis.clinicalContext.woundType || 'não informada'} em {analysis.clinicalContext.woundRegion || 'região não informada'}, exsudato {analysis.clinicalContext.exudate || 'não informado'}. A interpretação é limitada pelos dados preenchidos e pela qualidade da imagem.
                  </p>
                  {analysis.aiInference.summary ? (
                    <p className="mt-3 rounded-xl bg-heal-canvas/60 dark:bg-zinc-950 p-2.5 text-xs leading-relaxed text-heal-muted dark:text-zinc-400">
                      <strong>IA visual:</strong> {analysis.aiInference.summary}
                    </p>
                  ) : null}
                </ResultSection>

                <ResultSection title="Comparação evolutiva" icon={<History className="h-4 w-4" />}>
                  <p className="text-xs leading-relaxed text-heal-muted dark:text-zinc-400">{analysis.evolution.summary}</p>
                  {analysis.evolution.previousAssessmentDate ? (
                    <p className="mt-2 text-xs font-bold text-heal-muted dark:text-zinc-500">
                      Referência anterior: {formatDate(analysis.evolution.previousAssessmentDate)}
                    </p>
                  ) : null}
                </ResultSection>

                <ResultSection title="Alertas clínicos" icon={<AlertTriangle className="h-4 w-4" />}>
                  <AlertList alerts={analysis.alerts} />
                </ResultSection>

                <ResultSection title="Recomendações assistivas" icon={<Target className="h-4 w-4" />}>
                  <div className="space-y-2">
                    {analysis.recommendations.map(rec => (
                      <div key={rec} className="flex items-start gap-2 text-xs leading-relaxed text-heal-muted dark:text-zinc-400">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-heal-blue" />
                        <p>{rec}</p>
                      </div>
                    ))}
                  </div>
                </ResultSection>
              </>
            ) : (
              <div className="space-y-4">
                <div className="rounded-2xl border border-heal-blue/20 bg-heal-softBlue/10 p-4 dark:border-blue-500/20 dark:bg-blue-950/20 text-left">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
                      <BrainCircuit className="h-4.5 w-4.5" />
                    </div>
                    <div>
                      <p className="text-[10px] font-black uppercase tracking-wide text-heal-blue">Parecer de IA Generativa</p>
                      <h4 className="text-xs font-bold text-heal-ink dark:text-white">Laudo de Estomaterapia (Llama 3.1)</h4>
                    </div>
                  </div>

                  {aiAnalysis ? (
                    <div className="mt-3 animate-fade-in">
                      <div className="text-xs leading-relaxed text-slate-700 dark:text-zinc-300">
                        <MarkdownRenderer text={aiAnalysis} />
                      </div>
                      <div className="mt-3 flex items-center justify-between gap-3 border-t border-heal-line/30 dark:border-zinc-800/30 pt-3">
                        <p className="text-[9px] text-heal-muted dark:text-zinc-500 font-medium">
                          Aviso: Esta análise é gerada por inteligência artificial para apoio clínico e deve ser validada por um profissional de saúde.
                        </p>
                        <button
                          type="button"
                          onClick={handleGenerateAiAnalysis}
                          className="flex items-center gap-1 px-2 py-1 rounded-lg border border-heal-blue/20 bg-white dark:bg-zinc-900 text-[10px] font-bold text-heal-blue cursor-pointer hover:bg-heal-softBlue/30 transition-colors border-0"
                        >
                          <Sparkles className="h-2.5 w-2.5" />
                          Regerar
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3 flex flex-col items-center py-6 text-center">
                      {loadingAiAnalysis ? (
                        <div className="flex flex-col items-center gap-2">
                          <LoaderCircle className="h-5 w-5 animate-spin text-heal-blue" />
                          <p className="text-[10px] font-semibold text-heal-muted dark:text-zinc-400">Interpretando achados da ferida por IA...</p>
                        </div>
                      ) : (
                        <>
                          <p className="text-[10px] text-heal-muted dark:text-zinc-400 mb-3 max-w-[280px]">
                            Nenhum parecer gerado. Clique no botão abaixo para interpretar os achados.
                          </p>
                          <button
                            type="button"
                            onClick={handleGenerateAiAnalysis}
                            className="flex items-center gap-2 px-4 py-2 rounded-full bg-heal-blue hover:bg-heal-blueDark text-white text-[10px] font-bold shadow-sm cursor-pointer transition-all hover:scale-[1.02] active:scale-[0.98] border-0"
                          >
                            <Sparkles className="h-3 w-3" />
                            Gerar Parecer Clínico
                          </button>
                        </>
                      )}

                      {aiAnalysisError && (
                        <div className="mt-2 flex items-center gap-1.5 text-[10px] font-semibold text-red-500 bg-red-500/10 px-2.5 py-1.5 rounded-lg border border-red-500/20">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          <span>{aiAnalysisError}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="rounded-2xl border border-amber-200 bg-amber-500/5 p-4 text-xs leading-relaxed text-amber-900 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-50">
              <ShieldAlert className="mr-2 inline h-4 w-4" />
              {analysis.disclaimer}
            </div>
          </div>
        )}
      </Card>
    </div>
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
    <section className="rounded-xl border border-amber-300 bg-amber-500/5 p-4 text-amber-950 dark:border-amber-500/20 dark:bg-amber-500/5 dark:text-amber-200">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700 dark:text-amber-350" />
        <div>
          <p className="text-xs font-black">Imagem não adequada para análise de ferida</p>
          <p className="mt-2 text-xs leading-relaxed text-heal-muted dark:text-zinc-400">
            {analysis.blockedReason ||
              'O HEAL Analyzer não identificou uma ferida visível na ROI marcada. Revise a imagem ou marque corretamente a região da ferida.'}
          </p>
        </div>
      </div>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <Button type="button" variant="secondary" className="justify-center text-[10px] h-9" onClick={onEditRoi}>
          <Target className="h-3.5 w-3.5" />
          Editar ROI
        </Button>
        <Button type="button" variant="secondary" className="justify-center text-[10px] h-9" onClick={onSelectImage}>
          <ImagePlus className="h-3.5 w-3.5" />
          Trocar imagem
        </Button>
      </div>
    </section>
  );
}

function tissueLabel(label: ClinicalAnalysisResult['tissueClassification']['classes'][number]['label']) {
  if (label === 'granulation') return 'Granulação';
  if (label === 'slough_fibrin') return 'Esfacelo / Fibrina';
  if (label === 'necrosis') return 'Necrose';
  if (label === 'epithelial') return 'Epitelização';
  return 'Indeterminado';
}

function TissueClassificationList({ classes }: { classes: ClinicalAnalysisResult['tissueClassification']['classes'] }) {
  return (
    <div className="space-y-3">
      {classes.map(item => (
        <div key={item.label} className="text-xs">
          <div className="flex items-center justify-between font-bold">
            <span className="text-heal-ink dark:text-white">{tissueLabel(item.label)}</span>
            <span className="text-heal-blue">{item.percentage}%</span>
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-heal-canvas dark:bg-zinc-900">
            <div className="h-full rounded-full bg-heal-blue transition-all" style={{ width: `${item.percentage}%` }} />
          </div>
          <p className="mt-1 text-[10px] text-heal-muted dark:text-zinc-500 font-medium">Confiança: {Math.round(item.confidence * 100)}%</p>
        </div>
      ))}
    </div>
  );
}

function ResultSection({ children, icon, title }: { children: ReactNode; icon: ReactNode; title: string }) {
  return (
    <div className="border-b border-heal-line/40 dark:border-zinc-800/40 pb-5 pt-1 last:border-b-0 last:pb-0">
      <div className="mb-3 flex items-center gap-2 text-heal-ink dark:text-white">
        <span className="text-heal-blue shrink-0">{icon}</span>
        <p className="text-sm font-black tracking-tight">{title}</p>
      </div>
      {children}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-xs">
      <span className="text-heal-muted dark:text-zinc-400 font-semibold">{label}</span>
      <span className="text-right font-black text-heal-ink dark:text-white">{value}</span>
    </div>
  );
}

function ColorBreakdown({ colors }: { colors: ClinicalAnalysisResult['visualFindings']['dominantColors'] }) {
  if (!colors.length) return <p className="text-xs text-heal-muted dark:text-zinc-400">Sem cores dominantes calculadas.</p>;
  return (
    <div className="grid grid-cols-2 gap-2">
      {colors.slice(0, 4).map(color => (
        <div key={color.label} className="flex items-center justify-between rounded-xl border border-heal-line/40 bg-heal-canvas/30 px-3 py-2 text-xs dark:border-zinc-800/40 dark:bg-zinc-950/30">
          <span className="inline-flex items-center gap-2 font-medium text-heal-muted dark:text-zinc-400">
            <span className="h-2.5 w-2.5 rounded-full shrink-0 shadow-sm" style={{ backgroundColor: color.hex }} />
            {color.label}
          </span>
          <span className="font-black text-heal-ink dark:text-white">{color.percentage}%</span>
        </div>
      ))}
    </div>
  );
}

function AlertList({ alerts }: { alerts: ClinicalAnalysisAlert[] }) {
  if (!alerts.length) return <p className="text-xs text-heal-muted dark:text-zinc-400">Nenhum alerta clínico assistivo foi gerado com os dados atuais.</p>;
  return (
    <div className="space-y-2">
      {alerts.map(alert => (
        <div
          key={`${alert.title}-${alert.message}`}
          className={cn(
            'rounded-xl border p-3 text-xs leading-relaxed',
            alert.severity === 'high'
              ? 'border-red-200/60 bg-red-500/5 text-red-950 dark:border-red-950/40 dark:bg-red-500/5 dark:text-red-200'
              : alert.severity === 'medium'
                ? 'border-amber-200/60 bg-amber-500/5 text-amber-950 dark:border-amber-950/40 dark:bg-amber-500/5 dark:text-amber-200'
                : 'border-sky-200/60 bg-sky-500/5 text-sky-950 dark:border-sky-950/40 dark:bg-sky-500/5 dark:text-sky-200'
          )}
        >
          <p className="font-black mb-0.5">{alert.title}</p>
          <p className="text-heal-muted dark:text-zinc-400 font-medium">{alert.message}</p>
        </div>
      ))}
    </div>
  );
}

function TagList({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map(item => (
        <span
          key={item}
          className="inline-flex items-center rounded-lg border border-heal-line/50 bg-heal-canvas/40 px-2.5 py-1 text-[11px] font-semibold text-heal-muted dark:border-zinc-800/60 dark:bg-zinc-950/40 dark:text-zinc-400"
        >
          {item}
        </span>
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
