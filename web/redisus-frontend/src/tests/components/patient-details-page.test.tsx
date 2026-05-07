import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { Evaluation, Patient } from '../../lib/types';

const mocks = vi.hoisted(() => ({
  user: { uid: 'alice' },
  getPatient: vi.fn(),
  listEvaluations: vi.fn(),
  updateEvaluation: vi.fn()
}));

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => ({ user: mocks.user, profile: null, loading: false })
}));

vi.mock('../../features/patients/patientService', () => ({
  getPatient: mocks.getPatient
}));

vi.mock('../../features/evaluations/evaluationService', () => ({
  listEvaluations: mocks.listEvaluations,
  updateEvaluation: mocks.updateEvaluation
}));

const patient: Patient = {
  id: 'p1',
  name: 'Tania Silva',
  phone: '11999999999',
  email: '',
  birthDate: '1985-05-12',
  notes: '',
  archived: false
};

const evaluation: Evaluation = {
  id: 'eval-1',
  patientId: 'p1',
  patientName: 'Tania Silva',
  date: '2026-05-01',
  woundLocation: 'Perna Direita',
  woundEtiology: 'Lesão por Pressão',
  painLevel: 5,
  exudateAmount: 'Moderado',
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
  notes: 'Observação inicial',
  images: [
    {
      id: 'image-1',
      storagePath: 'users/alice/patients/p1/evaluations/eval-1/images/image-1.jpg',
      downloadURL: 'https://example.com/wound.jpg',
      fileName: 'wound.jpg',
      contentType: 'image/jpeg',
      size: 120,
      rois: [],
      uploadedAt: '2026-05-01T12:00:00.000Z'
    }
  ]
};

async function renderDetails() {
  const { PatientDetailsPage } = await import('../../features/patients/PatientDetailsPage');

  return render(
    <MemoryRouter initialEntries={['/patients/p1']}>
      <Routes>
        <Route path="/patients/:patientId" element={<PatientDetailsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('PatientDetailsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getPatient.mockResolvedValue(patient);
    mocks.listEvaluations.mockResolvedValue([evaluation]);
    mocks.updateEvaluation.mockResolvedValue({
      id: 'eval-1',
      uploadedImageCount: 1,
      requestedImageCount: 1
    });
  });

  it('exige confirmacao antes de editar um registro clinico', async () => {
    const user = userEvent.setup();
    await renderDetails();

    expect(await screen.findByText('Perna Direita')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /editar registro clínico/i }));

    expect(screen.getByRole('dialog', { name: /atenção: edição de dados clínicos/i })).toBeInTheDocument();
    expect(mocks.updateEvaluation).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: /entendi, editar registro/i }));
    expect(await screen.findByRole('dialog', { name: /editar registro clínico/i })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/região da ferida/i), 'Perna Esquerda');
    await user.clear(screen.getByLabelText(/observações clínicas/i));
    await user.type(screen.getByLabelText(/observações clínicas/i), 'Evolução ajustada');
    await user.click(screen.getByRole('button', { name: /salvar alterações/i }));

    await waitFor(() => {
      expect(mocks.updateEvaluation).toHaveBeenCalledWith(
        'alice',
        expect.objectContaining({
          patientId: 'p1',
          woundLocation: 'Perna Esquerda',
          notes: 'Evolução ajustada'
        }),
        'eval-1',
        expect.any(Array),
        expect.objectContaining({
          updatedBy: 'alice',
          previousData: expect.objectContaining({ id: 'eval-1', woundLocation: 'Perna Direita' })
        })
      );
    });
  });
});
