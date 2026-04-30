import { z } from 'zod';

export const patientSchema = z.object({
  name: z.string().min(2, 'Informe o nome do paciente.').max(120, 'Nome muito longo.'),
  phone: z.string().min(8, 'Informe um telefone de contato.').max(30, 'Telefone muito longo.'),
  email: z.string().email('Informe um e-mail valido.').or(z.literal('')),
  birthDate: z.string().min(1, 'Informe a data de nascimento.'),
  notes: z.string().max(1200, 'Observacoes muito longas.').optional().default(''),
  archived: z.boolean().default(false)
});

export type PatientFormValues = z.infer<typeof patientSchema>;
