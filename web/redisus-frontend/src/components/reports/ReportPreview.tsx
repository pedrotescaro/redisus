import { RoiImageOverlay } from '../roi/RoiImageOverlay';
import { Badge } from '../ui/Badge';
import { Card } from '../ui/Card';
import { CLINICAL_DISCLAIMER } from '../../lib/constants';
import { formatDateLong } from '../../lib/date';
import type { Evaluation, Patient, UserProfile } from '../../lib/types';
import logoUrl from '../../assets/brand/logo.png';

interface ReportPreviewProps {
  patient: Patient;
  evaluation: Evaluation;
  profile: UserProfile | null;
}

export function ReportPreview({ patient, evaluation, profile }: ReportPreviewProps) {
  const image = evaluation.images[0];

  return (
    <Card className="print:border-0 print:shadow-none">
      <div className="flex flex-col justify-between gap-4 border-b border-heal-line pb-5 dark:border-zinc-800 sm:flex-row sm:items-center">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white shadow-sm ring-1 ring-heal-line">
            <img src={logoUrl} alt="Heal+" className="h-10 w-10 object-contain" />
          </div>
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-heal-teal">Relatório clínico Heal+</p>
            <h3 className="mt-1 text-2xl font-black text-heal-ink dark:text-white">{patient.name}</h3>
            <p className="text-sm text-slate-500 dark:text-zinc-400">{formatDateLong(evaluation.date)}</p>
          </div>
        </div>
        <Badge tone="blue">Registro profissional</Badge>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1fr]">
        <div className="space-y-3">
          <Info label="Paciente" value={patient.name} />
          <Info label="Telefone" value={patient.phone} />
          <Info label="E-mail" value={patient.email || 'Não informado'} />
          <Info label="Nascimento" value={patient.birthDate} />
          <Info label="Localização" value={evaluation.woundLocation} />
          <Info label="Etiologia" value={evaluation.woundEtiology} />
          <Info label="Dor" value={`${evaluation.painLevel}/10`} />
          <Info label="Exsudato" value={`${evaluation.exudateAmount} · ${evaluation.exudateType}`} />
          <Info label="Bordas" value={evaluation.borderCharacteristics} />
          <Info label="Pele perilesional" value={evaluation.periwoundSkin} />
        </div>

        <div>
          <div className="relative aspect-[4/3] overflow-hidden rounded-lg bg-slate-950">
            {image ? (
              <>
                <img src={image.downloadURL} alt="Imagem da ferida" className="h-full w-full object-contain" />
                <RoiImageOverlay rois={image.rois} />
              </>
            ) : (
              <div className="flex h-full items-center justify-center text-sm font-semibold text-slate-400">Sem imagem vinculada</div>
            )}
          </div>
          {image?.rois.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {image.rois.map(roi => <Badge key={roi.id} tone="green">{roi.label}</Badge>)}
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {Object.entries(evaluation.timers).map(([key, value]) => (
          <div key={key} className="rounded-lg bg-slate-50 p-3 dark:bg-zinc-950">
            <p className="text-xs font-black uppercase tracking-wide text-heal-blue">{key}</p>
            <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-zinc-300">{value || 'Não informado'}</p>
          </div>
        ))}
      </div>

      {evaluation.notes ? (
        <div className="mt-5 rounded-lg bg-emerald-50 p-4 dark:bg-emerald-950/30">
          <p className="text-sm font-bold text-heal-ink dark:text-white">Observações</p>
          <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-zinc-300">{evaluation.notes}</p>
        </div>
      ) : null}

      <div className="mt-6 border-t border-heal-line pt-4 text-sm text-slate-500 dark:border-zinc-800 dark:text-zinc-400">
        <p>{profile?.displayName ? `Assinatura: ${profile.displayName}` : 'Assinatura: profissional não informado'}</p>
        <p className="mt-2 font-bold text-heal-blue">Cuidado inteligente. Evolução visível.</p>
        <p className="mt-2">{CLINICAL_DISCLAIMER}</p>
      </div>
    </Card>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 dark:bg-zinc-950">
      <span className="text-sm font-semibold text-slate-500 dark:text-zinc-400">{label}</span>
      <span className="text-right text-sm font-bold text-heal-ink dark:text-white">{value}</span>
    </div>
  );
}
