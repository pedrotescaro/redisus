import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setDoc } from 'firebase/firestore';
import { uploadBytes } from 'firebase/storage';

import { createEvaluation } from '../../features/evaluations/evaluationService';
import type { EvaluationFormValues } from '../../features/evaluations/evaluationSchema';
import type { ImageDraft } from '../../lib/types';

vi.mock('../../lib/firebase', () => ({
  db: {},
  storage: {},
  storageBucketName: 'healplus-d8b11.firebasestorage.app'
}));

vi.mock('firebase/firestore', () => ({
  collection: vi.fn((_db, path: string) => ({ path })),
  deleteDoc: vi.fn(),
  doc: vi.fn((collectionRef: { path: string }) => ({ id: 'evaluation-1', path: `${collectionRef.path}/evaluation-1` })),
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

    expect(result.imageUploadError).toContain('A avaliacao foi salva sem imagens');
    expect(setDoc).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'evaluation-1' }),
      expect.objectContaining({
        images: [],
        imageUploadStatus: 'failed',
        imageUploadError: expect.stringContaining('Firebase Storage nao esta disponivel')
      })
    );
  });
});
