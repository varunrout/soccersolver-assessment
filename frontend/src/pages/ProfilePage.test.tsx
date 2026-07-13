import { act, fireEvent, render, screen } from '@testing-library/react'
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getPlayerProfile } from '../api/client'
import type { PlayerDetailWithPercentiles } from '../types/player'
import ProfilePage from './ProfilePage'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()

  return {
    ...actual,
    getPlayerProfile: vi.fn(),
  }
})

vi.mock('../api/playerImages', () => ({
  getPlayerImage: vi.fn().mockResolvedValue({ player_id: '', image_url: null }),
}))

const mockedGetPlayerProfile = vi.mocked(getPlayerProfile)

const salah: PlayerDetailWithPercentiles = {
  player_id: 'e342ad68',
  name: 'Mohamed Salah',
  position: 'FWD',
  age: 29,
  club: 'Liverpool',
  league: 'Premier League',
  market_value_eur: 104_000_000,
  goals: 23,
  assists: 13,
  minutes_played: 2_762,
  shots: 139,
  passes: 1_391,
  xg: 21.8,
  xa: 9.7,
  percentiles: {
    player_id: 'e342ad68',
    metrics: {
      goals_p90: 82,
      assists_p90: 77.2,
      shots_p90: null,
      passes_p90: 64,
      xg_p90: 91,
      xa_p90: Number.NaN,
      malformed_p90: Number.POSITIVE_INFINITY,
    },
  },
}

const kane: PlayerDetailWithPercentiles = {
  ...salah,
  player_id: 'harry-kane',
  name: 'Harry Kane',
  club: 'Bayern Munich',
  league: 'Bundesliga',
  market_value_eur: 35_500_000,
  percentiles: {
    player_id: 'harry-kane',
    metrics: {
      goals_p90: 70,
    },
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

async function flushPromises() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

function renderProfile(path = '/player/e342ad68') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/player/:id" element={<ProfilePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  mockedGetPlayerProfile.mockReset()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('ProfilePage', () => {
  it('renders loading state and passes the route ID to getPlayerProfile', () => {
    mockedGetPlayerProfile.mockReturnValue(new Promise(() => {}))

    renderProfile('/player/e342ad68')

    expect(screen.getByLabelText(/loading player profile/i)).toBeTruthy()
    expect(mockedGetPlayerProfile).toHaveBeenCalledWith('e342ad68', expect.any(AbortSignal))
  })

  it('renders valid profile header, market value, and all seven core statistics', async () => {
    mockedGetPlayerProfile.mockResolvedValue(salah)

    renderProfile()
    await flushPromises()

    expect(screen.getByRole('heading', { name: 'Mohamed Salah' })).toBeTruthy()
    expect(screen.getByText('Liverpool · Premier League')).toBeTruthy()
    expect(screen.getByText('29')).toBeTruthy()
    expect(screen.getByText('€104m')).toBeTruthy()

    expect(screen.getByText('Goals')).toBeTruthy()
    expect(screen.getByText('23')).toBeTruthy()
    expect(screen.getByText('Assists')).toBeTruthy()
    expect(screen.getByText('13')).toBeTruthy()
    expect(screen.getByText('Minutes played')).toBeTruthy()
    expect(screen.getByText('2,762')).toBeTruthy()
    expect(screen.getByText('Shots')).toBeTruthy()
    expect(screen.getByText('139')).toBeTruthy()
    expect(screen.getByText('Passes')).toBeTruthy()
    expect(screen.getByText('1,391')).toBeTruthy()
    expect(screen.getByText('xG')).toBeTruthy()
    expect(screen.getByText('21.8')).toBeTruthy()
    expect(screen.getByText('xA')).toBeTruthy()
    expect(screen.getByText('9.7')).toBeTruthy()
  })

  it('renders not-found state for 404 responses', async () => {
    mockedGetPlayerProfile.mockRejectedValue(new ApiError('Player not found', 404))

    renderProfile('/player/missing')
    await flushPromises()

    expect(screen.getByRole('alert').textContent).toContain('Player not found.')
    expect(screen.getByRole('link', { name: 'Player Search' }).getAttribute('href')).toBe('/')
  })

  it('renders a general error state without raw exception text and retries', async () => {
    mockedGetPlayerProfile.mockRejectedValueOnce(new Error('backend stack trace'))
    mockedGetPlayerProfile.mockResolvedValueOnce(salah)

    renderProfile()
    await flushPromises()

    expect(screen.getByRole('alert').textContent).toContain("We couldn't load this player right now.")
    expect(screen.queryByText('backend stack trace')).toBeNull()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /retry/i }))
    })
    await flushPromises()

    expect(mockedGetPlayerProfile).toHaveBeenCalledTimes(2)
    expect(screen.getByRole('heading', { name: 'Mohamed Salah' })).toBeTruthy()
  })

  it('fetches again when the route ID changes', async () => {
    mockedGetPlayerProfile.mockResolvedValueOnce(salah).mockResolvedValueOnce(kane)

    render(
      <MemoryRouter initialEntries={['/player/e342ad68']}>
        <Routes>
          <Route
            path="/player/:id"
            element={
              <>
                <ProfilePage />
                <Link to="/player/harry-kane">Go to Harry Kane</Link>
              </>
            }
          />
        </Routes>
      </MemoryRouter>,
    )

    await flushPromises()
    fireEvent.click(screen.getByRole('link', { name: /go to harry kane/i }))
    await flushPromises()

    expect(mockedGetPlayerProfile).toHaveBeenCalledTimes(2)
    expect(mockedGetPlayerProfile).toHaveBeenLastCalledWith('harry-kane', expect.any(AbortSignal))
    expect(screen.getByRole('heading', { name: 'Harry Kane' })).toBeTruthy()
  })

  it('changing route ID triggers a new request and stale old data cannot overwrite the newer profile', async () => {
    const first = deferred<PlayerDetailWithPercentiles>()
    const second = deferred<PlayerDetailWithPercentiles>()
    mockedGetPlayerProfile.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    render(
      <MemoryRouter initialEntries={['/player/e342ad68']}>
        <Routes>
          <Route
            path="/player/:id"
            element={
              <>
                <ProfilePage />
                <LinkToPlayer id="harry-kane" />
              </>
            }
          />
        </Routes>
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('link', { name: /go to harry kane/i }))
    expect(mockedGetPlayerProfile).toHaveBeenCalledWith('harry-kane', expect.any(AbortSignal))

    await act(async () => {
      second.resolve(kane)
    })
    expect(screen.getByRole('heading', { name: 'Harry Kane' })).toBeTruthy()

    await act(async () => {
      first.resolve(salah)
    })
    expect(screen.queryByRole('heading', { name: 'Mohamed Salah' })).toBeNull()
    expect(screen.getByRole('heading', { name: 'Harry Kane' })).toBeTruthy()
  })

  it('aborts the active request on unmount', () => {
    let signal: AbortSignal | undefined
    mockedGetPlayerProfile.mockImplementation((_id, nextSignal) => {
      signal = nextSignal
      return new Promise(() => {})
    })

    const { unmount } = renderProfile()
    unmount()

    expect(signal?.aborted).toBe(true)
  })

  it('renders available percentile metrics and omits null, NaN, and infinite values', async () => {
    mockedGetPlayerProfile.mockResolvedValue(salah)

    renderProfile()
    await flushPromises()

    expect(screen.getByRole('img', { name: 'Goals per 90: 82nd percentile' })).toBeTruthy()
    expect(screen.getByRole('img', { name: 'Assists per 90: 77th percentile' })).toBeTruthy()
    expect(screen.getByRole('img', { name: 'Passes per 90: 64th percentile' })).toBeTruthy()
    expect(screen.queryByText('Shots per 90')).toBeNull()
    expect(screen.queryByText('xA per 90')).toBeNull()
    expect(screen.queryByText('malformed p90')).toBeNull()
  })

  it('renders fallback when percentiles are null', async () => {
    mockedGetPlayerProfile.mockResolvedValue({ ...salah, percentiles: null })

    renderProfile()
    await flushPromises()

    expect(screen.getByText('Contextual percentile data is not available for this player.')).toBeTruthy()
  })

  it('renders fallback when percentile metrics are empty', async () => {
    mockedGetPlayerProfile.mockResolvedValue({ ...salah, percentiles: { player_id: 'e342ad68', metrics: {} } })

    renderProfile()
    await flushPromises()

    expect(screen.getByText('Contextual percentile data is not available for this player.')).toBeTruthy()
  })

  it('includes back-to-search navigation', async () => {
    mockedGetPlayerProfile.mockResolvedValue(salah)

    renderProfile()
    await flushPromises()

    expect(screen.getByRole('link', { name: /back to player search/i }).getAttribute('href')).toBe('/')
  })
})

function LinkToPlayer({ id }: { id: string }) {
  return <Link to={`/player/${id}`}>Go to Harry Kane</Link>
}
