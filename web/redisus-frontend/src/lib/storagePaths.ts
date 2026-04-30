export const woundImagePath = (uid: string, patientId: string, evaluationId: string, imageId: string, extension = 'jpg') =>
  `users/${uid}/patients/${patientId}/evaluations/${evaluationId}/wounds/${imageId}.${extension}`;

export const profileImagePath = (uid: string, extension = 'jpg') => `users/${uid}/profile/photo.${extension}`;

export const getFileExtension = (file: File) => {
  const fromName = file.name.split('.').pop()?.toLowerCase();
  if (fromName && /^[a-z0-9]+$/.test(fromName)) return fromName;
  if (file.type === 'image/png') return 'png';
  if (file.type === 'image/webp') return 'webp';
  return 'jpg';
};
