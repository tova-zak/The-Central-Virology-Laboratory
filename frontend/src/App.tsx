import { useState, useEffect } from 'react'
import './App.css'
import { healthCheck, HealthResponse } from './services/api'
import { UploadForm } from './features/upload/UploadForm'

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastBatchId, setLastBatchId] = useState<string | null>(null)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await healthCheck()
        setHealth(data)
        setError(null)
      } catch (err) {
        setError('שגיאה בחיבור ל-Backend')
        console.error('Health check failed:', err)
      } finally {
        setLoading(false)
      }
    }

    checkHealth()
  }, [])

  const handleUploadSuccess = (batchId: string) => {
    setLastBatchId(batchId)
  }

  return (
    <div className="app">
      <h1>מערכת חילוץ התחייבויות - המעבדה המרכזית לנגיפים</h1>
      
      {loading && <p>בודק חיבור...</p>}
      
      {error && (
        <div style={{ color: 'red', padding: '1rem', border: '1px solid red', borderRadius: '4px' }}>
          <strong>שגיאה:</strong> {error}
        </div>
      )}
      
      {health && (
        <div style={{ 
          padding: '1rem', 
          border: '1px solid green', 
          borderRadius: '4px',
          backgroundColor: '#f0fff0',
          marginBottom: '2rem'
        }}>
          <h2>✅ המערכת פעילה</h2>
          <ul style={{ textAlign: 'right', listStyle: 'none' }}>
            <li><strong>שירות:</strong> {health.service}</li>
            <li><strong>גרסה:</strong> {health.version}</li>
            <li><strong>מודל AI:</strong> {health.model}</li>
            <li><strong>סטטוס:</strong> {health.status}</li>
          </ul>
        </div>
      )}

      {health && !loading && (
        <>
          <h2>העלאת קבצים</h2>
          <UploadForm onUploadSuccess={handleUploadSuccess} />
          
          {lastBatchId && (
            <div style={{ 
              marginTop: '2rem',
              padding: '1rem',
              border: '1px solid #2196F3',
              borderRadius: '4px',
              backgroundColor: '#e3f2fd'
            }}>
              <p><strong>Batch ID האחרון:</strong> {lastBatchId}</p>
              <p style={{ fontSize: '0.9em', color: '#666' }}>
                (עיבוד יתווסף ב-TASK-013)
              </p>
            </div>
          )}
        </>
      )}
      
      <p style={{ marginTop: '2rem', color: '#666' }}>
        מערכת MVP בשלבי פיתוח - Hackathon 2026
      </p>
    </div>
  )
}

export default App
