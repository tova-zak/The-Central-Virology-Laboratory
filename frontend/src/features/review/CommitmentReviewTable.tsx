/**
 * CommitmentReviewTable - one row per page/commitment, with field evidence for fields that need review.
 * Exception-only review: clean fields are shown read-only (auto-accepted, never "human verified"); only fields
 * with a real problem show the Hebrew reason and an edit/confirm button. Editing and approval go through the
 * existing edit dialog and backend; this component never verifies anything.
 */
import React from 'react';
import { CommitmentRecord } from '../../services/api';
import { getFieldLabel } from './utils/editPermissions';
import { FieldEvidence } from './FieldEvidence';
import './CommitmentReviewTable.css';
import {
  canApproveAsIs, exportableCommitmentCount, isHumanVerified, needsReview, reviewReasons,
  sourcePageLabel, visiblePageWarnings,
} from './utils/evidence';

export const REVIEW_FIELDS = [
  'patient_first_name', 'patient_last_name', 'patient_id_number',
  'sender', 'received_date', 'central_numbers', 'commitment_number',
] as const;

export type ReviewFieldName = typeof REVIEW_FIELDS[number];

interface CommitmentReviewTableProps {
  records: CommitmentRecord[];
  onEdit: (recordId: string, fieldName: ReviewFieldName, value: any, helperText?: string) => void;
  onRejectCandidate: (recordId: string, fieldName: ReviewFieldName, value: string) => void;
  onViewSource: (record: CommitmentRecord) => void;
}

const USE_CANDIDATE_HINT = 'הערך המוצע טרם אושר. ערוך אותו לפי הצורך ושמור כדי לאשר.';

/** Display text; for commitment numbers also lists every accepted extra number (one Excel row each). */
function displayText(name: ReviewFieldName, field: any, value: any): string {
  if (Array.isArray(value)) return value.join(', ');
  if (!value) return '';
  if (name === 'commitment_number') {
    const extras = (field?.candidates ?? [])
      .filter((c: any) => c.reason === 'multiple_commitments_on_page' && c.status !== 'rejected' && c.value && c.value !== value)
      .map((c: any) => c.value);
    return [value, ...extras].join(', ');
  }
  return String(value);
}

export const CommitmentReviewTable: React.FC<CommitmentReviewTableProps> = ({ records, onEdit, onRejectCandidate, onViewSource }) => (
  <section className="table-section commitment-review-table-section">
    <h2>בדיקת התחייבויות לפי עמוד</h2>
    <div className="table-wrapper">
    <table className="review-table commitment-review-table" dir="rtl">
      <thead>
        <tr>
          <th className="col-page">עמוד</th>
          {REVIEW_FIELDS.map(name => <th key={name} className={`col-${name}`}>{getFieldLabel(name)}</th>)}
        </tr>
      </thead>
      <tbody>
        {records.map(record => {
          const warnings = visiblePageWarnings(record.page_warnings);
          const page = sourcePageLabel(record);
          return (
            <tr key={record.commitment_record_id}>
              <td className="col-page" data-label="עמוד">
                <span className="page-number" title={record.form_id ? `מסמך: ${record.form_id}` : undefined}>{page}</span>
                <button type="button" onClick={() => onViewSource(record)} aria-label={`צפה במקור, עמוד ${page}`}>מקור</button>
                {warnings.length > 0 && (
                  <details className="page-warnings">
                    <summary>הערות ({warnings.length})</summary>
                    <ul>{warnings.map(w => <li key={w}>{w}</li>)}</ul>
                  </details>
                )}
              </td>
              {REVIEW_FIELDS.map(name => {
                const field = record[name] as any;
                const value = field?.reviewed_value ?? field?.normalized_value ?? field?.raw_value;
                const emptyValue = name === 'central_numbers' ? [] : '';
                const verified = isHumanVerified(field);
                const review = !verified && needsReview(name, field);
                const reasons = review ? reviewReasons(name, field) : [];
                const approvable = canApproveAsIs(name, field);
                const text = displayText(name, field, value);
                const label = getFieldLabel(name);
                const cellClass = verified ? 'cell-verified' : review ? 'cell-review' : 'cell-auto';
                return (
                  <td key={name} className={`col-${name} ${cellClass}`} data-label={label}>
                    <span className="cell-value" dir="auto" title={text || undefined} aria-label={text ? `${label}: ${text}` : undefined}>
                      {text || '-'}
                    </span>
                    {verified && <span className="cell-state state-approved">מאושר</span>}
                    {!verified && !review && <span className="cell-state state-auto">זוהה אוטומטית</span>}
                    {review && (
                      <>
                        <span className="cell-state state-review">דורש בדיקה</span>
                        {reasons.map(reason => <span key={reason} className="cell-reason" role="note">{reason}</span>)}
                        <button type="button" onClick={() => onEdit(record.commitment_record_id, name, value ?? emptyValue)}>
                          {approvable ? 'ערוך ואשר' : 'תקן ואשר'}
                        </button>
                      </>
                    )}
                    {name === 'commitment_number' && exportableCommitmentCount(field) > 1 && (
                      <span className="cell-export-note">
                        {`ייוצאו ${exportableCommitmentCount(field)} שורות באקסל`}
                      </span>
                    )}
                    {review && (
                      <FieldEvidence
                        fieldName={name}
                        field={field}
                        onUseCandidate={candidate => onEdit(record.commitment_record_id, name, candidate, USE_CANDIDATE_HINT)}
                        onRejectCandidate={candidate => onRejectCandidate(record.commitment_record_id, name, candidate)}
                      />
                    )}
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
    </div>
  </section>
);
