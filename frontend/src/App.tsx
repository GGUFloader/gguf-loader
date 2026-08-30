import { AppLayout } from './components/layout/AppLayout'
import { CrashReporter } from './components/ui/CrashReporter'
import { ToastContainer } from './components/ui/Toast'
import './index.css'

function App() {
  return (
    <CrashReporter>
      <AppLayout />
      <ToastContainer />
    </CrashReporter>
  )
}

export default App
