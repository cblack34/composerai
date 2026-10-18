import { useEffect, useRef, useState, type FormEvent } from 'react'
import { buildChatRequest, type ChatMessage } from './chatRequest.ts'

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [prompt, setPrompt] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sending = useRef(false)
  const transcript = useRef<HTMLOListElement>(null)
  const blank = prompt.trim() === ''

  useEffect(() => {
    const list = transcript.current
    if (list) list.scrollTop = list.scrollHeight
  }, [messages])

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = prompt.trim()
    if (text === '' || sending.current) return
    sending.current = true
    setPending(true)
    setError(null)
    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildChatRequest(text, messages)),
      })
      if (!response.ok) throw new Error('chat failed')
      const body = (await response.json()) as { reply: string }
      setMessages((current) => [
        ...current,
        { role: 'user', content: text },
        { role: 'assistant', content: body.reply },
      ])
      setPrompt('')
    } catch {
      setError('The chat request failed.')
    } finally {
      sending.current = false
      setPending(false)
    }
  }

  return (
    <main>
      <ol
        className="transcript"
        ref={transcript}
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Conversation"
      >
        {messages.map((message, index) => (
          <li key={index}>
            <span className="role">{message.role === 'user' ? 'You' : 'Lead'}</span>
            {message.content}
          </li>
        ))}
      </ol>
      <form onSubmit={onSubmit}>
        <label htmlFor="prompt">Prompt</label>
        <textarea
          id="prompt"
          name="prompt"
          rows={3}
          value={prompt}
          disabled={pending}
          onChange={(event) => setPrompt(event.target.value)}
        />
        <button type="submit" disabled={blank || pending}>
          {pending ? 'Sending...' : 'Send'}
        </button>
      </form>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
    </main>
  )
}
