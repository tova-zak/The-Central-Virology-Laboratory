/**
 * FieldEvidence - shows what the extractor preserved for a field that still needs review:
 * candidate values (with the label they came from), short notes, and the original ambiguous date.
 *
 * Candidates are suggestions only. "Use value" opens the edit dialog pre-filled; nothing is saved or
 * verified until the reviewer saves there. Rejecting only hides the suggestion. Human-verified fields
 * render nothing.
 */
import React from 'react';
import {
  EvidenceField, pendingCandidates, rejectedCandidates, visibleNotes, hasEvidence,
  isAmbiguousYearDate, reasonLabel,
} from './utils/evidence';

interface FieldEvidenceProps {
  fieldName: string;
  field?: EvidenceField | null;
  onUseCandidate: (value: string) => void;
  onRejectCandidate: (value: string) => void;
}

export const FieldEvidence: React.FC<FieldEvidenceProps> = ({ fieldName, field, onUseCandidate, onRejectCandidate }) => {
  if (!field) return null;
  const ambiguousDate = fieldName === 'received_date' && isAmbiguousYearDate(field);
  if (!hasEvidence(field) && !ambiguousDate) return null;

  const candidates = pendingCandidates(field);
  const rejected = rejectedCandidates(field);
  const notes = visibleNotes(field);
  const original = typeof field.raw_value === 'string' ? field.raw_value : '';
  const summary = ambiguousDate
    ? 'שנה לא חד-משמעית'
    : candidates.length > 0
      ? `${candidates.length} ${candidates.length === 1 ? 'מועמד לבדיקה' : 'מועמדים לבדיקה'}`
      : 'הערות לבדיקה';

  return (
    <details className="field-evidence" open={ambiguousDate || candidates.length > 0}>
      <summary>{summary}</summary>

      {ambiguousDate && (
        <p className="evidence-ambiguous-date" role="alert">
          התאריך שנקרא מהטופס: <bdi dir="ltr" className="evidence-value">{original}</bdi>.
          לא ניתן לדעת את המאה, ולכן נדרש להזין או לבחור תאריך מלא ולאשר אותו.
        </p>
      )}

      {candidates.length > 0 && (
        <ul className="evidence-candidates">
          {candidates.map(candidate => (
            <li key={candidate.value} className="evidence-candidate">
              <bdi dir="ltr" className="evidence-value">{candidate.value}</bdi>
              <span className="evidence-reason">{reasonLabel(candidate.reason)}</span>
              {candidate.source_label && fieldName === 'commitment_number' && (
                <span className="evidence-source">תווית בטופס: {candidate.source_label}</span>
              )}
              <span className="evidence-actions">
                <button type="button" className="evidence-btn" onClick={() => onUseCandidate(candidate.value)}>
                  השתמש בערך
                </button>
                <button type="button" className="evidence-btn evidence-btn-secondary" onClick={() => onRejectCandidate(candidate.value)}>
                  דחה
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {notes.length > 0 && (
        <ul className="evidence-notes">
          {notes.map(note => <li key={note}>{note}</li>)}
        </ul>
      )}

      {rejected.length > 0 && (
        <p className="evidence-rejected">נדחו: {rejected.map(c => c.value).join(', ')}</p>
      )}
    </details>
  );
};