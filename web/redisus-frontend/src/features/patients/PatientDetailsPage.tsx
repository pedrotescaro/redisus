import { AlertTriangle, CalendarPlus, ClipboardPlus, Mail, Pencil, Phone } from 'lucide-react';
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
import { formatDate } from '../../lib/date';
import type { Evaluation, ImageDraft, Patient } from '../../lib/types';
import { listEvaluations, updateEvaluation } from '../evaluations/evaluationService';
import type { EvaluationFormValues } from '../evaluations/evaluationSchema';
import { ClinicalEvaluationEditModal } from './ClinicalEvaluationEditModal';
import { getPatient } from './patientService';

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
  const [pendingEditEvaluation, setPendingEditEvaluation] = useState<Evaluation | null>(null);
  const [editingEvaluation, setEditingEvaluation] = useState<Evaluation | null>(null);
  const [savingClinicalEdit, setSavingClinicalEdit] = useState(false);
  const [clinicalEditError, setClinicalEditError] = useState('');
  const [clinicalEditNotice, setClinicalEditNotice] = useState('');
  const notice = (location.state as { evaluationNotice?: { type: 'success' | 'warning'; message: string } } | null)?.evaluationNotice;

  useEffect(() => {
    if (!user || !patientId) return;
    void Promise.all([getPatient(user.uid, patientId), listEvaluations(user.uid, patientId)]).then(([nextPatient, nextEvaluations]) => {
      setPatient(nextPatient);
      setEvaluations(nextEvaluations);
      setLoading(false);
    });
  }, [patientId, user]);

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

  return (
    <div className="space-y-5">
      {notice ? (
        <div
          role="status"
          className={`rounded-xl border px-4 py-3 text-sm font-bold ${
            notice.type === 'warning'
              ? 'border-amber-200 bg-amber-50 text-amber-800'
              : 'border-emerald-200 bg-emerald-50 text-emerald-800'
          }`}
        >
          {notice.message}
        </div>
      ) : null}

      {clinicalEditNotice ? (
        <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-800">
          {clinicalEditNotice}
        </div>
      ) : null}

      <Card className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-2xl font-black text-heal-ink dark:text-white">{patient.name}</h2>
            <Badge tone={patient.archived ? 'slate' : 'green'}>{patient.archived ? 'Arquivado' : 'Ativo'}</Badge>
          </div>
          <div className="mt-2 flex flex-wrap gap-4 text-sm text-slate-500 dark:text-zinc-400">
            <span className="inline-flex items-center gap-1"><Phone className="h-4 w-4" />{patient.phone}</span>
            <span className="inline-flex items-center gap-1"><Mail className="h-4 w-4" />{patient.email || 'sem e-mail'}</span>
            <span>Nascimento: {formatDate(patient.birthDate)}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/evaluations/new?patientId=${patient.id}`}>
            <Button icon={<ClipboardPlus className="h-4 w-4" />}>Nova avaliação</Button>
          </Link>
          <Link to={`/agenda?patientId=${patient.id}`}>
            <Button variant="secondary" icon={<CalendarPlus className="h-4 w-4" />}>Agendar</Button>
          </Link>
        </div>
      </Card>

      {patient.notes ? <Card><p className="text-sm leading-6 text-slate-600 dark:text-zinc-300">{patient.notes}</p></Card> : null}

      <section className="space-y-3">
        <h3 className="text-lg font-black text-heal-ink dark:text-white">Histórico de avaliações</h3>
        {evaluations.length ? (
          <div className="grid gap-3">
            {evaluations.map(evaluation => (
              <Card key={evaluation.id} className="relative grid gap-4 pt-12 md:grid-cols-[180px_1fr] md:pt-0 md:pr-14">
                <button
                  type="button"
                  aria-label={`Editar registro clínico de ${formatDate(evaluation.date)}`}
                  title="Editar registro clínico"
                  className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-xl border border-heal-blue/20 bg-heal-softBlue text-heal-blue shadow-sm transition hover:border-heal-blue hover:bg-heal-blue hover:text-white focus:outline-none focus:ring-2 focus:ring-heal-blue/25 dark:border-blue-400/20 dark:bg-blue-950/40 dark:text-blue-300 dark:hover:bg-heal-blue dark:hover:text-white"
                  onClick={() => {
                    setClinicalEditNotice('');
                    setPendingEditEvaluation(evaluation);
                  }}
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <div className="relative aspect-[4/3] overflow-hidden rounded-lg bg-slate-950">
                  {evaluation.images[0] ? (
                    <>
                      <img src={evaluation.images[0].downloadURL} alt="" className="h-full w-full object-contain" />
                      <RoiImageOverlay rois={evaluation.images[0].rois} />
                    </>
                  ) : (
                    <div className="flex h-full items-center justify-center text-xs font-semibold text-slate-400">Sem imagem</div>
                  )}
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="blue">{formatDate(evaluation.date)}</Badge>
                    <Badge tone={evaluation.painLevel >= 7 ? 'red' : evaluation.painLevel >= 4 ? 'amber' : 'green'}>Dor {evaluation.painLevel}/10</Badge>
                  </div>
                  <h4 className="mt-2 text-base font-bold text-heal-ink dark:text-white">{evaluation.woundLocation}</h4>
                  <p className="mt-1 text-sm text-slate-500 dark:text-zinc-400">{evaluation.woundEtiology} · {evaluation.exudateAmount} · {evaluation.exudateType}</p>
                  {evaluation.imageUploadStatus === 'failed' ? (
                    <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-bold text-amber-800">
                      {evaluation.imageUploadError || 'Imagens não enviadas ao Firebase Storage.'}
                    </div>
                  ) : null}
                  {evaluation.notes ? <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-zinc-300">{evaluation.notes}</p> : null}
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState title="Sem avaliações" description="Crie uma avaliação para testar subcoleções, upload e ROI." />
        )}
      </section>

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

      <ClinicalEvaluationEditModal
        open={!!editingEvaluation}
        evaluation={editingEvaluation}
        error={clinicalEditError}
        saving={savingClinicalEdit}
        onClose={closeClinicalEdit}
        onSave={saveClinicalEdit}
      />
    </div>
  );
}
