/**
 * RelationshipEditor Component
 * 
 * Modal for manually linking unresolved commitments to samples
 * Allows user to:
 * - See commitment details
 * - Select one or more samples (checkbox selection)
 * - Assign explicit relationship
 * - Disconnect relationship
 * 
 * Part of MVP 8-hour push - Form-based review UI
 */
import React, { useState, useEffect } from 'react';
import './RelationshipEditor.css';
import { CommitmentRecord, Sample } from '../../services/api';
import { getFieldDisplayValue } from './utils/editPermissions';

interface RelationshipEditorProps {
  isOpen: boolean;
  commitment: CommitmentRecord;
  samples: Sample[];
  onResolve: (commitmentId: string, sampleIds: string[], newStatus: 'explicit') => void;
  onDisconnect: (commitmentId: string) => void;
  onClose: () => void;
}

export const RelationshipEditor: React.FC<RelationshipEditorProps> = ({
  isOpen,
  commitment,
  samples,
  onResolve,
  onDisconnect,
  onClose
}) => {
  const [selectedSampleIds, setSelectedSampleIds] = useState<string[]>([]);

  // Initialize with existing sample_ids if present
  useEffect(() => {
    if (commitment.sample_ids && commitment.sample_ids.length > 0) {
      setSelectedSampleIds(commitment.sample_ids);
    } else {
      setSelectedSampleIds([]);
    }
  }, [commitment.commitment_record_id, isOpen]);

  if (!isOpen) return null;

  const handleToggleSample = (sampleId: string) => {
    setSelectedSampleIds(prev => {
      if (prev.includes(sampleId)) {
        return prev.filter(id => id !== sampleId);
      } else {
        return [...prev, sampleId];
      }
    });
  };

  const handleAssign = () => {
    if (selectedSampleIds.length === 0) {
      alert('יש לבחור לפחות דגימה אחת');
      return;
    }
    onResolve(commitment.commitment_record_id, selectedSampleIds, 'explicit');
    onClose();
  };

  const handleDisconnect = () => {
    if (confirm('האם לנתק את ההתחייבות מכל הדגימות?')) {
      onDisconnect(commitment.commitment_record_id);
      onClose();
    }
  };

  const handleCancel = () => {
    setSelectedSampleIds([]);
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      handleCancel();
    }
  };

  const commitmentNumberDisplay = getFieldDisplayValue(commitment.commitment_number);
  const currentStatus = commitment.relationship_status || commitment.relation_status;

  return (
    <div 
      className="modal-overlay" 
      onClick={handleCancel}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-labelledby="relationship-editor-title"
    >
      <div className="modal-content relationship-editor-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 id="relationship-editor-title">יישוב קשר התחייבות</h3>
          <button className="close-button" onClick={handleCancel} aria-label="סגור">
            ×
          </button>
        </div>

        <div className="modal-body relationship-editor-body">
          {/* Commitment Details Panel */}
          <div className="commitment-details-panel">
            <h4>פרטי התחייבות</h4>
            <div className="commitment-info">
              <div className="info-row">
                <span className="info-label">מספר התחייבות:</span>
                <span className="info-value commitment-number-display">
                  {Array.isArray(commitmentNumberDisplay) 
                    ? commitmentNumberDisplay.join(', ') 
                    : commitmentNumberDisplay || '—'}
                </span>
              </div>
              <div className="info-row">
                <span className="info-label">סטטוס נוכחי:</span>
                <span className={`info-value status-badge status-${
                  currentStatus === 'explicit' || currentStatus === 'clear' || currentStatus === 'manual' 
                    ? 'green' 
                    : currentStatus === 'unresolved_relationship' || currentStatus === 'ambiguous' 
                    ? 'orange' 
                    : 'red'
                }`}>
                  {currentStatus === 'explicit' && '✅ קשר מאומת'}
                  {currentStatus === 'inferred' && '✅ קשר משוער'}
                  {currentStatus === 'clear' && '✅ קשר ברור'}
                  {currentStatus === 'manual' && '✅ קשר ידני'}
                  {currentStatus === 'unresolved_relationship' && '⚠️ דורש ביקורת'}
                  {currentStatus === 'ambiguous' && '⚠️ לא ברור'}
                  {currentStatus === 'none' && '❌ לא משוייך'}
                </span>
              </div>
              {commitment.sample_ids && commitment.sample_ids.length > 0 && (
                <div className="info-row">
                  <span className="info-label">דגימות קיימות:</span>
                  <span className="info-value">{commitment.sample_ids.length}</span>
                </div>
              )}
            </div>
          </div>

          {/* Samples Selection Panel */}
          <div className="samples-selection-panel">
            <h4>דגימות זמינות ({samples.length})</h4>
            <p className="panel-instructions">בחר דגימה אחת או יותר לשיוך להתחייבות</p>
            
            {samples.length === 0 ? (
              <div className="empty-samples-message">
                <p>אין דגימות זמינות לשיוך</p>
              </div>
            ) : (
              <ul className="samples-selection-list" role="list">
                {samples.map(sample => {
                  const centralNumber = getFieldDisplayValue(sample.central_number);
                  const receivedDate = getFieldDisplayValue(sample.received_date);
                  const isSelected = selectedSampleIds.includes(sample.sample_id);
                  
                  return (
                    <li key={sample.sample_id} className="sample-selection-item">
                      <label className="sample-checkbox-label">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleSample(sample.sample_id)}
                          aria-label={`דגימה ${centralNumber}`}
                        />
                        <div className="sample-info">
                          <span className="sample-central-display">
                            מס׳ מרכזי: <strong>{centralNumber}</strong>
                          </span>
                          <span className="sample-date-display">
                            תאריך קבלה: {receivedDate}
                          </span>
                        </div>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
            
            <div className="selection-summary">
              נבחרו {selectedSampleIds.length} מתוך {samples.length} דגימות
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="button-secondary" onClick={handleCancel}>
            ביטול
          </button>
          <button 
            className="button-danger" 
            onClick={handleDisconnect}
            disabled={!commitment.sample_ids || commitment.sample_ids.length === 0}
          >
            נתק קשר
          </button>
          <button 
            className="button-primary" 
            onClick={handleAssign}
            disabled={selectedSampleIds.length === 0}
          >
            שייך לדגימות ({selectedSampleIds.length})
          </button>
        </div>
      </div>
    </div>
  );
};
