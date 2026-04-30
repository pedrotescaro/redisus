import { describe, expect, it } from 'vitest';

import { friendlyAuthError } from '../../features/auth/authService';

describe('friendlyAuthError', () => {
  it('traduz erros comuns do Firebase Auth', () => {
    expect(friendlyAuthError({ code: 'auth/user-not-found' })).toBe('E-mail ou senha incorretos.');
    expect(friendlyAuthError({ code: 'auth/email-already-in-use' })).toBe('Este e-mail ja esta cadastrado.');
    expect(friendlyAuthError({ code: 'auth/popup-closed-by-user' })).toBe('Login cancelado antes da conclusao.');
    expect(friendlyAuthError({ code: 'auth/unauthorized-domain' })).toBe('Este dominio nao esta autorizado no Firebase Auth.');
  });
});
