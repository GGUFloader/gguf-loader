import { AppLayout } from './components/layout/AppLayout'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import { ToastContainer } from './components/ui/Toast'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import './index.css'

function AppInner() {
  useKeyboardShortcuts()
  return <AppLayout />
}

function App() {
  return (
    <ErrorBoundary
      fallback={
        <div className="h-screen w-screen flex items-center justify-center bg-bg">
          <div className="text-center">
            <div className="text-6xl mb-4">🦜</div>
            <h1 className="text-xl font-semibold text-text mb-2">GGUF Loader</h1>
            <p className="text-text-muted text-sm">Application failed to load</p>
          </div>
        </div>
      }
    >
      <AppInner />
      <ToastContainer />
    </ErrorBoundary>
  )
}

export default App
