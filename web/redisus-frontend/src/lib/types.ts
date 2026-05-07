import type { Timestamp } from 'firebase/firestore';

export type ThemePreference = 'light' | 'dark';
export type AppointmentStatus = 'Confirmado' | 'Pendente' | 'Cancelado' | 'Realizado';
export type RoiType = 'polygon' | 'freehand';

export interface UserProfile {
  uid?: string;
  displayName: string;
  email: string;
  photoURL?: string | null;
  providerIds?: string[];
  professionalArea?: string;
  clinicName?: string;
  phone?: string;
  onboardingCompleted?: boolean;
  role: 'professional';
  createdAt?: Timestamp;
  updatedAt?: Timestamp;
  settings: {
    theme: ThemePreference;
    notificationsEnabled: boolean;
    emailNotificationsEnabled?: boolean;
    agendaRemindersEnabled?: boolean;
    hideEmailPreview?: boolean;
    showProfilePhoto?: boolean;
  };
}

export interface Patient {
  id: string;
  name: string;
  phone: string;
  email: string;
  birthDate: string;
  notes: string;
  archived: boolean;
  createdAt?: Timestamp;
  updatedAt?: Timestamp;
}

export interface RoiPoint {
  x: number;
  y: number;
}

export interface Roi {
  id: string;
  label: string;
  type: RoiType;
  points: RoiPoint[];
  color: string;
  createdAt: string;
}

export interface WoundImage {
  id: string;
  storagePath: string;
  downloadURL: string;
  fileName: string;
  contentType: string;
  size: number;
  rois: Roi[];
  uploadedAt: string;
}

export interface Evaluation {
  id: string;
  patientId: string;
  patientName: string;
  date: string;
  woundLocation: string;
  woundEtiology: string;
  painLevel: number;
  exudateAmount: string;
  exudateType: string;
  borderCharacteristics: string;
  periwoundSkin: string;
  infectionSigns: string[];
  timers: {
    tissue: string;
    infection: string;
    moisture: string;
    edge: string;
    repair: string;
    social: string;
  };
  comorbidities: string[];
  medications: string[];
  notes: string;
  images: WoundImage[];
  imageUploadStatus?: 'complete' | 'failed';
  imageUploadError?: string | null;
  updatedBy?: string;
  auditLog?: EvaluationAuditEntry[];
  createdAt?: Timestamp;
  updatedAt?: Timestamp;
}

export interface EvaluationAuditEntry {
  action: string;
  updatedAt: string;
  updatedBy: string;
  previousData?: Record<string, unknown>;
}

export interface Appointment {
  id: string;
  patientId: string;
  patientName: string;
  date: string;
  time: string;
  type: string;
  status: AppointmentStatus;
  notes: string;
  createdAt?: Timestamp;
  updatedAt?: Timestamp;
}

export interface ImageDraft {
  id: string;
  file?: File;
  previewURL: string;
  fileName: string;
  contentType: string;
  size: number;
  existingStoragePath?: string;
  existingDownloadURL?: string;
  existingRois?: Roi[];
  rois: Roi[];
}
