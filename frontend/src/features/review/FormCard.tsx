/**
 * FormCard Component
 * 
 * Displays a single LogicalForm (potentially multi-page) with:
 * - Patient information
 * - Samples list (central_number + received_date pairs)
 * - Commitments list with relationship status indicators
 * 
 * Part of MVP 8-hour push - Form-based review UI
 */
import React from 'react';
import './FormCard.css';
import { LogicalForm, Sample, CommitmentRecord, FieldValue } from '../../services/api';
import { getFieldDisplayValue, getFieldVisualState } from './utils/editPermissions';

interface FormCardProps {
  form: LogicalForm;
  samples: Sample[];
  commitments: CommitmentRecord[];
  onEdit: (formId: string) => void;
  onResolveRelationship: (commitmentId: string) => void;
}

/**
 * Get the display value from a FieldValue, with fallback chain:
 * reviewed_value (if human_verified) → normalized_value → raw_value
 */
const getDisplayValue = (field: FieldValue<any> | undefined): string => {
  if (!field) return '—';
  
  // Use existing utility if available
  const value = getFieldDisplayValue(field);
  
  if (Array.isArray(value)) {
    return value.join(', ');
  }
  
  return value || '—';
};

/**
 * Map relationship_status to visual color
 */
const getRelationshipColor = (commitment: CommitmentRecord): 'green' | 'orange' | 'red' => {
  const status = commitment.relationship_status || mapLegacyStatus(commitment.relation_status);
  
  if (status === 'explicit' || status === 'inferred') return 'green';
  if (status === 'unresolved_relationship') return 'orange';
  if (status === 'none') return 'red';
  return 'orange'; // fallback
};

/**
 * Map legacy relation_status to new relationship_status (Decision D2)
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
const getRelationshipLabel = (commitment: CommitmentRecord): string => {
  const status = commitment.relationship_status || mapLegacyStatus(commitment.relation_status);
  
  switch (status) {
    case 'explicit':
      return 'קשר מאומת';
    case 'inferred':
      return 'קשר משוער';
    case 'unresolved_relationship':
      return 'דורש ביקורת';
    case 'none':
      return 'לא משוייך';
    default:
      return 'לא ברור';
  }
};

export const FormCard: React.FC<FormCardProps> = ({
  form,
  samples,
  commitments,
  onEdit,
  onResolveRelationship
}) => {
  // Determine header text: only show page range if multi-page
  const getHeaderText = (): string => {
    if (form.page_indices.length > 1) {
      const min = Math.min(...form.page_indices);
      const max = Math.max(...form.page_indices);
      return `טופס ${form.form_id} (עמודים ${min + 1}-${max + 1})`;
    }
    return `טופס ${form.form_id}`;
  };

  // Get visual state for field highlighting
  const getFieldClass = (field: FieldValue<any> | undefined): string => {
    if (!field) return '';
    const visualState = getFieldVisualState(field);
    if (visualState.color === 'orange') return 'field-warning';
    if (visualState.color === 'red') return 'field-error';
    return '';
  };

  return (
    <div className="form-card" dir="rtl">
      <div className="form-card-header">
        <h3>{getHeaderText()}</h3>
        <span className="form-confidence">
          {form.segmentation_method === 'page_notation' ? '📄 זיהוי אוטומטי' : 
           form.segmentation_method === 'heuristic' ? '🔍 היוריסטיקה' : 
           '📋 עמוד יחיד'}
        </span>
      </div>

      <div className="form-card-body">
        {/* Patient Information Section */}
        <section className="patient-info-section">
          <h4>פרטי מטופל</h4>
          <div className="patient-info-grid">
            <div className={`info-field ${getFieldClass(form.patient_first_name)}`}>
              <span className="field-label">שם פרטי:</span>
              <span className="field-value">{getDisplayValue(form.patient_first_name)}</span>
            </div>
            <div className={`info-field ${getFieldClass(form.patient_last_name)}`}>
              <span className="field-label">שם משפחה:</span>
              <span className="field-value">{getDisplayValue(form.patient_last_name)}</span>
            </div>
            <div className={`info-field ${getFieldClass(form.patient_id_number)}`}>
              <span className="field-label">ת.ז.:</span>
              <span className="field-value">{getDisplayValue(form.patient_id_number)}</span>
            </div>
            <div className={`info-field ${getFieldClass(form.sender)}`}>
              <span className="field-label">גורם שולח:</span>
              <span className="field-value">{getDisplayValue(form.sender)}</span>
            </div>
          </div>
        </section>

        {/* Samples Section */}
        <section className="samples-section">
          <h4>דגימות ({samples.length})</h4>
          {samples.length === 0 ? (
            <p className="empty-message">אין דגימות מזוהות</p>
          ) : (
            <ul className="samples-list" role="list">
              {samples.map(sample => (
                <li key={sample.sample_id} className="sample-item">
                  <span className="sample-central">
                    מס׳ מרכזי: <strong>{getDisplayValue(sample.central_number)}</strong>
                  </span>
                  <span className="sample-date">
                    תאריך קבלה: {getDisplayValue(sample.received_date)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* Commitments Section */}
        <section className="commitments-section">
          <h4>התחייבויות ({commitments.length})</h4>
          {commitments.length === 0 ? (
            <p className="empty-message">אין התחייבויות מזוהות</p>
          ) : (
            <ul className="commitments-list" role="list">
              {commitments.map(commitment => {
                const color = getRelationshipColor(commitment);
                const label = getRelationshipLabel(commitment);
                const needsReview = color === 'orange';
                
                return (
                  <li key={commitment.commitment_record_id} className="commitment-item">
                    <span className="commitment-number">
                      {getDisplayValue(commitment.commitment_number)}
                    </span>
                    <span 
                      className={`relationship-status status-${color}`}
                      role="status"
                      aria-label={label}
                    >
                      {color === 'green' && '✅ '}
                      {color === 'orange' && '⚠️ '}
                      {color === 'red' && '❌ '}
                      {label}
                    </span>
                    {needsReview && (
                      <button
                        className="resolve-btn"
                        onClick={() => onResolveRelationship(commitment.commitment_record_id)}
                        aria-label="יישוב קשר לא ברור"
                      >
                        🔗 יישב קשר
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>

      <div className="form-card-footer">
        <button
          className="edit-form-btn"
          onClick={() => onEdit(form.form_id)}
          aria-label="עריכת טופס"
        >
          ✏️ ערוך
        </button>
      </div>
    </div>
  );
};
