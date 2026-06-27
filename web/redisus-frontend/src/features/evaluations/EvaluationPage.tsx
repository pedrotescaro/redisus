import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { useAuth } from '../../app/providers/AuthProvider';
import { LoadingState } from '../../components/ui/LoadingState';
import { PageHeader } from '../../components/ui/PageHeader';
import type { Patient } from '../../lib/types';
import { subscribePatients } from '../patients/patientService';
import { EvaluationForm } from './EvaluationForm';
import { createEvaluation } from './evaluationService';
import type { EvaluationFormValues } from './evaluationSchema';
import type { ImageDraft } from '../../lib/types';

export function EvaluationPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return undefined;
    return subscribePatients(user.uid, next => {
      setPatients(next.filter(patient => !patient.archived));
      setLoading(false);
    });
  }, [user]);

  const handleSubmit = async (values: EvaluationFormValues, images: ImageDraft[]) => {
    if (!user) return;
    const result = await createEvaluation(user.uid, values, images);
    navigate(`/patients/${values.patientId}`, {
      state: result.imageUploadError
        ? {
            evaluationNotice: {
              type: 'warning',
              message: result.imageUploadError
            }
          }
        : {
            evaluationNotice: {
              type: 'success',
              message: 'Avaliação salva com sucesso.'
            }
          }
    });
  };

  if (loading) return <LoadingState label="Carregando pacientes..." />;

  return (
    <div className="flex flex-col xl:flex-row min-h-screen min-w-0 bg-white dark:bg-[#0c0c0e]">
      {/* Coluna Central */}
      <div className="flex-grow max-w-4xl w-full border-r border-heal-line dark:border-zinc-800/60 min-h-screen flex flex-col min-w-0">
        <PageHeader
          showBack
          title="Nova avaliação"
          description="Fluxo estruturado de ferida, imagem e ROI"
        />
        
        <div className="p-4 sm:p-6">
          <EvaluationForm patients={patients} defaultPatientId={searchParams.get('patientId') || undefined} onSubmit={handleSubmit} />
        </div>
      </div>
    </div>
  );
}
