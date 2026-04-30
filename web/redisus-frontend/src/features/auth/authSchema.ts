import { z } from 'zod';

export const loginSchema = z.object({
  email: z.string().email('Informe um e-mail valido.'),
  password: z.string().min(6, 'A senha precisa ter pelo menos 6 caracteres.'),
});

export type LoginFormValues = z.infer<typeof loginSchema>;

export const registerSchema = z
  .object({
    displayName: z.string().min(2, 'Informe seu nome profissional.'),
    email: z.string().email('Informe um e-mail valido.'),
    password: z.string().min(6, 'Use pelo menos 6 caracteres.'),
    confirmPassword: z.string().min(1, 'Confirme sua senha.'),
    acceptedTerms: z.boolean().refine(value => value, 'Aceite os termos para continuar.'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'As senhas nao coincidem.',
    path: ['confirmPassword'],
  });

export type RegisterFormValues = z.infer<typeof registerSchema>;

export const onboardingSchema = z.object({
  professionalName: z.string().min(2, 'Informe seu nome profissional.'),
  professionalArea: z.string().min(2, 'Informe sua area de atuacao.'),
  clinicName: z.string().optional(),
  phone: z.string().optional(),
  theme: z.enum(['light', 'dark']).default('light'),
});

export type OnboardingFormValues = z.infer<typeof onboardingSchema>;
