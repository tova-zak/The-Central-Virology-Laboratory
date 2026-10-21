import type { SavedBatchStatus, SavedStatusFilter } from '../../services/api';

export const STATUS_FILTERS: { value: SavedStatusFilter; label: string }[] = [
  { value: 'all', label: 'הכול' },
  { value: 'pending', label: 'ממתין לבדיקה' },
  { value: 'needs_correction', label: 'דורש תיקון' },
  { value: 'approved', label: 'אושר' },
];

export const STATUS_LABEL: Record<SavedBatchStatus, string> = {
  pending: 'ממתין לבדיקה',
  needs_correction: 'דורש תיקון',
  approved: 'אושר',
};

export const formatSavedDate = (iso: string | null): string => {
  if (!iso) return 'לא ידוע';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return 'לא ידוע';
  return date.toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' });
};
