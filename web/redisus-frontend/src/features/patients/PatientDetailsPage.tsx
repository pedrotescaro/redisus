import {
  AlertTriangle,
  CalendarPlus,
  ClipboardPlus,
  Mail,
  Pencil,
  Phone,
  ScanSearch,
  UserRound,
  Calendar,
  MapPin,
  Activity,
  FileText,
  Droplet,
  Layers,
  ShieldAlert,
  Archive,
  Image as ImageIcon,
  Download,
  ZoomIn
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import { RoiImageOverlay } from '../../components/roi/RoiImageOverlay';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { LoadingState } from '../../components/ui/LoadingState';
import { Modal } from '../../components/ui/Modal';
import { PageHeader } from '../../components/ui/PageHeader';
import { formatDate } from '../../lib/date';
import type { Evaluation, ImageDraft, Patient } from '../../lib/types';
import { listEvaluations, updateEvaluation } from '../evaluations/evaluationService';
import type { EvaluationFormValues } from '../evaluations/evaluationSchema';
import { ClinicalEvaluationEditModal } from './ClinicalEvaluationEditModal';
import { getPatient, updatePatient } from './patientService';
import { PatientForm } from './PatientForm';
import type { PatientFormValues } from './patientSchema';
import { WoundEvolutionChart } from '../../components/charts/WoundEvolutionChart';

const CLINICAL_EDIT_WARNING =
  'Este registro contém informações clínicas sensíveis. Alterações incorretas podem comprometer o acompanhamento da evolução da ferida, a segurança do paciente e a integridade do histórico assistencial. Edite apenas se tiver certeza e mantenha as informações fiéis ao atendimento realizado.';

function clinicalAuditSnapshot(evaluation: Evaluation): Record<string, unknown> {
  return {
    id: evaluation.id,
    date: evaluation.date,
    woundLocation: evaluation.woundLocation,
    woundEtiology: evaluation.woundEtiology,
    painLevel: evaluation.painLevel,
    exudateAmount: evaluation.exudateAmount,
    exudateType: evaluation.exudateType,
    notes: evaluation.notes,
    imageCount: evaluation.images.length,
    images: evaluation.images.map(image => ({
      id: image.id,
      storagePath: image.storagePath,
      fileName: image.fileName,
      roiCount: image.rois.length
    }))
  };
}

export function PatientDetailsPage() {
  const { patientId = '' } = useParams();
  const location = useLocation();
  const { user } = useAuth();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [loading, setLoading] = useState(true);
  const [isEditingPatient, setIsEditingPatient] = useState(false);
  const [pendingEditEvaluation, setPendingEditEvaluation] = useState<Evaluation | null>(null);
  const [editingEvaluation, setEditingEvaluation] = useState<Evaluation | null>(null);
  const [savingClinicalEdit, setSavingClinicalEdit] = useState(false);
  const [clinicalEditError, setClinicalEditError] = useState('');
  const [clinicalEditNotice, setClinicalEditNotice] = useState('');
  const notice = (location.state as { evaluationNotice?: { type: 'success' | 'warning'; message: string } } | null)?.evaluationNotice;

  const EVALUATIONS_PAGE_SIZE = 5;
  const [visibleCount, setVisibleCount] = useState(EVALUATIONS_PAGE_SIZE);
  const [activeTab, setActiveTab] = useState<'avaliacoes' | 'imagens' | 'tecidos'>('avaliacoes');

  const handleEditPatientSubmit = async (values: PatientFormValues) => {
    if (!user || !patient) return;
    try {
      await updatePatient(user.uid, patient.id, values);
      const nextPatient = await getPatient(user.uid, patient.id);
      setPatient(nextPatient);
      setIsEditingPatient(false);
      setClinicalEditNotice('Cadastro do paciente atualizado com sucesso.');
    } catch (err: any) {
      alert('Erro ao atualizar dados do paciente: ' + (err.message || String(err)));
    }
  };

  useEffect(() => {
    if (!user || !patientId) return;
    void Promise.all([getPatient(user.uid, patientId), listEvaluations(user.uid, patientId)]).then(([nextPatient, nextEvaluations]) => {
      setPatient(nextPatient);
      setEvaluations(nextEvaluations);
      setLoading(false);
    });
  }, [patientId, user]);

  useEffect(() => {
    setVisibleCount(EVALUATIONS_PAGE_SIZE);
  }, [patientId]);

  const openClinicalEdit = () => {
    if (!pendingEditEvaluation) return;
    setEditingEvaluation(pendingEditEvaluation);
    setPendingEditEvaluation(null);
    setClinicalEditError('');
  };

  const closeClinicalEdit = () => {
    if (savingClinicalEdit) return;
    setEditingEvaluation(null);
    setClinicalEditError('');
  };

  const saveClinicalEdit = async (values: EvaluationFormValues, images: ImageDraft[]) => {
    if (!user || !editingEvaluation) return;
    setSavingClinicalEdit(true);
    setClinicalEditError('');
    setClinicalEditNotice('');

    try {
      await updateEvaluation(user.uid, values, editingEvaluation.id, images, {
        updatedBy: user.uid,
        previousData: clinicalAuditSnapshot(editingEvaluation)
      });
      const nextEvaluations = await listEvaluations(user.uid, patientId);
      setEvaluations(nextEvaluations);
      setEditingEvaluation(null);
      setClinicalEditNotice('Registro clínico atualizado com sucesso.');
    } catch (error) {
      setClinicalEditError(error instanceof Error ? error.message : 'Não foi possível atualizar o registro clínico.');
    } finally {
      setSavingClinicalEdit(false);
    }
  };

  if (loading) return <LoadingState label="Carregando prontuário..." />;
  if (!patient) return <EmptyState title="Paciente não encontrado" description="Verifique se o paciente existe para o usuário logado." />;

  const patientDashboardHeader = (
    <div className="w-full border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-[#0c0c0e] p-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-br from-heal-blue to-purple-600 text-white flex items-center justify-center shadow-md select-none shrink-0">
            <UserRound className="h-6 w-6 sm:h-7 sm:w-7" />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-zinc-900 dark:text-white leading-tight flex items-center gap-2 flex-wrap">
              {patient.name}
              <Badge tone={patient.archived ? 'slate' : 'green'} dot>
                {patient.archived ? 'Arquivado' : 'Ativo'}
              </Badge>
            </h1>
            <p className="text-xs text-zinc-400 dark:text-zinc-500 font-semibold mt-1">ID do Paciente: {patient.id.slice(0, 8)}</p>
          </div>
        </div>
        
        {/* Actions Row */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            className="rounded-full border border-zinc-300 dark:border-zinc-700 px-4 py-2 text-xs font-bold text-zinc-850 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-900/60 transition active:scale-95 select-none"
            onClick={() => setIsEditingPatient(true)}
          >
            Editar Cadastro
          </button>
          <Link to={`/evaluations/new?patientId=${patient.id}`}>
            <button className="rounded-full bg-heal-blue hover:bg-heal-blueDark text-white font-bold px-4 py-2 text-xs transition active:scale-95 shadow-sm">
              Nova Avaliação
            </button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-5 text-xs text-zinc-500 dark:text-zinc-400 font-semibold border-t border-zinc-100 dark:border-zinc-900 pt-4">
        <div>
          <span className="text-[10px] text-zinc-400 dark:text-zinc-500 font-black uppercase tracking-wider block mb-1">Contato</span>
          <p className="text-zinc-800 dark:text-zinc-200 text-sm font-bold flex items-center gap-1">
            <Phone className="h-3.5 w-3.5 opacity-75 shrink-0" /> {patient.phone}
          </p>
          {patient.email && (
            <p className="text-zinc-650 dark:text-zinc-300 font-medium flex items-center gap-1 mt-1 truncate">
              <Mail className="h-3.5 w-3.5 opacity-75 shrink-0" /> {patient.email}
            </p>
          )}
        </div>
        <div>
          <span className="text-[10px] text-zinc-400 dark:text-zinc-500 font-black uppercase tracking-wider block mb-1">Data de Nascimento</span>
          <p className="text-zinc-800 dark:text-zinc-200 text-sm font-bold flex items-center gap-1">
            <Calendar className="h-3.5 w-3.5 opacity-75 shrink-0" /> {formatDate(patient.birthDate)}
          </p>
        </div>
        <div>
          <span className="text-[10px] text-zinc-400 dark:text-zinc-500 font-black uppercase tracking-wider block mb-1">Notas do Prontuário</span>
          <p className="text-zinc-800 dark:text-zinc-200 text-sm font-medium italic truncate max-w-xs" title={patient.notes || 'Sem observações'}>
            {patient.notes ? `"${patient.notes}"` : 'Sem observações'}
          </p>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex flex-col lg:flex-row min-h-screen min-w-0 bg-white dark:bg-[#0c0c0e]">
      {/* Coluna Central (Timeline de Avaliações) */}
      <div className="flex-grow max-w-2xl w-full border-r border-zinc-200 dark:border-zinc-800 min-h-screen flex flex-col min-w-0">
        
        {/* Sticky Header */}
        <div className="sticky top-0 z-10 bg-white/80 dark:bg-[#0c0c0e]/80 backdrop-blur-md border-b border-zinc-200 dark:border-zinc-800 px-4 py-2.5 flex items-center gap-4">
          <PageHeader showBack title={patient.name} description="Prontuário Clínico & Evolução" />
        </div>

        {notice ? (
          <div
            role="status"
            className="m-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-bold text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-300"
          >
            {notice.message}
          </div>
        ) : null}

        {clinicalEditNotice ? (
          <div role="status" className="m-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-800 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-300">
            {clinicalEditNotice}
          </div>
        ) : null}

        {/* Dashboard Patient Header */}
        {patientDashboardHeader}

        {/* Navigation Tabs */}
        <div className="flex border-b border-zinc-200 dark:border-zinc-800 select-none">
          {(['avaliacoes', 'imagens', 'tecidos'] as const).map((tab) => {
            const labels = { avaliacoes: `Avaliações Clínicas (${evaluations.length})`, imagens: 'Banco de Imagens', tecidos: 'Evolução de Tecidos' };
            const isActive = activeTab === tab;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 py-3.5 text-xs sm:text-sm font-semibold text-center transition ${
                  isActive
                    ? 'font-black border-b-4 border-heal-blue text-zinc-900 dark:text-white bg-zinc-50/50 dark:bg-zinc-900/20'
                    : 'text-zinc-500 dark:text-zinc-500 hover:bg-zinc-50 dark:hover:bg-zinc-900/50'
                }`}
              >
                {labels[tab]}
              </button>
            );
          })}
        </div>

        {/* === TAB: Avaliações Clínicas === */}
        {activeTab === 'avaliacoes' && (
          <>
            <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {evaluations.length ? (
                evaluations.slice(0, visibleCount).map((evaluation) => {
                  const hasInfection = evaluation.infectionSigns && evaluation.infectionSigns.length > 0;
                  return (
                    <div key={evaluation.id} className="p-5 hover:bg-zinc-50/20 dark:hover:bg-zinc-900/10 transition border-b border-zinc-200 dark:border-zinc-800">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                        <div className="flex items-center gap-2">
                          <Badge tone="blue">{formatDate(evaluation.date)}</Badge>
                          <h4 className="text-sm font-bold text-zinc-900 dark:text-white flex items-center gap-1">
                            <MapPin className="h-3.5 w-3.5 text-zinc-400" />
                            {evaluation.woundLocation}
                          </h4>
                        </div>
                        {/* Pain level indicator */}
                        <div className="flex items-center gap-1.5 text-xs font-semibold">
                          <span className="text-zinc-400 dark:text-zinc-500">Nível de Dor:</span>
                          <div className="flex gap-0.5" title={`Dor: ${evaluation.painLevel}/10`}>
                            {Array.from({ length: 10 }).map((_, idx) => (
                              <div
                                key={idx}
                                className={`w-2.5 h-3.5 rounded-sm ${
                                  idx < evaluation.painLevel
                                    ? evaluation.painLevel >= 7
                                      ? 'bg-red-500'
                                      : evaluation.painLevel >= 4
                                      ? 'bg-amber-500'
                                      : 'bg-emerald-500'
                                    : 'bg-zinc-100 dark:bg-zinc-800'
                                }`}
                              />
                            ))}
                          </div>
                          <span className="text-zinc-900 dark:text-white font-extrabold">{evaluation.painLevel}/10</span>
                        </div>
                      </div>

                      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400 font-semibold">
                        Etiologia: <span className="text-zinc-800 dark:text-zinc-200 font-bold">{evaluation.woundEtiology}</span> · Exsudato: <span className="text-zinc-800 dark:text-zinc-200 font-bold">{evaluation.exudateAmount} ({evaluation.exudateType})</span>
                      </p>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs bg-zinc-50 dark:bg-zinc-900/30 border border-zinc-100 dark:border-zinc-800/40 rounded-xl p-3 mt-3">
                        <div>
                          <span className="font-bold text-zinc-400 dark:text-zinc-500">Características da borda:</span>
                          <p className="text-zinc-700 dark:text-zinc-300 font-semibold mt-0.5">{evaluation.borderCharacteristics || 'Não descrita'}</p>
                        </div>
                        <div>
                          <span className="font-bold text-zinc-400 dark:text-zinc-500">Pele perilesional:</span>
                          <p className="text-zinc-700 dark:text-zinc-300 font-semibold mt-0.5">{evaluation.periwoundSkin || 'Não descrita'}</p>
                        </div>
                      </div>

                      {hasInfection && (
                        <div className="rounded-xl border border-red-200 bg-red-50/50 dark:border-red-950/40 dark:bg-red-950/15 p-3 text-xs text-red-700 dark:text-red-300 mt-3 flex items-start gap-2">
                          <ShieldAlert className="h-4 w-4 shrink-0 text-red-500" />
                          <div>
                            <p className="font-extrabold text-red-800 dark:text-red-200">Sinais de infecção presentes:</p>
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              {evaluation.infectionSigns.map(sign => (
                                <span key={sign} className="px-2.5 py-0.5 rounded-full bg-red-100 dark:bg-red-900/50 text-[10px] font-bold">
                                  {sign}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}

                      {evaluation.notes && (
                        <div className="mt-3 bg-zinc-50/50 dark:bg-zinc-900/10 border-l-2 border-zinc-300 dark:border-zinc-700 pl-3 py-1">
                          <p className="text-xs text-zinc-400 dark:text-zinc-500 font-semibold uppercase tracking-wider">Observações Clínicas</p>
                          <p className="text-sm text-zinc-800 dark:text-zinc-200 leading-relaxed font-medium mt-0.5 whitespace-pre-wrap">
                            {evaluation.notes}
                          </p>
                        </div>
                      )}

                      {/* Attachment image with ROI */}
                      <div className="relative aspect-[16/9] w-full max-w-xl overflow-hidden rounded-xl bg-zinc-950 border border-zinc-200 dark:border-zinc-800 mt-3">
                        {evaluation.images[0] ? (
                          <>
                            <img src={evaluation.images[0].downloadURL} alt="" className="h-full w-full object-contain" />
                            <RoiImageOverlay rois={evaluation.images[0].rois} />
                          </>
                        ) : (
                          <div className="flex h-full items-center justify-center text-xs text-zinc-500">Sem imagem registrada</div>
                        )}
                      </div>

                      {/* Tags list: comorbidities and medications */}
                      <div className="flex flex-wrap gap-3 mt-3 text-xs">
                        {evaluation.comorbidities && evaluation.comorbidities.length > 0 && (
                          <div className="flex items-center gap-1.5">
                            <span className="text-[10px] uppercase font-bold text-zinc-400">Comorbidades:</span>
                            {evaluation.comorbidities.map(c => (
                              <span key={c} className="px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-850 text-zinc-650 dark:text-zinc-400 font-bold text-[10px]">{c}</span>
                            ))}
                          </div>
                        )}
                        {evaluation.medications && evaluation.medications.length > 0 && (
                          <div className="flex items-center gap-1.5">
                            <span className="text-[10px] uppercase font-bold text-zinc-400">Medicação:</span>
                            {evaluation.medications.map(m => (
                              <span key={m} className="px-2 py-0.5 rounded bg-purple-50 dark:bg-purple-950/20 text-purple-600 dark:text-purple-300 font-bold text-[10px]">{m}</span>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Actions Bar */}
                      <div className="flex items-center gap-3 border-t border-zinc-100 dark:border-zinc-900 pt-3 mt-4">
                        <Link
                          to={`/analyzer?patientId=${patient.id}&assessmentId=${evaluation.id}`}
                          className="flex items-center gap-1.5 py-1.5 px-3 rounded-full border border-heal-teal/20 bg-heal-tealSoft hover:bg-heal-teal text-heal-teal hover:text-white transition text-xs font-bold dark:border-teal-400/20 dark:bg-teal-950/40 dark:text-teal-300 dark:hover:bg-heal-teal dark:hover:text-white select-none"
                        >
                          <ScanSearch className="h-3.5 w-3.5" />
                          Analisar IA
                        </Link>
                        <button
                          type="button"
                          className="flex items-center gap-1.5 py-1.5 px-3 rounded-full border border-heal-blue/20 bg-heal-softBlue hover:bg-heal-blue text-heal-blue hover:text-white transition text-xs font-bold dark:border-blue-400/20 dark:bg-blue-950/40 dark:text-blue-300 dark:hover:bg-heal-blue dark:hover:text-white select-none"
                          onClick={() => {
                            setClinicalEditNotice('');
                            setPendingEditEvaluation(evaluation);
                          }}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          Editar Registro
                        </button>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="p-8">
                  <EmptyState title="Sem registros clínicos" description="Cadastre a primeira avaliação clínica deste paciente para iniciar a timeline." />
                </div>
              )}
            </div>

            {/* Load more button */}
            {visibleCount < evaluations.length && (
              <div className="flex justify-center p-4 border-t border-zinc-200 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setVisibleCount(prev => prev + EVALUATIONS_PAGE_SIZE)}
                  className="w-full py-3 bg-zinc-50 dark:bg-zinc-900/50 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-900 dark:text-white rounded-xl text-xs font-black transition cursor-pointer select-none border border-zinc-200/60 dark:border-zinc-800"
                >
                  Mostrar mais avaliações
                </button>
              </div>
            )}
          </>
        )}

        {/* === TAB: Banco de Imagens === */}
        {activeTab === 'imagens' && (
          <div className="p-4">
            {(() => {
              const allImages = evaluations.flatMap(ev =>
                ev.images.map(img => ({ ...img, evaluationDate: ev.date, evaluationId: ev.id, woundLocation: ev.woundLocation }))
              );
              if (allImages.length === 0) {
                return <EmptyState title="Nenhuma imagem registrada" description="As imagens de ferida aparecerão aqui conforme as avaliações clínicas forem cadastradas." />;
              }
              return (
                <>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 font-semibold mb-4">{allImages.length} {allImages.length === 1 ? 'imagem' : 'imagens'} encontradas nas avaliações</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {allImages.map((img) => (
                      <div key={img.id} className="group relative rounded-xl overflow-hidden border border-zinc-200 dark:border-zinc-800 bg-zinc-950 aspect-square cursor-pointer hover:ring-2 hover:ring-heal-blue/50 transition">
                        <img src={img.downloadURL} alt={img.fileName} className="h-full w-full object-cover transition group-hover:scale-105" />
                        <RoiImageOverlay rois={img.rois} />
                        {/* Overlay on hover */}
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition flex items-end justify-between p-2 opacity-0 group-hover:opacity-100">
                          <div className="text-white">
                            <p className="text-[10px] font-bold">{formatDate(img.evaluationDate)}</p>
                            <p className="text-[9px] opacity-80">{img.woundLocation}</p>
                          </div>
                          <div className="flex gap-1">
                            <a href={img.downloadURL} target="_blank" rel="noopener noreferrer" className="flex h-7 w-7 items-center justify-center rounded-full bg-white/20 hover:bg-white/40 text-white transition" title="Ampliar">
                              <ZoomIn className="h-3.5 w-3.5" />
                            </a>
                          </div>
                        </div>
                        {/* ROI count badge */}
                        {img.rois.length > 0 && (
                          <div className="absolute top-2 right-2 bg-heal-blue/90 text-white text-[9px] font-black px-1.5 py-0.5 rounded-full">
                            {img.rois.length} ROI{img.rois.length > 1 ? 's' : ''}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              );
            })()}
          </div>
        )}

        {/* === TAB: Evolução de Tecidos === */}
        {activeTab === 'tecidos' && (
          <div className="p-4">
            {evaluations.length === 0 ? (
              <EmptyState title="Nenhuma avaliação registrada" description="Os dados de evolução de tecidos aparecerão aqui conforme as avaliações forem cadastradas." />
            ) : (
              <>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 font-semibold mb-4">Evolução dos parâmetros TIME-R ao longo de {evaluations.length} {evaluations.length === 1 ? 'avaliação' : 'avaliações'}</p>

                {/* Wound Evolution Chart */}
                <div className="mb-6">
                  <WoundEvolutionChart evaluations={evaluations} />
                </div>

                {/* TIME-R legend */}
                <div className="flex flex-wrap gap-2 mb-5">
                  {[
                    { key: 'tissue', label: 'Tecido', color: 'bg-red-500' },
                    { key: 'infection', label: 'Infecção', color: 'bg-amber-500' },
                    { key: 'moisture', label: 'Umidade', color: 'bg-blue-500' },
                    { key: 'edge', label: 'Borda', color: 'bg-emerald-500' },
                    { key: 'repair', label: 'Reparo', color: 'bg-purple-500' },
                    { key: 'social', label: 'Social', color: 'bg-pink-500' },
                  ].map(item => (
                    <div key={item.key} className="flex items-center gap-1.5 text-[10px] font-bold text-zinc-500 dark:text-zinc-400">
                      <div className={`w-2.5 h-2.5 rounded-full ${item.color}`} />
                      {item.label}
                    </div>
                  ))}
                </div>

                {/* Timeline of evaluations with tissue data */}
                <div className="space-y-4">
                  {evaluations.map((evaluation, idx) => {
                    const timerLabels: Record<string, { label: string; color: string; bg: string }> = {
                      tissue: { label: 'Tecido', color: 'text-red-600 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-900/40' },
                      infection: { label: 'Infecção', color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-900/40' },
                      moisture: { label: 'Umidade', color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-900/40' },
                      edge: { label: 'Borda', color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900/40' },
                      repair: { label: 'Reparo', color: 'text-purple-600 dark:text-purple-400', bg: 'bg-purple-50 dark:bg-purple-950/30 border-purple-200 dark:border-purple-900/40' },
                      social: { label: 'Social', color: 'text-pink-600 dark:text-pink-400', bg: 'bg-pink-50 dark:bg-pink-950/30 border-pink-200 dark:border-pink-900/40' },
                    };
                    return (
                      <div key={evaluation.id} className="relative">
                        {/* Timeline connector */}
                        {idx < evaluations.length - 1 && (
                          <div className="absolute left-[15px] top-10 bottom-0 w-0.5 bg-zinc-200 dark:bg-zinc-800" />
                        )}
                        <div className="flex gap-3">
                          {/* Timeline dot */}
                          <div className="shrink-0 w-[30px] flex flex-col items-center">
                            <div className="w-3.5 h-3.5 rounded-full bg-heal-blue border-2 border-white dark:border-zinc-900 shadow-sm mt-1" />
                          </div>
                          {/* Content */}
                          <div className="flex-grow pb-4 min-w-0">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-sm font-black text-zinc-900 dark:text-white">{formatDate(evaluation.date)}</span>
                              <Badge tone="blue" className="text-[10px]">{evaluation.woundLocation}</Badge>
                            </div>

                            {/* Tissue parameters grid */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {Object.entries(evaluation.timers || {}).map(([key, value]) => {
                                const meta = timerLabels[key];
                                if (!meta || !value) return null;
                                // Parse pipe-delimited "Key: Value | Key: Value" format
                                const segments = String(value).split('|').map(s => s.trim()).filter(Boolean);
                                return (
                                  <div key={key} className={`rounded-lg border p-3 ${meta.bg}`}>
                                    <p className={`text-[10px] font-black uppercase tracking-wider mb-2 ${meta.color}`}>{meta.label}</p>
                                    <div className="space-y-1.5">
                                      {segments.map((segment, si) => {
                                        const colonIdx = segment.indexOf(':');
                                        if (colonIdx > 0) {
                                          const label = segment.slice(0, colonIdx).trim();
                                          const val = segment.slice(colonIdx + 1).trim();
                                          return (
                                            <div key={si} className="flex justify-between gap-2 text-[11px] leading-tight">
                                              <span className="text-zinc-500 dark:text-zinc-400 font-semibold shrink-0">{label}</span>
                                              <span className="text-zinc-800 dark:text-zinc-200 font-bold text-right">{val}</span>
                                            </div>
                                          );
                                        }
                                        return <p key={si} className="text-[11px] text-zinc-700 dark:text-zinc-300 font-semibold leading-tight">{segment}</p>;
                                      })}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>

                            {/* Additional context */}
                            <div className="flex flex-wrap gap-2 mt-2 text-[10px]">
                              <span className="text-zinc-500 dark:text-zinc-400 font-semibold">Etiologia: <span className="text-zinc-800 dark:text-zinc-200 font-bold">{evaluation.woundEtiology}</span></span>
                              <span className="text-zinc-500 dark:text-zinc-400 font-semibold">Exsudato: <span className="text-zinc-800 dark:text-zinc-200 font-bold">{evaluation.exudateAmount}</span></span>
                              <span className="text-zinc-500 dark:text-zinc-400 font-semibold">Dor: <span className="text-zinc-800 dark:text-zinc-200 font-bold">{evaluation.painLevel}/10</span></span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Coluna Direita (Widgets Clínicos) */}
      <aside className="hidden md:block w-80 shrink-0 p-4 space-y-4 min-h-screen">
        
        {/* Ações Rápidas Box */}
        <div className="bg-zinc-50 dark:bg-zinc-900/40 rounded-2xl border border-zinc-100 dark:border-zinc-800 p-4 space-y-3">
          <h3 className="text-sm font-black text-zinc-900 dark:text-white uppercase tracking-wider">Ações rápidas</h3>
          <div className="grid gap-2">
            <Link to={`/evaluations/new?patientId=${patient.id}`} className="w-full">
              <button className="w-full rounded-full bg-heal-blue hover:bg-heal-blueDark text-white font-bold py-2.5 text-xs transition active:scale-95 shadow-sm">
                Fazer Nova Avaliação
              </button>
            </Link>
            <Link to={`/agenda?patientId=${patient.id}`} className="w-full">
              <button className="w-full rounded-full border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-800 dark:text-white font-bold py-2.5 text-xs transition active:scale-95">
                Agendar Consulta
              </button>
            </Link>
          </div>
        </div>

        {/* Trends Box: Alertas Clínicos & Comorbidades */}
        <div className="bg-zinc-50 dark:bg-zinc-900/40 rounded-2xl border border-zinc-100 dark:border-zinc-800 overflow-hidden">
          <div className="p-4 border-b border-zinc-100 dark:border-zinc-800">
            <h3 className="text-sm font-black text-zinc-900 dark:text-white uppercase tracking-wider">Resumo do Paciente</h3>
          </div>
          
          <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {/* Status Item */}
            <div className="p-4">
              <p className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider">Status do Prontuário</p>
              <p className="text-sm font-extrabold text-zinc-800 dark:text-zinc-200 mt-1">
                {patient.archived ? 'Arquivado' : 'Acompanhamento Ativo'}
              </p>
              <p className="text-xs text-zinc-500 dark:text-zinc-500 mt-0.5">Criado em {patient.createdAt ? formatDate(String(patient.createdAt)) : 'Sem data'}</p>
            </div>

            {/* Total Evaluations */}
            <div className="p-4">
              <p className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider">Total de Fotos & ROI</p>
              <p className="text-sm font-extrabold text-zinc-800 dark:text-zinc-200 mt-1">
                {evaluations.length} Consultas Registradas
              </p>
              <p className="text-xs text-zinc-500 dark:text-zinc-500 mt-0.5">
                Média de dor declarada: {evaluations.length > 0 ? (evaluations.reduce((acc, curr) => acc + curr.painLevel, 0) / evaluations.length).toFixed(1) : 0}/10
              </p>
            </div>

            {/* Comorbidities list styled as trends */}
            <div className="p-4">
              <p className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider">Comorbidades Associadas</p>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {Array.from(new Set(evaluations.flatMap(e => e.comorbidities || []))).length > 0 ? (
                  Array.from(new Set(evaluations.flatMap(e => e.comorbidities || []))).map(c => (
                    <Badge key={c} tone="slate" className="text-[9px] font-black uppercase">{c}</Badge>
                  ))
                ) : (
                  <span className="text-xs text-zinc-400 dark:text-zinc-500 italic">Nenhuma comorbidade</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Warning confirmation modal for editing evaluations */}
      <Modal open={!!pendingEditEvaluation} title="Atenção: edição de dados clínicos" onClose={() => setPendingEditEvaluation(null)} size="lg">
        <div className="space-y-5">
          <div className="flex gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-amber-50 text-amber-600 ring-1 ring-amber-200">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <p className="text-sm leading-6 text-slate-600 dark:text-zinc-300">{CLINICAL_EDIT_WARNING}</p>
          </div>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button type="button" variant="secondary" onClick={() => setPendingEditEvaluation(null)}>
              Cancelar
            </Button>
            <Button type="button" onClick={openClinicalEdit}>
              Entendi, editar registro
            </Button>
          </div>
        </div>
      </Modal>

      {/* Complete evaluation editing modal */}
      <ClinicalEvaluationEditModal
        open={!!editingEvaluation}
        evaluation={editingEvaluation}
        error={clinicalEditError}
        saving={clinicalEditNotice ? false : savingClinicalEdit}
        onClose={closeClinicalEdit}
        onSave={saveClinicalEdit}
      />

      {/* Edit patient cadastral modal */}
      <Modal open={isEditingPatient} title="Editar Cadastro do Paciente" onClose={() => setIsEditingPatient(false)} size="lg">
        <div className="p-1">
          <PatientForm
            patient={patient}
            onSubmit={handleEditPatientSubmit}
            onCancel={() => setIsEditingPatient(false)}
          />
        </div>
      </Modal>
    </div>
  );
}
