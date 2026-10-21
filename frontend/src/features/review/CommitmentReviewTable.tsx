/**
 * CommitmentReviewTable - one row per page/commitment, with field evidence for fields that need review.
 * Editing and approval go through the existing edit dialog and backend; this component never verifies anything.
 */
import React from 'react';
import { CommitmentRecord } from '../../services/api';
import { getFieldLabel } from './utils/editPermissions';
import { FieldEvidence } from './FieldEvidence';
import { canApproveAsIs, isHumanVerified, visiblePageWarnings } from './utils/evidence';

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

export const CommitmentReviewTable: React.FC<CommitmentReviewTableProps> = ({ records, onEdit, onRejectCandidate, onViewSource }) => (
  <section className="table-section">
    <h2>בדיקת התחייבויות לפי עמוד</h2>
    <table className="review-table commitment-review-table" dir="rtl">
      <thead>
        <tr>
          <th>עמוד</th>
          {REVIEW_FIELDS.map(name => <th key={name}>{getFieldLabel(name)}</th>)}
        </tr>
      </thead>
      <tbody>
        {records.map(record => {
          const warnings = visiblePageWarnings(record.page_warnings);
          return (
            <tr key={record.commitment_record_id}>
              <td>
                {record.form_id}
                <button type="button" onClick={() => onViewSource(record)}>צפה במקור</button>
                {warnings.length > 0 && (
                  <details className="page-warnings">
                    <summary>הערות עמוד ({warnings.length})</summary>
                    <ul>{warnings.map(w => <li key={w}>{w}</li>)}</ul>
                  </details>
                )}
              </td>
              {REVIEW_FIELDS.map(name => {
                const field = record[name] as any;
                const value = field?.reviewed_value ?? field?.normalized_value ?? field?.raw_value;
                const emptyValue = name === 'central_numbers' ? [] : '';
                const verified = isHumanVerified(field);
                const approvable = canApproveAsIs(name, field);
                return (
                  <td key={name} className={verified ? 'cell-verified' : 'cell-review'}>
                    <span className="cell-value">{Array.isArray(value) ? value.join(', ') : value || '-'}</span>
                    <span className={verified ? 'cell-state state-approved' : 'cell-state state-review'}>
                      {verified ? 'מאושר' : 'דורש בדיקה'}
                    </span>
                    <button type="button" onClick={() => onEdit(record.commitment_record_id, name, value ?? emptyValue)}>
                      {approvable ? 'ערוך ואשר' : 'תקן ואשר'}
                    </button>
                    <FieldEvidence
                      fieldName={name}
                      field={field}
                      onUseCandidate={candidate => onEdit(record.commitment_record_id, name, candidate, USE_CANDIDATE_HINT)}
                      onRejectCandidate={candidate => onRejectCandidate(record.commitment_record_id, name, candidate)}
                    />
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  </section>
);