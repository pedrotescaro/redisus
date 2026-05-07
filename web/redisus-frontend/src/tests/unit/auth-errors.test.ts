import { describe, expect, it } from 'vitest';

import { friendlyAuthError } from '../../features/auth/authService';

describe('friendlyAuthError', () => {
  it('traduz erros comuns do Firebase Auth', () => {
    expect(friendlyAuthError({ code: 'auth/user-not-found' })).toBe('E-mail ou senha incorretos.');
    expect(friendlyAuthError({ code: 'auth/email-already-in-use' })).toBe('Este e-mail já está cadastrado.');
    expect(friendlyAuthError({ code: 'auth/popup-closed-by-user' })).toBe('Login cancelado antes da conclusão.');
    expect(friendlyAuthError({ code: 'auth/unauthorized-domain' })).toBe('Este domínio não está autorizado no Firebase Auth.');
  });
});
