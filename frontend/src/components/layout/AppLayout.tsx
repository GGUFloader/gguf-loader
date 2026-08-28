import { Header } from './Header'
import { LeftPanel } from './LeftPanel'
import { RightPanel } from './RightPanel'
import { ChatPanel } from '../chat/ChatPanel'
import { useUIStore } from '../../stores/uiStore'

export function AppLayout() {
  const { leftPanelOpen, rightPanelOpen } = useUIStore()

  return (
    <div className="h-screen flex flex-col bg-bg">
      <Header />
      <div className="flex-1 flex overflow-hidden">
        {leftPanelOpen && <LeftPanel />}
        <div className="flex-1 min-w-0">
          <ChatPanel />
        </div>
        {rightPanelOpen && <RightPanel />}
      </div>
    </div>
  )
}
