import { initializeApp } from 'firebase/app';
import { initializeAppCheck, ReCaptchaEnterpriseProvider } from 'firebase/app-check';
import {
  browserLocalPersistence,
  connectAuthEmulator,
  getAuth,
  setPersistence
} from 'firebase/auth';
import {
  connectFirestoreEmulator,
  getFirestore
} from 'firebase/firestore';
import {
  connectStorageEmulator,
  getStorage
} from 'firebase/storage';

const requiredEnv = {
  VITE_FIREBASE_API_KEY: import.meta.env.VITE_FIREBASE_API_KEY,
  VITE_FIREBASE_AUTH_DOMAIN: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  VITE_FIREBASE_PROJECT_ID: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  VITE_FIREBASE_STORAGE_BUCKET: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  VITE_FIREBASE_MESSAGING_SENDER_ID: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  VITE_FIREBASE_APP_ID: import.meta.env.VITE_FIREBASE_APP_ID
};

export const missingFirebaseEnv = Object.entries(requiredEnv)
  .filter(([, value]) => !value)
  .map(([key]) => key);

export const isFirebaseConfigured = missingFirebaseEnv.length === 0;

const firebaseConfig = {
  apiKey: requiredEnv.VITE_FIREBASE_API_KEY || 'missing-firebase-api-key',
  authDomain: requiredEnv.VITE_FIREBASE_AUTH_DOMAIN || 'missing-firebase-auth-domain',
  projectId: requiredEnv.VITE_FIREBASE_PROJECT_ID || 'missing-firebase-project',
  storageBucket: requiredEnv.VITE_FIREBASE_STORAGE_BUCKET || 'missing-firebase-storage',
  messagingSenderId: requiredEnv.VITE_FIREBASE_MESSAGING_SENDER_ID || '000000000000',
  appId: requiredEnv.VITE_FIREBASE_APP_ID || '1:000000000000:web:0000000000000000000000',
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID
};

function resolveStorageBucketUrl(storageBucket: string) {
  if (!storageBucket) return undefined;
  return `gs://${storageBucket.replace(/^gs:\/\//, '')}`;
}

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
export const storageBucketName = firebaseConfig.storageBucket.replace(/^gs:\/\//, '');
const storageBucketUrl = resolveStorageBucketUrl(firebaseConfig.storageBucket);
export const storage = storageBucketUrl ? getStorage(app, storageBucketUrl) : getStorage(app);

setPersistence(auth, browserLocalPersistence).catch(() => undefined);
storage.maxUploadRetryTime = 5000;

const useEmulators = import.meta.env.VITE_USE_FIREBASE_EMULATORS === 'true';
const emulatorHost = import.meta.env.VITE_FIREBASE_EMULATOR_HOST || '127.0.0.1';

if (isFirebaseConfigured && useEmulators) {
  connectAuthEmulator(auth, `http://${emulatorHost}:9099`, { disableWarnings: true });
  connectFirestoreEmulator(db, emulatorHost, 8080);
  connectStorageEmulator(storage, emulatorHost, 9199);
}

const appCheckSiteKey = import.meta.env.VITE_RECAPTCHA_ENTERPRISE_SITE_KEY;

if (isFirebaseConfigured && !useEmulators && appCheckSiteKey && typeof window !== 'undefined') {
  const debugToken = import.meta.env.VITE_APPCHECK_DEBUG_TOKEN;
  if (debugToken) {
    (window as unknown as { FIREBASE_APPCHECK_DEBUG_TOKEN: string }).FIREBASE_APPCHECK_DEBUG_TOKEN = debugToken;
  }

  initializeAppCheck(app, {
    provider: new ReCaptchaEnterpriseProvider(appCheckSiteKey),
    isTokenAutoRefreshEnabled: true
  });
}
