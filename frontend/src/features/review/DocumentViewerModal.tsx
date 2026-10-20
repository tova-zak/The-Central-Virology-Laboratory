/**
 * DocumentViewerModal Component
 * 
 * Modal for viewing PDF/image documents inline without leaving the review screen.
 * Supports PDF documents and image files with proper blob handling.
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';
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

  // Load document as blob
  useEffect(() => {
    if (!isOpen) return;

    setIsLoading(true);
    setError(null);
    setBlobUrl(null);
    setContentType('');

    const loadDocument = async () => {
      try {
        const url = `${API_BASE_URL}/api/batches/${batchId}/documents/${documentId}`;
        const response = await axios.get(url, {
          responseType: 'blob',
          timeout: 30000,
        });

        // Create object URL from blob
        const blob = response.data;
        const objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
        
        // Get content type from response headers
        const ct = response.headers['content-type'];
        setContentType(typeof ct === 'string' ? ct : 'application/octet-stream');
        setIsLoading(false);
      } catch (err: any) {
        console.error('Failed to load document:', err);
        setError(err.response?.status === 404 
          ? 'המסמך לא נמצא במערכת.'
          : 'שגיאה בטעינת המסמך. נסה שוב מאוחר יותר.');
        setIsLoading(false);
      }
    };

    loadDocument();

    // Cleanup: revoke object URL when modal closes or document changes
    return () => {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
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
          <h3>צפייה במסמך - {documentId}</h3>
          <button className="modal-close-btn" onClick={onClose}>×</button>
        </div>

        <div className="document-viewer-controls">
          <div>
            <button onClick={handleZoomOut} disabled={zoom <= 50 || isLoading || !!error}>-</button>
            <span style={{ margin: '0 1rem', fontWeight: 600 }}>{zoom}%</span>
            <button onClick={handleZoomIn} disabled={zoom >= 200 || isLoading || !!error}>+</button>
            <button onClick={handleZoomReset} style={{ marginRight: '1rem' }} disabled={isLoading || !!error}>איפוס</button>
          </div>
          <div style={{ color: '#666', fontSize: '0.9rem' }}>
            {isPDF && `עמוד ${pageIndex + 1}`}
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
              <p>טוען מסמך...</p>
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
              <p><strong>שגיאה בטעינת המסמך</strong></p>
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
              <p><strong>סוג קובץ לא נתמך להצגה</strong></p>
              <p>Content-Type: {contentType}</p>
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
