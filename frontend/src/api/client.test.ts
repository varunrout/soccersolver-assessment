import { afterEach, describe, expect, it, vi } from 'vitest'
import { getPlayerProfile } from './client'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('getPlayerProfile', () => {
  it('trims and URL-encodes the player ID', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ player_id: 'abc 123', percentiles: null }),
    } as Response)

    await getPlayerProfile(' abc 123 ')

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/players/abc%20123',
      expect.objectContaining({ signal: undefined }),
    )
  })
})
