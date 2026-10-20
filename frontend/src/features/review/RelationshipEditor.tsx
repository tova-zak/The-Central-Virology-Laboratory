/**
 * RelationshipEditor Component - Manual Commitment-Sample Linking
 * 
 * Allows users to resolve unresolved commitment-sample relationships.
 * Conforms to actual backend API contract: central_number_refs + relation_status.
 * 
 * Agent B - MVP 8-hour implementation (Iteration 2: API contract conformance)
 */
import React, { useState, useEffect } from 'react';
import './RelationshipEditor.css';
import { CommitmentRecord, Sample, FieldValue } from '../../services/api';

interface RelationshipEditorProps {
  isOpen: boolean;
  commitment: CommitmentRecord;
  samples: Sample[]; // All samples in the batch
  onResolve: (commitmentId: string, centralNumberRefs: string[], newStatus: 'related' | 'unrelated') => void;
  onDisconnect: (commitmentId: string) => void;
  onClose: () => void;
}

/**
 * Get display value from FieldValue
 */
const getFieldDisplayValue = (field: FieldValue<any> | null | undefined): string => {
  if (!field) return '-';
  
  if (field.review_state === 'human_verified' && field.reviewed_value != null) {
    return String(field.reviewed_value);
  }
  
  if (field.normalized_value != null) {
    return String(field.normalized_value);
  }
  
  if (field.raw_value != null) {
    return String(field.raw_value);
  }
  
  return '-';
};

export const RelationshipEditor: React.FC<RelationshipEditorProps> = ({
  isOpen,
  commitment,
  samples,
  onResolve,
  onDisconnect,
  onClose
}) => {
  // Track selected central numbers (NOT sample IDs - backend expects central_number_refs)
  const [selectedCentralNumbers, setSelectedCentralNumbers] = useState<string[]>([]);

  useEffect(() => {
    // Initialize with current central_number_refs if any
    if (isOpen && commitment.central_number_refs) {
      setSelectedCentralNumbers([...commitment.central_number_refs]);
    } else {
      setSelectedCentralNumbers([]);
    }
  }, [isOpen, commitment]);

  if (!isOpen) return null;

  const commitmentNumber = getFieldDisplayValue(commitment.commitment_number);

  const handleToggleCentralNumber = (centralNumber: string) => {
    setSelectedCentralNumbers(prev => {
      if (prev.includes(centralNumber)) {
        return prev.filter(cn => cn !== centralNumber);
      } else {
        return [...prev, centralNumber];
      }
    });
  };

  const handleResolve = () => {
    if (selectedCentralNumbers.length === 0) {
      alert('אנא בחר לפחות מספר מרכזי אחד או נתק את הקשר');
      return;
    }
    
    // User selection = explicit confirmation = 'related'
    onResolve(commitment.commitment_record_id, selectedCentralNumbers, 'related');
  };

  const handleDisconnect = () => {
    if (!window.confirm('האם לנתק את ההתחייבות מכל הדגימות?')) {
      return;
    }
    
    // Disconnect = empty refs + 'unrelated'
    onDisconnect(commitment.commitment_record_id);
  };

  const handleCancel = () => {
    setSelectedCentralNumbers(commitment.central_number_refs || []);
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      handleCancel();
    }
  };

  return (
    <div className="modal-overlay" onClick={handleCancel} onKeyDown={handleKeyDown}>
      <div
        className="relationship-editor-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="relationship-editor-title"
        aria-modal="true"
      >
        <div className="modal-header">
          <h3 id="relationship-editor-title">פתרון קשר התחייבות-דגימות</h3>
          <button className="close-button" onClick={handleCancel} aria-label="סגור">
            ×
          </button>
        </div>

        <div className="modal-body">
          {/* Commitment Info */}
          <div className="commitment-panel">
            <h4>התחייבות</h4>
            <div className="commitment-display">
              <span className="commitment-number-display">{commitmentNumber}</span>
              <span className="current-status">
                {commitment.relationship_status === 'unresolved_relationship' && '⚠️ דורש ביקורת'}
                {commitment.relationship_status === 'none' && '❌ לא משוייך'}
                {commitment.relationship_status === 'explicit' && '✅ קשר מאומת'}
                {commitment.relationship_status === 'inferred' && '✅ קשר מוסק'}
                {!commitment.relationship_status && commitment.relation_status === 'ambiguous' && '⚠️ לא ברור (ישן)'}
              </span>
            </div>
            <p className="helper-text">
              בחר את המספרים המרכזיים (דגימות) המשויכים להתחייבות זו
            </p>
          </div>

          {/* Samples Selection */}
          <div className="samples-panel">
            <h4>דגימות זמינות ({samples.length})</h4>
            {samples.length === 0 ? (
              <p className="empty-message">אין דגימות זמינות באצווה זו</p>
            ) : (
              <div className="samples-selection-list">
                {samples.map((sample) => {
                  const centralNumber = getFieldDisplayValue(sample.central_number);
                  const receivedDate = getFieldDisplayValue(sample.received_date);
                  const isSelected = selectedCentralNumbers.includes(centralNumber);

                  return (
                    <label
                      key={sample.sample_id}
                      className={`sample-checkbox-item ${isSelected ? 'selected' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleToggleCentralNumber(centralNumber)}
                        aria-label={`בחר דגימה ${centralNumber}`}
                      />
                      <div className="sample-info">
                        <span className="sample-central">{centralNumber}</span>
                        <span className="sample-date">{receivedDate}</span>
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* Selection Summary */}
          {selectedCentralNumbers.length > 0 && (
            <div className="selection-summary">
              <strong>נבחרו {selectedCentralNumbers.length} דגימות:</strong>
              <span className="selected-items">{selectedCentralNumbers.join(', ')}</span>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="button-secondary" onClick={handleCancel}>
            ביטול
          </button>
          <button
            className="button-danger"
            onClick={handleDisconnect}
            title="נתק התחייבות זו מכל הדגימות"
          >
            נתק קשר
          </button>
          <button
            className="button-primary"
            onClick={handleResolve}
            disabled={selectedCentralNumbers.length === 0}
          >
            שייך לדגימות
          </button>
        </div>
      </div>
    </div>
  );
};
