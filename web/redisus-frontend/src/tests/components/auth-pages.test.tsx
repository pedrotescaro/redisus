import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { LoginPage } from '../../features/auth/LoginPage';
import { RegisterPage } from '../../features/auth/RegisterPage';

vi.mock('../../app/providers/AuthProvider', () => ({
  useAuth: () => ({ user: null, profile: null, loading: false })
}));

const serviceMocks = vi.hoisted(() => ({
  loginWithEmail: vi.fn(),
  registerWithEmail: vi.fn(),
  signInWithGoogle: vi.fn(),
  signInWithMicrosoft: vi.fn(),
  signInWithApple: vi.fn()
}));

vi.mock('../../features/auth/authService', () => ({
  friendlyAuthError: () => 'Erro amigavel',
  loginWithEmail: serviceMocks.loginWithEmail,
  registerWithEmail: serviceMocks.registerWithEmail,
  signInWithGoogle: serviceMocks.signInWithGoogle,
  signInWithMicrosoft: serviceMocks.signInWithMicrosoft,
  signInWithApple: serviceMocks.signInWithApple
}));

describe('paginas de autenticacao', () => {
  it('renderiza LoginPage', () => {
    render(<LoginPage />, { wrapper: MemoryRouter });
    expect(screen.getByRole('button', { name: /entrar com e-mail/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/e-mail/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /continuar com google/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /continuar com microsoft/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /continuar com apple/i })).toBeInTheDocument();
  });

  it('renderiza RegisterPage', () => {
    render(<RegisterPage />, { wrapper: MemoryRouter });
    expect(screen.getByRole('button', { name: /cadastrar/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/nome profissional/i)).toBeInTheDocument();
  });

  it('envia login com e-mail para o servico correto', async () => {
    const user = userEvent.setup();
    render(<LoginPage />, { wrapper: MemoryRouter });

    await user.type(screen.getByLabelText(/e-mail/i), 'dra@heal.plus');
    await user.type(screen.getByLabelText(/senha/i), '123456');
    await user.click(screen.getByRole('button', { name: /entrar com e-mail/i }));

    expect(serviceMocks.loginWithEmail).toHaveBeenCalledWith({ email: 'dra@heal.plus', password: '123456' });
  });

  it('chama provedores sociais', async () => {
    const user = userEvent.setup();
    render(<LoginPage />, { wrapper: MemoryRouter });

    await user.click(screen.getByRole('button', { name: /continuar com google/i }));
    await user.click(screen.getByRole('button', { name: /continuar com microsoft/i }));
    await user.click(screen.getByRole('button', { name: /continuar com apple/i }));

    expect(serviceMocks.signInWithGoogle).toHaveBeenCalled();
    expect(serviceMocks.signInWithMicrosoft).toHaveBeenCalled();
    expect(serviceMocks.signInWithApple).toHaveBeenCalled();
  });
});
