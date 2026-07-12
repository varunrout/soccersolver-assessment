import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, comparePlayers, getPlayerProfile, sendChatMessage } from './client'

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

describe('comparePlayers', () => {
  it('builds the correct request with encoded IDs and forwards abort signal', async () => {
    const signal = new AbortController().signal
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ metrics: [] }),
    } as Response)

    await comparePlayers(' player/a ', ' player b ', signal)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/players/compare?player_a_id=player%2Fa&player_b_id=player+b',
      expect.objectContaining({ signal }),
    )
  })

  it('throws ApiError for non-OK responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ detail: 'One or both players not found' }),
    } as Response)

    await expect(comparePlayers('a', 'b')).rejects.toBeInstanceOf(ApiError)
  })
})

describe('sendChatMessage', () => {
  it('POSTs a valid trimmed message to /chat as JSON and forwards abort signal', async () => {
    const signal = new AbortController().signal
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ response: { type: 'text', message: 'ok', is_error: false } }),
    } as Response)

    await sendChatMessage('  Compare Mohamed Salah and Harry Kane  ', signal)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/chat',
      expect.objectContaining({
        method: 'POST',
        signal,
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ message: 'Compare Mohamed Salah and Harry Kane' }),
      }),
    )
  })

  it('rejects blank messages without fetching', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')

    await expect(sendChatMessage('   ')).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('throws ApiError for non-OK chat responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: 'raw backend details' }),
    } as Response)

    await expect(sendChatMessage('Who is best?')).rejects.toBeInstanceOf(ApiError)
  })
})
