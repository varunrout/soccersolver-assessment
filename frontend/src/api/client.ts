import type { PlayerSummary } from '../types/player'

export const baseURL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type ErrorPayload = {
  detail?: unknown
  message?: unknown
}

function buildUrl(path: string, params?: Record<string, string>) {
  const url = new URL(path, baseURL)

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.set(key, value)
    })
  }

  return url.toString()
}

function extractSafeError(payload: ErrorPayload | null) {
  const detail = payload?.detail ?? payload?.message

  if (typeof detail === 'string' && detail.length <= 160) {
    return detail
  }

  return 'Request failed'
}

async function requestJson<T>(path: string, options: RequestInit = {}, params?: Record<string, string>): Promise<T> {
  const response = await fetch(buildUrl(path, params), {
    ...options,
    headers: {
      Accept: 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    let payload: ErrorPayload | null = null

    try {
      payload = await response.json()
    } catch {
      payload = null
    }

    throw new Error(extractSafeError(payload))
  }

  return response.json() as Promise<T>
}

export async function searchPlayers(query: string, signal?: AbortSignal): Promise<PlayerSummary[]> {
  const trimmedQuery = query.trim()

  if (!trimmedQuery) {
    return []
  }

  return requestJson<PlayerSummary[]>('/players/search', { signal }, { q: trimmedQuery })
}
