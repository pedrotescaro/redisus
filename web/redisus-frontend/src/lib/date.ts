import { addDays, format, isValid, parseISO } from 'date-fns';
import { ptBR } from 'date-fns/locale';

export const todayISO = () => format(new Date(), 'yyyy-MM-dd');
export const tomorrowISO = () => format(addDays(new Date(), 1), 'yyyy-MM-dd');

export const formatDate = (value?: string) => {
  if (!value) return 'Sem data';
  const parsed = parseISO(value);
  return isValid(parsed) ? format(parsed, 'dd/MM/yyyy', { locale: ptBR }) : value;
};

export const formatDateLong = (value?: string) => {
  if (!value) return 'Sem data';
  const parsed = parseISO(value);
  return isValid(parsed) ? format(parsed, "dd 'de' MMMM 'de' yyyy", { locale: ptBR }) : value;
};

export const sortByDateTime = <T extends { date: string; time?: string }>(items: T[]) =>
  [...items].sort((a, b) => `${a.date} ${a.time || ''}`.localeCompare(`${b.date} ${b.time || ''}`));
