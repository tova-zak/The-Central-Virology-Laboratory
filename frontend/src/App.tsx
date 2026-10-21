import { useState, useEffect, type FormEvent } from 'react'
import './App.css'
import { healthCheck, HealthResponse, apiClient } from './services/api'
import { WorkflowScreen } from './features/workflow/WorkflowScreen'
import { ErrorBoundary } from './components/ErrorBoundary'
import { getHealthStatusLabel, AUTH_TEXT } from './utils/hebrewMessages'

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [authenticated, setAuthenticated] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [signingIn, setSigningIn] = useState(false)

  useEffect(() => {
    const requireSignIn = () => setAuthenticated(false)
    window.addEventListener('api-auth-required', requireSignIn)
    return () => window.removeEventListener('api-auth-required', requireSignIn)
  }, [])

  const signIn = async (event: FormEvent) => {
    event.preventDefault()
    setSigningIn(true)
    apiClient.defaults.auth = { username, password }
    try {
      await apiClient.get('/api/session')
      setAuthenticated(true)
      setPassword('')
      setLoginError('')
    } catch {
      delete apiClient.defaults.auth
      setLoginError(AUTH_TEXT.failed)
    } finally {
      setSigningIn(false)
    }
  }

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
              <p role="status">בודק חיבור לשרת…</p>
            </div>
          )}
          
          {error && (
            <div className="status-box error-box" role="alert">
              <strong><span aria-hidden="true">⚠</span> שגיאת חיבור:</strong> {error}
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

              {health.demo_mode && <p role="status" className="env-banner env-banner-demo">{AUTH_TEXT.demoBanner}</p>}
              {health.environment === 'staging-real' && <p role="status" className="env-banner env-banner-staging">
                {AUTH_TEXT.stagingBanner}
              </p>}
              {health.requires_auth && !authenticated ? (
                <form onSubmit={signIn} className="auth-form">
                  <label className="auth-field">{AUTH_TEXT.username} <input dir="ltr" autoComplete="username" value={username}
                    onChange={event => setUsername(event.target.value)} required /></label>
                  <label className="auth-field">{AUTH_TEXT.password} <input dir="ltr" type="password" autoComplete="current-password" value={password}
                    onChange={event => setPassword(event.target.value)} required /></label>
                  <button type="submit" className="auth-submit" disabled={signingIn}>{signingIn ? AUTH_TEXT.submitting : AUTH_TEXT.submit}</button>
                  {loginError && <p role="alert" className="auth-error">{loginError}</p>}
                </form>
              ) : <WorkflowScreen />}
            </>
          )}
        </main>
      </div>
    </ErrorBoundary>
  )
}

export default App
