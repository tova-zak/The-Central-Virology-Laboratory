/**
 * Error Boundary Component
 * 
 * Catches JavaScript errors anywhere in the component tree
 * and displays a fallback UI instead of crashing the whole app.
 */
import { Component, ErrorInfo, ReactNode } from 'react';
import './ErrorBoundary.css';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(_error: Error): Partial<State> {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Error Boundary caught error:', error, errorInfo);
    this.setState({
      error,
      errorInfo
    });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    });
    // Reload the page to reset state
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-content">
            <h1><span aria-hidden="true">😕</span> משהו השתבש</h1>
            <p className="error-message">
              אירעה שגיאה לא צפויה באפליקציה.
            </p>
            
            {this.state.error && (
              <details className="error-details">
                <summary>פרטי השגיאה (לצורכי תמיכה)</summary>
                <pre className="error-stack" dir="ltr">
                  <strong>שגיאה:</strong> {this.state.error.toString()}
                  {this.state.errorInfo && (
                    <>
                      <br /><br />
                      <strong>מיקום ברכיבים:</strong>
                      {this.state.errorInfo.componentStack}
                    </>
                  )}
                </pre>
              </details>
            )}

            <div className="error-actions">
              <button 
                className="button-primary"
                onClick={this.handleReset}
              >
                <span aria-hidden="true">🔄</span> טעינה מחדש של האפליקציה
              </button>
              <button 
                className="button-secondary"
                onClick={() => window.history.back()}
              >
                <span aria-hidden="true">→</span> חזרה לדף הקודם
              </button>
            </div>

            <p className="error-hint">
              אם הבעיה נמשכת, פנו לתמיכה וציינו מה עשיתם לפני שהופיעה השגיאה.
            </p>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
