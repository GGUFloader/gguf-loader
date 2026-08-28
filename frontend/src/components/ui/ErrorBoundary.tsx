import { Component, type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="h-full flex flex-col items-center justify-center p-8 text-center">
          <AlertTriangle size={48} className="text-yellow-400 mb-4" />
          <h2 className="text-lg font-semibold text-text mb-2">Something went wrong</h2>
          <p className="text-sm text-text-muted mb-1 max-w-md">
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <p className="text-xs text-text-muted mb-4">
            The error has been logged. You can try reloading this section.
          </p>
          <button
            onClick={this.handleRetry}
            className="flex items-center gap-2 px-4 py-2 bg-accent text-onAccent rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            <RefreshCw size={14} />
            Try Again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
