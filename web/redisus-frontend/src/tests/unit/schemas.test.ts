import { describe, expect, it } from 'vitest';

import { loginSchema, registerSchema } from '../../features/auth/authSchema';
import { evaluationSchema } from '../../features/evaluations/evaluationSchema';
import { patientSchema } from '../../features/patients/patientSchema';

describe('validacoes Zod', () => {
  it('valida login com e-mail e senha', () => {
    expect(loginSchema.safeParse({ email: 'dr@heal.plus', password: '123456' }).success).toBe(true);
    expect(loginSchema.safeParse({ email: 'invalido', password: '123' }).success).toBe(false);
  });

  it('valida cadastro e confirmacao de senha', () => {
    expect(registerSchema.safeParse({ displayName: 'Dra Ana', email: 'ana@heal.plus', password: '123456', confirmPassword: '123456', acceptedTerms: true }).success).toBe(true);
    expect(registerSchema.safeParse({ displayName: 'Dra Ana', email: 'ana@heal.plus', password: '123456', confirmPassword: 'abcdef', acceptedTerms: true }).success).toBe(false);
    expect(registerSchema.safeParse({ displayName: 'Dra Ana', email: 'ana@heal.plus', password: '123456', confirmPassword: '123456', acceptedTerms: false }).success).toBe(false);
  });

  it('valida paciente minimo', () => {
    expect(patientSchema.safeParse({ name: 'Tania Silva', phone: '11999999999', email: '', birthDate: '1985-05-12', notes: '', archived: false }).success).toBe(true);
  });

  it('valida avaliacao clinica minima', () => {
    expect(
      evaluationSchema.safeParse({
        patientId: 'p1',
        patientName: 'Tania Silva',
        date: '2026-04-28',
        woundLocation: 'Regiao Sacral',
        woundEtiology: 'Lesao por Pressao',
        painLevel: 5,
        exudateAmount: 'Moderado',
        exudateType: 'Seroso',
        borderCharacteristics: 'Regulares',
        periwoundSkin: 'Integra',
        infectionSigns: [],
        timers: { tissue: '', infection: '', moisture: '', edge: '', repair: '', social: '' },
        comorbidities: [],
        medications: [],
        notes: ''
      }).success
    ).toBe(true);
  });
});
