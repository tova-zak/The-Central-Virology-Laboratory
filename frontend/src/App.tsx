import { useState, useEffect } from 'react'
import './App.css'
import { healthCheck, HealthResponse } from './services/api'
import { WorkflowScreen } from './features/workflow/WorkflowScreen'
import { ErrorBoundary } from './components/ErrorBoundary'

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await healthCheck()
        setHealth(data)
        setError(null)
      } catch (err) {
        setError('Failed to connect to Backend')
        console.error('Health check failed:', err)
      } finally {
        setLoading(false)
      }
    }

    checkHealth()
  }, [])

  return (
    <ErrorBoundary>
      <div className="app">
        {/* Tzalul Header */}
        <header className="tzalul-header">
          <div className="tzalul-header-brand">
            <div className="tzalul-header-text">
              <h1 className="tzalul-header-title">המעבדה המרכזית לנגיפים</h1>
              <p className="tzalul-header-subtitle">סביבת בדיקת נתונים · צלול</p>
            </div>
            {/* Logo placeholder - will be added when logo file is provided */}
            <div className="tzalul-logo-placeholder" style={{
              width: '48px',
              height: '48px',
              background: 'var(--primary)',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              fontWeight: 'bold',
              fontSize: '24px'
            }}>
              צ
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="app-main">
          {loading && (
            <div className="status-box loading-box">
              <p>בודק חיבור למערכת...</p>
            </div>
          )}
          
          {error && (
            <div className="status-box error-box">
              <strong>⚠ שגיאת חיבור:</strong> {error}
              <p className="hint">ודא שהשרת פועל על פורט 8000</p>
            </div>
          )}
          
          {health && (
            <>
              <div className="status-box success-box">
                <div className="status-content">
                  <h3>✓ המערכת פעילה</h3>
                  <div className="status-details">
                    <span><strong>שירות:</strong> {health.service}</span>
                    <span><strong>גרסה:</strong> {health.version}</span>
                    <span><strong>מודל AI:</strong> {health.model}</span>
                    <span><strong>סטטוס:</strong> {health.status}</span>
                  </div>
                </div>
              </div>

              <WorkflowScreen />
            </>
          )}
        </main>
      </div>
    </ErrorBoundary>
  )
}

export default App
