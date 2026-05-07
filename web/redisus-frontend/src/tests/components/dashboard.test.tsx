import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => ({ user: { uid: 'alice', displayName: 'Dra Ana' }, profile: { displayName: 'Dra Ana' }, loading: false })
}));

vi.mock('../../features/patients/patientService', () => ({
  subscribePatients: (_uid: string, onData: (patients: unknown[]) => void) => {
    onData([
      { id: 'p1', name: 'Tania Silva', phone: '11', email: '', birthDate: '1985-01-01', notes: '', archived: false },
      { id: 'p2', name: 'Joao Lima', phone: '11', email: '', birthDate: '1980-01-01', notes: '', archived: true }
    ]);
    return vi.fn();
  }
}));

vi.mock('../../features/agenda/agendaService', () => ({
  subscribeAppointments: (_uid: string, onData: (appointments: unknown[]) => void) => {
    onData([{ id: 'a1', patientId: 'p1', patientName: 'Tania Silva', date: '2099-01-01', time: '09:00', type: 'Retorno', status: 'Confirmado', notes: '' }]);
    return vi.fn();
  }
}));

vi.mock('../../features/evaluations/evaluationService', () => ({
  listEvaluations: vi.fn().mockResolvedValue([{ id: 'e1' }])
}));

describe('DashboardPage', () => {
  it('renderiza cards com dados carregados', async () => {
    const { DashboardPage } = await import('../../features/dashboard/DashboardPage');
    render(<DashboardPage />, { wrapper: MemoryRouter });

    expect(await screen.findByText('Pronto para continuar o acompanhamento?')).toBeInTheDocument();
    expect(screen.getByText('Pacientes ativos')).toBeInTheDocument();
    expect(screen.getByText('Próximos atendimentos')).toBeInTheDocument();
    expect(screen.getByText('Avaliações')).toBeInTheDocument();
  });
});
