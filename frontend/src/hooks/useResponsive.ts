import { useState, useEffect } from 'react'

export type Breakpoint = 'mobile' | 'tablet' | 'desktop' | 'wide'

const BREAKPOINTS = {
  mobile: 0,
  tablet: 768,
  desktop: 1024,
  wide: 1440,
}

function getBreakpoint(width: number): Breakpoint {
  if (width >= BREAKPOINTS.wide) return 'wide'
  if (width >= BREAKPOINTS.desktop) return 'desktop'
  if (width >= BREAKPOINTS.tablet) return 'tablet'
  return 'mobile'
}

export function useResponsive() {
  const [breakpoint, setBreakpoint] = useState<Breakpoint>(() =>
    typeof window !== 'undefined' ? getBreakpoint(window.innerWidth) : 'desktop'
  )
  const [width, setWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1024)

  useEffect(() => {
    function handleResize() {
      const w = window.innerWidth
      setWidth(w)
      setBreakpoint(getBreakpoint(w))
    }

    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return {
    breakpoint,
    width,
    isMobile: breakpoint === 'mobile',
    isTablet: breakpoint === 'tablet',
    isDesktop: breakpoint === 'desktop' || breakpoint === 'wide',
    isWide: breakpoint === 'wide',
  }
}
