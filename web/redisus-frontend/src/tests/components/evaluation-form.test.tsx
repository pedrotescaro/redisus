import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { EvaluationForm } from '../../features/evaluations/EvaluationForm';

describe('EvaluationForm', () => {
  it('renderiza fluxo clinico TIMERS estruturado', async () => {
    const user = userEvent.setup();
    render(
      <EvaluationForm
        patients={[{ id: 'p1', name: 'Tania Silva', phone: '11999999999', email: '', birthDate: '1985-05-12', notes: '', archived: false }]}
        onSubmit={vi.fn()}
      />
    );
    await user.selectOptions(screen.getByLabelText(/paciente/i), 'p1');
    await user.click(screen.getByRole('button', { name: /continuar/i }));

    expect(await screen.findByText(/T - Tecido/i)).toBeInTheDocument();
    expect(screen.getByText(/I - Infec[cç][aã]o e Inflam[aã]ç[aã]o/i)).toBeInTheDocument();
    expect(screen.getByText(/M - Umidade/i)).toBeInTheDocument();
    expect(screen.getByText(/E - Bordas/i)).toBeInTheDocument();
    expect(screen.getByText(/R - Reparo/i)).toBeInTheDocument();
    expect(screen.getByText(/S - Fatores Sociais/i)).toBeInTheDocument();
  });
});
