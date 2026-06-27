import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { Sidebar } from '../../components/layout/sidebar';

const mocks = vi.hoisted(() => ({
  user: { uid: 'alice', email: 'alice@example.com' },
  profile: { displayName: 'Alice Liddell', clinicName: 'Fatec Itaquera', email: 'alice@example.com' }
}));

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => ({ user: mocks.user, profile: mocks.profile, loading: false })
}));

describe('Sidebar', () => {
  it('renderiza itens principais, instituicao e email', async () => {
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
    expect(screen.getByText('Assistente')).toBeInTheDocument();
    expect(screen.getByText('Perfil')).toBeInTheDocument();
    expect(screen.getByText('Fatec Itaquera')).toBeInTheDocument();
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
    expect(screen.getByText('Alice Liddell')).toBeInTheDocument();

    // Clica em "Mais" para abrir o dropdown
    const maisButton = screen.getByRole('button', { name: /Mais/i });
    await userEvent.click(maisButton);

    expect(screen.getByText(/Comparar evolu[cç][aã]o/i)).toBeInTheDocument();
    expect(screen.getByText(/Configura[cç][oõ]es/i)).toBeInTheDocument();
  });

  it('ativa apenas Relatórios na rota /reports', async () => {
    render(
      <MemoryRouter initialEntries={['/reports']}>
        <Sidebar isOpen={false} setIsOpen={() => undefined} />
      </MemoryRouter>
    );

    const reportsLink = screen.getByRole('link', { name: /Relat[oó]rios/i });
    expect(reportsLink.className).toContain('font-black');

    // Abre o dropdown "Mais" para verificar "Comparar evolução"
    const maisButton = screen.getByRole('button', { name: /Mais/i });
    await userEvent.click(maisButton);

    const compareLink = screen.getByRole('link', { name: /Comparar evolu[cç][aã]o/i });
    expect(compareLink.className).not.toContain('font-bold');
  });

  it('ativa apenas Comparar evolução na rota /reports/compare', async () => {
    render(
      <MemoryRouter initialEntries={['/reports/compare']}>
        <Sidebar isOpen={false} setIsOpen={() => undefined} />
      </MemoryRouter>
    );

    const reportsLink = screen.getByRole('link', { name: /Relat[oó]rios/i });
    expect(reportsLink.className).not.toContain('font-black');

    // Abre o dropdown "Mais" para verificar "Comparar evolução"
    const maisButton = screen.getByRole('button', { name: /Mais/i });
    await userEvent.click(maisButton);

    const compareLink = screen.getByRole('link', { name: /Comparar evolu[cç][aã]o/i });
    expect(compareLink.className).toContain('font-bold');
  });
});
