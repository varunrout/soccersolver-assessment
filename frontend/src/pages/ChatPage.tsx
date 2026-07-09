import { useState } from 'react'
import ResponseRenderer from '../components/ResponseRenderer'
import type { ChatMessage } from '../types/chat'

let _msgCounter = 0
function makeId() { return `msg-${++_msgCounter}` }

export default function ChatPage() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])

  // TODO (Issue #11): POST /chat
  const handleSend = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    const userMsg: ChatMessage = {
      id: makeId(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    }
    const stubReply: ChatMessage = {
      id: makeId(),
      role: 'assistant',
      content: 'Chat API not yet connected — coming in Issue #11.',
      response: { type: 'text', message: 'Chat API not yet connected — coming in Issue #11.', is_error: false },
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMsg, stubReply])
    setInput('')
  }

  return (
    <div className="page chat-page">
      <h1 className="page-title">Ask SoccerSolver</h1>

      <div className="chat-history">
        {messages.length === 0 && (
          <p className="placeholder-text">
            Ask anything about players, stats, or comparisons. (e.g. "Who has more xG — Salah or Firmino?")
          </p>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-bubble chat-bubble--${msg.role}`}>
            {msg.role === 'assistant' && msg.response ? (
              <ResponseRenderer response={msg.response} />
            ) : (
              <span>{msg.content}</span>
            )}
          </div>
        ))}
      </div>

      <form className="chat-input-form" onSubmit={handleSend}>
        <input
          className="search-input"
          type="text"
          placeholder="Ask a question…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="btn btn-primary" type="submit">Send</button>
      </form>
    </div>
  )
}
