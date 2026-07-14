import type { ReactNode } from 'react'

interface PageShellProps {
  title: string
  description?: string
  children: ReactNode
}

export function PageShell({ title, description, children }: PageShellProps) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="text-sm text-muted-foreground mt-1">{description}</p>
        )}
      </div>
      {children}
    </div>
  )
}
