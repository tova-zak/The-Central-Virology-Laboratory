/**
 * Complete Workflow Screen
 * 
 * Manages the full flow: Upload → Process → Review → Export
 * Integration Package 1: End-to-end workflow with async processing and polling
 * 
 * State Persistence: Uses URL params and localStorage to restore batch after refresh
 */
import React, { useState, useEffect, useRef } from 'react';
import { UploadForm } from '../upload/UploadForm';
import { ReviewScreenNew } from '../review/ReviewScreenNew';
import { processBatch, getBatchStatus, retryFailedPages } from '../../services/api';
import type { BatchStatusResponse, ProcessingProgress } from '../../services/api';
import { decidePoll, POLL_INTERVAL_MS } from './pollingPolicy';
import { getErrorMessage, localizeProcessingMessage } from '../../utils/hebrewMessages';
import './WorkflowScreen.css';
import './WorkflowStages.css';

type WorkflowStage = 'upload' | 'processing' | 'review';

const STORAGE_KEY = 'virology_lab_active_batch';

export const WorkflowScreen: React.FC = () => {
  const [stage, setStage] = useState<WorkflowStage>('upload');
  const [currentBatchId, setCurrentBatchId] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProcessingProgress | null>(null);
  const pollRef = useRef<number | null>(null);
  const [pollingInterval, setPollingInterval] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore batch on mount
  useEffect(() => {
    restoreBatchState();
  }, []);

  // Save batch ID when it changes
  useEffect(() => {
    if (currentBatchId) {
      localStorage.setItem(STORAGE_KEY, currentBatchId);
      // Update URL without reload
      const url = new URL(window.location.href);
      url.searchParams.set('batch', currentBatchId);
      window.history.replaceState({}, '', url.toString());
    }
  }, [currentBatchId]);

  const restoreBatchState = async () => {
    try {
      // Try URL first, then localStorage
      const urlParams = new URLSearchParams(window.location.search);
      let batchId = urlParams.get('batch');
      
      if (!batchId) {
        batchId = localStorage.getItem(STORAGE_KEY);
      }
      
      if (batchId) {
        console.log('Restoring batch:', batchId);
        
        // Try to load batch from backend
        const batchStatus = await getBatchStatus(batchId);
        
        setCurrentBatchId(batchId);
        
        // Determine stage based on batch status
        if (batchStatus.status === 'completed' || batchStatus.status === 'completed_with_errors') {
          setStage('review');
        } else if (batchStatus.status === 'processing' || batchStatus.status === 'queued') {
          setStage('processing');
          setProcessing(true);
          if (batchStatus.progress) {
            setProgress(batchStatus.progress);
          }
          // Resume polling
          startPolling(batchId);
        } else if (batchStatus.status === 'failed') {
          setStage('review'); // Show errors in review
          setProcessingError('העיבוד נכשל. פרטי השגיאות מוצגים במסך הבדיקה.');
        } else if (batchStatus.status === 'quota_exhausted') {
          setStage('review');
          setProcessingError('מכסת השימוש בשירות Gemini מוצתה. בדקו את שגיאות החילוץ ונסו שוב מאוחר יותר.');
        } else {
          // uploaded but not processed yet
          setStage('upload');
        }
      }
    } catch (err: any) {
      console.error('Failed to restore batch:', err);
      // Batch not found or error - start fresh
      if (err.response?.status === 404) {
        // Clear invalid batch ID
        localStorage.removeItem(STORAGE_KEY);
        const url = new URL(window.location.href);
        url.searchParams.delete('batch');
        window.history.replaceState({}, '', url.toString());
      }
    } finally {
      setLoading(false);
    }
  };

  const startPolling = (batchId: string) => {
    // Never run two pollers for the same screen.
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
    }
    const startedAt = Date.now();
    let consecutiveErrors = 0;
    let inFlight = false;

    const stop = () => {
      window.clearInterval(interval);
      pollRef.current = null;
      setPollingInterval(null);
      setProcessing(false);
    };

    const interval = window.setInterval(async () => {
      if (inFlight) {
        return; // previous request still running; do not stack requests
      }
      inFlight = true;
      let snapshot: BatchStatusResponse | null = null;
      try {
        snapshot = await getBatchStatus(batchId);
        consecutiveErrors = 0;
        if (snapshot.progress) {
          setProgress(snapshot.progress);
        }
      } catch (err) {
        consecutiveErrors += 1;
        console.error('Polling error:', err);
      } finally {
        inFlight = false;
      }

      // Every poll ends in: keep waiting, show results, or show a clear error (never poll forever).
      const decision = decidePoll(snapshot, { startedAt, now: Date.now(), consecutiveErrors });
      if (decision.action === 'review') {
        stop();
        // Move to review after short delay
        setTimeout(() => {
          setStage('review');
        }, 500);
      } else if (decision.action === 'fail') {
        stop();
        console.warn('Processing stopped:', decision.message);
        setProcessingError(localizeProcessingMessage(decision.message, 'העיבוד לא הושלם. נסו שוב או העלו את המסמכים מחדש.'));
        if (decision.goToReview) {
          // The review screen lists the persisted extraction errors per page.
          setStage('review');
        }
      }
    }, POLL_INTERVAL_MS);

    pollRef.current = interval;
    setPollingInterval(interval);
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);

  const handleUploadSuccess = (batchId: string) => {
    setCurrentBatchId(batchId);
    // Don't auto-process, let user trigger it
  };

  const handleStartProcessing = async () => {
    if (!currentBatchId) return;

    setProcessing(true);
    setProcessingError(null);
    setStage('processing');
    setProgress({ current: 0, total: 0, current_file: null });

    try {
      // Start processing (returns 202 immediately)
      await processBatch(currentBatchId);
      
      // Start polling
      startPolling(currentBatchId);
      
    } catch (err: any) {
      console.error('Processing failed to start:', err);
      setProcessingError(getErrorMessage(err, 'startProcessing'));
      setProcessing(false);
    }
  };

  const handleRetryFailed = async () => {
    if (!currentBatchId) return;
    try {
      await retryFailedPages(currentBatchId);
    } catch (err: any) {
      console.error('Retry could not be started:', err);
      window.alert(getErrorMessage(err, 'retryFailed'));
      return;
    }
    setProcessing(true);
    setProcessingError(null);
    setStage('processing');
    setProgress({ current: 0, total: 0, current_file: null });
    startPolling(currentBatchId);
  };

  const handleBackToUpload = () => {
    // Stop polling if active
    if (pollingInterval) {
      clearInterval(pollingInterval);
      setPollingInterval(null);
    }
    
    setStage('upload');
    setCurrentBatchId(null);
    setProcessingError(null);
    setProcessing(false);
    setProgress(null);
    
    // Clear storage
    localStorage.removeItem(STORAGE_KEY);
    const url = new URL(window.location.href);
    url.searchParams.delete('batch');
    window.history.replaceState({}, '', url.toString());
  };

  const handleNewBatch = () => {
    handleBackToUpload();
  };

  // Show loading spinner while restoring state
  if (loading) {
    return (
      <div className="workflow-screen loading-state">
        <img className="loading-gif" src="/loading.gif" alt="" />
        <p role="status">טוען את מצב העבודה הקודם…</p>
      </div>
    );
  }

  return (
    <div className="workflow-screen">
      {/* Stage Indicator */}
      <div className="stage-indicator">
        <div className={`stage-item ${stage === 'upload' ? 'active' : stage === 'processing' || stage === 'review' ? 'completed' : ''}`}>
          <span className="stage-number">1</span>
          <span className="stage-label">העלאה</span>
        </div>
        <div className="stage-connector"></div>
        <div className={`stage-item ${stage === 'processing' ? 'active' : stage === 'review' ? 'completed' : ''}`}>
          <span className="stage-number">2</span>
          <span className="stage-label">עיבוד</span>
        </div>
        <div className="stage-connector"></div>
        <div className={`stage-item ${stage === 'review' ? 'active' : ''}`}>
          <span className="stage-number">3</span>
          <span className="stage-label">בדיקה וייצוא</span>
        </div>
      </div>

      {/* Upload Stage */}
      {stage === 'upload' && (
        <div className="stage-content">
          <h2>העלאת מסמכים</h2>
          <UploadForm onUploadSuccess={handleUploadSuccess} />
          
          {currentBatchId && (
            <div className="post-upload-actions">
              <div className="batch-info-box">
                <p><strong>נוצרה קבוצת מסמכים:</strong> <bdi dir="ltr">{currentBatchId}</bdi></p>
                <p className="hint">הקבצים הועלו. לחצו על „התחלת עיבוד” כדי להתחיל בחילוץ הנתונים.</p>
              </div>
              <button 
                className="button-primary button-large"
                onClick={handleStartProcessing}
                disabled={processing}
              >
                {processing ? 'העיבוד מתבצע…' : 'התחלת עיבוד'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Processing Stage */}
      {stage === 'processing' && (
        <div className="stage-content">
          <h2>עיבוד המסמכים</h2>
          <div className="processing-indicator">
            <img className="loading-gif" src="/loading.gif" alt="" />
            <p role="status">העיבוד מתבצע: הנתונים מחולצים מהמסמכים בעזרת בינה מלאכותית (Gemini).</p>
            
            {progress && progress.total > 0 && (
              <div className="progress-details">
                <p className="progress-text">
                  מעבד קובץ <bdi dir="ltr">{progress.current}</bdi> מתוך <bdi dir="ltr">{progress.total}</bdi>
                </p>
                {progress.current_file && (
                  <p className="current-file"><bdi dir="ltr">{progress.current_file}</bdi></p>
                )}
                {!!progress.page_total && (
                  <p className="progress-text">
                    עמוד <bdi dir="ltr">{progress.page_current ?? 0}</bdi> מתוך <bdi dir="ltr">{progress.page_total}</bdi>
                    {!!progress.pages_failed && <> – <bdi dir="ltr">{progress.pages_failed}</bdi> נכשלו{progress.last_error_code ? <> (<bdi dir="ltr">{progress.last_error_code}</bdi>)</> : null}</>}
                  </p>
                )}
                <div className="progress-bar">
                  <div 
                    className="progress-fill" 
                    style={{ width: `${(progress.current / progress.total) * 100}%` }}
                  ></div>
                </div>
              </div>
            )}
            
            <p className="hint">העיבוד נמשך ברקע בשרת. אם תסגרו את הדף, בחזרה אליו באותו דפדפן יוצג המצב העדכני של קבוצת המסמכים.</p>
          </div>
          
          {processingError && (
            <div className="error-box">
              <h3>העיבוד לא הושלם</h3>
              <p>{processingError}</p>
              <button onClick={handleBackToUpload}>חזרה להעלאת מסמכים</button>
            </div>
          )}
        </div>
      )}

      {/* Review Stage */}
      {stage === 'review' && currentBatchId && (
        <div className="stage-content">
          <div className="review-header-actions">
            <button 
              className="button-secondary"
              onClick={handleNewBatch}
              title="התחלת קבוצת מסמכים חדשה"
            >
              <span aria-hidden="true">📤</span> קבוצת מסמכים חדשה
            </button>
          </div>
          <ReviewScreenNew 
            batchId={currentBatchId} 
            onBack={handleBackToUpload}
            onRetryFailed={handleRetryFailed}
          />
        </div>
      )}
    </div>
  );
};
