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
import { getFieldDisplayValue as getSharedFieldDisplayValue, getFieldVisualState as getSharedFieldVisualState } from './utils/editPermissions';
import { getRelationshipStatusLabel as getRelationshipLabel, getSegmentationLabel } from '../../utils/hebrewMessages';

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
  // Shared util: reviewed > normalized > raw (list values supported)
  const value = getSharedFieldDisplayValue(field);
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(', ') : '-';
  }
  return value || '-';
};

/**
 * Get field visual state for styling.
 * Red/orange come from the shared util (missing, invalid, uncertain, conflicting,
 * needs_review, validation issues); green is added for human-verified fields.
 */
const getFieldVisualState = (field: FieldValue<any> | null | undefined): { color: 'green' | 'orange' | 'red' | 'default'; icon?: string } => {
  if (!field) return { color: 'default' };

  const shared = getSharedFieldVisualState(field);
  if (shared.color === 'red') return { color: 'red', icon: 'error' };
  if (shared.color === 'orange') return { color: 'orange', icon: 'warning' };

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
const mapLegacyStatus = (legacy: CommitmentRecord['relation_status']): string => {
  if (legacy === 'clear') return 'explicit';
  if (legacy === 'ambiguous') return 'unresolved_relationship';
  if (legacy === 'manual') return 'explicit';
  if (legacy === 'related') return 'explicit';
  if (legacy === 'unrelated') return 'none';
  return 'unresolved_relationship';
};

/**
 * Get relationship status label in Hebrew
 */
const getRelationshipStatusLabel = (commitment: CommitmentRecord): string => {
  const status = commitment.relationship_status || mapLegacyStatus(commitment.relation_status);
  return getRelationshipLabel(status);
};

/**
 * Hebrew accessibility label for a field state color (display only)
 */
const getStateLabel = (color: string): string => {
  if (color === 'red') return 'חסר או לא תקין';
  if (color === 'orange') return 'דורש בדיקה';
  if (color === 'green') return 'אושר ידנית';
  return '';
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
          <h3>טופס <bdi dir="ltr">{form.form_id}</bdi>{pageRangeText}</h3>
          <span className="segmentation-badge" title={`אופן זיהוי גבולות הטופס: ${getSegmentationLabel(form.segmentation_method)}`}>
            {form.segmentation_method === 'page_notation' ? '📄 ' :
             form.segmentation_method === 'heuristic' ? '🔍 ' :
             '📋 '}
            {getSegmentationLabel(form.segmentation_method)}
          </span>
        </div>
        <button
          className="form-edit-btn"
          onClick={() => onEdit(form.form_id)}
          aria-label={`עריכת טופס ${form.form_id}`}
        >
          <span aria-hidden="true">✏️</span> עריכה
        </button>
      </div>

      {/* Patient Info Section */}
      <div className="form-section">
        <h4 className="section-title">פרטי מטופל</h4>
        <div className="patient-info-grid">
          <div className={`info-field ${firstNameState.color}`}>
            <label>שם פרטי:</label>
            <span className="field-value">{firstName}</span>
            {firstNameState.icon && <span className="field-icon" role="img" aria-label={getStateLabel(firstNameState.color)}>{firstNameState.icon === 'error' ? '❌' : firstNameState.icon === 'verified' ? '✅' : '⚠️'}</span>}
          </div>
          <div className={`info-field ${lastNameState.color}`}>
            <label>שם משפחה:</label>
            <span className="field-value">{lastName}</span>
            {lastNameState.icon && <span className="field-icon" role="img" aria-label={getStateLabel(lastNameState.color)}>{lastNameState.icon === 'error' ? '❌' : lastNameState.icon === 'verified' ? '✅' : '⚠️'}</span>}
          </div>
          <div className={`info-field ${idNumberState.color}`}>
            <label>מספר זהות:</label>
            <span className="field-value">{idNumber}</span>
            {idNumberState.icon && <span className="field-icon" role="img" aria-label={getStateLabel(idNumberState.color)}>{idNumberState.icon === 'error' ? '❌' : idNumberState.icon === 'verified' ? '✅' : '⚠️'}</span>}
          </div>
          <div className={`info-field ${senderState.color}`}>
            <label>גורם שולח:</label>
            <span className="field-value">{sender}</span>
            {senderState.icon && <span className="field-icon" role="img" aria-label={getStateLabel(senderState.color)}>{senderState.icon === 'error' ? '❌' : senderState.icon === 'verified' ? '✅' : '⚠️'}</span>}
          </div>
        </div>
      </div>

      {/* Samples Section */}
      <div className="form-section">
        <h4 className="section-title">דגימות ({samples.length})</h4>
        {samples.length === 0 ? (
          <p className="empty-message">אין דגימות משויכות לטופס</p>
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
          <p className="empty-message">אין התחייבויות משויכות לטופס</p>
        ) : (
          <ul className="commitments-list" role="list">
            {commitments.map((commitment) => {
              const commitmentNumber = getFieldDisplayValue(commitment.commitment_number);
              const statusColor = getRelationshipStatusColor(commitment);
              const statusLabel = getRelationshipStatusLabel(commitment);
              const needsReview = statusColor === 'orange';

              return (
                <li key={commitment.commitment_record_id} className="commitment-item">
                  <span className="commitment-number" dir="auto">{commitmentNumber}</span>
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
                      aria-label={`שיוך דגימות להתחייבות ${commitmentNumber}`}
                    >
                      <span aria-hidden="true">🔗</span> שיוך דגימות
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
          <span className="confidence-warning" title={`רמת ודאות: ${(form.segmentation_confidence * 100).toFixed(0)}%\u200E`}>
            <span aria-hidden="true">⚠️</span> זיהוי גבולות הטופס אינו ודאי. מומלץ לבדוק מול המסמך.
          </span>
        </div>
      )}
    </div>
  );
};
