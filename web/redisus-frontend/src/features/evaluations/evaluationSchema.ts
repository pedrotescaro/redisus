import { z } from 'zod';

export const evaluationSchema = z.object({
  patientId: z.string().min(1, 'Selecione um paciente.'),
  patientName: z.string().min(1, 'Paciente inválido.'),
  date: z.string().min(1, 'Informe a data da avaliação.'),
  woundLocation: z.string().min(2, 'Informe a localização da ferida.'),
  woundEtiology: z.string().min(2, 'Informe a etiologia.'),
  painLevel: z.coerce.number().min(0).max(10),
  exudateAmount: z.string().min(1, 'Informe a quantidade de exsudato.'),
  exudateType: z.string().min(1, 'Informe o tipo de exsudato.'),
  borderCharacteristics: z.string().min(1, 'Informe as bordas.'),
  periwoundSkin: z.string().min(1, 'Informe a pele perilesional.'),
  infectionSigns: z.array(z.string()).default([]),
  timers: z.object({
    tissue: z.string().max(600).default(''),
    infection: z.string().max(600).default(''),
    moisture: z.string().max(600).default(''),
    edge: z.string().max(600).default(''),
    repair: z.string().max(600).default(''),
    social: z.string().max(600).default('')
  }),
  comorbidities: z.array(z.string()).default([]),
  medications: z.array(z.string()).default([]),
  notes: z.string().max(2000).optional().default(''),
  signature: z.string().optional()
});

export type EvaluationFormValues = z.infer<typeof evaluationSchema>;
