/**
 * ReviewScreen - Three-Table Redesign
 * 
 * Displays extracted records in three tables based on classification:
 * - Table 1: טפסים ללא התראות (no warnings - read-only)
 * - Table 2: טפסים עם הערות לבדיקה (warnings - only problematic fields editable)
 * - Table 3: טפסים הדורשים השלמה ידנית (missing - only missing fields editable)
 */
import React, { useState, useEffect } from 'react';
import './ReviewScreen.css';
import './ReviewScreenExtras.css';
import { 
  getBatchStatus, 
  updateField,
  rejectFieldCandidate,
  checkExportEligibility,
  BatchStatusResponse,
  TestRecord,
  CommitmentRecord
} from '../../services/api';
import { classifyTestRecords, ClassifiedRecords } from './utils/classification';
import { isFieldEditable, getFieldDisplayValue, getFieldVisualState, getFieldLabel } from './utils/editPermissions';
import { getCommitmentNumbersForTest } from './utils/relationships';
import { EditFieldModal } from './EditFieldModal';
import { AssignCommitmentModal } from './AssignCommitmentModal';
import { ResolveRelationshipModal } from './ResolveRelationshipModal';
import { DocumentViewerModal } from './DocumentViewerModal';
import { CommitmentReviewTable } from './CommitmentReviewTable';
import { validateEditedValue } from './utils/evidence';
import {
  getErrorMessage,
  formatExportBlocker,
  getRecordStatusLabel,
  getExtractionErrorMessage,
  formatRetryAfter
} from '../../utils/hebrewMessages';

interface ReviewScreenProps {
  batchId: string;
  onBack?: () => void;
  onRetryFailed?: () => void;
}

type FieldName = 'patient_first_name' | 'patient_last_name' | 'patient_id_number' | 
                 'sender' | 'received_date' | 'central_numbers';

export const ReviewScreenNew: React.FC<ReviewScreenProps> = ({ batchId, onBack, onRetryFailed }) => {
  const [batchData, setBatchData] = useState<BatchStatusResponse | null>(null);
  const [classified, setClassified] = useState<ClassifiedRecords | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exportEligibility, setExportEligibility] = useState<{
    can_export: boolean;
    blockers: string[];
  } | null>(null);
  
  // Search/filter state (independent per table)
  const [searchTable1, setSearchTable1] = useState('');
  const [searchTable2, setSearchTable2] = useState('');
  const [searchTable3, setSearchTable3] = useState('');
  
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
    helperText?: string;
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
    testRecord: Pick<TestRecord, 'test_id' | 'central_numbers'>;
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
      // Note: Backend now returns only commitment_records (one per page)
      // test_records is deprecated but classifyTestRecords expects it
      const classifiedRecords = classifyTestRecords(
        data.test_records || [],  // Fallback to empty array if not present
        data.commitment_records || [],
        data.status
      );
      setClassified(classifiedRecords);
      
      // Check export eligibility
      if (data.status === 'completed' || data.status === 'completed_with_errors') {
        const eligibility = await checkExportEligibility(batchId);
        setExportEligibility(eligibility);
      }
      
    } catch (err: any) {
      console.error('Failed to load batch data:', err);
      setError(getErrorMessage(err, 'loadBatch'));
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
      console.error('Failed to update field:', err);
      alert(`שמירת התיקון נכשלה: ${getErrorMessage(err, 'updateField')}`);
    }
  };

  const handleRejectCandidate = async (recordId: string, fieldName: string, value: string) => {
    try {
      await rejectFieldCandidate(batchId, recordId, fieldName, value);
      await loadBatchData();
    } catch (err: any) {
      console.error('Failed to reject candidate:', err);
      alert(`דחיית המועמד נכשלה: ${getErrorMessage(err, 'rejectCandidate')}`);
    }
  };

  const handleAssignCommitment = async (commitmentId: string, testId: string) => {
    try {
      const { assignCommitmentToTest } = await import('../../services/api');
      await assignCommitmentToTest(batchId, commitmentId, testId);
      setAssignModal(null);
      await loadBatchData(); // Reload to show updated classification
    } catch (err: any) {
      console.error('Failed to assign commitment:', err);
      alert(`שיוך ההתחייבות לא הצליח: ${getErrorMessage(err, 'assign')}`);
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
      console.error('Failed to resolve relationship:', err);
      alert(`אישור הקשר לא הצליח: ${getErrorMessage(err, 'resolve')}`);
    }
  };

  const handleConfirmRecord = async (record: CommitmentRecord) => {
    try {
      const { approveRecordReview } = await import('../../services/api');
      await approveRecordReview(batchId, record.commitment_record_id);
      await loadBatchData();
    } catch (err: any) {
      console.error('Failed to confirm record review:', err);
      alert(`אישור הרשומה נכשל: ${getErrorMessage(err, 'updateField')}`);
    }
  };

  const handleExport = async () => {
    // Check blockers first - include both legacy and new statistics
    const hasUnresolvedRelationships = batchData?.statistics?.unresolved_relationships ?? 0;
    
    if (!exportEligibility?.can_export || hasUnresolvedRelationships > 0) {
      const blockers = exportEligibility?.blockers || [];
      if (hasUnresolvedRelationships > 0) {
        blockers.push(`${hasUnresolvedRelationships} קשרים שטרם נפתרו`);
      }
      const blockerLines = blockers.map(b => '• ' + (b.endsWith('שטרם נפתרו') ? b : formatExportBlocker(b)));
      alert(`לא ניתן להוריד קובץ אקסל כרגע. יש ${blockers.length} פריטים שחוסמים את ההורדה:\n${blockerLines.join('\n')}`);
      return;
    }

    try {
      const { exportBatch } = await import('../../services/api');
      
      // Show loading state
      const originalText = 'הורדת קובץ אקסל';
      const button = document.querySelector('.export-btn') as HTMLButtonElement;
      if (button) button.textContent = 'מוריד…';
      
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
      
      alert('הקובץ ירד למחשב.');
    } catch (err: any) {
      alert(`הורדת הקובץ נכשלה. ${getErrorMessage(err, 'export')}`);
      console.error('Export error:', err);
    }
  };

  if (loading) return <div className="review-screen loading" role="status">טוען את נתוני קבוצת המסמכים…</div>;
  if (error) return <div className="review-screen error" role="alert">לא ניתן היה לטעון את הנתונים: {error}</div>;
  if (!batchData || !classified) return null;

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
            placeholder="חיפוש לפי שם, מספר זהות או מזהה טופס…"
            aria-label={`חיפוש בטבלה: ${title}`}
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="search-input"
          />
        </div>

<div className="table-wrapper">
        <table className="review-table" dir="rtl">
          <thead>
            <tr>
              <th>מס׳</th>
              <th>שם פרטי</th>
              <th>שם משפחה</th>
              <th>מספר זהות</th>
              <th>מספרים מרכזיים</th>
              <th>תאריך קבלה</th>
              <th>גורם שולח</th>
              <th>מספרי התחייבות</th>
              <th>הערות</th>
              <th>מצב הטופס</th>
              {showViewColumn && <th>צפייה במסמך</th>}
            </tr>
          </thead>
          <tbody>
            {paginated.map((record, idx) => renderRow(record, (page - 1) * PAGE_SIZE + idx + 1, showViewColumn))}
          </tbody>
        </table>
        </div>

        {totalPages > 1 && (
          <div className="pagination">
            <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} aria-label="העמוד הקודם">הקודם</button>
            <span>עמוד <bdi dir="ltr">{page}</bdi> מתוך <bdi dir="ltr">{totalPages}</bdi></span>
            <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages} aria-label="העמוד הבא">הבא</button>
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
                <bdi dir="auto">{item.value}</bdi>
                {isAmbiguous && (
                  <button
                    className="resolve-btn-inline"
                    onClick={() => setResolveModal({ 
                      isOpen: true, 
                      commitment: commitment!,
                      testRecord: record
                    })}
                    title="אישור או ניתוק קשר שאינו ברור"
                    aria-label="אישור או ניתוק קשר שאינו ברור"
                  >
                    🔗
                  </button>
                )}
                {item.editable && (
                  <button
                    className="edit-btn-inline"
                    onClick={() => openEditModal(record.test_id, 'commitment_number', item.value)}
                    title="עריכת מספר התחייבות"
                    aria-label="עריכת מספר התחייבות"
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
        <td className={`status-cell status-${recordStatus}`}>{getRecordStatusLabel(recordStatus)}</td>
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
              <span aria-hidden="true">👁️</span> צפייה במסמך
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
<bdi dir="auto">{valueDisplay}</bdi>
        {editable && (
          <button
            className="edit-btn-inline"
            onClick={() => openEditModal(record.test_id, fieldName, displayValue)}
            title={`עריכת השדה: ${getFieldLabel(fieldName)}`}
            aria-label={`עריכת השדה: ${getFieldLabel(fieldName)}`}
          >
            ✏️
          </button>
        )}
        {visualState.icon && (
          <span
            className="icon"
            role="img"
            aria-label={visualState.message}
            title={visualState.message}
          >
            {visualState.icon === 'error' ? '❌' : '⚠️'}
          </span>
        )}
      </td>
    );
  };

  const openEditModal = (testId: string, fieldName: string, currentValue: any, helperText?: string) => {
    setEditModal({
      isOpen: true,
      testId,
      fieldName,
      currentValue,
      fieldType: fieldName === 'central_numbers' ? 'list' : 'text',
      helperText
    });
  };

  return (
    <div className="review-screen-new" dir="rtl">
      <div className="header">
        <h1>בדיקת נתונים – קבוצת מסמכים <bdi dir="ltr">{batchId}</bdi></h1>
        <div className="header-actions">
          {onBack && <button onClick={onBack} className="back-btn">חזרה להעלאת מסמכים</button>}
          {exportEligibility && (
            <button
              className={`export-btn ${!exportEligibility.can_export || (batchData.statistics?.unresolved_relationships ?? 0) > 0 ? 'export-btn-blocked' : ''}`}
              onClick={handleExport}
              disabled={!exportEligibility.can_export || (batchData.statistics?.unresolved_relationships ?? 0) > 0}
              title={!exportEligibility.can_export || (batchData.statistics?.unresolved_relationships ?? 0) > 0 ? 'ההורדה חסומה: יש לטפל בפריטים החוסמים לפני ההורדה' : 'הפעולה מורידה את הנתונים לקובץ אקסל במחשב'}
            >
              {exportEligibility.can_export && (batchData.statistics?.unresolved_relationships ?? 0) === 0
                ? 'הורדת קובץ אקסל' 
                : `הורדת קובץ אקסל (${exportEligibility.blockers.length + (batchData.statistics?.unresolved_relationships ?? 0)} חסימות)`}
            </button>
          )}
        </div>
      </div>

      {!!batchData.errors?.length && (
        <section className="error-box extraction-errors" role="alert">
          <h2>שגיאות בחילוץ הנתונים</h2>
          <p>החילוץ לא הושלם. עמודים שנכשלו דורשים בדיקה ידנית. יש לבדוק את כל השדות הנדרשים לפני הורדת קובץ אקסל.</p>
          {onRetryFailed && (
            <button onClick={onRetryFailed} className="retry-failed-btn">
              ניסיון חוזר לעמודים שנכשלו או דולגו (עמודים שכבר חולצו או תוקנו נשמרים)
            </button>
          )}
          <ul>{batchData.errors.map((failure, index) => (
            <li key={index} className="extraction-error-item">
              {failure.error_code && <><bdi dir="ltr" className="extraction-error-code">{failure.error_code}</bdi>: </>}
              {getExtractionErrorMessage(failure)}
              {failure.page_index !== undefined && <> (עמוד <bdi dir="ltr">{failure.page_index + 1}</bdi>)</>}
              {failure.retry_after_seconds != null && <>. {formatRetryAfter(failure.retry_after_seconds)}</>}
            </li>
          ))}</ul>
        </section>
      )}
      <p className="hint review-guidance">
        בדקו מול המסמך המקורי את השדות המסומנים כחסרים, לא תקינים או הדורשים בדיקה. סיום העיבוד אינו מהווה אישור אנושי של הנתונים.
      </p>
      {exportEligibility && (
        (exportEligibility.can_export && (batchData.statistics?.unresolved_relationships ?? 0) === 0) ? (
          <p className="hint review-guidance">
            הכפתור „הורדת קובץ אקסל” מוריד את הנתונים לקובץ אקסל במחשב.
          </p>
        ) : (
          <div className="hint review-guidance review-guidance-blocked">
            <p>הורדת קובץ אקסל חסומה. מה שעדיין מונע את ההורדה:</p>
            <ul>
              {exportEligibility.blockers.map((b, i) => (
                <li key={i}>{formatExportBlocker(b)}</li>
              ))}
              {(batchData.statistics?.unresolved_relationships ?? 0) > 0 && (
                <li><bdi dir="ltr">{batchData.statistics?.unresolved_relationships}</bdi> קשרים שטרם נפתרו</li>
              )}
            </ul>
          </div>
        )
      )}

      {/* Review tables */}
      {batchData.commitment_records?.length > 0 && !batchData.test_records?.length ? (
        <CommitmentReviewTable
          records={batchData.commitment_records}
          onEdit={(recordId, fieldName, value, helperText) =>
            openEditModal(recordId, fieldName, value, helperText)}
          onRejectCandidate={handleRejectCandidate}
          onConfirmReview={handleConfirmRecord}
          onResolveRelationship={record => setResolveModal({isOpen:true, commitment:record,
            testRecord:{test_id:record.commitment_record_id, central_numbers:record.central_numbers!}})}
          onViewSource={record => {
            const source = record.form_id?.match(/^(.+)_page_(\d+)$/);
            if (source) setDocumentModal({ isOpen: true, documentId: source[1], pageIndex: Number(source[2]) });
          }}
        />
      ) : (
        <>
          {/* Orphaned Commitments Section */}
          {classified.orphanedCommitments && classified.orphanedCommitments.length > 0 && (
            <div className="orphaned-commitments-section">
              <h2 className="warning-header"><span aria-hidden="true">⚠️</span> התחייבויות שלא שויכו לטופס (<bdi dir="ltr">{classified.orphanedCommitments.length}</bdi>)</h2>
              <div className="orphaned-list">
                {classified.orphanedCommitments.map((commitment) => (
                  <div key={commitment.commitment_record_id} className="orphaned-item">
                    <span className="warning-icon" aria-hidden="true">⚠️</span>
                    <span className="commitment-value" dir="auto">
                      {commitment.commitment_number?.reviewed_value || 
                       commitment.commitment_number?.normalized_value || 
                       commitment.commitment_number?.raw_value || 
                       'לא זוהה'}
                    </span>
                    <span className="orphaned-message">לא שויכה לטופס</span>
                    <button
                      className="assign-btn"
                      onClick={() => setAssignModal({ isOpen: true, commitment })}
                    >
                      שיוך לטופס
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {renderTable(
            '✅ טפסים ללא התראות',
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
          helperText={editModal.helperText}
          validate={(value) => validateEditedValue(editModal.fieldName, value)}
          onSave={(newValue) => handleEditField(editModal.testId, editModal.fieldName, newValue)}
          onClose={() => setEditModal(null)}
        />
      )}

      {assignModal && assignModal.isOpen && batchData && (
        <AssignCommitmentModal
          isOpen={assignModal.isOpen}
          commitment={assignModal.commitment}
          testRecords={batchData.test_records || []}
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

    </div>
  );
};

// Export as ReviewScreen for compatibility with WorkflowScreen import
export { ReviewScreenNew as ReviewScreen };
