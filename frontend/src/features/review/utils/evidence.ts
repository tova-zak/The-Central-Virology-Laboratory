/**
 * Pure helpers for presenting extraction evidence to a human reviewer.
 * No React and no side effects, so the rules can be tested with `node --test`.
 *
 * Rules enforced here:
 *  - a candidate is only a suggestion; nothing in this file marks anything verified;
 *  - a field that is already human_verified shows no candidate actions;
 *  - a two-digit-year date is read as 20YY (backend policy 2000+YY), is always flagged as an inferred century,
 *    and is only accepted after a human confirms or types it.
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
  validation_issues?: { severity?: string; message?: string; code?: string | null }[];
  candidates?: EvidenceCandidate[];
  extraction_notes?: string[];
  review_required?: boolean;
  review_reasons_he?: string[];
}

const REASON_LABELS: Record<string, string> = {
  multiple_commitments_on_page: 'מספר נוסף שזוהה בעמוד',
  no_recognized_label: 'לא זוהתה תווית התחייבות',
  ambiguous_label: 'התווית אינה חד-משמעית',
  sample_label_requires_leumit: 'תווית "דגימה" מתקבלת רק עבור לאומית',
  overlaps_central_number: 'זהה למספר מרכזי',
  century_inferred: 'השנה נקראה בספרתיים בלבד ופוענחה כ-20YY - יש לאשר או לתקן',
  possible_full_name_in_first_name_field: 'ייתכן שזה שם מלא (לא פוצל אוטומטית)',
};

const TWO_DIGIT_YEAR = /^\s*\d{1,2}([./-])\d{1,2}\1\d{2}\s*$/;
const COMPLETE_DATE = /^\s*(\d{1,2}([./-])\d{1,2}\2\d{4}|\d{4}-\d{1,2}-\d{1,2})\s*$/;

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
    const note = String(raw).replace(/\s+/g, ' ').trim();
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
    const text = String(raw).replace(/\s+/g, ' ').trim();
    if (text && !seen.has(text)) {
      seen.add(text);
      result.push(text);
    }
  }
  return result;
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

/** True when the date has a two-digit year, so its century (20YY) was inferred and awaits human confirmation. */
export function isCenturyInferredDate(field?: EvidenceField | null): boolean {
  if (!field || isHumanVerified(field)) return false;
  const original = typeof field.raw_value === 'string' ? field.raw_value : '';
  if (TWO_DIGIT_YEAR.test(original)) return true;
  return (field.validation_issues ?? []).some(
    issue => issue.code === 'century_inferred' || (issue.message ?? '').startsWith('Century inferred'),
  );
}

/** Backward-compatible name for isCenturyInferredDate. */
export const isAmbiguousYearDate = isCenturyInferredDate;

export function isCompleteDate(text: unknown): boolean {
  return typeof text === 'string' && COMPLETE_DATE.test(text);
}

/**
 * Approving the value unchanged is allowed for a century-inferred date only when its normalized value is a
 * complete 4-digit date (the backend stores that value on approval). Unrecognized or incomplete dates cannot be approved.
 */
export function canApproveAsIs(fieldName: string, field?: EvidenceField | null): boolean {
  if (fieldName === 'received_date') {
    const value = effectiveValue(field);
    if (typeof value === 'string' && value.trim() && !isCompleteDate(value)) return false;
  }
  return true;
}

const MISSING_HE: Record<string, string> = {
  patient_first_name: 'השם הפרטי לא זוהה במסמך.',
  patient_last_name: 'שם המשפחה לא זוהה במסמך.',
  patient_id_number: 'מספר תעודת הזהות לא זוהה במסמך.',
  sender: 'הגורם השולח לא זוהה או אינו ברשימה המאושרת.',
  received_date: 'תאריך קבלת הדגימה לא זוהה במסמך.',
  central_numbers: 'לא זוהה מספר מרכזי במסמך.',
  commitment_number: 'לא זוהה מספר התחייבות במסמך.',
};
const WARNING_HE: Record<string, string> = {
  patient_first_name: 'השם בכתב היד אינו קריא באופן ברור.',
  patient_last_name: 'שם המשפחה בכתב היד אינו קריא באופן ברור.',
  patient_id_number: 'מספר תעודת הזהות אינו קריא או אינו חד-משמעי במסמך.',
  sender: 'הגורם השולח אינו חד-משמעי במסמך.',
  received_date: 'התאריך אינו ברור או אינו חד-משמעי במסמך.',
  central_numbers: 'המספר המרכזי אינו ברור או אינו חד-משמעי במסמך.',
  commitment_number: 'מספר ההתחייבות אינו ברור או אינו חד-משמעי במסמך.',
};

function isEmptyValue(value: unknown): boolean {
  return value === null || value === undefined || (typeof value === 'string' && !value.trim())
    || (Array.isArray(value) && value.length === 0);
}

/**
 * Hebrew reasons why a field still needs a human. The backend (review_reasons_he) is authoritative; this
 * fallback mirrors its rules for older responses. Empty list == clean/auto-accepted or already resolved.
 */
export function reviewReasons(fieldName: string, field?: EvidenceField | null): string[] {
  if (!field) return [MISSING_HE[fieldName] ?? 'הערך חסר.'];
  if (isHumanVerified(field)) return [];
  if (Array.isArray(field.review_reasons_he)) return field.review_reasons_he;
  const reasons: string[] = [];
  const add = (text: string) => { if (!reasons.includes(text)) reasons.push(text); };
  if (isEmptyValue(effectiveValue(field))) add(MISSING_HE[fieldName] ?? 'הערך חסר.');
  if (isCenturyInferredDate(field)) add('התאריך כולל שנה דו־ספרתית שהורחבה ל־20YY — נדרש אישור.');
  for (const issue of field.validation_issues ?? []) {
    if (issue.code !== 'century_inferred') add(issue.message ? 'נמצאה בעיית תקינות בערך — יש לתקן או לאשר.' : 'הערך אינו תקין.');
  }
  if (pendingCandidates(field).some(c => c.reason !== 'multiple_commitments_on_page')) {
    add('זוהו אפשרויות נוספות — נדרשת בחירה ידנית.');
  }
  if ((field.extraction_notes ?? []).length > 0 || ['uncertain', 'conflicting', 'invalid'].includes(field.extraction_state ?? '')) {
    add(WARNING_HE[fieldName] ?? 'זוהתה אזהרת חילוץ בשדה.');
  }
  if (reasons.length === 0 && (field.review_state === 'needs_review' || field.review_state === 'rejected')) {
    add('השדה סומן לבדיקה ידנית.');
  }
  return reasons;
}

/** Exception-only review: true only for an unresolved field that needs a human. */
export function needsReview(fieldName: string, field?: EvidenceField | null): boolean {
  if (field && typeof field.review_required === 'boolean' && !isHumanVerified(field)) return field.review_required;
  return reviewReasons(fieldName, field).length > 0;
}

/** Source page (1-based) as stored by the backend; never a row index. */
export function sourcePageLabel(record: { source_page?: number | null; form_id?: string | null }): string {
  if (typeof record.source_page === 'number' && record.source_page >= 1) return String(record.source_page);
  const match = (record.form_id ?? '').match(/_page_(\d+)$/);
  return match ? String(Number(match[1]) + 1) : '—';
}

/** Validator for the edit dialog: returns an error message or null. */
export function validateEditedValue(fieldName: string, value: unknown): string | null {
  if (fieldName === 'received_date' && typeof value === 'string' && value.trim()) {
    return isCompleteDate(value) || TWO_DIGIT_YEAR.test(value)
      ? null
      : 'יש להזין תאריך מלא, למשל 15/03/2024 (שנה בת 2 ספרות תיקרא כ-20YY)';
  }
  return null;
}
