import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getPlayerImage } from '../../api/playerImages'
import PlayerAvatar from './PlayerAvatar'

vi.mock('../../api/playerImages', () => ({
  getPlayerImage: vi.fn(),
}))

const mockedGetPlayerImage = vi.mocked(getPlayerImage)

type IntersectionObserverCallback = ConstructorParameters<typeof IntersectionObserver>[0]

let intersectionObserverCallback: IntersectionObserverCallback | null = null

beforeEach(() => {
  mockedGetPlayerImage.mockReset()
  intersectionObserverCallback = null
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PlayerAvatar', () => {
  it('renders a provided player image with useful alt text', () => {
    render(<PlayerAvatar name="Mohamed Salah" imageUrl="https://images.example.test/salah.jpg" position="FWD" />)

    const image = screen.getByRole('img', { name: 'Mohamed Salah player portrait' }) as HTMLImageElement
    expect(image.src).toBe('https://images.example.test/salah.jpg')
    expect(image.getAttribute('referrerpolicy')).toBe('no-referrer')
  })

  it('renders deterministic initials when an image URL is absent', () => {
    render(<PlayerAvatar name="Mohamed Salah" />)

    expect(screen.getByRole('img', { name: 'Mohamed Salah avatar' })).toBeTruthy()
    expect(screen.getByText('MS')).toBeTruthy()
  })

  it('switches to fallback initials when the external image fails', () => {
    render(<PlayerAvatar name="Harry Kane" imageUrl="https://images.example.test/broken.jpg" />)

    fireEvent.error(screen.getByRole('img', { name: 'Harry Kane player portrait' }))

    expect(screen.getByRole('img', { name: 'Harry Kane avatar' })).toBeTruthy()
    expect(screen.getByText('HK')).toBeTruthy()
    expect(screen.queryByRole('img', { name: 'Harry Kane player portrait' })).toBeNull()
  })

  it('does not expose fallback initials twice to assistive technology', () => {
    render(<PlayerAvatar name="Kylian Mbappe" />)

    const fallback = screen.getByRole('img', { name: 'Kylian Mbappe avatar' })
    expect(fallback.querySelector('[aria-hidden="true"]')?.textContent).toBe('KM')
  })

  it('waits until the avatar is near the viewport before requesting a remote image', async () => {
    vi.stubGlobal('IntersectionObserver', class {
      constructor(callback: IntersectionObserverCallback) {
        intersectionObserverCallback = callback
      }

      observe() {}
      disconnect() {}
      unobserve() {}
      takeRecords() { return [] }
      root = null
      rootMargin = '200px'
      thresholds = []
    })
    mockedGetPlayerImage.mockResolvedValue({
      player_id: 'e342ad68',
      image_url: 'https://images.example.test/salah.jpg',
    })

    render(<PlayerAvatar name="Mohamed Salah" playerId="e342ad68" />)

    expect(mockedGetPlayerImage).not.toHaveBeenCalled()
    expect(intersectionObserverCallback).toBeTypeOf('function')

    await act(async () => {
      intersectionObserverCallback?.([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver)
    })

    await waitFor(() => expect(mockedGetPlayerImage).toHaveBeenCalledWith('e342ad68', expect.any(AbortSignal)))
  })
})