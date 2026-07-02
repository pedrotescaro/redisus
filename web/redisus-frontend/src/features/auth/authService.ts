import {
  createUserWithEmailAndPassword,
  GoogleAuthProvider,
  OAuthProvider,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  signInWithRedirect,
  signOut,
  updateProfile,
  type AuthProvider,
  type User
} from 'firebase/auth';
import { auth } from '../../lib/firebase';
import { supabase } from '../../lib/supabase';
import type { UserProfile } from '../../lib/types';
import type { LoginFormValues, RegisterFormValues } from './authSchema';

const defaultSettings: UserProfile['settings'] = {
  theme: 'light',
  notificationsEnabled: true,
  emailNotificationsEnabled: true,
  agendaRemindersEnabled: true,
  hideEmailPreview: false,
  showProfilePhoto: true
};

const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: 'select_account' });

const microsoftProvider = new OAuthProvider('microsoft.com');
microsoftProvider.setCustomParameters({ prompt: 'select_account' });

const appleProvider = new OAuthProvider('apple.com');
appleProvider.addScope('email');
appleProvider.addScope('name');

export function friendlyAuthError(error: unknown) {
  const code = typeof error === 'object' && error && 'code' in error ? String(error.code) : '';

  if (code.includes('auth/user-not-found') || code.includes('auth/wrong-password') || code.includes('auth/invalid-credential')) {
    return 'E-mail ou senha incorretos.';
  }
  if (code.includes('auth/email-already-in-use')) return 'Este e-mail já está cadastrado.';
  if (code.includes('auth/weak-password')) return 'Use uma senha mais forte.';
  if (code.includes('auth/popup-closed-by-user')) return 'Login cancelado antes da conclusão.';
  if (code.includes('auth/account-exists-with-different-credential')) {
    return 'Já existe uma conta com este e-mail usando outro provedor.';
  }
  if (code.includes('auth/unauthorized-domain')) return 'Este domínio não está autorizado no Firebase Auth.';
  if (code.includes('auth/popup-blocked')) return 'O navegador bloqueou o popup. Tente novamente ou permita popups.';
  if (code.includes('auth/too-many-requests')) return 'Muitas tentativas. Aguarde alguns minutos.';
  if (code.includes('auth/network-request-failed')) return 'Falha de rede ao falar com o Firebase.';
  return 'Não foi possível concluir a autenticação. Tente novamente.';
}

function providerIds(user: User) {
  const ids = user.providerData.map(provider => provider.providerId);
  return Array.from(new Set(ids));
}

export async function ensureUserProfile(user: User, extras: Partial<UserProfile> = {}) {
  const { data: profileSnap, error: fetchError } = await supabase
    .from('users')
    .select('*')
    .eq('uid', user.uid)
    .maybeSingle();

  if (fetchError) throw new Error(fetchError.message);

  const baseProfile = {
    uid: user.uid,
    display_name: extras.displayName || user.displayName || user.email?.split('@')[0] || 'Profissional',
    email: extras.email || user.email || '',
    photo_url: extras.photoURL ?? user.photoURL ?? null,
    provider_ids: providerIds(user),
    role: 'professional',
    settings: extras.settings || defaultSettings
  };

  if (!profileSnap) {
    const { error: insertError } = await supabase
      .from('users')
      .insert({
        ...baseProfile,
        professional_area: extras.professionalArea || '',
        clinic_name: extras.clinicName || '',
        phone: extras.phone || '',
        onboarding_completed: extras.onboardingCompleted ?? false
      });
    if (insertError) throw new Error(insertError.message);
    return;
  }

  const { error: updateError } = await supabase
    .from('users')
    .update({
      display_name: baseProfile.display_name,
      email: baseProfile.email,
      photo_url: baseProfile.photo_url,
      provider_ids: baseProfile.provider_ids,
      updated_at: new Date().toISOString()
    })
    .eq('uid', user.uid);

  if (updateError) throw new Error(updateError.message);
}

export async function signInWithEmail(email: string, password: string) {
  const credential = await signInWithEmailAndPassword(auth, email, password);
  await ensureUserProfile(credential.user);
  return credential.user;
}

export async function signUpWithEmail(name: string, email: string, password: string) {
  const credential = await createUserWithEmailAndPassword(auth, email, password);
  await updateProfile(credential.user, { displayName: name });
  await ensureUserProfile(credential.user, { displayName: name, email, onboardingCompleted: false });
  return credential.user;
}

async function signInWithProvider(provider: AuthProvider) {
  try {
    const credential = await signInWithPopup(auth, provider);
    await ensureUserProfile(credential.user);
    return credential.user;
  } catch (error) {
    const code = typeof error === 'object' && error && 'code' in error ? String(error.code) : '';
    if (code.includes('auth/popup-blocked')) {
      await signInWithRedirect(auth, provider);
      return null;
    }
    throw error;
  }
}

export const signInWithGoogle = () => signInWithProvider(googleProvider);
export const signInWithMicrosoft = () => signInWithProvider(microsoftProvider);
export const signInWithApple = () => signInWithProvider(appleProvider);
export const resetPassword = (email: string) => sendPasswordResetEmail(auth, email);
export const logout = () => signOut(auth);

export async function updateUserProfile(uid: string, values: Partial<UserProfile>) {
  const payload: Record<string, any> = {
    uid,
    updated_at: new Date().toISOString()
  };
  if ('displayName' in values) payload.display_name = values.displayName;
  if ('email' in values) payload.email = values.email;
  if ('photoURL' in values) payload.photo_url = values.photoURL;
  if ('providerIds' in values) payload.provider_ids = values.providerIds;
  if ('role' in values) payload.role = values.role;
  if ('settings' in values) payload.settings = values.settings;
  if ('professionalArea' in values) payload.professional_area = values.professionalArea;
  if ('clinicName' in values) payload.clinic_name = values.clinicName;
  if ('phone' in values) payload.phone = values.phone;
  if ('onboardingCompleted' in values) payload.onboarding_completed = values.onboardingCompleted;

  const { error } = await supabase
    .from('users')
    .upsert(payload, { onConflict: 'uid' });

  if (error) throw new Error(error.message);
}

export const loginWithEmail = (values: LoginFormValues) => signInWithEmail(values.email, values.password);
export const registerWithEmail = (values: RegisterFormValues) => signUpWithEmail(values.displayName, values.email, values.password);
