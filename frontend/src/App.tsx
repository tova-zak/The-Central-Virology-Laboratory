import { useState, useEffect } from 'react'
import './App.css'
import { healthCheck, HealthResponse } from './services/api'
import { WorkflowScreen } from './features/workflow/WorkflowScreen'
import { ErrorBoundary } from './components/ErrorBoundary'
import { getHealthStatusLabel } from './utils/hebrewMessages'

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
        setError('לא ניתן להתחבר לשרת.')
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
            <img className="tzalul-logo" src="/logo.png" alt="" />
            <div className="tzalul-header-text">
              <h1 className="tzalul-header-title">המעבדה המרכזית לנגיפים</h1>
              <p className="tzalul-header-subtitle">סביבת בדיקת נתונים · צלול</p>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="app-main">
          {loading && (
            <div className="status-box loading-box">
              <p>בודק חיבור לשרת…</p>
            </div>
          )}
          
          {error && (
            <div className="status-box error-box">
              <strong>⚠ שגיאת חיבור:</strong> {error}
              <p className="hint">בדקו שהשרת פועל ורעננו את הדף.</p>
            </div>
          )}
          
          {health && (
            <>
              <div className="status-box success-box">
                <div className="status-content">
                  <h3><span aria-hidden="true">✓</span> המערכת פעילה</h3>
                  <div className="status-details">
                    <span><strong>שירות:</strong> <bdi dir="ltr">{health.service}</bdi></span>
                    <span><strong>גרסה:</strong> <bdi dir="ltr">{health.version}</bdi></span>
                    <span><strong>מודל בינה מלאכותית:</strong> <bdi dir="ltr">{health.model}</bdi></span>
                    <span><strong>מצב השרת:</strong> {getHealthStatusLabel(health.status)}</span>
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
