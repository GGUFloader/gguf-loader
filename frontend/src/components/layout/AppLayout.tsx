import { Header } from './Header'
import { LeftPanel } from './LeftPanel'
import { RightPanel } from './RightPanel'
import { MobileNav } from './MobileNav'
import { ChatPanel } from '../chat/ChatPanel'
import { CommandPalette } from '../ui/CommandPalette'
import { VersionBanner } from '../ui/VersionBanner'
import { CompatibilityDialog } from '../model/CompatibilityDialog'
import { AriaLive } from '../ui/AriaLive'
import { OfflineIndicator } from '../ui/OfflineIndicator'
import { UpdatePanel } from '../ui/UpdatePanel'
import { NotificationPanel } from '../ui/NotificationPanel'
import { useUIStore } from '../../stores/uiStore'
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'
import { useAccessibilityShortcuts } from '../../hooks/useAccessibility'
import { useResponsive } from '../../hooks/useResponsive'
import { initTheme } from '../../stores/themeStore'

// Initialize theme on module load
initTheme()

export function AppLayout() {
  const { leftPanelOpen, rightPanelOpen } = useUIStore()
  const { isMobile } = useResponsive()

  // Register and listen for keyboard shortcuts
  useKeyboardShortcuts()
  useAccessibilityShortcuts()

  return (
    <div className="h-screen flex flex-col bg-bg">
      <AriaLive />
      <Header />
      <VersionBanner />
      <div className="flex-1 flex overflow-hidden" id="main-content" role="main">
        {/* Left panel: hidden on mobile, visible on tablet+ */}
        {leftPanelOpen && !isMobile && <LeftPanel />}
        <div className="flex-1 min-w-0">
          <ChatPanel />
        </div>
        {/* Right panel: hidden on mobile, overlay on tablet, side on desktop */}
        {rightPanelOpen && !isMobile && <RightPanel />}
      </div>
      {/* Mobile bottom navigation */}
      <MobileNav />
      <CommandPalette />
      <CompatibilityDialog />
      <OfflineIndicator />
      <NotificationPanel />
      <UpdatePanel />
    </div>
  )
}
