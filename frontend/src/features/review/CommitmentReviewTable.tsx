/**
 * CommitmentReviewTable - one row per page/commitment, with field evidence for fields that need review.
 * All fields remain editable; explicit whole-record confirmation is separate from field verification.
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
  onConfirmReview: (record: CommitmentRecord) => void;
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

export const CommitmentReviewTable: React.FC<CommitmentReviewTableProps> = ({ records, onEdit, onRejectCandidate, onViewSource, onConfirmReview }) => (
  <section className="table-section commitment-review-table-section">
    <h2>בדיקה סופית של הרשומות לפני ייצוא</h2>
    <p>יש לבדוק מול המקור את כל שבעת השדות, גם ללא התראות, לתקן לפי הצורך ולאשר כל רשומה בסיום.</p>
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
            <React.Fragment key={record.commitment_record_id}>
            <tr>
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
                      </>
                    )}
                    <button type="button" aria-label={`עריכת ${label}, עמוד ${page}`} onClick={() => {
                      const editValue = name === 'commitment_number'
                        ? [value, ...(field?.candidates ?? []).filter((c: any) => c.reason === 'multiple_commitments_on_page' && c.status !== 'rejected').map((c: any) => c.value)].filter((v, i, all) => v && all.indexOf(v) === i)
                        : value ?? emptyValue;
                      onEdit(record.commitment_record_id, name, editValue);
                    }}>
                      {review ? (approvable ? 'ערוך ואשר' : 'תקן ואשר') : 'עריכה'}
                    </button>
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
            <tr className="final-record-review">
              <td colSpan={8}>
                {record.final_review_confirmed ? <span role="status">בדיקת הרשומה אושרה. האישור נשמר עד לשינוי הנתונים.</span> : <>
                  <span>נדרש אישור בדיקה סופית של כל הרשומה. </span>
                  <button type="button" onClick={() => onConfirmReview(record)}
                    disabled={!record.final_review_token || REVIEW_FIELDS.some(name => needsReview(name, record[name])) || record.relationship_status === 'unresolved_relationship'}>
                    אישור בדיקת הרשומה, עמוד {page}
                  </button>
                  {(REVIEW_FIELDS.some(name => needsReview(name, record[name])) || record.relationship_status === 'unresolved_relationship') && <span> יש לפתור את ההערות והקשרים לפני האישור.</span>}
                </>}
              </td>
            </tr>
            </React.Fragment>
          );
        })}
      </tbody>
    </table>
    </div>
  </section>
);
