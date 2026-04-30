export const formatPhone = (value?: string) => value?.trim() || 'Não informado';
export const formatEmail = (value?: string) => value?.trim() || 'Não informado';

export const pluralize = (count: number, singular: string, plural: string) =>
  `${count} ${count === 1 ? singular : plural}`;

export const formatBytes = (bytes: number) => {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
};

export const getInitials = (name?: string | null) =>
  String(name || 'H+')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase())
    .join('');
