import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { Evaluation, Patient } from '../../lib/types';

const mocks = vi.hoisted(() => ({
  user: { uid: 'alice' },
  subscribePatients: vi.fn(),
  listEvaluations: vi.fn()
}));

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => ({ user: mocks.user, profile: null, loading: false })
}));

vi.mock('../../features/patients/patientService', () => ({
  subscribePatients: mocks.subscribePatients
}));

vi.mock('../../features/evaluations/evaluationService', () => ({
  listEvaluations: mocks.listEvaluations
}));

vi.mock('../../components/reports/ReportPreview', () => ({
  ReportPreview: ({ evaluation }: { evaluation: Evaluation }) => <div>Prévia {evaluation.woundLocation}</div>
}));

const patient: Patient = {
  id: 'p1',
  name: 'Caroline Paula Ribeiro Silvestre Tescaro',
  phone: '11',
  email: '',
  birthDate: '1985-05-12',
  notes: '',
  archived: false
};

const evaluation: Evaluation = {
  id: 'eval-1',
  patientId: 'p1',
  patientName: patient.name,
  date: '2026-05-01',
  woundLocation: 'Região Sacral',
  woundEtiology: 'Lesão por Pressão',
  painLevel: 2,
  exudateAmount: 'Escasso',
  exudateType: 'Seroso',
  borderCharacteristics: 'Regulares',
  periwoundSkin: 'Íntegra',
  infectionSigns: [],
  timers: {
    tissue: '',
    infection: '',
    moisture: '',
    edge: '',
    repair: '',
    social: ''
  },
  comorbidities: [],
  medications: [],
  notes: '',
  images: []
};

describe('ReportsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.subscribePatients.mockImplementation((_uid: string, onData: (patients: Patient[]) => void) => {
      onData([patient]);
      return vi.fn();
    });
    mocks.listEvaluations.mockResolvedValue([evaluation]);
  });

  it('seleciona automaticamente o primeiro paciente com avaliacao e mostra as avaliacoes', async () => {
    const { ReportsPage } = await import('../../features/reports/ReportsPage');
    render(<ReportsPage />, { wrapper: MemoryRouter });

    const evaluationSelect = (await screen.findByLabelText(/avalia/i)) as HTMLSelectElement;

    await waitFor(() => expect(evaluationSelect.value).toBe('eval-1'));
    expect(screen.getByText('2026-05-01 - Região Sacral')).toBeInTheDocument();
    expect(screen.getByText('Prévia Região Sacral')).toBeInTheDocument();
  });
});
