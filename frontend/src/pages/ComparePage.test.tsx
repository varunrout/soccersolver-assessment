import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, comparePlayers, getPlayerProfile, searchPlayers } from '../api/client'
import type { ComparisonResult, PlayerDetail, PlayerSummary } from '../types/player'
import ComparePage from './ComparePage'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()

  return {
    ...actual,
    comparePlayers: vi.fn(),
    getPlayerProfile: vi.fn(),
    searchPlayers: vi.fn(),
  }
})

vi.mock('../api/playerImages', () => ({
  getPlayerImage: vi.fn().mockResolvedValue({ player_id: '', image_url: null }),
}))

const mockedSearchPlayers = vi.mocked(searchPlayers)
const mockedComparePlayers = vi.mocked(comparePlayers)
const mockedGetPlayerProfile = vi.mocked(getPlayerProfile)

const salahSummary: PlayerSummary = {
  player_id: 'e342ad68',
  name: 'Mohamed Salah',
  position: 'FWD',
  club: 'Liverpool',
  league: 'Premier League',
  market_value_eur: 104_000_000,
}

const kaneSummary: PlayerSummary = {
  player_id: 'harry-kane',
  name: 'Harry Kane',
  position: 'FWD',
  club: 'Bayern Munich',
  league: 'Bundesliga',
  market_value_eur: 35_500_000,
}

const salahDetail: PlayerDetail = {
  ...salahSummary,
  age: 29,
  goals: 23,
  assists: 13,
  minutes_played: 2762,
  shots: 134,
  passes: 1118,
  xg: 23.7,
  xa: 9.7,
}

const kaneDetail: PlayerDetail = {
  ...kaneSummary,
  age: 28,
  goals: 16,
  assists: 8,
  minutes_played: 2840,
  shots: 112,
  passes: 870,
  xg: 15.2,
  xa: 6.4,
}

const comparisonResult: ComparisonResult = {
  player_a: salahDetail,
  player_b: kaneDetail,
  metrics: [
    { metric_name: 'goals_p90', label: 'Goals per 90', value_a: 0.75, value_b: 0.51, winner: 'a' },
    { metric_name: 'assists_p90', label: 'Assists per 90', value_a: 0.42, value_b: 0.25, winner: 'a' },
    { metric_name: 'shots_p90', label: 'Shots per 90', value_a: 4.37, value_b: 3.55, winner: 'a' },
    { metric_name: 'passes_p90', label: 'Passes per 90', value_a: 36.43, value_b: 27.57, winner: 'b' },
    { metric_name: 'xg_p90', label: 'xG per 90', value_a: 0.77, value_b: 0.48, winner: 'draw' },
    { metric_name: 'xa_p90', label: 'xA per 90', value_a: 0.32, value_b: 0.2, winner: 'a' },
  ],
  market_context: {
    value_a: 104_000_000,
    value_b: 35_500_000,
    league_avg_a: 22_000_000,
    league_avg_b: null,
  },
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

function renderCompare(path = '/compare') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/compare" element={<ComparePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

function getSelectorInput(label: 'Player A' | 'Player B') {
  return screen.getByRole('searchbox', { name: label })
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

async function selectPlayer(label: 'Player A' | 'Player B', query: string, player: PlayerSummary) {
  mockedSearchPlayers.mockResolvedValueOnce([player])
  fireEvent.change(getSelectorInput(label), { target: { value: query } })
  await advanceDebounce()
  fireEvent.click(screen.getByRole('button', { name: new RegExp(player.name, 'i') }))
}

beforeEach(() => {
  vi.useFakeTimers()
  mockedSearchPlayers.mockReset()
  mockedComparePlayers.mockReset()
  mockedGetPlayerProfile.mockReset()
  mockedSearchPlayers.mockResolvedValue([])
})

afterEach(() => {
  vi.clearAllTimers()
  vi.useRealTimers()
})

describe('ComparePage selectors', () => {
  it('renders both selectors and keeps compare disabled until selections exist', () => {
    renderCompare()

    expect(screen.getByRole('heading', { name: 'Compare Players' })).toBeTruthy()
    expect(getSelectorInput('Player A')).toBeTruthy()
    expect(getSelectorInput('Player B')).toBeTruthy()
    expect((screen.getByRole('button', { name: /compare players/i }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('does not search for under-2-character input', async () => {
    renderCompare()

    fireEvent.change(getSelectorInput('Player A'), { target: { value: 'S' } })
    await advanceDebounce()

    expect(mockedSearchPlayers).not.toHaveBeenCalled()
  })

  it('searches after debounce, renders results, selects, displays, and clears a player', async () => {
    renderCompare()

    await selectPlayer('Player A', 'Salah', salahSummary)

    expect(mockedSearchPlayers).toHaveBeenCalledWith('Salah', expect.any(AbortSignal))
    expect(screen.getByText('Estimated market value €104m')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /clear/i }))
    expect(getSelectorInput('Player A')).toBeTruthy()
  })

  it('ignores stale selector responses', async () => {
    const first = deferred<PlayerSummary[]>()
    const second = deferred<PlayerSummary[]>()
    mockedSearchPlayers.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    renderCompare()

    fireEvent.change(getSelectorInput('Player A'), { target: { value: 'Sa' } })
    await advanceDebounce()
    fireEvent.change(getSelectorInput('Player A'), { target: { value: 'Salah' } })
    await advanceDebounce()

    await act(async () => {
      second.resolve([salahSummary])
    })
    expect(screen.getByRole('button', { name: /mohamed salah/i })).toBeTruthy()

    await act(async () => {
      first.resolve([kaneSummary])
    })
    expect(screen.queryByRole('button', { name: /harry kane/i })).toBeNull()
  })

  it('selector errors do not expose raw error text', async () => {
    mockedSearchPlayers.mockRejectedValueOnce(new Error('raw backend failure'))
    renderCompare()

    fireEvent.change(getSelectorInput('Player A'), { target: { value: 'Salah' } })
    await advanceDebounce()
    await flushPromises()

    expect(screen.getByRole('alert').textContent).toContain("We couldn't search for players right now.")
    expect(screen.queryByText('raw backend failure')).toBeNull()
  })
})

describe('ComparePage preselection', () => {
  it('loads playerA query parameter and preselects Player A', async () => {
    mockedGetPlayerProfile.mockResolvedValue({ ...salahDetail, percentiles: null })

    renderCompare('/compare?playerA=e342ad68')
    await flushPromises()

    expect(mockedGetPlayerProfile).toHaveBeenCalledWith('e342ad68', expect.any(AbortSignal))
    expect(screen.getByText('Mohamed Salah')).toBeTruthy()
  })

  it('handles invalid preselection safely', async () => {
    mockedGetPlayerProfile.mockRejectedValue(new ApiError('not found', 404))

    renderCompare('/compare?playerA=bad-id')
    await flushPromises()

    expect(getSelectorInput('Player A')).toBeTruthy()
    expect((screen.getByRole('button', { name: /compare players/i }) as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('ComparePage comparison', () => {
  async function selectBothPlayers() {
    await selectPlayer('Player A', 'Salah', salahSummary)
    await selectPlayer('Player B', 'Kane', kaneSummary)
  }

  it('calls comparison with selected IDs, shows loading, and renders success', async () => {
    const pending = deferred<ComparisonResult>()
    mockedComparePlayers.mockReturnValueOnce(pending.promise)
    renderCompare()
    await selectBothPlayers()

    fireEvent.click(screen.getByRole('button', { name: /compare players/i }))

    expect(mockedComparePlayers).toHaveBeenCalledWith('e342ad68', 'harry-kane', expect.any(AbortSignal))
    expect(screen.getByLabelText(/loading comparison/i)).toBeTruthy()

    await act(async () => {
      pending.resolve(comparisonResult)
    })

    expect(screen.getByRole('link', { name: 'Mohamed Salah' }).getAttribute('href')).toBe('/player/e342ad68')
    expect(screen.getByRole('link', { name: 'Harry Kane' }).getAttribute('href')).toBe('/player/harry-kane')
    expect(screen.getAllByText('Goals per 90').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Player A leads').length).toBeGreaterThan(0)
    expect(screen.getByText('Player B leads')).toBeTruthy()
    expect(screen.getByText('Draw')).toBeTruthy()
    expect(screen.getAllByText('€104m').length).toBeGreaterThan(0)
    expect(screen.getAllByText('€35.5m').length).toBeGreaterThan(0)
    expect(screen.getByText('€22m')).toBeTruthy()
    expect(screen.getByText('Not available')).toBeTruthy()
  })

  it('renders all metric rows with backend winner labels', async () => {
    mockedComparePlayers.mockResolvedValue(comparisonResult)
    renderCompare()
    await selectBothPlayers()

    fireEvent.click(screen.getByRole('button', { name: /compare players/i }))
    await flushPromises()

    const rows = screen.getAllByRole('article').filter((row) => row.getAttribute('aria-label')?.includes('per 90'))
    expect(rows).toHaveLength(6)
    expect(within(rows[4]).getByText('Draw')).toBeTruthy()
  })

  it('renders same-player market context cards without duplicate-key warnings', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const samePlayerResult: ComparisonResult = {
      ...comparisonResult,
      player_b: salahDetail,
      market_context: {
        value_a: 104_000_000,
        value_b: 104_000_000,
        league_avg_a: 22_000_000,
        league_avg_b: 22_000_000,
      },
    }
    mockedComparePlayers.mockResolvedValue(samePlayerResult)
    renderCompare()

    await selectPlayer('Player A', 'Salah', salahSummary)
    await selectPlayer('Player B', 'Salah', salahSummary)
    fireEvent.click(screen.getByRole('button', { name: /compare players/i }))
    await flushPromises()

    const marketSection = screen.getByRole('heading', { name: 'Market Context' }).closest('section')
    expect(marketSection).not.toBeNull()
    expect(within(marketSection as HTMLElement).getAllByText('Mohamed Salah')).toHaveLength(2)
    expect(consoleErrorSpy).not.toHaveBeenCalledWith(expect.stringContaining('Encountered two children with the same key'))

    consoleErrorSpy.mockRestore()
  })

  it('renders 404 and general error states, then retries', async () => {
    mockedComparePlayers
      .mockRejectedValueOnce(new ApiError('missing', 404))
      .mockRejectedValueOnce(new Error('raw stack'))
      .mockResolvedValueOnce(comparisonResult)
    renderCompare()
    await selectBothPlayers()

    fireEvent.click(screen.getByRole('button', { name: /compare players/i }))
    await flushPromises()
    expect(screen.getByRole('alert').textContent).toContain('One or both selected players could not be found.')

    fireEvent.click(screen.getByRole('button', { name: /compare players/i }))
    await flushPromises()
    expect(screen.getByRole('alert').textContent).toContain("We couldn't compare these players right now.")
    expect(screen.queryByText('raw stack')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /retry/i }))
    await flushPromises()
    expect(mockedComparePlayers).toHaveBeenCalledTimes(3)
    expect(screen.getByText('Market Context')).toBeTruthy()
  })

  it('changing selection clears old comparison', async () => {
    mockedComparePlayers.mockResolvedValue(comparisonResult)
    renderCompare()
    await selectBothPlayers()

    fireEvent.click(screen.getByRole('button', { name: /compare players/i }))
    await flushPromises()
    expect(screen.getByText('Market Context')).toBeTruthy()

    fireEvent.click(screen.getAllByRole('button', { name: /clear/i })[0])
    expect(screen.queryByText('Market Context')).toBeNull()
  })

  it('stale comparison results cannot overwrite newer requests', async () => {
    const first = deferred<ComparisonResult>()
    const second = deferred<ComparisonResult>()
    mockedComparePlayers.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    renderCompare()
    await selectBothPlayers()

    fireEvent.click(screen.getByRole('button', { name: /compare players/i }))
    fireEvent.click(screen.getAllByRole('button', { name: /clear/i })[0])
    await selectPlayer('Player A', 'Salah', salahSummary)
    fireEvent.click(screen.getByRole('button', { name: /compare players/i }))

    await act(async () => {
      second.resolve(comparisonResult)
    })
    expect(screen.getByText('Market Context')).toBeTruthy()

    await act(async () => {
      first.resolve({
        ...comparisonResult,
        player_a: { ...salahDetail, name: 'Stale Player' },
      })
    })
    expect(screen.queryByText('Stale Player')).toBeNull()
  })

  it('unmount aborts active comparison requests', async () => {
    let signal: AbortSignal | undefined
    mockedComparePlayers.mockImplementation((_a, _b, nextSignal) => {
      signal = nextSignal
      return new Promise(() => {})
    })
    const { unmount } = renderCompare()
    await selectBothPlayers()

    fireEvent.click(screen.getByRole('button', { name: /compare players/i }))
    unmount()

    expect(signal?.aborted).toBe(true)
  })
})
