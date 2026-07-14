interface ConnectionBadgeProps {
  connected: boolean
  label?: string
}

export function ConnectionBadge({ connected, label }: ConnectionBadgeProps) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className={`w-2 h-2 rounded-full ${
          connected ? 'bg-green-500' : 'bg-red-500'
        }`}
      />
      <span className="text-sm text-muted-foreground">
        {label || (connected ? 'Connected' : 'Disconnected')}
      </span>
    </span>
  )
}
