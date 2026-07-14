interface ErrorBannerProps {
  message: string | null
  onRetry?: () => void
}

export function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  if (!message) return null

  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 flex items-center justify-between">
      <div className="flex items-center gap-2 text-sm text-destructive-foreground">
        <span>⚠</span>
        <span>{message}</span>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-xs px-2.5 py-1 rounded-md bg-accent text-accent-foreground hover:bg-accent/80 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  )
}
