/**
 * AssignCommitmentModal Component
 * 
 * Modal for assigning an orphaned commitment to a test record.
 * Displays list of available test records for selection.
 */
import React, { useState } from 'react';
import './ReviewScreen.css';

interface CommitmentRecord {
  commitment_record_id: string;
  commitment_number: {
    raw_value?: string;
    normalized_value?: string;
    reviewed_value?: string;
  };
  test_id?: string;
}

interface TestRecord {
  test_id: string;
  patient_first_name: any;
  patient_last_name: any;
  patient_id_number: any;
}

interface AssignCommitmentModalProps {
  isOpen: boolean;
  commitment: CommitmentRecord;
  testRecords: TestRecord[];
  onAssign: (testId: string) => void;
  onClose: () => void;
}

export const AssignCommitmentModal: React.FC<AssignCommitmentModalProps> = ({
  isOpen,
  commitment,
  testRecords,
  onAssign,
  onClose
}) => {
  const [selectedTestId, setSelectedTestId] = useState<string | null>(null);

  if (!isOpen) return null;

  const commitmentValue = 
    commitment.commitment_number?.reviewed_value ||
    commitment.commitment_number?.normalized_value ||
    commitment.commitment_number?.raw_value ||
    'לא זוהה';

  const handleAssign = () => {
    if (selectedTestId) {
      onAssign(selectedTestId);
      setSelectedTestId(null);
    }
  };

  const getFieldValue = (field: any): string => {
    if (!field) return '-';
    return field.reviewed_value || field.normalized_value || field.raw_value || '-';
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} dir="rtl">
        <div className="modal-header">
          <h3>שיוך התחייבות לבדיקה</h3>
          <button className="modal-close-btn" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <p style={{ marginBottom: '1rem' }}>
            התחייבות מספר: <strong>{commitmentValue}</strong>
          </p>
          <p style={{ marginBottom: '1rem', color: '#666' }}>
            בחר את הבדיקה שאליה משתייכת ההתחייבות:
          </p>

          <div className="test-record-list">
            {testRecords.map(record => (
              <div
                key={record.test_id}
                className={`test-record-item ${selectedTestId === record.test_id ? 'selected' : ''}`}
                onClick={() => setSelectedTestId(record.test_id)}
              >
                <div className="test-record-item-header">
                  {getFieldValue(record.patient_first_name)} {getFieldValue(record.patient_last_name)}
                </div>
                <div className="test-record-item-details">
                  ת.ז: {getFieldValue(record.patient_id_number)} | מזהה: {record.test_id}
                </div>
              </div>
            ))}
          </div>

          {testRecords.length === 0 && (
            <p style={{ textAlign: 'center', color: '#999', padding: '2rem' }}>
              אין בדיקות זמינות
            </p>
          )}
        </div>

        <div className="modal-footer">
          <button className="modal-btn modal-btn-secondary" onClick={onClose}>
            ביטול
          </button>
          <button
            className="modal-btn modal-btn-primary"
            onClick={handleAssign}
            disabled={!selectedTestId}
          >
            שייך לבדיקה
          </button>
        </div>
      </div>
    </div>
  );
};
