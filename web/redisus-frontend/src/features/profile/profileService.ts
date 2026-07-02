import { z } from 'zod';
import { supabase } from '../../lib/supabase';
import { generateUUID } from '../../lib/uuid';
import { validateImageFile } from '../../lib/validators';

export const profileSchema = z.object({
  displayName: z.string().min(2, 'Informe seu nome.').max(90),
  email: z.string().email('Informe um e-mail válido.'),
  professionalArea: z.string().max(90).optional().default(''),
  clinicName: z.string().max(120).optional().default(''),
  phone: z.string().max(30).optional().default('')
});

export type ProfileFormValues = z.infer<typeof profileSchema>;

export async function updateProfileData(uid: string, values: ProfileFormValues): Promise<void> {
  const { error } = await supabase
    .from('users')
    .update({
      display_name: values.displayName,
      email: values.email,
      professional_area: values.professionalArea || '',
      clinic_name: values.clinicName || '',
      phone: values.phone || '',
      updated_at: new Date().toISOString()
    })
    .eq('uid', uid);

  if (error) throw new Error(error.message);
}

export async function uploadProfilePhoto(uid: string, file: File): Promise<string> {
  const validationError = validateImageFile(file);
  if (validationError) throw new Error(validationError);

  const ext = file.name.split('.').pop() || 'png';
  const storagePath = `${uid}/profile_${generateUUID()}.${ext}`;

  const { error: uploadError } = await supabase.storage
    .from('profile-photos')
    .upload(storagePath, file, {
      contentType: file.type,
      upsert: true
    });

  if (uploadError) throw uploadError;

  const { data: urlData } = supabase.storage
    .from('profile-photos')
    .getPublicUrl(storagePath);

  const downloadURL = urlData.publicUrl;

  const { error: updateError } = await supabase
    .from('users')
    .update({
      photo_url: downloadURL,
      updated_at: new Date().toISOString()
    })
    .eq('uid', uid);

  if (updateError) throw new Error(updateError.message);

  return downloadURL;
}

export async function updateSettings(uid: string, settings: Record<string, unknown>): Promise<void> {
  const { data: user, error: fetchError } = await supabase
    .from('users')
    .select('settings')
    .eq('uid', uid)
    .single();

  if (fetchError) throw new Error(fetchError.message);

  const mergedSettings = {
    ...(user?.settings || {}),
    ...settings
  };

  const { error } = await supabase
    .from('users')
    .update({
      settings: mergedSettings,
      updated_at: new Date().toISOString()
    })
    .eq('uid', uid);

  if (error) throw new Error(error.message);
}
