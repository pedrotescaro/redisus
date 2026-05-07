import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setDoc, updateDoc } from 'firebase/firestore';
import { uploadBytes } from 'firebase/storage';

import { createEvaluation, updateEvaluation } from '../../features/evaluations/evaluationService';
import type { EvaluationFormValues } from '../../features/evaluations/evaluationSchema';
import type { ImageDraft } from '../../lib/types';

vi.mock('../../lib/firebase', () => ({
  db: {},
  storage: {},
  storageBucketName: 'healplus-d8b11.firebasestorage.app'
}));

vi.mock('firebase/firestore', () => ({
  arrayUnion: vi.fn((value: unknown) => ({ __arrayUnion: value })),
  collection: vi.fn((_db, path: string) => ({ path })),
  deleteDoc: vi.fn(),
  doc: vi.fn((_dbOrCollectionRef: { path?: string }, path?: string) => {
    if (path) return { id: path.split('/').pop(), path };
    return { id: 'evaluation-1', path: `${_dbOrCollectionRef.path}/evaluation-1` };
  }),
  getDocs: vi.fn(),
  onSnapshot: vi.fn(),
  orderBy: vi.fn(),
  query: vi.fn(),
  serverTimestamp: vi.fn(() => 'server-timestamp'),
  setDoc: vi.fn(),
  updateDoc: vi.fn()
}));

vi.mock('firebase/storage', () => ({
  getDownloadURL: vi.fn(),
  ref: vi.fn((_storage, path: string) => ({ path })),
  uploadBytes: vi.fn()
}));

const evaluationValues: EvaluationFormValues = {
  patientId: 'patient-1',
  patientName: 'Paciente Teste',
  date: '2026-04-28',
  woundLocation: 'Perna',
  woundEtiology: 'Venosa',
  painLevel: 2,
  exudateAmount: 'Pouco',
  exudateType: 'Seroso',
  borderCharacteristics: 'Regular',
  periwoundSkin: 'Integra',
  infectionSigns: [],
  timers: {
    tissue: '',
    infection: '',
    moisture: '',
    edge: '',
    repair: '',
    social: ''
  },
  comorbidities: [],
  medications: [],
  notes: ''
};

describe('evaluationService', () => {
  beforeEach(() => {
    vi.mocked(setDoc).mockReset();
    vi.mocked(updateDoc).mockReset();
    vi.mocked(uploadBytes).mockReset();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 200 }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('salva a avaliacao mesmo quando o upload da imagem falha', async () => {
    vi.mocked(uploadBytes).mockRejectedValue({ code: 'storage/unknown' });

    const images: ImageDraft[] = [
      {
        id: 'image-1',
        file: new File(['image'], 'ferida.jpeg', { type: 'image/jpeg' }),
        previewURL: 'blob:test',
        fileName: 'ferida.jpeg',
        contentType: 'image/jpeg',
        size: 5,
        rois: []
      }
    ];

    const result = await createEvaluation('user-1', evaluationValues, images);

    expect(result.imageUploadError).toMatch(/A avalia[cç][aã]o foi salva sem imagens/i);
    expect(setDoc).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'evaluation-1' }),
      expect.objectContaining({
        images: [],
        imageUploadStatus: 'failed',
        imageUploadError: expect.stringMatching(/Firebase Storage n[aã]o est[aá] dispon[ií]vel/i)
      })
    );
  });

  it('atualiza a avaliacao selecionada com metadados de auditoria', async () => {
    await updateEvaluation('user-1', evaluationValues, 'evaluation-9', [], {
      updatedBy: 'user-1',
      previousData: { id: 'evaluation-9', painLevel: 2 }
    });

    expect(updateDoc).toHaveBeenCalledWith(
      expect.objectContaining({ path: 'users/user-1/patients/patient-1/evaluations/evaluation-9' }),
      expect.objectContaining({
        patientId: 'patient-1',
        updatedBy: 'user-1',
        auditLog: expect.objectContaining({
          __arrayUnion: expect.objectContaining({
            action: 'clinical_record_update',
            updatedBy: 'user-1',
            previousData: { id: 'evaluation-9', painLevel: 2 }
          })
        })
      })
    );
  });
});
