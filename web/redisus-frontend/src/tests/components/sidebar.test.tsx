import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { Sidebar } from '../../components/layout/Sidebar';

describe('Sidebar', () => {
  it('renderiza itens principais', () => {
    render(
      <MemoryRouter>
        <Sidebar isOpen={false} setIsOpen={() => undefined} />
      </MemoryRouter>
    );

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Pacientes')).toBeInTheDocument();
    expect(screen.getByText(/Avalia[cç][oõ]es/i)).toBeInTheDocument();
    expect(screen.getByText('Agenda')).toBeInTheDocument();
    expect(screen.getByText(/Relat[oó]rios/i)).toBeInTheDocument();
    expect(screen.getByText(/Comparar evolu[cç][aã]o/i)).toBeInTheDocument();
    expect(screen.getByText('Assistente')).toBeInTheDocument();
    expect(screen.getByText('Perfil')).toBeInTheDocument();
    expect(screen.getByText(/Configura[cç][oõ]es/i)).toBeInTheDocument();
  });
});
