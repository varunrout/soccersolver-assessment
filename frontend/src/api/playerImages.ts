const imageApiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export type PlayerImageResponse = {
  player_id: string
  image_url: string | null
}

export async function getPlayerImage(playerId: string, signal?: AbortSignal): Promise<PlayerImageResponse> {
  const trimmedId = playerId.trim()
  if (!trimmedId) {
    return { player_id: '', image_url: null }
  }

  const response = await fetch(
    new URL(`/players/${encodeURIComponent(trimmedId)}/image`, imageApiBaseUrl),
    { headers: { Accept: 'application/json' }, signal },
  )
  if (!response.ok) {
    return { player_id: trimmedId, image_url: null }
  }
  return response.json() as Promise<PlayerImageResponse>
}