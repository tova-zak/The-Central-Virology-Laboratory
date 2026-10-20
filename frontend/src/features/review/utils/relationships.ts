/**
 * Relationship utilities for commitments and central numbers
 */
import { TestRecord, CommitmentRecord } from '../../../services/api';
import { isFieldEditable } from './editPermissions';

export interface CommitmentNumberItem {
  value: string;
  commitment_record_id: string;
  editable: boolean;
  hasWarning: boolean;
  warningMessage?: string;
}

export interface CommitmentNumbersResult {
  items: CommitmentNumberItem[];
  hasWarning: boolean;
  warningMessage?: string;
}

/**
 * Get commitment numbers for a test record.
 * 
 * Iterates through testRecord.commitment_ids, finds matching CommitmentRecord,
 * extracts commitment_number value and editability.
 * 
 * Detects orphaned commitments (have test_id but not in commitment_ids) and logs warning.
 * Display only items from commitment_ids (per H-2 resolution).
 */
export function getCommitmentNumbersForTest(
  testRecord: TestRecord,
  commitmentRecords: CommitmentRecord[]
): CommitmentNumbersResult {
  const items: CommitmentNumberItem[] = [];
  let hasOverallWarning = false;
  let overallWarningMessage: string | undefined;
  
  // Get commitments referenced by this test
  for (const commitmentId of testRecord.commitment_ids) {
    const commitment = commitmentRecords.find(c => c.commitment_record_id === commitmentId);
    
    if (!commitment) {
      // Missing commitment - data integrity issue
      console.warn(`Commitment ${commitmentId} referenced by test ${testRecord.test_id} but not found`);
      hasOverallWarning = true;
      overallWarningMessage = 'התחייבות חסרה';
      continue;
    }
    
    // Extract commitment number value
    const commitmentNumber = commitment.commitment_number;
    const value = commitmentNumber.reviewed_value ??
                  commitmentNumber.normalized_value ??
                  commitmentNumber.raw_value ??
                  '';
    
    // Check if editable
    const editable = isFieldEditable(commitmentNumber);
    
    // Check for warnings
    const hasWarning = commitmentNumber.extraction_state === 'uncertain' ||
                       commitmentNumber.extraction_state === 'conflicting' ||
                       commitmentNumber.review_state === 'needs_review';
    
    items.push({
      value: value as string,
      commitment_record_id: commitmentId,
      editable,
      hasWarning,
      warningMessage: hasWarning ? 'דורש בדיקה' : undefined
    });
    
    if (hasWarning) {
      hasOverallWarning = true;
    }
  }
  
  // Check for orphaned commitments (have test_id but not in commitment_ids)
  // Per H-2 resolution: log warning, don't display
  const orphans = commitmentRecords.filter(
    c => c.test_id === testRecord.test_id && !testRecord.commitment_ids.includes(c.commitment_record_id)
  );
  
  if (orphans.length > 0) {
    console.warn(
      `Found ${orphans.length} orphaned commitments for test ${testRecord.test_id}:`,
      orphans.map(c => c.commitment_record_id)
    );
    // Don't display orphans, just log
  }
  
  return {
    items,
    hasWarning: hasOverallWarning,
    warningMessage: overallWarningMessage
  };
}
