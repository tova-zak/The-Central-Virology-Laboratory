/**
 * ResolveRelationshipModal Component
 * 
 * Modal for resolving ambiguous relationship between commitment and central numbers.
 * Secretary confirms whether the commitment is correctly linked to the central number(s).
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
  central_number_refs: string[];
  relation_status: string;
}

interface ResolveRelationshipModalProps {
  isOpen: boolean;
  commitment: CommitmentRecord;
  availableCentralNumbers: string[];
  onResolve: (newRefs: string[], newStatus: 'related' | 'unrelated') => void;
  onClose: () => void;
}

export const ResolveRelationshipModal: React.FC<ResolveRelationshipModalProps> = ({
  isOpen,
  commitment,
  availableCentralNumbers,
  onResolve,
  onClose
}) => {
  const [selectedRefs, setSelectedRefs] = useState<string[]>(commitment.central_number_refs || []);

  if (!isOpen) return null;

  const commitmentValue = 
    commitment.commitment_number?.reviewed_value ||
    commitment.commitment_number?.normalized_value ||
    commitment.commitment_number?.raw_value ||
    'לא זוהה';

  const handleConfirm = () => {
    onResolve(selectedRefs, 'related');
  };

  const handleUnrelate = () => {
    onResolve([], 'unrelated');
  };

  const toggleCentralNumber = (num: string) => {
    setSelectedRefs(prev => 
      prev.includes(num) 
        ? prev.filter(n => n !== num)
        : [...prev, num]
    );
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} dir="rtl">
        <div className="modal-header">
          <h3>פתרון קשר לא ברור</h3>
          <button className="modal-close-btn" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div style={{ marginBottom: '1.5rem' }}>
            <p style={{ marginBottom: '0.5rem' }}>
              התחייבות מספר: <strong>{commitmentValue}</strong>
            </p>
            <p style={{ color: '#666', fontSize: '0.9rem' }}>
              בחר את המספרים המרכזיים שאליהם משתייכת ההתחייבות:
            </p>
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            {availableCentralNumbers.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {availableCentralNumbers.map(num => (
                  <label
                    key={num}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      padding: '0.75rem',
                      border: '2px solid #e0e0e0',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      background: selectedRefs.includes(num) ? '#e3f2fd' : 'white'
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedRefs.includes(num)}
                      onChange={() => toggleCentralNumber(num)}
                      style={{ marginLeft: '0.5rem' }}
                    />
                    <span style={{ fontWeight: 600 }}>{num}</span>
                  </label>
                ))}
              </div>
            ) : (
              <p style={{ textAlign: 'center', color: '#999', padding: '1rem' }}>
                אין מספרים מרכזיים זמינים בבדיקה זו
              </p>
            )}
          </div>

          <div style={{ 
            padding: '1rem', 
            background: '#fff3e0', 
            borderRadius: '4px',
            border: '1px solid #FF9800',
            fontSize: '0.9rem'
          }}>
            <strong>הסבר:</strong> בחר את המספרים המרכזיים הרלוונטיים להתחייבות זו.
            אם ההתחייבות לא משתייכת לאף מספר מרכזי בטופס זה, לחץ על "נתק קשר".
          </div>
        </div>

        <div className="modal-footer">
          <button className="modal-btn modal-btn-secondary" onClick={onClose}>
            ביטול
          </button>
          <button 
            className="modal-btn modal-btn-danger" 
            onClick={handleUnrelate}
            title="התחייבות זו לא משתייכת לבדיקה זו"
          >
            נתק קשר
          </button>
          <button
            className="modal-btn modal-btn-primary"
            onClick={handleConfirm}
            disabled={selectedRefs.length === 0}
            title="אשר את הקשר למספרים המרכזיים שנבחרו"
          >
            אשר קשר
          </button>
        </div>
      </div>
    </div>
  );
};
