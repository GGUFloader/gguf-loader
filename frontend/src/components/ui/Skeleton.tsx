export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-elevated/60 rounded ${className}`} />
  )
}

export function MessageSkeleton() {
  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-elevated/60 animate-pulse flex-shrink-0" />
      <div className="flex-1 space-y-2 py-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-2/3" />
      </div>
    </div>
  )
}

export function FileTreeSkeleton() {
  return (
    <div className="space-y-1 px-2">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div key={i} className="flex items-center gap-2 px-2 py-1.5">
          <Skeleton className="w-3 h-3" />
          <Skeleton className="w-4 h-4" />
          <Skeleton className={`h-3 ${i % 2 === 0 ? 'w-24' : 'w-32'}`} />
        </div>
      ))}
    </div>
  )
}

export function SessionListSkeleton() {
  return (
    <div className="space-y-1 px-2">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="px-3 py-2.5 rounded-lg space-y-1.5">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      ))}
    </div>
  )
}

export function TerminalSkeleton() {
  return (
    <div className="space-y-1 p-3 font-mono text-xs">
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-2/3" />
      <Skeleton className="h-3 w-4/5" />
      <Skeleton className="h-3 w-1/3" />
    </div>
  )
}

export function GitPanelSkeleton() {
  return (
    <div className="space-y-2 p-3">
      <Skeleton className="h-4 w-32" />
      <div className="space-y-1 mt-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-center gap-2 py-1">
            <Skeleton className="w-3 h-3" />
            <Skeleton className={`h-3 ${i === 1 ? 'w-40' : 'w-28'}`} />
          </div>
        ))}
      </div>
    </div>
  )
}
