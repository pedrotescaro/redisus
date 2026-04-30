import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  user: { uid: 'alice' }
}));

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => ({ user: mocks.user, profile: null, loading: false })
}));

vi.mock('../../features/patients/patientService', () => ({
  subscribePatients: (_uid: string, onData: (patients: unknown[]) => void) => {
    onData([{ id: 'p1', name: 'Tania Silva', phone: '11999999999', email: '', birthDate: '1985-05-12', notes: '', archived: false }]);
    return vi.fn();
  },
  createPatient: vi.fn(),
  updatePatient: vi.fn(),
  deletePatient: vi.fn(),
  setPatientArchived: vi.fn()
}));

describe('PatientsPage', () => {
  it('lista pacientes carregados do servico', async () => {
    const { PatientsPage } = await import('../../features/patients/PatientsPage');
    render(<PatientsPage />, { wrapper: MemoryRouter });
    expect((await screen.findAllByText('Tania Silva')).length).toBeGreaterThan(0);
  });
});
