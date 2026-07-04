import type { Timestamp } from 'firebase/firestore';

export type ThemePreference = 'light' | 'dark';
export type AppointmentStatus = 'Confirmado' | 'Pendente' | 'Cancelado' | 'Realizado';
export type RoiType = 'polygon' | 'freehand' | 'circle';

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
  normalized?: true;
  updatedAt?: string;
  createdBy?: string;
  updatedBy?: string;
  roiVersion?: string;
  imageId?: string;
  assessmentId?: string;
  patientId?: string;
  verifiedByProfessional?: boolean;
  consentForResearch?: boolean;
  anonymizedExportReady?: boolean;
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
  signature?: string;
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

export type ClinicalAnalysisMode = 'assessment_context' | 'standalone';
export type ClinicalAnalysisSeverity = 'low' | 'medium' | 'high';

export interface ClinicalAnalysisAlert {
  severity: ClinicalAnalysisSeverity;
  title: string;
  message: string;
}

export interface ClinicalAnalysisResult {
  id: string;
  patientId?: string;
  assessmentId?: string;
  imageId?: string;
  roisUsed: Roi[];
  createdAt: string;
  createdBy?: string;
  mode: ClinicalAnalysisMode;
  analysisVersion: string;
  roiVersion: string;
  canAnalyze: boolean;
  blockedReason?: string;
  imageQuality: {
    status: 'good' | 'regular' | 'poor';
    score: number;
    issues: string[];
    metrics: {
      width: number;
      height: number;
      brightness: number;
      contrast: number;
      sharpness: number;
    };
    preprocessing: string[];
  };
  visualFindings: {
    dominantColors: Array<{ label: string; hex: string; percentage: number }>;
    tissueHints: string[];
    attentionAreas: string[];
    roiCoveragePercent: number;
  };
  roiValidation: {
    isValid: boolean;
    woundLikelihood: number;
    reason: string;
    issues: string[];
    roiId?: string;
    areaRatio: number;
    features?: Record<string, number>;
  };
  woundDetection: {
    hasWound: boolean;
    confidence: number;
    reason: string;
    mode: 'roi_validation_gate' | 'trained_model';
    modelVersion: string;
  };
  segmentation: {
    maskUrl?: string;
    areaPixels?: number;
    overlayUrl?: string;
    confidence?: number;
    method: 'manual_roi_mask' | 'trained_segmentation_model';
    limited: boolean;
    reason?: string;
  };
  tissueClassification: {
    enabled: boolean;
    reason: string;
    modelVersion?: string;
    classes: Array<{
      label: 'granulation' | 'slough_fibrin' | 'necrosis' | 'epithelial' | 'unknown';
      percentage: number;
      confidence: number;
    }>;
  };
  clinicalContext: {
    patientName?: string;
    patientStatus?: string;
    patientAge?: number | null;
    painLevel?: number;
    woundRegion?: string;
    woundType?: string;
    exudate?: string;
    odor?: string;
    observations?: string;
    consideredFields: string[];
    missingFields: string[];
  };
  evolution: {
    hasPreviousAssessment: boolean;
    previousAssessmentId?: string;
    previousAssessmentDate?: string;
    painTrend: 'increased' | 'decreased' | 'stable' | 'unknown';
    exudateTrend: 'changed' | 'stable' | 'unknown';
    regionComparison: 'same' | 'different' | 'unknown';
    generalTrend: 'possible_improvement' | 'possible_worsening' | 'stable' | 'insufficient_data';
    summary: string;
  };
  aiInference: {
    status: 'completed' | 'unavailable' | 'skipped';
    modelVersion?: string;
    confidence?: number;
    primaryTissue?: string;
    summary?: string;
    error?: string;
  };
  alerts: ClinicalAnalysisAlert[];
  recommendations: string[];
  consideredData: string[];
  disclaimer: string;
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
