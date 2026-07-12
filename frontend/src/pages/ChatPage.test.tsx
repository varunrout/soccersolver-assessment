import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { sendChatMessage } from '../api/client'
import type { ChatResponse } from '../types/chat'
import ChatPage from './ChatPage'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()

  return {
    ...actual,
    sendChatMessage: vi.fn(),
  }
})

const mockedSendChatMessage = vi.mocked(sendChatMessage)

const textResponse: ChatResponse = {
  response: {
    type: 'text',
    message: 'Which metric should I rank by?',
    is_error: false,
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

beforeEach(() => {
  mockedSendChatMessage.mockReset()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('ChatPage', () => {
  it('renders initial introduction and examples', () => {
    render(<ChatPage />)

    expect(screen.getByRole('heading', { name: 'Ask SoccerSolver' })).toBeTruthy()
    expect(screen.getByText(/player rankings, individual profiles/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /top 5 forwards/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /show me mohamed salah/i })).toBeTruthy()
  })

  it('keeps the textarea controlled and ignores blank submissions', () => {
    render(<ChatPage />)

    const input = screen.getByLabelText('Ask a question') as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(input.value).toBe('   ')
    expect(mockedSendChatMessage).not.toHaveBeenCalled()
  })

  it('submits a valid message, shows loading, clears input, and renders success', async () => {
    const pending = deferred<ChatResponse>()
    mockedSendChatMessage.mockReturnValueOnce(pending.promise)
    render(<ChatPage />)

    const input = screen.getByLabelText('Ask a question') as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: 'Who is the best player?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(screen.getByText('Who is the best player?')).toBeTruthy()
    expect(screen.getByText(/analysing your question/i)).toBeTruthy()
    expect(input.value).toBe('')
    expect((screen.getByRole('button', { name: 'Send' }) as HTMLButtonElement).disabled).toBe(true)
    expect(mockedSendChatMessage).toHaveBeenCalledWith('Who is the best player?', expect.any(AbortSignal))

    await act(async () => {
      pending.resolve(textResponse)
    })

    expect(screen.getByText('Which metric should I rank by?')).toBeTruthy()
  })

  it('renders only list items as direct children of the chat history list', async () => {
    mockedSendChatMessage.mockResolvedValue(textResponse)
    render(<ChatPage />)

    fireEvent.change(screen.getByLabelText('Ask a question'), { target: { value: 'Who is the best player?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    await flushPromises()

    const history = screen.getByRole('list', { name: 'Chat messages' })
    expect(Array.from(history.children).every((child) => child.tagName.toLowerCase() === 'li')).toBe(true)
  })

  it('Enter submits and Shift+Enter does not submit', () => {
    mockedSendChatMessage.mockResolvedValue(textResponse)
    render(<ChatPage />)

    const input = screen.getByLabelText('Ask a question')
    fireEvent.change(input, { target: { value: 'Line one' } })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })
    expect(mockedSendChatMessage).not.toHaveBeenCalled()

    fireEvent.keyDown(input, { key: 'Enter' })
    expect(mockedSendChatMessage).toHaveBeenCalledTimes(1)
  })

  it('clicking an example sends it through the backend', () => {
    mockedSendChatMessage.mockResolvedValue(textResponse)
    render(<ChatPage />)

    fireEvent.click(screen.getByRole('button', { name: /compare mohamed salah and harry kane/i }))

    expect(mockedSendChatMessage).toHaveBeenCalledWith('Compare Mohamed Salah and Harry Kane', expect.any(AbortSignal))
  })

  it('preserves prior messages after later questions', async () => {
    mockedSendChatMessage
      .mockResolvedValueOnce({ response: { type: 'text', message: 'First answer', is_error: false } })
      .mockResolvedValueOnce({ response: { type: 'text', message: 'Second answer', is_error: false } })
    render(<ChatPage />)

    const input = screen.getByLabelText('Ask a question')
    fireEvent.change(input, { target: { value: 'First question' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    await flushPromises()
    fireEvent.change(input, { target: { value: 'Second question' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    await flushPromises()

    expect(screen.getByText('First question')).toBeTruthy()
    expect(screen.getByText('First answer')).toBeTruthy()
    expect(screen.getByText('Second question')).toBeTruthy()
    expect(screen.getByText('Second answer')).toBeTruthy()
  })

  it('renders safe retry state for transport errors and resends the original message', async () => {
    mockedSendChatMessage.mockRejectedValueOnce(new Error('raw backend stack')).mockResolvedValueOnce(textResponse)
    render(<ChatPage />)

    fireEvent.change(screen.getByLabelText('Ask a question'), { target: { value: 'Compare Salah' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    await flushPromises()

    expect(screen.getByRole('alert').textContent).toContain("We couldn't process your question right now.")
    expect(screen.queryByText('raw backend stack')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await flushPromises()

    expect(mockedSendChatMessage).toHaveBeenCalledTimes(2)
    expect(mockedSendChatMessage).toHaveBeenLastCalledWith('Compare Salah', expect.any(AbortSignal))
    expect(screen.getByText('Which metric should I rank by?')).toBeTruthy()
  })

  it('unmount aborts the active request', () => {
    let signal: AbortSignal | undefined
    mockedSendChatMessage.mockImplementation((_message, nextSignal) => {
      signal = nextSignal
      return new Promise(() => {})
    })
    const { unmount } = render(<ChatPage />)

    fireEvent.change(screen.getByLabelText('Ask a question'), { target: { value: 'Show me Mohamed Salah' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    unmount()

    expect(signal?.aborted).toBe(true)
  })
})
