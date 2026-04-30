import { doc, serverTimestamp, updateDoc } from 'firebase/firestore';
import { getDownloadURL, ref, uploadBytes } from 'firebase/storage';
import { z } from 'zod';

import { db, storage } from '../../lib/firebase';
import { userPath } from '../../lib/firestorePaths';
import { getFileExtension, profileImagePath } from '../../lib/storagePaths';
import { validateImageFile } from '../../lib/validators';

export const profileSchema = z.object({
  displayName: z.string().min(2, 'Informe seu nome.').max(90),
  email: z.string().email('Informe um e-mail válido.'),
  professionalArea: z.string().max(90).optional().default(''),
  clinicName: z.string().max(120).optional().default(''),
  phone: z.string().max(30).optional().default('')
});

export type ProfileFormValues = z.infer<typeof profileSchema>;

export async function updateProfileData(uid: string, values: ProfileFormValues) {
  await updateDoc(doc(db, userPath(uid)), {
    displayName: values.displayName,
    email: values.email,
    professionalArea: values.professionalArea || '',
    clinicName: values.clinicName || '',
    phone: values.phone || '',
    updatedAt: serverTimestamp()
  });
}

export async function uploadProfilePhoto(uid: string, file: File) {
  const validationError = validateImageFile(file);
  if (validationError) throw new Error(validationError);

  const path = profileImagePath(uid, getFileExtension(file));
  const fileRef = ref(storage, path);
  await uploadBytes(fileRef, file, { contentType: file.type });
  const downloadURL = await getDownloadURL(fileRef);

  await updateDoc(doc(db, userPath(uid)), {
    photoURL: downloadURL,
    updatedAt: serverTimestamp()
  });

  return downloadURL;
}

export async function updateSettings(uid: string, settings: Record<string, unknown>) {
  const updatePayload = Object.fromEntries(Object.entries(settings).map(([key, value]) => [`settings.${key}`, value]));
  await updateDoc(doc(db, userPath(uid)), {
    ...updatePayload,
    updatedAt: serverTimestamp()
  });
}
