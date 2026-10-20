/**
 * FormCard Component - Multi-Page Form Display
 * 
 * Displays a LogicalForm with its associated samples and commitments.
 * Shows relationship status indicators with color coding.
 * 
 * Agent B - MVP 8-hour implementation
 */
import React from 'react';
import './FormCard.css';
import { LogicalForm, Sample, CommitmentRecord, FieldValue } from '../../services/api';

interface FormCardProps {
  form: LogicalForm;
  samples: Sample[];
  commitments: CommitmentRecord[];
  onEdit: (formId: string) => void;
  onResolveRelationship?: (commitmentId: string) => void;
}

/**
 * Get display value from FieldValue - prioritizes reviewed, then normalized, then raw
 */
const getFieldDisplayValue = (field: FieldValue<any> | null | undefined): string => {
  if (!field) return '-';
  
  // Prioritize reviewed_value if human_verified
  if (field.review_state === 'human_verified' && field.reviewed_value != null) {
    return String(field.reviewed_value);
  }
  
  // Otherwise: normalized > raw
  if (field.normalized_value != null) {
    return String(field.normalized_value);
  }
  
  if (field.raw_value != null) {
    return String(field.raw_value);
  }
  
  return '-';
};

/**
 * Get field visual state for styling
 */
const getFieldVisualState = (field: FieldValue<any> | null | undefined): { color: 'green' | 'orange' | 'red' | 'default'; icon?: string } => {
  if (!field) return { color: 'default' };
  
  if (field.extraction_state === 'missing') {
    return { color: 'red', icon: 'error' };
  }
  
  if (field.extraction_state === 'uncertain' || field.extraction_state === 'conflicting') {
    return { color: 'orange', icon: 'warning' };
  }
  
  if (field.review_state === 'human_verified') {
    return { color: 'green', icon: 'verified' };
  }
  
  return { color: 'default' };
};

/**
 * Get relationship status color based on contract (Decision D2)
 */
const getRelationshipStatusColor = (commitment: CommitmentRecord): 'green' | 'orange' | 'red' => {
  const status = commitment.relationship_status || mapLegacyStatus(commitment.relation_status);
  
  if (status === 'explicit' || status === 'inferred') return 'green';
  if (status === 'unresolved_relationship') return 'orange';
  if (status === 'none') return 'red';
  
  return 'orange'; // fallback for unknown
};

/**
 * Map legacy relation_status to new relationship_status
 */
const mapLegacyStatus = (legacy: 'clear' | 'ambiguous' | 'manual'): string => {
  if (legacy === 'clear') return 'explicit';
  if (legacy === 'ambiguous') return 'unresolved_relationship';
  if (legacy === 'manual') return 'explicit';
  return 'unresolved_relationship';
};

/**
 * Get relationship status label in Hebrew
 */
const getRelationshipStatusLabel = (commitment: CommitmentRecord): string => {
  const status = commitment.relationship_status || mapLegacyStatus(commitment.relation_status);
  
  if (status === 'explicit') return 'קשר מאומת';
  if (status === 'inferred') return 'קשר מוסק';
  if (status === 'unresolved_relationship') return 'דורש ביקורת';
  if (status === 'none') return 'לא משוייך';
  
  return 'לא ברור';
};

export const FormCard: React.FC<FormCardProps> = ({
  form,
  samples,
  commitments,
  onEdit,
  onResolveRelationship
}) => {
  // Header: show page range ONLY for multi-page forms
  const pageRangeText = form.page_indices.length > 1
    ? ` (עמודים ${Math.min(...form.page_indices) + 1}-${Math.max(...form.page_indices) + 1})`
    : '';

  const firstName = getFieldDisplayValue(form.patient_first_name);
  const lastName = getFieldDisplayValue(form.patient_last_name);
  const idNumber = getFieldDisplayValue(form.patient_id_number);
  const sender = getFieldDisplayValue(form.sender);

  const firstNameState = getFieldVisualState(form.patient_first_name);
  const lastNameState = getFieldVisualState(form.patient_last_name);
  const idNumberState = getFieldVisualState(form.patient_id_number);
  const senderState = getFieldVisualState(form.sender);

  return (
    <div className="form-card" dir="rtl">
      <div className="form-card-header">
        <div className="form-title">
          <h3>טופס {form.form_id}{pageRangeText}</h3>
          <span className="segmentation-badge" title={`שיטת חלוקה: ${form.segmentation_method}`}>
            {form.segmentation_method === 'page_notation' ? '📄 סימון עמוד' :
             form.segmentation_method === 'heuristic' ? '🔍 היוריסטי' :
             '📋 עמוד יחיד'}
          </span>
        </div>
        <button
          className="form-edit-btn"
          onClick={() => onEdit(form.form_id)}
          aria-label={`ערוך טופס ${form.form_id}`}
        >
          ✏️ ערוך
        </button>
      </div>

      {/* Patient Info Section */}
      <div className="form-section">
        <h4 className="section-title">פרטי מטופל</h4>
        <div className="patient-info-grid">
          <div className={`info-field ${firstNameState.color}`}>
            <label>שם פרטי:</label>
            <span className="field-value">{firstName}</span>
            {firstNameState.icon && <span className="field-icon" aria-label={firstNameState.color}>{firstNameState.icon === 'error' ? '❌' : '⚠️'}</span>}
          </div>
          <div className={`info-field ${lastNameState.color}`}>
            <label>שם משפחה:</label>
            <span className="field-value">{lastName}</span>
            {lastNameState.icon && <span className="field-icon" aria-label={lastNameState.color}>{lastNameState.icon === 'error' ? '❌' : '⚠️'}</span>}
          </div>
          <div className={`info-field ${idNumberState.color}`}>
            <label>מספר זהות:</label>
            <span className="field-value">{idNumber}</span>
            {idNumberState.icon && <span className="field-icon" aria-label={idNumberState.color}>{idNumberState.icon === 'error' ? '❌' : '⚠️'}</span>}
          </div>
          <div className={`info-field ${senderState.color}`}>
            <label>גורם שולח:</label>
            <span className="field-value">{sender}</span>
            {senderState.icon && <span className="field-icon" aria-label={senderState.color}>{senderState.icon === 'error' ? '❌' : '⚠️'}</span>}
          </div>
        </div>
      </div>

      {/* Samples Section */}
      <div className="form-section">
        <h4 className="section-title">דגימות ({samples.length})</h4>
        {samples.length === 0 ? (
          <p className="empty-message">אין דגימות משוייכות</p>
        ) : (
          <ul className="samples-list" role="list">
            {samples.map((sample) => {
              const centralNumber = getFieldDisplayValue(sample.central_number);
              const receivedDate = getFieldDisplayValue(sample.received_date);
              return (
                <li key={sample.sample_id} className="sample-item">
                  <span className="sample-central-number">{centralNumber}</span>
                  <span className="sample-separator">•</span>
                  <span className="sample-received-date">{receivedDate}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Commitments Section */}
      <div className="form-section">
        <h4 className="section-title">התחייבויות ({commitments.length})</h4>
        {commitments.length === 0 ? (
          <p className="empty-message">אין התחייבויות משוייכות</p>
        ) : (
          <ul className="commitments-list" role="list">
            {commitments.map((commitment) => {
              const commitmentNumber = getFieldDisplayValue(commitment.commitment_number);
              const statusColor = getRelationshipStatusColor(commitment);
              const statusLabel = getRelationshipStatusLabel(commitment);
              const needsReview = statusColor === 'orange';

              return (
                <li key={commitment.commitment_record_id} className="commitment-item">
                  <span className="commitment-number">{commitmentNumber}</span>
                  <span
                    className={`relationship-status status-${statusColor}`}
                    role="status"
                    aria-label={statusLabel}
                  >
                    {statusColor === 'green' && '✅'}
                    {statusColor === 'orange' && '⚠️'}
                    {statusColor === 'red' && '❌'}
                    <span className="status-label">{statusLabel}</span>
                  </span>
                  {needsReview && onResolveRelationship && (
                    <button
                      className="resolve-btn"
                      onClick={() => onResolveRelationship(commitment.commitment_record_id)}
                      aria-label={`פתור קשר עבור התחייבות ${commitmentNumber}`}
                    >
                      🔗 פתור
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Confidence indicator (optional footer) */}
      {form.segmentation_confidence < 0.8 && (
        <div className="form-card-footer">
          <span className="confidence-warning" title={`רמת ודאות: ${(form.segmentation_confidence * 100).toFixed(0)}%`}>
            ⚠️ חלוקה בוודאות נמוכה - מומלץ בדיקה ידנית
          </span>
        </div>
      )}
    </div>
  );
};
