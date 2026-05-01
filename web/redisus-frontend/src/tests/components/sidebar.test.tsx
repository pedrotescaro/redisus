import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { Sidebar } from '../../components/layout/sidebar';

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

  it('ativa apenas Relatórios na rota /reports', () => {
    render(
      <MemoryRouter initialEntries={['/reports']}>
        <Sidebar isOpen={false} setIsOpen={() => undefined} />
      </MemoryRouter>
    );

    const reportsLink = screen.getByRole('link', { name: /Relat[oó]rios/i });
    const compareLink = screen.getByRole('link', { name: /Comparar evolu[cç][aã]o/i });

    expect(reportsLink.className).toContain('bg-heal-softBlue');
    expect(compareLink.className).not.toContain('bg-heal-softBlue');
  });

  it('ativa apenas Comparar evolução na rota /reports/compare', () => {
    render(
      <MemoryRouter initialEntries={['/reports/compare']}>
        <Sidebar isOpen={false} setIsOpen={() => undefined} />
      </MemoryRouter>
    );

    const reportsLink = screen.getByRole('link', { name: /Relat[oó]rios/i });
    const compareLink = screen.getByRole('link', { name: /Comparar evolu[cç][aã]o/i });

    expect(compareLink.className).toContain('bg-heal-softBlue');
    expect(reportsLink.className).not.toContain('bg-heal-softBlue');
  });
});
