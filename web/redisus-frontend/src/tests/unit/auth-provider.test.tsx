import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const firebaseAuth = vi.hoisted(() => ({
  onAuthStateChanged: vi.fn()
}));

vi.mock('firebase/auth', () => firebaseAuth);
vi.mock('../../lib/firebase', () => ({
  auth: {},
  isFirebaseConfigured: false
}));
vi.mock('../../lib/supabase', () => ({
  supabase: {}
}));
vi.mock('../../features/auth/authService', () => ({
  ensureUserProfile: vi.fn()
}));

import { AuthProvider, useAuth } from '../../app/providers/AuthProvider';

function AuthProbe() {
  const { loading, user } = useAuth();
  return <span>{loading ? 'carregando' : user ? 'autenticado' : 'pronto'}</span>;
}

describe('AuthProvider sem Firebase configurado', () => {
  it('libera as rotas públicas sem iniciar o listener remoto', async () => {
    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    expect(await screen.findByText('pronto')).toBeInTheDocument();
    expect(firebaseAuth.onAuthStateChanged).not.toHaveBeenCalled();
  });
});
