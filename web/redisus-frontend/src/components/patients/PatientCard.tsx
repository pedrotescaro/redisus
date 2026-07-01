import { Archive, ArchiveRestore, Edit, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';

import type { Patient } from '../../lib/types';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/button';

interface PatientCardProps {
  patient: Patient;
  onEdit: (patient: Patient) => void;
  onArchive: (patient: Patient) => void;
}

export function PatientCard({ patient, onEdit, onArchive }: PatientCardProps) {
  return (
    <article className="rounded-card border border-heal-line bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-heal-blue/40 hover:shadow-soft dark:border-zinc-800 dark:bg-zinc-900 flex flex-col justify-between h-full">
      <div>
        <Link to={`/patients/${patient.id}`} className="flex items-start gap-3 min-w-0">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-heal-softBlue text-heal-blue dark:bg-blue-950/40">
            <UserRound className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <h3 className="truncate text-base font-black text-heal-ink dark:text-white" title={patient.name}>{patient.name}</h3>
              <Badge tone={patient.archived ? 'slate' : 'green'}>{patient.archived ? 'Arquivado' : 'Ativo'}</Badge>
            </div>
            <p className="mt-1.5 text-xs text-heal-muted dark:text-zinc-400 truncate" title={patient.phone}>
              <strong>Tel:</strong> {patient.phone || 'Sem telefone'}
            </p>
            <p className="mt-0.5 text-xs text-heal-muted dark:text-zinc-400 truncate" title={patient.email}>
              <strong>Email:</strong> {patient.email || 'Sem e-mail'}
            </p>
          </div>
        </Link>
      </div>

      <div className="mt-4 pt-3 border-t border-heal-line/60 dark:border-zinc-800/60 flex items-center justify-end gap-2">
        <Button 
          type="button" 
          variant="secondary" 
          icon={<Edit className="h-3.5 w-3.5" />} 
          onClick={() => onEdit(patient)}
          className="text-xs py-1 px-3"
        >
          Editar
        </Button>
        <Button
          type="button"
          variant="secondary"
          icon={patient.archived ? <ArchiveRestore className="h-3.5 w-3.5" /> : <Archive className="h-3.5 w-3.5" />}
          onClick={() => onArchive(patient)}
          className="text-xs py-1 px-3"
        >
          {patient.archived ? 'Desarquivar' : 'Arquivar'}
        </Button>
      </div>
    </article>
  );
}
