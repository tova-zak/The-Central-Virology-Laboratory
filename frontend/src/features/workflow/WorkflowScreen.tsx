/**
 * Complete Workflow Screen
 * 
 * Manages the full flow: Upload → Process → Review → Export
 * Integration Package 1: End-to-end workflow with async processing and polling
 * 
 * State Persistence: Uses URL params and localStorage to restore batch after refresh
 */
import React, { useState, useEffect } from 'react';
import { UploadForm } from '../upload/UploadForm';
import { ReviewScreenNew } from '../review/ReviewScreenNew';
import { processBatch, getBatchStatus } from '../../services/api';
import './WorkflowScreen.css';

type WorkflowStage = 'upload' | 'processing' | 'review';

const STORAGE_KEY = 'virology_lab_active_batch';

export const WorkflowScreen: React.FC = () => {
  const [stage, setStage] = useState<WorkflowStage>('upload');
  const [currentBatchId, setCurrentBatchId] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ current: number; total: number; current_file: string | null } | null>(null);
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
          setProcessingError('Processing failed. Check details below.');
        } else if (batchStatus.status === 'quota_exhausted') {
          setStage('review');
          setProcessingError('Gemini quota exhausted. Check extraction errors and provider cooldown.');
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
    const interval = window.setInterval(async () => {
      try {
        const status = await getBatchStatus(batchId);
        
        // Update progress
        if (status.progress) {
          setProgress(status.progress);
        }
        
        // Check if completed
        if (status.status === 'completed' || status.status === 'completed_with_errors') {
          clearInterval(interval);
          setPollingInterval(null);
          setProcessing(false);
          
          // Move to review after short delay
          setTimeout(() => {
            setStage('review');
          }, 500);
        } else if (status.status === 'failed') {
          clearInterval(interval);
          setPollingInterval(null);
          setProcessing(false);
          setProcessingError('Processing failed. Check errors in review screen.');
          
          // Still allow review to see errors
          setTimeout(() => {
            setStage('review');
          }, 2000);
        } else if (status.status === 'quota_exhausted') {
          clearInterval(interval);
          setPollingInterval(null);
          setProcessing(false);
          setProcessingError('Gemini quota exhausted. Check extraction errors and provider cooldown.');
          setStage('review');
        }
      } catch (err) {
        console.error('Polling error:', err);
        // Continue polling - might be transient error
      }
    }, 2500);
    
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
      setProcessingError(err.response?.data?.detail || 'Failed to start processing');
      setProcessing(false);
    }
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
        <div className="spinner"></div>
        <p>טוען מצב קודם...</p>
      </div>
    );
  }

  return (
    <div className="workflow-screen">
      {/* Stage Indicator */}
      <div className="stage-indicator">
        <div className={`stage-item ${stage === 'upload' ? 'active' : stage === 'processing' || stage === 'review' ? 'completed' : ''}`}>
          <span className="stage-number">1</span>
          <span className="stage-label">Upload</span>
        </div>
        <div className="stage-connector"></div>
        <div className={`stage-item ${stage === 'processing' ? 'active' : stage === 'review' ? 'completed' : ''}`}>
          <span className="stage-number">2</span>
          <span className="stage-label">Process</span>
        </div>
        <div className="stage-connector"></div>
        <div className={`stage-item ${stage === 'review' ? 'active' : ''}`}>
          <span className="stage-number">3</span>
          <span className="stage-label">Review & Export</span>
        </div>
      </div>

      {/* Upload Stage */}
      {stage === 'upload' && (
        <div className="stage-content">
          <h2>Upload Documents</h2>
          <UploadForm onUploadSuccess={handleUploadSuccess} />
          
          {currentBatchId && (
            <div className="post-upload-actions">
              <div className="batch-info-box">
                <p><strong>Batch Created:</strong> {currentBatchId}</p>
                <p className="hint">Files are uploaded. Click "Start Processing" to extract data.</p>
              </div>
              <button 
                className="button-primary button-large"
                onClick={handleStartProcessing}
                disabled={processing}
              >
                {processing ? 'Processing...' : 'Start Processing with AI'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Processing Stage */}
      {stage === 'processing' && (
        <div className="stage-content">
          <h2>Processing Documents</h2>
          <div className="processing-indicator">
            <div className="spinner"></div>
            <p>Extracting data with Gemini AI...</p>
            
            {progress && progress.total > 0 && (
              <div className="progress-details">
                <p className="progress-text">
                  Processing file {progress.current} of {progress.total}
                </p>
                {progress.current_file && (
                  <p className="current-file">{progress.current_file}</p>
                )}
                <div className="progress-bar">
                  <div 
                    className="progress-fill" 
                    style={{ width: `${(progress.current / progress.total) * 100}%` }}
                  ></div>
                </div>
              </div>
            )}
            
            <p className="hint">This process runs in the background. You can safely close this tab and return later.</p>
          </div>
          
          {processingError && (
            <div className="error-box">
              <h3>Processing Error</h3>
              <p>{processingError}</p>
              <button onClick={handleBackToUpload}>Back to Upload</button>
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
              title="התחל אצווה חדשה"
            >
              📤 אצווה חדשה
            </button>
          </div>
          <ReviewScreenNew 
            batchId={currentBatchId} 
            onBack={handleBackToUpload}
          />
        </div>
      )}
    </div>
  );
};
