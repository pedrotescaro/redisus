import { CalendarPlus, ClipboardPlus, Mail, Phone } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import { RoiImageOverlay } from '../../components/roi/RoiImageOverlay';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/button';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { LoadingState } from '../../components/ui/LoadingState';
import { formatDate } from '../../lib/date';
import type { Evaluation, Patient } from '../../lib/types';
import { listEvaluations } from '../evaluations/evaluationService';
import { getPatient } from './patientService';

export function PatientDetailsPage() {
  const { patientId = '' } = useParams();
  const location = useLocation();
  const { user } = useAuth();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [evaluations, setEvaluations] = useState<Evaluation[]>([]);
  const [loading, setLoading] = useState(true);
  const notice = (location.state as { evaluationNotice?: { type: 'success' | 'warning'; message: string } } | null)?.evaluationNotice;

  useEffect(() => {
    if (!user || !patientId) return;
    void Promise.all([getPatient(user.uid, patientId), listEvaluations(user.uid, patientId)]).then(([nextPatient, nextEvaluations]) => {
      setPatient(nextPatient);
      setEvaluations(nextEvaluations);
      setLoading(false);
    });
  }, [patientId, user]);

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
              <Card key={evaluation.id} className="grid gap-4 md:grid-cols-[180px_1fr]">
                <div className="relative aspect-[4/3] overflow-hidden rounded-lg bg-slate-100 dark:bg-zinc-800">
                  {evaluation.images[0] ? (
                    <>
                      <img src={evaluation.images[0].downloadURL} alt="" className="h-full w-full object-cover" />
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
    </div>
  );
}
