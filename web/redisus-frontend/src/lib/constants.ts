export const APP_NAME = 'Heal+';
export const APP_VERSION = '2.0.0';

export const HEAL_COLORS = {
  blue: '#3B82F6',
  blueDark: '#2563EB',
  teal: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
  green: '#22C55E',
  slate: '#6B6B70',
  purple: '#8B5CF6'
};

export const ROI_COLORS = [
  HEAL_COLORS.blue,
  HEAL_COLORS.teal,
  HEAL_COLORS.warning,
  HEAL_COLORS.green,
  HEAL_COLORS.purple
];

export const MAX_IMAGE_UPLOAD_MB = Number(import.meta.env.VITE_MAX_IMAGE_UPLOAD_MB || 10);
export const MAX_IMAGE_UPLOAD_BYTES = MAX_IMAGE_UPLOAD_MB * 1024 * 1024;

export const FORM_OPTIONS = {
  woundLocations: [
    'Região Sacral',
    'Calcanhar Direito',
    'Calcanhar Esquerdo',
    'Perna Esquerda',
    'Perna Direita',
    'Pé Diabético',
    'Abdome',
    'Tórax',
    'Membros Superiores',
    'Outro'
  ],
  woundEtiologies: [
    'Lesão por Pressão',
    'Úlcera Venosa',
    'Úlcera Arterial',
    'Pé Diabético',
    'Ferida Cirúrgica',
    'Ferida Traumática',
    'Queimadura',
    'Outra'
  ],
  exudateAmounts: ['Ausente', 'Escasso', 'Pequeno', 'Moderado', 'Abundante'],
  exudateTypes: ['Seroso', 'Sanguinolento', 'Serossanguinolento', 'Purulento', 'Seropurulento'],
  exudateConsistency: ['Fina', 'Viscosa', 'Espessa'],
  borderCharacteristics: ['Regulares', 'Irregulares', 'Elevadas', 'Maceradas', 'Epitelizadas'],
  edgeFixations: ['Aderidas', 'Não aderidas', 'Descoladas'],
  healingSpeeds: ['Rápida', 'Moderada', 'Lenta', 'Estagnada'],
  periwoundSkin: ['Íntegra', 'Eritematosa', 'Macerada', 'Seca', 'Edemaciada', 'Indurada'],
  periwoundMoisture: ['Seca', 'Hidratada', 'Macerada', 'Edemaciada'],
  periwoundConditions: [
    'Íntegra',
    'Eritematosa',
    'Macerada',
    'Seca e descamativa',
    'Eczematosa',
    'Hiperpigmentada',
    'Hipopigmentada',
    'Indurada',
    'Sensível',
    'Edema'
  ],
  infectionSigns: ['Eritema', 'Calor local', 'Edema', 'Dor local', 'Odor', 'Exsudato purulento'],
  inflammationSigns: ['Rubor', 'Calor', 'Edema', 'Dor local', 'Perda de função'],
  localInfectionSigns: [
    'Eritema perilesional',
    'Calor local',
    'Edema',
    'Dor local',
    'Exsudato purulento',
    'Odor fétido',
    'Retardo na cicatrização'
  ],
  activityLevels: ['Acamado', 'Sedentário', 'Parcialmente ativo', 'Ativo'],
  adherenceLevels: ['Boa', 'Regular', 'Baixa'],
  comorbidities: [
    'DMI',
    'DMII',
    'HAS',
    'Neoplasia',
    'Obesidade',
    'Cardiopatia',
    'DPOC',
    'Doença vascular',
    'Insuficiência renal',
    'Doença autoimune'
  ],
  medications: [
    'Anti-hipertensivo',
    'Corticoide',
    'Hipoglicemiante oral',
    'Insulina',
    'Anticoagulante',
    'Antibiótico',
    'Suplemento'
  ],
  appointmentTypes: ['Troca de Curativo', 'Retorno', 'Follow-up', 'Avaliação Fotográfica', 'Wound Care', 'Primeira Consulta'],
  appointmentStatuses: ['Confirmado', 'Pendente', 'Cancelado', 'Realizado']
} as const;

export const CLINICAL_DISCLAIMER =
  'O Heal+ apoia o registro e acompanhamento clínico, mas não substitui avaliação, decisão ou responsabilidade profissional.';
