/** Fetch wrapper for API calls.

The frontend does NOT send an API key — browser requests to the same origin
do not require authentication. External API clients should provide
an ``X-API-Key`` header directly.
*/
const BASE = '/api/v1'

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json() as Promise<T>
}
