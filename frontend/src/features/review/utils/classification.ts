/**
 * Classification utility for test records
 * 
 * Classifies records into three tables:
 * 1. Table 1 (success): All required fields present, no issues
 * 2. Table 2 (warnings): Has warnings/uncertainties but no missing required
 * 3. Table 3 (missing): Has missing or invalid required fields
 */
import { TestRecord, CommitmentRecord, FieldValue } from '../../../services/api';

// Required business fields (must match backend)
const REQUIRED_FIELDS: Array<keyof TestRecord> = [
  'patient_first_name',
  'patient_last_name',
  'patient_id_number',
  'sender',
  'received_date',
  'central_numbers'
];

export interface ClassifiedRecords {
  table1_success: TestRecord[];
  table2_warnings: TestRecord[];
  table3_missing: TestRecord[];
  unprocessed: TestRecord[];
  orphanedCommitments: CommitmentRecord[];
}

/**
 * Check if a field is considered missing.
 * 
 * A field is NOT missing if:
 * - It has reviewed_value (even empty string) AND review_state is human_verified (confirmed empty)
 * - It has extraction_state 'found' with a value
 * 
 * A field IS missing if:
 * - extraction_state is 'missing' or 'invalid'
 * - No value at all (raw_value, normalized_value, reviewed_value all null/empty)
 */
export function isFieldMissing(field: FieldValue): boolean {
  // If human verified with a reviewed_value (including empty string), it's not missing
  if (field.review_state === 'human_verified') {
    return false; // Confirmed empty is valid
  }
  
  // If extraction_state is invalid or missing, treat as missing
  if (field.extraction_state === 'invalid' || field.extraction_state === 'missing') {
    return true;
  }
  
  // Get the best available value
  const value = field.reviewed_value !== null && field.reviewed_value !== undefined
    ? field.reviewed_value
    : (field.normalized_value !== null && field.normalized_value !== undefined
      ? field.normalized_value
      : field.raw_value);
  
  // For list fields, check if list is empty
  if (Array.isArray(value)) {
    return value.length === 0;
  }
  
  // For scalar fields, check if value is null or empty string
  if (value === null || value === undefined || value === '') {
    return true;
  }
  
  return false;
}

/**
 * Check if record has any required field missing or invalid.
 */
export function hasRequiredFieldMissing(record: TestRecord): boolean {
  for (const fieldName of REQUIRED_FIELDS) {
    const field = record[fieldName] as FieldValue;
    if (!field || isFieldMissing(field)) {
      return true;
    }
  }
  return false;
}

/**
 * Check if record has any warnings or uncertainties.
 * 
 * Warnings include:
 * - uncertain extraction_state
 * - conflicting extraction_state
 * - needs_review review_state (on non-missing fields)
 * - validation_issues present
 * - ambiguous relation_status on any related commitment
 */
export function hasWarnings(
  record: TestRecord,
  commitmentRecords: CommitmentRecord[]
): boolean {
  const fieldsToCheck: Array<keyof TestRecord> = [
    'patient_first_name',
    'patient_last_name',
    'patient_id_number',
    'sender',
    'received_date',
    'central_numbers'
  ];
  
  for (const fieldName of fieldsToCheck) {
    const field = record[fieldName] as FieldValue;
    if (!field) continue;
    
    // Uncertain or conflicting extraction
    if (field.extraction_state === 'uncertain' || field.extraction_state === 'conflicting') {
      return true;
    }
    
    // Needs review (but not missing - those go to Table 3)
    if (field.review_state === 'needs_review' && !isFieldMissing(field)) {
      return true;
    }
    
    // Has validation issues
    if (field.validation_issues && field.validation_issues.length > 0) {
      return true;
    }
  }
  
  // Check for ambiguous relationships
  if (record.commitment_ids && record.commitment_ids.length > 0) {
    for (const commitmentId of record.commitment_ids) {
      const commitment = commitmentRecords.find(c => c.commitment_record_id === commitmentId);
      if (commitment && commitment.relation_status === 'ambiguous') {
        return true;
      }
    }
  }
  
  return false;
}

/**
 * Classify a single test record.
 * 
 * Priority (check in order):
 * 1. Table 3 ('missing'): Any required field missing/invalid → HIGHEST PRIORITY
 * 2. Table 2 ('warnings'): Has warnings but no missing required
 * 3. Table 1 ('success'): All good
 */
export function classifyRecord(
  record: TestRecord,
  commitmentRecords: CommitmentRecord[]
): 'success' | 'warnings' | 'missing' {
  // Priority 1: Missing/invalid required fields → Table 3
  if (hasRequiredFieldMissing(record)) {
    return 'missing';
  }
  
  // Priority 2: Warnings → Table 2
  if (hasWarnings(record, commitmentRecords)) {
    return 'warnings';
  }
  
  // Priority 3: All good → Table 1
  return 'success';
}

/**
 * Classify all test records into three tables.
 * 
 * Separates unprocessed records (status not 'completed' or 'completed_with_errors')
 * into a separate list.
 * 
 * Also detects orphaned commitments (not referenced by any test record).
 */
export function classifyTestRecords(
  testRecords: TestRecord[],
  commitmentRecords: CommitmentRecord[],
  batchStatus: string
): ClassifiedRecords {
  const result: ClassifiedRecords = {
    table1_success: [],
    table2_warnings: [],
    table3_missing: [],
    unprocessed: [],
    orphanedCommitments: []
  };
  
  // Only classify if batch is completed
  if (batchStatus !== 'completed' && batchStatus !== 'completed_with_errors') {
    result.unprocessed = testRecords;
    return result;
  }
  
  // Classify test records
  for (const record of testRecords) {
    const classification = classifyRecord(record, commitmentRecords);
    
    switch (classification) {
      case 'missing':
        result.table3_missing.push(record);
        break;
      case 'warnings':
        result.table2_warnings.push(record);
        break;
      case 'success':
        result.table1_success.push(record);
        break;
    }
  }
  
  // Detect orphaned commitments
  const allReferencedCommitmentIds = new Set<string>();
  for (const record of testRecords) {
    if (record.commitment_ids) {
      for (const commitmentId of record.commitment_ids) {
        allReferencedCommitmentIds.add(commitmentId);
      }
    }
  }
  
  for (const commitment of commitmentRecords) {
    if (!allReferencedCommitmentIds.has(commitment.commitment_record_id)) {
      result.orphanedCommitments.push(commitment);
    }
  }
  
  return result;
}
