import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { searchPlayers } from '../api/client'
import type { PlayerSummary } from '../types/player'
import SearchPage from './SearchPage'

vi.mock('../api/client', () => ({
  searchPlayers: vi.fn(),
}))

const mockedSearchPlayers = vi.mocked(searchPlayers)

const salah: PlayerSummary = {
  player_id: 'mohamed-salah',
  name: 'Mohamed Salah',
  position: 'FWD',
  club: 'Liverpool',
  league: 'Premier League',
  market_value_eur: 120_000_000,
}

const kane: PlayerSummary = {
  player_id: 'harry-kane',
  name: 'Harry Kane',
  position: 'FWD',
  club: 'Bayern Munich',
  league: 'Bundesliga',
  market_value_eur: 35_500_000,
}

function renderSearchPage() {
  return render(
    <MemoryRouter>
      <SearchPage />
    </MemoryRouter>,
  )
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })

  return { promise, resolve, reject }
}

async function advanceDebounce() {
  await act(async () => {
    vi.advanceTimersByTime(300)
  })
}

async function flushPromises() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

beforeEach(() => {
  vi.useFakeTimers()
  mockedSearchPlayers.mockReset()
  mockedSearchPlayers.mockResolvedValue([])
})

afterEach(() => {
  vi.clearAllTimers()
  vi.useRealTimers()
})

describe('SearchPage', () => {
  it('renders the initial state', () => {
    renderSearchPage()

    expect(screen.getByRole('heading', { name: /player search/i })).toBeTruthy()
    expect(screen.getByText(/search more than 2,400 players/i)).toBeTruthy()
    expect(screen.getByText('Mohamed Salah')).toBeTruthy()
  })

  it('keeps the input controlled', () => {
    renderSearchPage()

    const input = screen.getByLabelText(/search players/i) as HTMLInputElement
    fireEvent.change(input, { target: { value: 'Salah' } })

    expect(input.value).toBe('Salah')
  })

  it('does not call the API for blank or one-character input', async () => {
    renderSearchPage()

    const input = screen.getByLabelText(/search players/i)
    fireEvent.change(input, { target: { value: ' ' } })
    await advanceDebounce()
    fireEvent.change(input, { target: { value: 'S' } })
    await advanceDebounce()

    await flushPromises()
    expect(mockedSearchPlayers).not.toHaveBeenCalled()
  })

  it('calls search after debounce and shows loading', async () => {
    const pending = deferred<PlayerSummary[]>()
    mockedSearchPlayers.mockReturnValue(pending.promise)
    renderSearchPage()

    fireEvent.change(screen.getByLabelText(/search players/i), { target: { value: 'Salah' } })

    expect(mockedSearchPlayers).not.toHaveBeenCalled()
    await advanceDebounce()

    expect(mockedSearchPlayers).toHaveBeenCalledWith('Salah', expect.any(AbortSignal))
    expect(screen.getAllByText(/loading player result/i)).toHaveLength(3)

    await act(async () => {
      pending.resolve([salah])
    })
    expect(screen.getByText('Mohamed Salah')).toBeTruthy()
  })

  it('runs an immediate search when Enter submits the form', async () => {
    mockedSearchPlayers.mockResolvedValue([salah])
    renderSearchPage()

    const input = screen.getByLabelText(/search players/i)
    fireEvent.change(input, { target: { value: 'Salah' } })
    await act(async () => {
      fireEvent.submit(input.closest('form') as HTMLFormElement)
    })
    await flushPromises()

    expect(mockedSearchPlayers).toHaveBeenCalledWith('Salah', expect.any(AbortSignal))
    expect(screen.getByText('Mohamed Salah')).toBeTruthy()
  })

  it('renders result fields and plural result count', async () => {
    mockedSearchPlayers.mockResolvedValue([salah, kane])
    renderSearchPage()

    fireEvent.change(screen.getByLabelText(/search players/i), { target: { value: 'Salah' } })
    await advanceDebounce()
    await flushPromises()

    expect(screen.getAllByText('2 players found for "Salah"')).toHaveLength(2)
    expect(screen.getByText('Mohamed Salah')).toBeTruthy()
    expect(screen.getByText('Harry Kane')).toBeTruthy()
    expect(screen.getByText('Liverpool')).toBeTruthy()
    expect(screen.getByText('Bundesliga')).toBeTruthy()
  })

  it('renders singular result count', async () => {
    mockedSearchPlayers.mockResolvedValue([salah])
    renderSearchPage()

    fireEvent.change(screen.getByLabelText(/search players/i), { target: { value: 'Salah' } })
    await advanceDebounce()
    await flushPromises()

    expect(screen.getAllByText('1 player found for "Salah"')).toHaveLength(2)
  })

  it('renders empty state for completed searches without matches', async () => {
    mockedSearchPlayers.mockResolvedValue([])
    renderSearchPage()

    fireEvent.change(screen.getByLabelText(/search players/i), { target: { value: 'Nobody' } })
    await advanceDebounce()
    await flushPromises()

    expect(screen.getByText('No players found for "Nobody".')).toBeTruthy()
    expect(screen.getByText(/try checking the spelling/i)).toBeTruthy()
  })

  it('renders error state without raw exception text and retries', async () => {
    mockedSearchPlayers.mockRejectedValueOnce(new Error('Backend stack trace'))
    mockedSearchPlayers.mockResolvedValueOnce([salah])
    renderSearchPage()

    fireEvent.change(screen.getByLabelText(/search players/i), { target: { value: 'Salah' } })
    await advanceDebounce()
    await flushPromises()

    expect(screen.getByRole('alert').textContent).toContain(
      "We couldn't search for players right now. Please try again.",
    )
    expect(screen.queryByText('Backend stack trace')).toBeNull()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /retry/i }))
    })
    await flushPromises()

    expect(mockedSearchPlayers).toHaveBeenCalledTimes(2)
    expect(screen.getByText('Mohamed Salah')).toBeTruthy()
  })

  it('prevents stale requests from overwriting newer results', async () => {
    const first = deferred<PlayerSummary[]>()
    const second = deferred<PlayerSummary[]>()
    mockedSearchPlayers.mockReturnValueOnce(first.promise)
    mockedSearchPlayers.mockReturnValueOnce(second.promise)
    renderSearchPage()

    const input = screen.getByLabelText(/search players/i)
    fireEvent.change(input, { target: { value: 'Sa' } })
    await advanceDebounce()
    fireEvent.change(input, { target: { value: 'Salah' } })
    await advanceDebounce()

    await act(async () => {
      second.resolve([salah])
    })
    expect(screen.getByText('Mohamed Salah')).toBeTruthy()

    await act(async () => {
      first.resolve([kane])
    })
    expect(screen.queryByText('Harry Kane')).toBeNull()
    expect(screen.getByText('Mohamed Salah')).toBeTruthy()
  })

  it('clearing the query clears results', async () => {
    mockedSearchPlayers.mockResolvedValue([salah])
    renderSearchPage()

    const input = screen.getByLabelText(/search players/i)
    fireEvent.change(input, { target: { value: 'Salah' } })
    await advanceDebounce()
    await flushPromises()

    expect(screen.getByText('Mohamed Salah')).toBeTruthy()

    await act(async () => {
      fireEvent.change(input, { target: { value: '' } })
    })

    expect(screen.queryByRole('link', { name: /view mohamed salah profile/i })).toBeNull()
    expect(screen.getByText(/try a player name/i)).toBeTruthy()
  })
})
