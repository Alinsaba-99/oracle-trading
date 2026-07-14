/** Number and date formatting utilities. */

function isValid(v: number): boolean {
  return Number.isFinite(v)
}

export function formatPrice(value: number): string {
  if (!isValid(value)) return '—'
  if (Math.abs(value) < 1) return `$${value.toFixed(6)}`
  if (Math.abs(value) >= 100) return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  return `$${value.toFixed(2)}`
}

export function formatPnl(value: number): string {
  if (!isValid(value)) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function formatPct(value: number): string {
  if (!isValid(value)) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${(value * 100).toFixed(1)}%`
}

export function formatRatio(value: number): string {
  if (!isValid(value)) return '—'
  return value.toFixed(2)
}

export function formatDate(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatTime(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

export function formatShortDateTime(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return `${d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })} ${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false })}`
}
