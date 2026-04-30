import { Archive, ArchiveRestore, Edit, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';

import type { Patient } from '../../lib/types';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

interface PatientCardProps {
  patient: Patient;
  onEdit: (patient: Patient) => void;
  onArchive: (patient: Patient) => void;
}

export function PatientCard({ patient, onEdit, onArchive }: PatientCardProps) {
  return (
    <article className="rounded-card border border-heal-line bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-heal-blue/40 hover:shadow-soft dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <Link to={`/patients/${patient.id}`} className="flex min-w-0 items-center gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue">
            <UserRound className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="truncate text-base font-black text-heal-ink dark:text-white">{patient.name}</h3>
              <Badge tone={patient.archived ? 'slate' : 'green'}>{patient.archived ? 'Arquivado' : 'Ativo'}</Badge>
            </div>
            <p className="mt-1 truncate text-sm text-heal-muted dark:text-zinc-400">
              {patient.phone || 'Sem telefone'} - {patient.email || 'sem e-mail'}
            </p>
          </div>
        </Link>

        <div className="flex flex-wrap gap-2 md:justify-end">
          <Button type="button" variant="secondary" icon={<Edit className="h-4 w-4" />} onClick={() => onEdit(patient)}>
            Editar
          </Button>
          <Button
            type="button"
            variant="secondary"
            icon={patient.archived ? <ArchiveRestore className="h-4 w-4" /> : <Archive className="h-4 w-4" />}
            onClick={() => onArchive(patient)}
          >
            {patient.archived ? 'Desarquivar' : 'Arquivar'}
          </Button>
        </div>
      </div>
    </article>
  );
}
