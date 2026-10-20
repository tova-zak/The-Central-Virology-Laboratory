/**
 * Edit Field Modal Component
 * 
 * Allows manual correction of extracted fields
 * Supports:
 * - Single-value fields (text input)
 * - Multi-value fields (list with add/remove)
 * - Relationship editing (central ↔ commitment mapping)
 * 
 * TASK-015: Manual correction interface
 */
import React, { useState, useEffect } from 'react';
import './EditFieldModal.css';

interface EditFieldModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (newValue: any) => void;
  fieldName: string;
  fieldLabel: string;
  currentValue: any;
  fieldType: 'text' | 'list';
  suggestions?: string[]; // For dropdown suggestions
}

export const EditFieldModal: React.FC<EditFieldModalProps> = ({
  isOpen,
  onClose,
  onSave,
  fieldName,
  fieldLabel,
  currentValue,
  fieldType,
  suggestions = []
}) => {
  const [editValue, setEditValue] = useState<any>(currentValue);
  const [newListItem, setNewListItem] = useState('');
  
  useEffect(() => {
    // Reset edit value when modal opens with new data
    setEditValue(currentValue);
    setNewListItem('');
  }, [currentValue, isOpen]);

  if (!isOpen) return null;

  const handleSave = () => {
    onSave(editValue);
    onClose();
  };

  const handleCancel = () => {
    setEditValue(currentValue); // Reset
    onClose();
  };

  const handleAddListItem = () => {
    if (newListItem.trim()) {
      const updated = [...(editValue || []), newListItem.trim()];
      setEditValue(updated);
      setNewListItem('');
    }
  };

  const handleRemoveListItem = (index: number) => {
    const updated = [...(editValue || [])];
    updated.splice(index, 1);
    setEditValue(updated);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && fieldType === 'list') {
      e.preventDefault();
      handleAddListItem();
    } else if (e.key === 'Enter' && fieldType === 'text') {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  return (
    <div className="modal-overlay" onClick={handleCancel}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Edit {fieldLabel}</h3>
          <button className="close-button" onClick={handleCancel} aria-label="Close">
            ×
          </button>
        </div>

        <div className="modal-body">
          {fieldType === 'text' && (
            <div className="text-input-group">
              <label htmlFor={`edit-${fieldName}`}>
                {fieldLabel}
              </label>
              
              {suggestions.length > 0 ? (
                <div className="input-with-suggestions">
                  <input
                    id={`edit-${fieldName}`}
                    type="text"
                    value={editValue || ''}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={`Enter ${fieldLabel.toLowerCase()}`}
                    autoFocus
                    list={`suggestions-${fieldName}`}
                  />
                  <datalist id={`suggestions-${fieldName}`}>
                    {suggestions.map((suggestion, idx) => (
                      <option key={idx} value={suggestion} />
                    ))}
                  </datalist>
                </div>
              ) : (
                <input
                  id={`edit-${fieldName}`}
                  type="text"
                  value={editValue || ''}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={`Enter ${fieldLabel.toLowerCase()}`}
                  autoFocus
                />
              )}
              
              <p className="field-hint">
                Original: <strong>{currentValue || '(none)'}</strong>
              </p>
            </div>
          )}

          {fieldType === 'list' && (
            <div className="list-input-group">
              <label>Current Values</label>
              
              {(!editValue || editValue.length === 0) && (
                <p className="empty-list">No values yet</p>
              )}
              
              {editValue && editValue.length > 0 && (
                <ul className="list-items">
                  {editValue.map((item: string, index: number) => (
                    <li key={index} className="list-item">
                      <span className="item-value">{item}</span>
                      <button
                        className="remove-button"
                        onClick={() => handleRemoveListItem(index)}
                        aria-label={`Remove ${item}`}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <div className="add-item-section">
                <label htmlFor="new-item-input">Add New Value</label>
                <div className="add-item-controls">
                  <input
                    id="new-item-input"
                    type="text"
                    value={newListItem}
                    onChange={(e) => setNewListItem(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Enter value and press Enter"
                  />
                  <button
                    className="add-button"
                    onClick={handleAddListItem}
                    disabled={!newListItem.trim()}
                  >
                    Add
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="button-secondary" onClick={handleCancel}>
            Cancel
          </button>
          <button className="button-primary" onClick={handleSave}>
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
};
