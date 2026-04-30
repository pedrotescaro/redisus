// @vitest-environment node

import { readFileSync } from 'node:fs';

import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment
} from '@firebase/rules-unit-testing';
import { doc, getDoc, setDoc, Timestamp } from 'firebase/firestore';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';

let testEnv: RulesTestEnvironment;

const projectId = `healplus-rules-${Date.now()}`;
const now = Timestamp.now();

const userDoc = {
  displayName: 'Dra Alice',
  email: 'alice@heal.plus',
  photoURL: null,
  role: 'professional',
  createdAt: now,
  updatedAt: now,
  settings: {
    theme: 'light',
    notificationsEnabled: true,
    emailNotificationsEnabled: true,
    agendaRemindersEnabled: true,
    hideEmailPreview: false,
    showProfilePhoto: true
  }
};

const patientDoc = {
  name: 'Tania Silva',
  phone: '11999999999',
  email: '',
  birthDate: '1985-05-12',
  notes: '',
  archived: false,
  createdAt: now,
  updatedAt: now
};

const evaluationDoc = {
  patientId: 'p1',
  patientName: 'Tania Silva',
  date: '2026-04-28',
  woundLocation: 'Regiao Sacral',
  woundEtiology: 'Lesao por Pressao',
  painLevel: 4,
  exudateAmount: 'Pequeno',
  exudateType: 'Seroso',
  borderCharacteristics: 'Regulares',
  periwoundSkin: 'Integra',
  infectionSigns: [],
  timers: { tissue: '', infection: '', moisture: '', edge: '', repair: '', social: '' },
  comorbidities: [],
  medications: [],
  notes: '',
  images: [],
  createdAt: now,
  updatedAt: now
};

beforeAll(async () => {
  testEnv = await initializeTestEnvironment({
    projectId,
    firestore: {
      rules: readFileSync('firestore.rules', 'utf8')
    }
  });
});

afterAll(async () => {
  await testEnv.cleanup();
});

beforeEach(async () => {
  await testEnv.clearFirestore();
});

describe('Firestore security rules', () => {
  it('usuario autenticado cria seu perfil e paciente', async () => {
    const alice = testEnv.authenticatedContext('alice').firestore();
    await assertSucceeds(setDoc(doc(alice, 'users/alice'), userDoc));
    await assertSucceeds(setDoc(doc(alice, 'users/alice/patients/p1'), patientDoc));
  });

  it('usuario autenticado le seus pacientes', async () => {
    const alice = testEnv.authenticatedContext('alice').firestore();
    await assertSucceeds(setDoc(doc(alice, 'users/alice'), userDoc));
    await assertSucceeds(setDoc(doc(alice, 'users/alice/patients/p1'), patientDoc));
    await assertSucceeds(getDoc(doc(alice, 'users/alice/patients/p1')));
  });

  it('usuario nao autenticado nao acessa nada', async () => {
    const guest = testEnv.unauthenticatedContext().firestore();
    await assertFails(getDoc(doc(guest, 'users/alice/patients/p1')));
  });

  it('usuario A nao acessa dados do usuario B', async () => {
    const bob = testEnv.authenticatedContext('bob').firestore();
    await assertFails(getDoc(doc(bob, 'users/alice/patients/p1')));
  });

  it('avaliacao precisa ficar dentro do paciente correto', async () => {
    const alice = testEnv.authenticatedContext('alice').firestore();
    await assertSucceeds(setDoc(doc(alice, 'users/alice/patients/p1/evaluations/e1'), evaluationDoc));
    await assertFails(setDoc(doc(alice, 'users/alice/patients/p2/evaluations/e1'), evaluationDoc));
  });

  it('bloqueia documentos com estrutura invalida', async () => {
    const alice = testEnv.authenticatedContext('alice').firestore();
    await assertFails(setDoc(doc(alice, 'users/alice/patients/bad'), { name: 'X' }));
    await expect(true).toBe(true);
  });
});
