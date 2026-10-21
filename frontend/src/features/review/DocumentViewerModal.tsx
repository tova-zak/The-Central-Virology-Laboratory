/**
 * DocumentViewerModal Component
 * 
 * Modal for viewing PDF/image documents inline without leaving the review screen.
 * Supports PDF documents and image files with proper blob handling.
 */
import React, { useState, useEffect } from 'react';
import { isCancel } from 'axios';
import { apiClient } from '../../services/api';
import './ReviewScreen.css';

// Get API base URL from environment
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface DocumentViewerModalProps {
  isOpen: boolean;
  batchId: string;
  documentId: string;
  pageIndex?: number;
  onClose: () => void;
}

export const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({
  isOpen,
  batchId,
  documentId,
  pageIndex = 0,
  onClose
}) => {
  const [zoom, setZoom] = useState(100);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [contentType, setContentType] = useState<string>('');

  // Load document as blob. Each run owns its AbortController and its blob URL,
  // so cleanup (close / document change / unmount / StrictMode re-run) cancels
  // the in-flight request and revokes exactly the URL this run created.
  useEffect(() => {
    if (!isOpen) return;

    const controller = new AbortController();
    let objectUrl: string | null = null;

    setIsLoading(true);
    setError(null);
    setBlobUrl(null);
    setContentType('');

    const loadDocument = async () => {
      try {
        const url = `${API_BASE_URL}/api/batches/${batchId}/documents/${documentId}`;
        const response = await apiClient.get(url, {
          responseType: 'blob',
          timeout: 30000,
          signal: controller.signal,
        });

        // Cancelled/outdated request: do not create a URL or touch state
        if (controller.signal.aborted) return;

        // Create object URL from blob
        objectUrl = URL.createObjectURL(response.data);
        setBlobUrl(objectUrl);

        // Get content type from response headers
        const ct = response.headers['content-type'];
        setContentType(typeof ct === 'string' ? ct : 'application/octet-stream');
        setIsLoading(false);
      } catch (err: any) {
        // Expected cancellation (close, document change, unmount): ignore silently
        if (
          controller.signal.aborted ||
          isCancel(err) ||
          err?.code === 'ERR_CANCELED' ||
          err?.name === 'AbortError' ||
          err?.name === 'CanceledError'
        ) {
          return;
        }
        // Log only non-sensitive fields (never err.config, which may hold auth)
        console.error('Failed to load document:', err?.code, err?.message);
        if (err?.response?.status === 404) {
          setError('המסמך לא נמצא.');
        } else if (!err?.response) {
          setError('לא ניתן לטעון את המסמך. בדוק את החיבור לשרת ונסה שוב.');
        } else {
          setError('לא ניתן היה לטעון את המסמך. נסו שוב מאוחר יותר.');
        }
        setIsLoading(false);
      }
    };

    loadDocument();

    return () => {
      controller.abort();
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
    };
  }, [isOpen, batchId, documentId]);

  // Reset zoom when modal opens
  useEffect(() => {
    if (isOpen) {
      setZoom(100);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleZoomIn = () => setZoom(prev => Math.min(200, prev + 25));
  const handleZoomOut = () => setZoom(prev => Math.max(50, prev - 25));
  const handleZoomReset = () => setZoom(100);

  const isImage = contentType.startsWith('image/');
  const isPDF = contentType === 'application/pdf';

  return (
    <div className="modal-overlay document-viewer-modal" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>צפייה במסמך <bdi dir="ltr">{documentId}</bdi></h3>
          <button className="modal-close-btn" onClick={onClose} aria-label="סגירה">×</button>
        </div>

        <div className="document-viewer-controls">
          <div>
            <button onClick={handleZoomOut} disabled={zoom <= 50 || isLoading || !!error} aria-label="הקטנה" title="הקטנה">-</button>
            <span style={{ margin: '0 1rem', fontWeight: 600 }}><bdi dir="ltr">{zoom}%</bdi></span>
            <button onClick={handleZoomIn} disabled={zoom >= 200 || isLoading || !!error} aria-label="הגדלה" title="הגדלה">+</button>
            <button onClick={handleZoomReset} style={{ marginRight: '1rem' }} disabled={isLoading || !!error}>איפוס זום</button>
          </div>
          <div style={{ color: '#666', fontSize: '0.9rem' }}>
            {isPDF && <>עמוד <bdi dir="ltr">{pageIndex + 1}</bdi></>}
            {isImage && 'תמונה'}
          </div>
        </div>

        <div className="document-viewer-body">
          {isLoading && (
            <div style={{ 
              padding: '3rem', 
              textAlign: 'center',
              color: '#666'
            }}>
              <div className="spinner" style={{
                border: '4px solid #f3f3f3',
                borderTop: '4px solid #3498db',
                borderRadius: '50%',
                width: '40px',
                height: '40px',
                animation: 'spin 1s linear infinite',
                margin: '0 auto 1rem'
              }}></div>
              <p>טוען את המסמך…</p>
            </div>
          )}
          
          {error && (
            <div style={{ 
              padding: '2rem', 
              textAlign: 'center', 
              color: '#F44336',
              background: '#ffebee',
              borderRadius: '4px',
              margin: '1rem'
            }}>
              <p><strong>טעינת המסמך נכשלה</strong></p>
              <p>{error}</p>
            </div>
          )}
          
          {!isLoading && !error && blobUrl && isImage && (
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              padding: '1rem',
              overflow: 'auto',
              maxHeight: '70vh'
            }}>
              <img
                src={blobUrl}
                alt={`מסמך ${documentId}`}
                style={{
                  maxWidth: '100%',
                  height: 'auto',
                  transform: `scale(${zoom / 100})`,
                  transformOrigin: 'center center',
                  transition: 'transform 0.2s ease'
                }}
              />
            </div>
          )}
          
          {!isLoading && !error && blobUrl && isPDF && (
            <iframe
              src={`${blobUrl}#page=${pageIndex + 1}`}
              style={{
                width: '100%',
                height: '70vh',
                minHeight: '600px',
                border: '1px solid #ddd',
                transform: `scale(${zoom / 100})`,
                transformOrigin: 'top center'
              }}
              title={`מסמך ${documentId}`}
            />
          )}
          
          {!isLoading && !error && blobUrl && !isImage && !isPDF && (
            <div style={{ 
              padding: '2rem', 
              textAlign: 'center',
              color: '#FF9800',
              background: '#fff3e0',
              borderRadius: '4px',
              margin: '1rem'
            }}>
              <p><strong>לא ניתן להציג סוג קובץ זה</strong></p>
              <p>סוג הקובץ: <bdi dir="ltr">{contentType}</bdi></p>
            </div>
          )}
        </div>
      </div>
      
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
