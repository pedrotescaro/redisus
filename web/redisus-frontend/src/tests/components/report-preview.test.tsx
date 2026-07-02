import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ReportPreview } from '../../components/reports/ReportPreview';
import type { Evaluation, Patient, UserProfile } from '../../lib/types';

const patient: Patient = {
  id: 'p1',
  name: 'Tania Silva',
  phone: '11999999999',
  email: 'tania@heal.plus',
  birthDate: '1985-05-12',
  notes: '',
  archived: false
};

const evaluation: Evaluation = {
  id: 'e1',
  patientId: 'p1',
  patientName: 'Tania Silva',
  date: '2026-04-28',
  woundLocation: 'Regiao Sacral',
  woundEtiology: 'Lesao por Pressao',
  painLevel: 3,
  exudateAmount: 'Pequeno',
  exudateType: 'Seroso',
  borderCharacteristics: 'Regulares',
  periwoundSkin: 'Integra',
  infectionSigns: [],
  timers: { tissue: '', infection: '', moisture: '', edge: '', repair: '', social: '' },
  comorbidities: [],
  medications: [],
  notes: 'Boa evolucao.',
  images: []
};

const profile: UserProfile = {
  displayName: 'Dra Ana',
  email: 'ana@heal.plus',
  role: 'professional',
  settings: { theme: 'light', notificationsEnabled: true }
};

describe('ReportPreview', () => {
  it('mostra dados reais do paciente e avaliacao', () => {
    render(
      <ReportPreview
        patient={patient}
        evaluation={evaluation}
        profile={profile}
        analysis={null}
        loadingAnalysis={false}
        analysisError={null}
        onGenerateAnalysis={() => {}}
        includeAi={true}
      />
    );
    expect(screen.getAllByText('Tania Silva')).toHaveLength(2);
    expect(screen.getByText(/Boa evolucao/i)).toBeInTheDocument();
    expect(screen.getByText(/Assinatura: Dra Ana/i)).toBeInTheDocument();
  });
});
