import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

const authState = vi.hoisted(() => ({
  user: null as null | { uid: string },
  profile: null as null | { onboardingCompleted?: boolean },
  loading: false
}));

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => authState
}));

describe('ProtectedRoute', () => {
  it('bloqueia usuario nao autenticado', async () => {
    authState.user = null;
    authState.profile = null;
    const { ProtectedRoute } = await import('../../components/layout/ProtectedRoute');

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<div>Dashboard privado</div>} />
          </Route>
          <Route path="/login" element={<div>Tela de login</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Tela de login')).toBeInTheDocument();
  });

  it('redireciona primeiro acesso para onboarding', async () => {
    authState.user = { uid: 'alice' };
    authState.profile = { onboardingCompleted: false };
    const { ProtectedRoute } = await import('../../components/layout/ProtectedRoute');

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<div>Dashboard privado</div>} />
            <Route path="/onboarding" element={<div>Onboarding</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Onboarding')).toBeInTheDocument();
  });
});
