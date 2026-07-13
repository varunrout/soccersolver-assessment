import { useEffect, useRef, useState } from 'react'
import { Bot, CornerDownLeft, Search, Sparkles, UserRound, UsersRound } from 'lucide-react'
import { sendChatMessage } from '../api/client'
import ResponseRenderer from '../components/ResponseRenderer'
import PageHeader from '../components/ui/PageHeader'
import type { ResponseUnion } from '../types/chat'

type ChatMessage =
  | {
      id: string
      role: 'user'
      text: string
    }
  | {
      id: string
      role: 'assistant'
      response?: ResponseUnion
      loading?: boolean
      retryText?: string
    }

const MAX_MESSAGE_LENGTH = 1000
const EXAMPLE_PROMPTS = [
  { text: 'Top 5 forwards in the Premier League by goals', label: 'Rank players', icon: Sparkles },
  { text: 'Show me Mohamed Salah', label: 'Player profile', icon: Search },
  { text: 'Compare Mohamed Salah and Harry Kane', label: 'Compare players', icon: UsersRound },
  { text: 'Who is the best player?', label: 'Ask broadly', icon: Bot },
]

let messageCounter = 0

function makeId(prefix: string) {
  messageCounter += 1
  return `${prefix}-${Date.now()}-${messageCounter}`
}

const transportErrorResponse: ResponseUnion = {
  type: 'text',
  message: "We couldn't process your question right now. Please try again.",
  is_error: true,
}

export default function ChatPage() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ block: 'end' })
  }, [messages])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const sendMessage = (rawMessage: string, options: { includeUserMessage: boolean } = { includeUserMessage: true }) => {
    const trimmedMessage = rawMessage.trim()

    if (!trimmedMessage || isLoading) {
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const assistantId = makeId('assistant')

    if (options.includeUserMessage) {
      setMessages((current) => [
        ...current,
        { id: makeId('user'), role: 'user', text: trimmedMessage },
        { id: assistantId, role: 'assistant', loading: true },
      ])
    } else {
      setMessages((current) => current.map((message) => (
        message.id === assistantId ? { id: assistantId, role: 'assistant', loading: true } : message
      )))
    }

    setInput('')
    setIsLoading(true)

    sendChatMessage(trimmedMessage, controller.signal)
      .then((chatResponse) => {
        if (controller.signal.aborted) {
          return
        }

        setMessages((current) => current.map((message) => (
          message.id === assistantId
            ? { id: assistantId, role: 'assistant', response: chatResponse.response }
            : message
        )))
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) {
          return
        }

        setMessages((current) => current.map((message) => (
          message.id === assistantId
            ? { id: assistantId, role: 'assistant', response: transportErrorResponse, retryText: trimmedMessage }
            : message
        )))
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false)
          textareaRef.current?.focus()
        }
      })
  }

  const retryMessage = (messageId: string, text: string) => {
    if (isLoading) {
      return
    }

    const controller = new AbortController()
    abortRef.current = controller
    setIsLoading(true)
    setMessages((current) => current.map((message) => (
      message.id === messageId ? { id: messageId, role: 'assistant', loading: true } : message
    )))

    sendChatMessage(text, controller.signal)
      .then((chatResponse) => {
        if (controller.signal.aborted) {
          return
        }

        setMessages((current) => current.map((message) => (
          message.id === messageId ? { id: messageId, role: 'assistant', response: chatResponse.response } : message
        )))
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) {
          return
        }

        setMessages((current) => current.map((message) => (
          message.id === messageId
            ? { id: messageId, role: 'assistant', response: transportErrorResponse, retryText: text }
            : message
        )))
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false)
          textareaRef.current?.focus()
        }
      })
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    sendMessage(input)
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendMessage(input)
    }
  }

  const remainingCharacters = MAX_MESSAGE_LENGTH - input.length

  return (
    <div className="page chat-page">
      <PageHeader eyebrow="Structured football analysis" title="Ask SoccerSolver" description="Ask questions about player rankings, individual profiles and two-player comparisons." actions={<div className="assistant-identity"><span><Bot size={20} aria-hidden="true" /></span><div><strong>Analysis assistant</strong><small>Dataset grounded</small></div></div>} />

      {messages.length === 0 ? (
        <section className="chat-empty-state" aria-label="Example prompts">
          <div className="chat-empty-state__intro"><span className="empty-state__icon"><Sparkles size={20} aria-hidden="true" /></span><div><strong>Start an analysis</strong><p>Try one of these prompts:</p></div></div>
          <div className="prompt-grid">
            {EXAMPLE_PROMPTS.map((prompt) => (
              <button className="example-button" key={prompt.text} type="button" onClick={() => sendMessage(prompt.text)}>
                <span className="example-button__icon"><prompt.icon size={18} aria-hidden="true" /></span>
                <span><strong>{prompt.label}</strong><small>{prompt.text}</small></span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <ol className="chat-history" aria-label="Chat messages" aria-live="polite">
        {messages.map((message) => (
          <li className={`chat-message chat-message--${message.role}`} key={message.id}>
            <div className="chat-message__identity">
              <span className="chat-message__avatar" aria-hidden="true">{message.role === 'user' ? <UserRound size={16} /> : <Bot size={16} />}</span>
              <span className="chat-message__author">{message.role === 'user' ? 'You' : 'SoccerSolver'}</span>
            </div>
            <div className={`chat-bubble chat-bubble--${message.role}`}>
              {message.role === 'user' ? (
                <p>{message.text}</p>
              ) : null}

              {message.role === 'assistant' && message.loading ? (
                <p className="placeholder-text">SoccerSolver is analysing your question...</p>
              ) : null}

              {message.role === 'assistant' && message.response ? (
                <>
                  <ResponseRenderer response={message.response} />
                  {message.retryText ? (
                    <button className="btn btn-primary retry-button" type="button" onClick={() => retryMessage(message.id, message.retryText ?? '')}>
                      Retry
                    </button>
                  ) : null}
                </>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
      <div ref={bottomRef} aria-hidden="true" />

      <form className="chat-input-form" onSubmit={handleSubmit}>
        <label className="search-label" htmlFor="chat-message">Ask a question</label>
        <textarea
          className="chat-textarea"
          disabled={isLoading}
          id="chat-message"
          maxLength={MAX_MESSAGE_LENGTH}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about player rankings, profiles or comparisons"
          ref={textareaRef}
          rows={3}
          value={input}
        />
        <div className="chat-input-actions">
          <span className="search-help">{remainingCharacters} characters remaining</span>
          <button className="btn btn-primary" disabled={isLoading || !input.trim()} type="submit">
            <CornerDownLeft size={17} aria-hidden="true" />
            Send
          </button>
        </div>
      </form>
    </div>
  )
}
