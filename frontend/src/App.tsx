import { useState, useEffect, type FormEvent } from 'react'
import './App.css'
import { healthCheck, HealthResponse, apiClient } from './services/api'
import { WorkflowScreen } from './features/workflow/WorkflowScreen'
import { ErrorBoundary } from './components/ErrorBoundary'

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
      setLoginError('Sign-in failed. Check credentials and connection.')
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

              {health.demo_mode && <p role="status">DEMO MODE — synthetic extraction only. Upload synthetic documents only.</p>}
              {health.requires_auth && !authenticated ? (
                <form onSubmit={signIn}>
                  <label>Username <input autoComplete="username" value={username}
                    onChange={event => setUsername(event.target.value)} required /></label>
                  <label>Password <input type="password" autoComplete="current-password" value={password}
                    onChange={event => setPassword(event.target.value)} required /></label>
                  <button type="submit" disabled={signingIn}>{signingIn ? 'Signing in...' : 'Sign in'}</button>
                  {loginError && <p role="alert">{loginError}</p>}
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
