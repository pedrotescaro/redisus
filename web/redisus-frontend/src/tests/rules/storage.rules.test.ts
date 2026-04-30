// @vitest-environment node

import { readFileSync } from 'node:fs';

import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment
} from '@firebase/rules-unit-testing';
import type firebase from 'firebase/compat/app';
import 'firebase/compat/storage';
import { afterAll, beforeAll, beforeEach, describe, it } from 'vitest';

let testEnv: RulesTestEnvironment;

function uploadTaskPromise(task: firebase.storage.UploadTask) {
  return new Promise((resolve, reject) => {
    task.on('state_changed', undefined, reject, () => resolve(task.snapshot));
  });
}

beforeAll(async () => {
  testEnv = await initializeTestEnvironment({
    projectId: 'demo-healplus',
    storage: {
      rules: readFileSync('storage.rules', 'utf8'),
      host: '127.0.0.1',
      port: 9199
    }
  });
});

afterAll(async () => {
  await testEnv.cleanup();
});

beforeEach(async () => {
  await testEnv.clearStorage();
});

describe('Storage security rules', () => {
  it('permite imagem no path do proprio usuario', async () => {
    const storage = testEnv.authenticatedContext('alice').storage(`gs://${testEnv.projectId}.appspot.com`);
    const image = new Uint8Array([1, 2, 3]);
    await assertSucceeds(uploadTaskPromise(storage.ref('users/alice/patients/p1/evaluations/e1/wounds/img.png').put(image, { contentType: 'image/png' })));
  });

  it('bloqueia upload no path de outro usuario', async () => {
    const storage = testEnv.authenticatedContext('bob').storage(`gs://${testEnv.projectId}.appspot.com`);
    const image = new Uint8Array([1, 2, 3]);
    await assertFails(uploadTaskPromise(storage.ref('users/alice/patients/p1/evaluations/e1/wounds/img.png').put(image, { contentType: 'image/png' })));
  });

  it('bloqueia arquivo que nao e imagem', async () => {
    const storage = testEnv.authenticatedContext('alice').storage(`gs://${testEnv.projectId}.appspot.com`);
    const text = new Uint8Array([1, 2, 3]);
    await assertFails(uploadTaskPromise(storage.ref('users/alice/patients/p1/evaluations/e1/wounds/img.txt').put(text, { contentType: 'text/plain' })));
  });
});
