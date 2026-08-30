import { Component, type ReactNode, type ErrorInfo } from 'react'
import { RefreshCw, Copy, Send, AlertTriangle, ChevronDown, ChevronRight, Cpu } from 'lucide-react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  showDetails: boolean
  reportSent: boolean
  systemInfo: Record<string, string>
}

function getSystemInfo(): Record<string, string> {
  return {
    'User Agent': navigator.userAgent.slice(0, 100),
    'Platform': navigator.platform,
    'Language': navigator.language,
    'Screen': `${screen.width}x${screen.height}`,
    'Viewport': `${window.innerWidth}x${window.innerHeight}`,
    'Device Memory': `${(navigator as any).deviceMemory || '?'} GB`,
    'Cores': `${navigator.hardwareConcurrency || '?'}`,
    'Online': String(navigator.onLine),
    'Cookie Enabled': String(navigator.cookieEnabled),
  }
}

export class CrashReporter extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
      reportSent: false,
      systemInfo: {},
    }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({
      error,
      errorInfo,
      systemInfo: getSystemInfo(),
    })

    // Log to console for development
    console.error('[CrashReporter]', error, errorInfo)

    // Auto-report to backend if available
    this.sendReport(error, errorInfo)
  }

  async sendReport(error: Error, errorInfo: ErrorInfo) {
    try {
      const report = {
        message: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        system: getSystemInfo(),
        timestamp: new Date().toISOString(),
        url: window.location.href,
      }

      // Try to send to backend crash endpoint
      await fetch('/api/crash-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(report),
      }).catch(() => {}) // silently fail if endpoint doesn't exist

      this.setState({ reportSent: true })
    } catch {}
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  handleCopyReport = () => {
    const { error, errorInfo, systemInfo } = this.state
    const report = [
      '## Crash Report',
      `**Error:** ${error?.message}`,
      `**Stack:**\n${error?.stack}`,
      `**Component Stack:**\n${errorInfo?.componentStack}`,
      '',
      '## System Info',
      ...Object.entries(systemInfo).map(([k, v]) => `- ${k}: ${v}`),
      '',
      `**Time:** ${new Date().toISOString()}`,
      `**URL:** ${window.location.href}`,
    ].join('\n')

    navigator.clipboard.writeText(report).catch(() => {})
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      const { error, errorInfo, showDetails, reportSent, systemInfo } = this.state

      return (
        <div className="min-h-screen flex items-center justify-center bg-bg p-4">
          <div className="w-full max-w-lg bg-surface border border-border rounded-xl shadow-2xl overflow-hidden">
            {/* Header */}
            <div className="px-6 py-5 bg-red-500/5 border-b border-red-500/20">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-red-500/10 rounded-lg">
                  <AlertTriangle size={20} className="text-red-400" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold text-text">Something went wrong</h2>
                  <p className="text-[11px] text-text-muted mt-0.5">The application encountered an unexpected error</p>
                </div>
              </div>
            </div>

            {/* Error message */}
            <div className="px-6 py-4">
              <div className="bg-bg border border-border rounded-lg px-4 py-3">
                <div className="text-xs text-red-400 font-mono">{error?.message || 'Unknown error'}</div>
              </div>

              {/* Report status */}
              {reportSent && (
                <div className="mt-2 text-[10px] text-green-400 flex items-center gap-1">
                  <Send size={10} /> Crash report sent automatically
                </div>
              )}

              {/* Details toggle */}
              <button
                onClick={() => this.setState({ showDetails: !showDetails })}
                className="mt-3 flex items-center gap-1.5 text-[11px] text-text-muted hover:text-text transition-colors"
              >
                {showDetails ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                Technical details
              </button>

              {showDetails && (
                <div className="mt-2 space-y-2">
                  {/* Stack trace */}
                  <div className="bg-bg border border-border rounded-lg overflow-hidden">
                    <div className="px-3 py-1.5 bg-elevated text-[9px] text-text-muted uppercase">Stack Trace</div>
                    <pre className="px-3 py-2 text-[10px] text-text-sec font-mono overflow-x-auto max-h-40 overflow-y-auto whitespace-pre-wrap">
                      {error?.stack || 'No stack trace available'}
                    </pre>
                  </div>

                  {/* Component stack */}
                  {errorInfo?.componentStack && (
                    <div className="bg-bg border border-border rounded-lg overflow-hidden">
                      <div className="px-3 py-1.5 bg-elevated text-[9px] text-text-muted uppercase">Component Stack</div>
                      <pre className="px-3 py-2 text-[10px] text-text-sec font-mono overflow-x-auto max-h-32 overflow-y-auto whitespace-pre-wrap">
                        {errorInfo.componentStack}
                      </pre>
                    </div>
                  )}

                  {/* System info */}
                  <div className="bg-bg border border-border rounded-lg overflow-hidden">
                    <div className="px-3 py-1.5 bg-elevated text-[9px] text-text-muted uppercase flex items-center gap-1">
                      <Cpu size={9} /> System Info
                    </div>
                    <div className="px-3 py-2 space-y-0.5">
                      {Object.entries(systemInfo).map(([k, v]) => (
                        <div key={k} className="flex gap-2 text-[9px]">
                          <span className="text-text-muted w-24 flex-shrink-0">{k}</span>
                          <span className="text-text-sec font-mono truncate">{v}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="px-6 py-4 border-t border-border flex gap-2">
              <button
                onClick={this.handleRetry}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 bg-accent text-onAccent rounded-lg text-xs font-medium hover:bg-accent-hover transition-colors"
              >
                <RefreshCw size={13} /> Try Again
              </button>
              <button
                onClick={this.handleCopyReport}
                className="flex items-center justify-center gap-1.5 px-3 py-2 bg-elevated border border-border rounded-lg text-xs text-text-sec hover:border-accent/30 transition-colors"
              >
                <Copy size={12} /> Copy Report
              </button>
              <button
                onClick={() => window.location.reload()}
                className="flex items-center justify-center gap-1.5 px-3 py-2 bg-elevated border border-border rounded-lg text-xs text-text-sec hover:border-accent/30 transition-colors"
              >
                Reload
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
