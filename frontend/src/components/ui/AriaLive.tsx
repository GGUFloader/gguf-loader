/**
 * ARIA live regions for screen reader announcements.
 * Mount once at the root level.
 */
export function AriaLive() {
  return (
    <>
      {/* Polite announcements (won't interrupt current speech) */}
      <div
        id="aria-live-polite"
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      />
      {/* Assertive announcements (interrupt current speech) */}
      <div
        id="aria-live-assertive"
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
      />
      {/* Hidden skip links */}
      <div className="sr-only">
        <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-accent focus:text-onAccent focus:px-4 focus:py-2 focus:rounded-lg">
          Skip to main content
        </a>
        <a href="#chat-input" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-40 focus:z-50 focus:bg-accent focus:text-onAccent focus:px-4 focus:py-2 focus:rounded-lg">
          Skip to chat input
        </a>
      </div>
    </>
  )
}
