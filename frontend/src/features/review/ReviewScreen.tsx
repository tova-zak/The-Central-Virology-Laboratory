/**
 * Review Screen Component
 * 
 * Displays extracted commitment data with visual indicators:
 * - Orange: uncertain fields (needs_review)
 * - Red: invalid fields (failed validation)
 * - Default: valid fields (no special marking needed)
 * 
 * TASK-014: Review screen with color flagging
 * TASK-015: Manual correction with edit modal
 * Integration Package 1: Connected to real Backend API
 */
import React, { useState, useEffect } from 'react';
import './ReviewScreen.css';
import { EditFieldModal } from './EditFieldModal';
import { 
  getBatchStatus, 
  updateField, 
  exportBatch, 
  checkExportEligibility,
  BatchStatusResponse,
  TestRecord,
  FieldValue 
} from '../../services/api';

interface ReviewScreenProps {
  batchId: string;
  onBack?: () => void;
}

export const ReviewScreen: React.FC<ReviewScreenProps> = ({
  batchId,
  onBack
}) => {
  const [batchData, setBatchData] = useState<BatchStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exportEligibility, setExportEligibility] = useState<{
    can_export: boolean;
    blockers: string[];
  } | null>(null);
  const [exportingInner, setExportingInner] = useState(false);

  const [editModal, setEditModal] = useState<{
    isOpen: boolean;
    testId: string;
    fieldName: string;
    fieldLabel: string;
    currentValue: any;
    fieldType: 'text' | 'list';
    suggestions?: string[];
  } | null>(null);

  // Load batch data on mount and refresh
  useEffect(() => {
    loadBatchData();
  }, [batchId]);

  const loadBatchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const data = await getBatchStatus(batchId);
      setBatchData(data);
      
      // Check export eligibility
      if (data.status === 'completed' || data.status === 'completed_with_errors') {
        const eligibility = await checkExportEligibility(batchId);
        setExportEligibility(eligibility);
      }
    } catch (err: any) {
      console.error('Failed to load batch data:', err);
      setError(err.response?.data?.detail || 'Failed to load batch data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="review-screen">
        <div className="loading">
          <p>Loading batch data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="review-screen">
        <div className="error-message">
          <h3>Error</h3>
          <p>{error}</p>
          {onBack && (
            <button onClick={onBack} className="button-secondary">
              Go Back
            </button>
          )}
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="review-screen">
        <div className="loading">
          <p>Loading batch data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="review-screen">
        <div className="error-message">
          <h3>Error</h3>
          <p>{error}</p>
          {onBack && (
            <button onClick={onBack} className="button-secondary">
              Go Back
            </button>
          )}
        </div>
      </div>
    );
  }

  if (!batchData) {
    return (
      <div className="review-screen">
        <div className="no-data">
          <p>No batch data to review. Please upload and process documents first.</p>
        </div>
      </div>
    );
  }

  // Handle case where batch exists but not yet processed or no data
  const testRecords = batchData.test_records || [];
  const commitmentRecords = batchData.commitment_records || [];
  const errors = batchData.errors || [];

  if (batchData.status === 'uploaded') {
    return (
      <div className="review-screen">
        <div className="info-message">
          <h3>⚠ Batch Not Yet Processed</h3>
          <p>This batch has been uploaded but not processed yet.</p>
          <p>Please click "Start Processing" to extract data with AI.</p>
          {onBack && (
            <button onClick={onBack} className="button-primary">
              Back to Upload
            </button>
          )}
        </div>
      </div>
    );
  }

  // Handle case where processing completed with errors only (no successful extractions)
  if (testRecords.length === 0 && errors.length > 0) {
    return (
      <div className="review-screen">
        <div className="error-message">
          <h3>❌ Processing Failed</h3>
          <p>Processing completed but encountered errors with all documents:</p>
          <ul className="error-list">
            {errors.map((err, idx) => (
              <li key={idx}>
                <strong>Document {err.document_id || idx + 1}:</strong> {err.error}
              </li>
            ))}
          </ul>
          <p className="help-text">
            Common causes:
            <ul>
              <li>PDF pages too large or corrupted</li>
              <li>Documents don't match expected format</li>
              <li>Images are too blurry or low quality</li>
            </ul>
          </p>
          {onBack && (
            <button onClick={onBack} className="button-secondary">
              Back to Upload
            </button>
          )}
        </div>
      </div>
    );
  }

  if (testRecords.length === 0 && errors.length === 0) {
    return (
      <div className="review-screen">
        <div className="info-message">
          <h3>ℹ No Data Extracted</h3>
          <p>Processing completed but no records were extracted.</p>
          <p>This might happen if the documents don't contain recognizable forms.</p>
          {onBack && (
            <button onClick={onBack} className="button-secondary">
              Back to Upload
            </button>
          )}
        </div>
      </div>
    );
  }

  const getFieldClassName = (field: FieldValue): string => {
    const classes = ['field'];
    
    // Color coding based on state
    if (field.extraction_state === 'invalid') {
      classes.push('field-invalid'); // Red
    } else if (field.review_state === 'needs_review') {
      classes.push('field-needs-review'); // Orange
    }
    // No special green styling - default is fine
    
    return classes.join(' ');
  };

  const getFieldValue = (field: FieldValue): string => {
    // Priority: reviewed > normalized > raw
    const value = field.reviewed_value ?? field.normalized_value ?? field.raw_value;
    
    if (value === null || value === undefined) {
      return '(missing)';
    }
    
    if (Array.isArray(value)) {
      return value.length > 0 ? value.join(', ') : '(empty list)';
    }
    
    return String(value);
  };

  const hasProblematicFields = (record: TestRecord): boolean => {
    const fields = [
      record.patient_first_name,
      record.patient_last_name,
      record.patient_id_number,
      record.sender,
      record.received_date,
      record.central_numbers
    ];
    
    return fields.some(f => 
      f.review_state === 'needs_review' || 
      f.extraction_state === 'invalid'
    );
  };

  const canExport = (): boolean => {
    return exportEligibility?.can_export ?? false;
  };

  const handleEditClick = (
    testId: string,
    fieldName: string,
    fieldLabel: string,
    field: FieldValue,
    isListField: boolean = false
  ) => {
    setEditModal({
      isOpen: true,
      testId,
      fieldName,
      fieldLabel,
      currentValue: field.reviewed_value ?? field.normalized_value ?? field.raw_value,
      fieldType: isListField ? 'list' : 'text',
      suggestions: fieldName === 'sender' ? getSenderSuggestions() : undefined
    });
  };

  const getSenderSuggestions = (): string[] => {
    // Could be loaded from API or hardcoded list of institutions
    // For now, return empty array (can be enhanced later)
    return [];
  };

  const handleSaveEdit = async (newValue: any) => {
    if (!editModal) return;
    
    try {
      // Update field via API
      await updateField(batchId, editModal.testId, editModal.fieldName, newValue);
      
      // Reload batch data to get updated state
      await loadBatchData();
      
      setEditModal(null);
    } catch (err: any) {
      console.error('Failed to save edit:', err);
      alert('Failed to save changes: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleCloseModal = () => {
    setEditModal(null);
  };

  const handleExport = async () => {
    if (!canExport()) {
      alert('Cannot export: some fields need review');
      return;
    }
    
    setExportingInner(true);
    
    try {
      const blob = await exportBatch(batchId);
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `commitments_${batchId}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error('Export failed:', err);
      alert('Export failed: ' + (err.response?.data?.detail?.message || err.message));
    } finally {
      setExportingInner(false);
    }
  };


  return (
    <div className="review-screen">
      <header className="review-header">
        <h2>Review Extracted Data</h2>
        <div className="batch-info">
          <span>Batch: {batchData.batch_id}</span>
          <span>Status: {batchData.status}</span>
          <span>Processed: {batchData.processed_count ?? testRecords.length}</span>
          {batchData.error_count !== undefined && batchData.error_count > 0 && (
            <span className="error-count">Errors: {batchData.error_count}</span>
          )}
        </div>
      </header>

      {/* Errors section */}
      {errors.length > 0 && (
        <section className="errors-section">
          <h3>Processing Errors</h3>
          <ul className="error-list">
            {errors.map((err, idx) => (
              <li key={idx} className="error-item">
                <strong>Document {err.document_id}</strong>
                {err.page_index !== undefined && ` (Page ${err.page_index})`}: {err.error}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Legend */}
      <section className="legend">
        <h3>Field Status Legend</h3>
        <div className="legend-items">
          <div className="legend-item">
            <span className="legend-color field-found"></span>
            <span>Valid - Found</span>
          </div>
          <div className="legend-item">
            <span className="legend-color field-needs-review"></span>
            <span>Needs Review - Uncertain or Missing</span>
          </div>
          <div className="legend-item">
            <span className="legend-color field-invalid"></span>
            <span>Invalid - Failed Validation</span>
          </div>
        </div>
      </section>

      {/* Test Records */}
      <section className="test-records">
        <h3>Test Records ({testRecords.length})</h3>
        
        {testRecords.length === 0 && (
          <p className="no-records">No test records found.</p>
        )}
        
        {testRecords.map((record) => (
          <div key={record.test_id} className="test-record-card">
            <div className="record-header">
              <h4>Test ID: {record.test_id}</h4>
              <div className="record-meta">
                <span>Document: {record.document_id}</span>
                <span>Pages: {record.page_indices.join(', ')}</span>
                {hasProblematicFields(record) && (
                  <span className="flag-warning">⚠ Needs Review</span>
                )}
              </div>
            </div>

            <div className="record-fields">
              <div className={getFieldClassName(record.patient_first_name)}>
                <div className="field-header">
                  <label>First Name</label>
                  <button
                    className="edit-button"
                    onClick={() => handleEditClick(
                      record.test_id,
                      'patient_first_name',
                      'First Name',
                      record.patient_first_name
                    )}
                    title="Edit field"
                  >
                    ✎ Edit
                  </button>
                </div>
                <div className="field-value">{getFieldValue(record.patient_first_name)}</div>
                {record.patient_first_name.validation_issues.length > 0 && (
                  <ul className="validation-issues">
                    {record.patient_first_name.validation_issues.map((issue, idx) => (
                      <li key={idx} className={`issue-${issue.severity}`}>
                        {issue.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className={getFieldClassName(record.patient_last_name)}>
                <label>Last Name</label>
                <div className="field-value">{getFieldValue(record.patient_last_name)}</div>
                {record.patient_last_name.validation_issues.length > 0 && (
                  <ul className="validation-issues">
                    {record.patient_last_name.validation_issues.map((issue, idx) => (
                      <li key={idx} className={`issue-${issue.severity}`}>
                        {issue.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className={getFieldClassName(record.patient_id_number)}>
                <label>ID Number</label>
                <div className="field-value">{getFieldValue(record.patient_id_number)}</div>
                {record.patient_id_number.validation_issues.length > 0 && (
                  <ul className="validation-issues">
                    {record.patient_id_number.validation_issues.map((issue, idx) => (
                      <li key={idx} className={`issue-${issue.severity}`}>
                        {issue.message}
                        {issue.suggested_fix && <span className="suggested-fix"> → {issue.suggested_fix}</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className={getFieldClassName(record.sender)}>
                <label>Sender</label>
                <div className="field-value">{getFieldValue(record.sender)}</div>
                {record.sender.validation_issues.length > 0 && (
                  <ul className="validation-issues">
                    {record.sender.validation_issues.map((issue, idx) => (
                      <li key={idx} className={`issue-${issue.severity}`}>
                        {issue.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className={getFieldClassName(record.received_date)}>
                <label>Received Date</label>
                <div className="field-value">{getFieldValue(record.received_date)}</div>
                {record.received_date.validation_issues.length > 0 && (
                  <ul className="validation-issues">
                    {record.received_date.validation_issues.map((issue, idx) => (
                      <li key={idx} className={`issue-${issue.severity}`}>
                        {issue.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className={getFieldClassName(record.central_numbers)}>
                <label>Central Numbers</label>
                <div className="field-value">{getFieldValue(record.central_numbers)}</div>
                {record.central_numbers.validation_issues.length > 0 && (
                  <ul className="validation-issues">
                    {record.central_numbers.validation_issues.map((issue, idx) => (
                      <li key={idx} className={`issue-${issue.severity}`}>
                        {issue.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Associated Commitments */}
            {record.commitment_ids.length > 0 && (
              <div className="associated-commitments">
                <h5>Associated Commitment Numbers ({record.commitment_ids.length})</h5>
                <ul className="commitment-list">
                  {record.commitment_ids.map((commId) => {
                    const comm = commitmentRecords.find(c => c.commitment_record_id === commId);
                    if (!comm) return null;
                    
                    return (
                      <li key={commId} className="commitment-item">
                        <span className="commitment-number">{getFieldValue(comm.commitment_number)}</span>
                        <span className={`relation-status status-${comm.relation_status}`}>
                          {comm.relation_status}
                        </span>
                        {comm.central_number_refs.length > 0 && (
                          <span className="refs">→ Centrals: {comm.central_number_refs.join(', ')}</span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>
        ))}
      </section>

      {/* Export section */}
      <section className="export-section">
        <button 
          className="export-button"
          onClick={handleExport}
          disabled={!canExport() || exportingInner}
          title={!canExport() ? 'Cannot export: some fields need review' : 'Export to Excel'}
        >
          {exportingInner ? 'Exporting...' : 'Export to Excel'}
        </button>
        {!canExport() && exportEligibility && (
          <div className="export-blocked-message">
            <p>⚠ Export blocked: Please review and fix all flagged fields before exporting</p>
            {exportEligibility.blockers.length > 0 && (
              <details>
                <summary>Show blockers ({exportEligibility.blockers.length})</summary>
                <ul>
                  {exportEligibility.blockers.map((blocker, idx) => (
                    <li key={idx}>{blocker}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
        {onBack && (
          <button 
            className="button-secondary"
            onClick={onBack}
            style={{ marginTop: '1rem' }}
          >
            Back to Upload
          </button>
        )}
      </section>
      
      {/* Edit Modal */}
      {editModal && (
        <EditFieldModal
          isOpen={editModal.isOpen}
          onClose={handleCloseModal}
          onSave={handleSaveEdit}
          fieldName={editModal.fieldName}
          fieldLabel={editModal.fieldLabel}
          currentValue={editModal.currentValue}
          fieldType={editModal.fieldType}
          suggestions={editModal.suggestions}
        />
      )}
    </div>
  );
};
