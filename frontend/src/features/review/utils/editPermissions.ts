/**
 * Edit permission utilities for field-level editability
 */
import { FieldValue } from '../../../services/api';

/**
 * Determine if a field is editable.
 * 
 * A field is editable if:
 * - review_state is 'needs_review', OR
 * - extraction_state is 'invalid', 'missing', 'uncertain', or 'conflicting'
 * 
 * A field is NOT editable if:
 * - extraction_state is 'found' AND review_state is 'pending' AND no validation_issues
 */
export function isFieldEditable(field: FieldValue): boolean {
  // If needs review, it's editable
  if (field.review_state === 'needs_review') {
    return true;
  }
  
  // If extraction state indicates a problem, it's editable
  if (['invalid', 'missing', 'uncertain', 'conflicting'].includes(field.extraction_state)) {
    return true;
  }
  
  // If has validation issues, it's editable
  if (field.validation_issues && field.validation_issues.length > 0) {
    return true;
  }
  
  // Otherwise not editable (valid field with no issues)
  return false;
}

/**
 * Get the display value for a field.
 * Priority: reviewed_value > normalized_value > raw_value
 */
export function getFieldDisplayValue(field: FieldValue): string | string[] {
  if (field.reviewed_value !== null && field.reviewed_value !== undefined) {
    return field.reviewed_value;
  }
  
  if (field.normalized_value !== null && field.normalized_value !== undefined) {
    return field.normalized_value;
  }
  
  if (field.raw_value !== null && field.raw_value !== undefined) {
    return field.raw_value;
  }
  
  // For list fields
  if (Array.isArray(field.reviewed_value) || Array.isArray(field.normalized_value) || Array.isArray(field.raw_value)) {
    return [];
  }
  
  return '';
}

/**
 * Visual state for a field (color, icon, editability).
 */
export interface FieldVisualState {
  color: 'default' | 'orange' | 'red';
  editable: boolean;
  icon?: 'warning' | 'error';
  message?: string;
}

/**
 * Get visual styling state for a field.
 */
export function getFieldVisualState(field: FieldValue): FieldVisualState {
  // Red: invalid or missing
  if (field.extraction_state === 'invalid' || field.extraction_state === 'missing') {
    return {
      color: 'red',
      editable: true,
      icon: 'error',
      message: field.extraction_state === 'missing' ? 'חסר' : 'לא תקין'
    };
  }
  
  // Orange: uncertain, conflicting, or needs review
  if (
    field.extraction_state === 'uncertain' ||
    field.extraction_state === 'conflicting' ||
    field.review_state === 'needs_review' ||
    (field.validation_issues && field.validation_issues.length > 0)
  ) {
    return {
      color: 'orange',
      editable: true,
      icon: 'warning',
      message: 'דורש בדיקה'
    };
  }
  
  // Default: valid, no issues
  return {
    color: 'default',
    editable: false,
    message: undefined
  };
}

/**
 * Get field label in Hebrew.
 */
export function getFieldLabel(fieldName: string): string {
  const labels: Record<string, string> = {
    patient_first_name: 'שם פרטי',
    patient_last_name: 'שם משפחה',
    patient_id_number: 'מספר זהות',
    sender: 'גורם שולח',
    received_date: 'תאריך קבלת הדגימה',
    central_numbers: 'מספרים מרכזיים',
    commitment_number: 'מספר התחייבות'
  };
  
  return labels[fieldName] || 'שדה';
}
