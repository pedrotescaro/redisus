import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { PatientForm } from '../../features/patients/PatientForm';

describe('PatientForm', () => {
  it('renderiza campos principais', () => {
    render(<PatientForm onSubmit={vi.fn()} />);
    expect(screen.getByLabelText(/nome/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/telefone/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /salvar paciente/i })).toBeInTheDocument();
  });
});
