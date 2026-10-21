/**
 * Pure helpers for presenting extraction evidence to a human reviewer.
 * No React and no side effects, so the rules can be tested with `node --test`.
 *
 * Rules enforced here:
 *  - a candidate is only a suggestion; nothing in this file marks anything verified;
 *  - a field that is already human_verified shows no candidate actions;
 *  - an ambiguous two-digit-year date can never be approved as is.
 */

export interface EvidenceCandidate {
  value: string;
  source_label?: string | null;
  reason: string;
  status?: string;
}

export interface EvidenceField {
  raw_value?: unknown;
  normalized_value?: unknown;
  reviewed_value?: unknown;
  extraction_state?: string;
  review_state?: string;
  validation_issues?: { severity?: string; message?: string }[];
  candidates?: EvidenceCandidate[];
  extraction_notes?: string[];
}

const REASON_LABELS: Record<string, string> = {
  multiple_commitments_on_page: 'מספר נוסף שזוהה בעמוד',
  no_recognized_label: 'לא זוהתה תווית התחייבות',
  ambiguous_label: 'התווית אינה חד-משמעית',
  sample_label_requires_leumit: 'תווית "דגימה" מתקבלת רק עבור לאומית',
  overlaps_central_number: 'זהה למספר מרכזי',
  ambiguous_two_digit_year: 'שנה אפשרית (לא נקבעה אוטומטית)',
  possible_full_name_in_first_name_field: 'ייתכן שזה שם מלא (לא פוצל אוטומטית)',
};

const TWO_DIGIT_YEAR = /^\s*\d{1,2}([./-])\d{1,2}\1\d{2}\s*$/;
const COMPLETE_DATE = /^\s*(\d{1,2}([./-])\d{1,2}\2\d{4}|\d{4}-\d{1,2}-\d{1,2})\s*$/;
const NOTE_DISPLAY_LIMIT = 200;
const WARNING_DISPLAY_LIMIT = 5;

export function reasonLabel(reason: string): string {
  return REASON_LABELS[reason] ?? 'מועמד לבדיקה';
}

export function isHumanVerified(field?: EvidenceField | null): boolean {
  return field?.review_state === 'human_verified';
}

/** Candidates the reviewer has not rejected. Empty for human-verified fields. */
export function pendingCandidates(field?: EvidenceField | null): EvidenceCandidate[] {
  if (!field || isHumanVerified(field)) return [];
  return (field.candidates ?? []).filter(c => (c.status ?? 'pending') !== 'rejected');
}

export function rejectedCandidates(field?: EvidenceField | null): EvidenceCandidate[] {
  if (!field || isHumanVerified(field)) return [];
  return (field.candidates ?? []).filter(c => c.status === 'rejected');
}

/** Short, non-technical notes worth showing; duplicates removed. */
export function visibleNotes(field?: EvidenceField | null): string[] {
  if (!field || isHumanVerified(field)) return [];
  const seen = new Set<string>();
  const notes: string[] = [];
  for (const raw of field.extraction_notes ?? []) {
    const note = String(raw).replace(/\s+/g, ' ').trim().slice(0, NOTE_DISPLAY_LIMIT);
    if (note && !seen.has(note)) {
      seen.add(note);
      notes.push(note);
    }
  }
  return notes;
}

export function visiblePageWarnings(warnings?: string[] | null): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const raw of warnings ?? []) {
    const text = String(raw).replace(/\s+/g, ' ').trim().slice(0, NOTE_DISPLAY_LIMIT);
    if (text && !seen.has(text)) {
      seen.add(text);
      result.push(text);
    }
  }
  return result.slice(0, WARNING_DISPLAY_LIMIT);
}

export function hasEvidence(field?: EvidenceField | null): boolean {
  return pendingCandidates(field).length > 0 || visibleNotes(field).length > 0;
}

export function effectiveValue(field?: EvidenceField | null): unknown {
  if (!field) return null;
  return field.reviewed_value ?? field.normalized_value ?? field.raw_value ?? null;
}

/**
 * Number of Excel rows a commitment_number field produces (mirrors the backend export):
 * the effective value plus every non-rejected "multiple_commitments_on_page" candidate.
 * Unlike pendingCandidates, this stays accurate after the field is approved.
 */
export function exportableCommitmentCount(field?: EvidenceField | null): number {
  const value = effectiveValue(field);
  if (value === null || value === undefined || String(value).trim() === '') return 1;
  const numbers = new Set<string>([String(value)]);
  for (const c of field?.candidates ?? []) {
    if (c.reason === 'multiple_commitments_on_page' && c.status !== 'rejected' && c.value) {
      numbers.add(c.value);
    }
  }
  return numbers.size;
}

/** True when the date has a two-digit year, so the century is unknown. */
export function isAmbiguousYearDate(field?: EvidenceField | null): boolean {
  if (!field || isHumanVerified(field)) return false;
  const original = typeof field.raw_value === 'string' ? field.raw_value : '';
  if (TWO_DIGIT_YEAR.test(original)) return true;
  return (field.validation_issues ?? []).some(issue => (issue.message ?? '').startsWith('Ambiguous two-digit year'));
}

export function isCompleteDate(text: unknown): boolean {
  return typeof text === 'string' && COMPLETE_DATE.test(text);
}

/** Approving the value unchanged is not allowed for an ambiguous date. */
export function canApproveAsIs(fieldName: string, field?: EvidenceField | null): boolean {
  if (fieldName === 'received_date') {
    const value = effectiveValue(field);
    if (isAmbiguousYearDate(field)) return false;
    if (typeof value === 'string' && TWO_DIGIT_YEAR.test(value)) return false;
  }
  return true;
}

/** Validator for the edit dialog: returns an error message or null. */
export function validateEditedValue(fieldName: string, value: unknown): string | null {
  if (fieldName === 'received_date' && typeof value === 'string' && value.trim()) {
    return isCompleteDate(value) ? null : 'יש להזין תאריך מלא עם שנה בת 4 ספרות, למשל 15/03/2024';
  }
  return null;
}