/**
 * ReviewScreen - Three-Table Redesign
 * 
 * Displays extracted records in three tables based on classification:
 * - Table 1: טפסים שחולצו בהצלחה (success - read-only)
 * - Table 2: טפסים עם הערות לבדיקה (warnings - only problematic fields editable)
 * - Table 3: טפסים הדורשים השלמה ידנית (missing - only missing fields editable)
 */
import React, { useState, useEffect } from 'react';
import './ReviewScreen.css';
import { 
  getBatchStatus, 
  updateField,
  checkExportEligibility,
  BatchStatusResponse,
  TestRecord,
  LogicalForm,
  Sample,
  CommitmentRecord
} from '../../services/api';
import { classifyTestRecords, ClassifiedRecords } from './utils/classification';
import { isFieldEditable, getFieldDisplayValue, getFieldVisualState, getFieldLabel } from './utils/editPermissions';
import { getCommitmentNumbersForTest } from './utils/relationships';
import { EditFieldModal } from './EditFieldModal';
import { AssignCommitmentModal } from './AssignCommitmentModal';
import { ResolveRelationshipModal } from './ResolveRelationshipModal';
import { DocumentViewerModal } from './DocumentViewerModal';
import { FormCard } from './FormCard';
import { RelationshipEditor } from './RelationshipEditor';

interface ReviewScreenProps {
  batchId: string;
  onBack?: () => void;
}

type FieldName = 'patient_first_name' | 'patient_last_name' | 'patient_id_number' | 
                 'sender' | 'received_date' | 'central_numbers';

export const ReviewScreenNew: React.FC<ReviewScreenProps> = ({ batchId, onBack }) => {
  const [batchData, setBatchData] = useState<BatchStatusResponse | null>(null);
  const [classified, setClassified] = useState<ClassifiedRecords | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exportEligibility, setExportEligibility] = useState<{
    can_export: boolean;
    blockers: string[];
  } | null>(null);
  
  // View mode: 'cards' for form-based view, 'table' for legacy three-table view
  const [viewMode, setViewMode] = useState<'table' | 'cards'>('cards');
  
  // Search/filter state (independent per table)
  const [searchTable1, setSearchTable1] = useState('');
  const [searchTable2, setSearchTable2] = useState('');
  const [searchTable3, setSearchTable3] = useState('');
  
  // Search for cards view
  const [searchCards, setSearchCards] = useState('');
  
  // Pagination state (20 per page, independent per table)
  const [pageTable1, setPageTable1] = useState(1);
  const [pageTable2, setPageTable2] = useState(1);
  const [pageTable3, setPageTable3] = useState(1);
  const PAGE_SIZE = 20;
  
  // Edit modal state
  const [editModal, setEditModal] = useState<{
    isOpen: boolean;
    testId: string;
    fieldName: string;
    currentValue: any;
    fieldType: 'text' | 'list';
  } | null>(null);
  
  // Assign commitment modal state
  const [assignModal, setAssignModal] = useState<{
    isOpen: boolean;
    commitment: any;
  } | null>(null);
  
  // Resolve relationship modal state
  const [resolveModal, setResolveModal] = useState<{
    isOpen: boolean;
    commitment: any;
    testRecord: TestRecord;
  } | null>(null);
  
  // Relationship editor modal state (for form-based view)
  const [relationshipEditorModal, setRelationshipEditorModal] = useState<{
    isOpen: boolean;
    commitment: CommitmentRecord;
  } | null>(null);
  
  // Document viewer modal state
  const [documentModal, setDocumentModal] = useState<{
    isOpen: boolean;
    documentId: string;
    pageIndex: number;
  } | null>(null);

  // Load batch data
  useEffect(() => {
    loadBatchData();
  }, [batchId]);

  const loadBatchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getBatchStatus(batchId);
      setBatchData(data);
      
      // Classify records for table view
      const classifiedRecords = classifyTestRecords(
        data.test_records,
        data.commitment_records,
        data.status
      );
      setClassified(classifiedRecords);
      
      // Check export eligibility
      if (data.status === 'completed' || data.status === 'completed_with_errors') {
        const eligibility = await checkExportEligibility(batchId);
        setExportEligibility(eligibility);
      }
      
      // Auto-switch to cards view if forms are available
      if (data.forms && data.forms.length > 0) {
        setViewMode('cards');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load batch data');
    } finally {
      setLoading(false);
    }
  };

  const handleEditField = async (testId: string, fieldName: string, newValue: any) => {
    try {
      await updateField(batchId, testId, fieldName, newValue);
      await loadBatchData(); // Reload to reclassify
      setEditModal(null);
    } catch (err: any) {
      alert(`Failed to update field: ${err.message}`);
    }
  };

  const handleAssignCommitment = async (commitmentId: string, testId: string) => {
    try {
      const { assignCommitmentToTest } = await import('../../services/api');
      await assignCommitmentToTest(batchId, commitmentId, testId);
      setAssignModal(null);
      await loadBatchData(); // Reload to show updated classification
    } catch (err: any) {
      alert(`שגיאה בשיוך התחייבות: ${err.message || 'שגיאה לא צפויה'}`);
    }
  };

  const handleResolveRelationship = async (
    commitmentId: string,
    _testId: string,
    newRefs: string[],
    newStatus: 'related' | 'unrelated'
  ) => {
    try {
      const { resolveCommitmentRelationship } = await import('../../services/api');
      await resolveCommitmentRelationship(batchId, commitmentId, newRefs, newStatus);
      setResolveModal(null);
      await loadBatchData(); // Reload to show updated classification
    } catch (err: any) {
      alert(`שגיאה בפתרון קשר: ${err.message || 'שגיאה לא צפויה'}`);
    }
  };

  const handleResolveRelationshipFromEditor = async (
    commitmentId: string,
    sampleIds: string[],
    _newStatus: 'explicit'
  ) => {
    try {
      // For MVP, we'll call the existing resolve endpoint
      // Backend should be updated to accept sample_ids
      const { resolveCommitmentRelationship } = await import('../../services/api');
      await resolveCommitmentRelationship(batchId, commitmentId, sampleIds, 'related');
      setRelationshipEditorModal(null);
      await loadBatchData();
    } catch (err: any) {
      alert(`שגיאה בשיוך דגימות: ${err.message || 'שגיאה לא צפויה'}`);
    }
  };

  const handleDisconnectRelationship = async (commitmentId: string) => {
    try {
      const { resolveCommitmentRelationship } = await import('../../services/api');
      await resolveCommitmentRelationship(batchId, commitmentId, [], 'unrelated');
      setRelationshipEditorModal(null);
      await loadBatchData();
    } catch (err: any) {
      alert(`שגיאה בניתוק קשר: ${err.message || 'שגיאה לא צפויה'}`);
    }
  };

  const handleExport = async () => {
    // Check blockers first - include both legacy and new statistics
    const hasUnresolvedRelationships = batchData?.statistics?.unresolved_relationships ?? 0;
    
    if (!exportEligibility?.can_export || hasUnresolvedRelationships > 0) {
      const blockers = exportEligibility?.blockers || [];
      if (hasUnresolvedRelationships > 0) {
        blockers.push(`${hasUnresolvedRelationships} קשרים לא פתורים`);
      }
      alert(`לא ניתן לייצא - יש ${blockers.length} חוסמים:\n${blockers.join('\n')}`);
      return;
    }

    try {
      const { exportBatch } = await import('../../services/api');
      
      // Show loading state
      const originalText = 'ייצא ל-Excel';
      const button = document.querySelector('.export-btn') as HTMLButtonElement;
      if (button) button.textContent = 'מוריד...';
      
      // Get the Excel blob
      const blob = await exportBatch(batchId);
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `batch_${batchId}_export_${new Date().toISOString().split('T')[0]}.xlsx`;
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      // Reset button text
      if (button) button.textContent = originalText;
      
      alert('הקובץ הורד בהצלחה!');
    } catch (err: any) {
      alert(`שגיאה בייצוא: ${err.response?.data?.detail || err.message || 'שגיאה לא צפויה'}`);
      console.error('Export error:', err);
    }
  };

  if (loading) return <div className="review-screen loading">טוען נתונים...</div>;
  if (error) return <div className="review-screen error">שגיאה: {error}</div>;
  if (!batchData || !classified) return null;

  // Helper: Filter forms based on search query
  const filterForms = (forms: LogicalForm[], search: string): LogicalForm[] => {
    if (!search.trim()) return forms;
    const searchLower = search.toLowerCase();
    return forms.filter(form => {
      const firstName = getFieldDisplayValue(form.patient_first_name) as string;
      const lastName = getFieldDisplayValue(form.patient_last_name) as string;
      const idNumber = getFieldDisplayValue(form.patient_id_number) as string;
      const sender = getFieldDisplayValue(form.sender) as string;
      return (
        firstName?.toLowerCase().includes(searchLower) ||
        lastName?.toLowerCase().includes(searchLower) ||
        idNumber?.includes(searchLower) ||
        sender?.toLowerCase().includes(searchLower) ||
        form.form_id.toLowerCase().includes(searchLower)
      );
    });
  };

  // Helper: Get samples for a form
  const getSamplesForForm = (formId: string): Sample[] => {
    if (!batchData.samples) return [];
    return batchData.samples.filter(s => s.form_id === formId);
  };

  // Helper: Get commitments for a form
  const getCommitmentsForForm = (formId: string): CommitmentRecord[] => {
    if (!batchData.commitment_records) return [];
    return batchData.commitment_records.filter(c => c.form_id === formId);
  };

  // Cards view rendering
  const renderCardsView = () => {
    if (!batchData.forms || batchData.forms.length === 0) {
      return (
        <div className="empty-state">
          <p>אין טפסים זמינים. עובר לתצוגת טבלאות...</p>
        </div>
      );
    }

    const filtered = filterForms(batchData.forms, searchCards);

    return (
      <div className="forms-cards-container">
        <div className="cards-view-header">
          <div className="cards-search-controls">
            <input
              type="search"
              placeholder="חיפוש לפי שם, ת.ז., גורם שולח או מספר טופס..."
              value={searchCards}
              onChange={(e) => setSearchCards(e.target.value)}
              className="search-input"
              aria-label="חיפוש טפסים"
            />
          </div>
          <div className="cards-summary">
            {filtered.length === batchData.forms.length ? (
              <span>מציג {batchData.forms.length} טפסים</span>
            ) : (
              <span>מציג {filtered.length} מתוך {batchData.forms.length} טפסים</span>
            )}
            {batchData.statistics && batchData.statistics.unresolved_relationships > 0 && (
              <span className="unresolved-badge">
                ⚠️ {batchData.statistics.unresolved_relationships} קשרים לא פתורים
              </span>
            )}
          </div>
        </div>

        <div className="forms-cards-grid">
          {filtered.map(form => (
            <FormCard
              key={form.form_id}
              form={form}
              samples={getSamplesForForm(form.form_id)}
              commitments={getCommitmentsForForm(form.form_id)}
              onEdit={(formId) => {
                // For MVP, editing is not implemented at form level
                alert(`עריכת טופס ${formId} תהיה זמינה בגרסה עתידית`);
              }}
              onResolveRelationship={(commitmentId) => {
                const commitment = batchData.commitment_records.find(
                  c => c.commitment_record_id === commitmentId
                );
                if (commitment) {
                  setRelationshipEditorModal({
                    isOpen: true,
                    commitment
                  });
                }
              }}
            />
          ))}
        </div>
      </div>
    );
  };

  // Filter function
  const filterRecords = (records: TestRecord[], search: string): TestRecord[] => {
    if (!search.trim()) return records;
    const searchLower = search.toLowerCase();
    return records.filter(record => {
      const firstName = getFieldDisplayValue(record.patient_first_name) as string;
      const lastName = getFieldDisplayValue(record.patient_last_name) as string;
      const idNumber = getFieldDisplayValue(record.patient_id_number) as string;
      return (
        firstName?.toLowerCase().includes(searchLower) ||
        lastName?.toLowerCase().includes(searchLower) ||
        idNumber?.includes(searchLower) ||
        record.test_id.includes(searchLower)
      );
    });
  };

  // Paginate function
  const paginate = (records: TestRecord[], page: number): TestRecord[] => {
    const start = (page - 1) * PAGE_SIZE;
    return records.slice(start, start + PAGE_SIZE);
  };

  // Render a single table
  const renderTable = (
    title: string,
    records: TestRecord[],
    search: string,
    setSearch: (val: string) => void,
    page: number,
    setPage: (val: number) => void,
    showViewColumn: boolean
  ) => {
    const filtered = filterRecords(records, search);
    const paginated = paginate(filtered, page);
    const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

    return (
      <div className="table-section">
        <h2>{title} ({records.length})</h2>
        
        <div className="table-controls">
          <input
            type="text"
            placeholder="חיפוש לפי שם, ת.ז., או מספר טופס..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="search-input"
          />
        </div>

        <table className="review-table" dir="rtl">
          <thead>
            <tr>
              <th>מספר סידורי</th>
              <th>שם פרטי</th>
              <th>שם משפחה</th>
              <th>מספר זהות</th>
              <th>מספרים מרכזיים</th>
              <th>תאריך קבלה</th>
              <th>גורם שולח</th>
              <th>מספרי התחייבות</th>
              <th>הערות/סיבה</th>
              <th>סטטוס ביקורת</th>
              {showViewColumn && <th>צפייה</th>}
            </tr>
          </thead>
          <tbody>
            {paginated.map((record, idx) => renderRow(record, (page - 1) * PAGE_SIZE + idx + 1, showViewColumn))}
          </tbody>
        </table>

        {totalPages > 1 && (
          <div className="pagination">
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}>הקודם</button>
            <span>עמוד {page} מתוך {totalPages}</span>
            <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages}>הבא</button>
          </div>
        )}
      </div>
    );
  };

  // Render a single row
  const renderRow = (record: TestRecord, index: number, showViewColumn: boolean) => {
    const commitmentNumbers = getCommitmentNumbersForTest(record, batchData!.commitment_records);
    const recordStatus = (record as any).record_status || '-';
    
    return (
      <tr key={record.test_id}>
        <td>{index}</td>
        {renderFieldCell(record, 'patient_first_name')}
        {renderFieldCell(record, 'patient_last_name')}
        {renderFieldCell(record, 'patient_id_number')}
        {renderFieldCell(record, 'central_numbers')}
        {renderFieldCell(record, 'received_date')}
        {renderFieldCell(record, 'sender')}
        <td>
          {commitmentNumbers.items.map((item, i) => {
            // Find the actual commitment record to check for ambiguous status
            const commitment = batchData!.commitment_records.find(c => c.commitment_record_id === item.commitment_record_id);
            const isAmbiguous = commitment && commitment.relation_status === 'ambiguous';
            
            return (
              <span key={i} className={item.hasWarning || isAmbiguous ? 'field-warning' : ''}>
                {item.value}
                {isAmbiguous && (
                  <button
                    className="resolve-btn-inline"
                    onClick={() => setResolveModal({ 
                      isOpen: true, 
                      commitment: commitment!,
                      testRecord: record
                    })}
                    title="יישוב קשר לא ברור"
                  >
                    🔗
                  </button>
                )}
                {item.editable && (
                  <button
                    className="edit-btn-inline"
                    onClick={() => openEditModal(record.test_id, 'commitment_number', item.value)}
                  >
                    ✏️
                  </button>
                )}
                {i < commitmentNumbers.items.length - 1 && ', '}
              </span>
            );
          })}
        </td>
        <td>-</td>
        <td className={`status-cell status-${recordStatus}`}>{recordStatus}</td>
        {showViewColumn && (
          <td>
            <button 
              className="view-doc-btn" 
              onClick={() => setDocumentModal({
                isOpen: true,
                documentId: record.document_id,
                pageIndex: record.page_indices?.[0] || 0
              })}
              title="צפייה במסמך המקורי"
            >
              👁️ צפה
            </button>
          </td>
        )}
      </tr>
    );
  };

  // Render a field cell with edit button if editable
  const renderFieldCell = (record: TestRecord, fieldName: FieldName) => {
    const field = record[fieldName];
    const visualState = getFieldVisualState(field);
    const displayValue = getFieldDisplayValue(field);
    const editable = isFieldEditable(field);
    
    const className = visualState.color === 'orange' ? 'field-warning' : 
                      visualState.color === 'red' ? 'field-error' : '';

    const valueDisplay = Array.isArray(displayValue)
      ? displayValue.join(', ')
      : displayValue || '-';

    return (
      <td className={className}>
        {valueDisplay}
        {editable && (
          <button
            className="edit-btn-inline"
            onClick={() => openEditModal(record.test_id, fieldName, displayValue)}
          >
            ✏️
          </button>
        )}
        {visualState.icon && <span className="icon">{visualState.icon === 'error' ? '❌' : '⚠️'}</span>}
      </td>
    );
  };

  const openEditModal = (testId: string, fieldName: string, currentValue: any) => {
    setEditModal({
      isOpen: true,
      testId,
      fieldName,
      currentValue,
      fieldType: fieldName === 'central_numbers' ? 'list' : 'text'
    });
  };

  return (
    <div className="review-screen-new" dir="rtl">
      <div className="header">
        <h1>בדיקת נתונים - אצווה {batchId}</h1>
        <div className="header-actions">
          {/* View Mode Toggle */}
          <div className="view-mode-toggle">
            <button
              className={`toggle-btn ${viewMode === 'cards' ? 'active' : ''}`}
              onClick={() => setViewMode('cards')}
              disabled={!batchData.forms || batchData.forms.length === 0}
              aria-label="תצוגת טפסים"
            >
              📋 תצוגת טפסים
            </button>
            <button
              className={`toggle-btn ${viewMode === 'table' ? 'active' : ''}`}
              onClick={() => setViewMode('table')}
              aria-label="תצוגת טבלאות"
            >
              📊 תצוגת טבלאות
            </button>
          </div>
          
          {onBack && <button onClick={onBack} className="back-btn">חזרה</button>}
          {exportEligibility && (
            <button
              className={`export-btn ${!exportEligibility.can_export || (batchData.statistics?.unresolved_relationships ?? 0) > 0 ? 'export-btn-blocked' : ''}`}
              onClick={handleExport}
              disabled={!exportEligibility.can_export || (batchData.statistics?.unresolved_relationships ?? 0) > 0}
              title={!exportEligibility.can_export || (batchData.statistics?.unresolved_relationships ?? 0) > 0 ? 'ייצוא חסום עד לפתרון הבעיות' : 'ייצא לאקסל'}
            >
              {exportEligibility.can_export && (batchData.statistics?.unresolved_relationships ?? 0) === 0
                ? 'ייצא ל-Excel' 
                : `ייצא ל-Excel (${exportEligibility.blockers.length + (batchData.statistics?.unresolved_relationships ?? 0)} חוסמים)`}
            </button>
          )}
        </div>
      </div>

      {/* Render based on view mode */}
      {viewMode === 'cards' ? renderCardsView() : (
        <>
          {/* Orphaned Commitments Section */}
          {classified.orphanedCommitments && classified.orphanedCommitments.length > 0 && (
            <div className="orphaned-commitments-section">
              <h2 className="warning-header">⚠️ התחייבויות לא משוייכות ({classified.orphanedCommitments.length})</h2>
              <div className="orphaned-list">
                {classified.orphanedCommitments.map((commitment) => (
                  <div key={commitment.commitment_record_id} className="orphaned-item">
                    <span className="warning-icon">⚠️</span>
                    <span className="commitment-value">
                      {commitment.commitment_number?.reviewed_value || 
                       commitment.commitment_number?.normalized_value || 
                       commitment.commitment_number?.raw_value || 
                       'לא זוהה'}
                    </span>
                    <span className="orphaned-message">לא משוייכת לבדיקה</span>
                    <button
                      className="assign-btn"
                      onClick={() => setAssignModal({ isOpen: true, commitment })}
                    >
                      שייך לבדיקה
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {renderTable(
            '✅ טפסים שחולצו בהצלחה',
            classified.table1_success,
            searchTable1,
            setSearchTable1,
            pageTable1,
            setPageTable1,
            false
          )}

          {renderTable(
            '⚠️ טפסים עם הערות לבדיקה',
            classified.table2_warnings,
            searchTable2,
            setSearchTable2,
            pageTable2,
            setPageTable2,
            true
          )}

          {renderTable(
            '❌ טפסים הדורשים השלמה ידנית',
            classified.table3_missing,
            searchTable3,
            setSearchTable3,
            pageTable3,
            setPageTable3,
            true
          )}
        </>
      )}

      {editModal && editModal.isOpen && (
        <EditFieldModal
          isOpen={editModal.isOpen}
          fieldName={editModal.fieldName}
          fieldLabel={getFieldLabel(editModal.fieldName)}
          currentValue={editModal.currentValue}
          fieldType={editModal.fieldType}
          onSave={(newValue) => handleEditField(editModal.testId, editModal.fieldName, newValue)}
          onClose={() => setEditModal(null)}
        />
      )}

      {assignModal && assignModal.isOpen && batchData && (
        <AssignCommitmentModal
          isOpen={assignModal.isOpen}
          commitment={assignModal.commitment}
          testRecords={batchData.test_records}
          onAssign={(testId) => handleAssignCommitment(assignModal.commitment.commitment_record_id, testId)}
          onClose={() => setAssignModal(null)}
        />
      )}

      {resolveModal && resolveModal.isOpen && (
        <ResolveRelationshipModal
          isOpen={resolveModal.isOpen}
          commitment={resolveModal.commitment}
          availableCentralNumbers={
            (resolveModal.testRecord.central_numbers?.reviewed_value ||
             resolveModal.testRecord.central_numbers?.normalized_value ||
             resolveModal.testRecord.central_numbers?.raw_value ||
             []) as string[]
          }
          onResolve={(newRefs, newStatus) => 
            handleResolveRelationship(
              resolveModal.commitment.commitment_record_id,
              resolveModal.testRecord.test_id,
              newRefs,
              newStatus
            )
          }
          onClose={() => setResolveModal(null)}
        />
      )}

      {documentModal && documentModal.isOpen && (
        <DocumentViewerModal
          isOpen={documentModal.isOpen}
          batchId={batchId}
          documentId={documentModal.documentId}
          pageIndex={documentModal.pageIndex}
          onClose={() => setDocumentModal(null)}
        />
      )}

      {relationshipEditorModal && relationshipEditorModal.isOpen && batchData && (
        <RelationshipEditor
          isOpen={relationshipEditorModal.isOpen}
          commitment={relationshipEditorModal.commitment}
          samples={batchData.samples || []}
          onResolve={handleResolveRelationshipFromEditor}
          onDisconnect={handleDisconnectRelationship}
          onClose={() => setRelationshipEditorModal(null)}
        />
      )}
    </div>
  );
};

// Export as ReviewScreen for compatibility with WorkflowScreen import
export { ReviewScreenNew as ReviewScreen };
