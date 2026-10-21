/**
 * File upload form component
 */
import { useState } from 'react'
import { uploadFiles } from '../../services/api'
import { getErrorMessage } from '../../utils/hebrewMessages'
import './UploadForm.css'
import './UploadFormExtras.css'

export interface UploadFormProps {
  onUploadSuccess?: (batchId: string) => void
}

export function UploadForm({ onUploadSuccess }: UploadFormProps) {
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedFiles(event.target.files)
    setError(null)
    setSuccess(null)
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()

    if (!selectedFiles || selectedFiles.length === 0) {
      setError('לא נבחרו קבצים. בחרו לפחות קובץ אחד.')
      return
    }

    setUploading(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await uploadFiles(selectedFiles)
      const pageCount = response.documents.reduce((sum, doc) => sum + (doc.page_count ?? 1), 0)
      // \u2066...\u2069 isolates the ID as left-to-right inside the Hebrew sentence
      setSuccess(`הועלו ${response.documents.length} קבצים בהצלחה, ${pageCount} עמודים. נוצרה קבוצת מסמכים: \u2066${response.batch_id}\u2069`)
      setSelectedFiles(null)
      
      if (onUploadSuccess) {
        onUploadSuccess(response.batch_id)
      }
      
      // Clear file input
      const fileInput = document.getElementById('file-input') as HTMLInputElement
      if (fileInput) {
        fileInput.value = ''
      }
    } catch (err: any) {
      console.error('Upload failed:', err)
      setError(getErrorMessage(err, 'upload'))
    } finally {
      setUploading(false)
    }
  }

  const fileCount = selectedFiles ? selectedFiles.length : 0
  const fileList = selectedFiles ? Array.from(selectedFiles).map(f => f.name).join(', ') : ''

  return (
    <form onSubmit={handleSubmit} className="upload-form">
      <div className="form-group">
        <label htmlFor="file-input">בחירת מסמכים להעלאה (PDF, PNG, JPEG). אפשר לבחור כמה קבצים יחד:</label>
        <input
          id="file-input"
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          multiple
          onChange={handleFileChange}
          disabled={uploading}
        />
        {fileCount > 0 && (
          <p className="file-info">
            נבחרו {fileCount} קבצים: <bdi dir="ltr">{fileList}</bdi>
          </p>
        )}
        <p className="hint">לאחר ההעלאה תיווצר קבוצת מסמכים, ובשלב הבא תלחצו על „התחלת עיבוד”.</p>
      </div>

      <button type="submit" disabled={uploading || fileCount === 0}>
        {uploading ? 'מעלה…' : 'העלאת מסמכים'}
      </button>

      {error && (
        <div className="alert alert-error">
          <strong>ההעלאה נכשלה:</strong> {error}
        </div>
      )}

      {success && (
        <div className="alert alert-success">
          <strong aria-hidden="true">✓</strong> {success}
        </div>
      )}
    </form>
  )
}
