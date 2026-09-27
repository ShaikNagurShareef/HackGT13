import { useId, useRef, useState, type FormEvent } from 'react'
import { api } from '../../api/client'
import { ASK_THREAD_TOKEN_RE } from '../../api/schemas'
import { useDialog } from '../../hooks/useDialog'
import { Icon } from '../ui/Icon'

/**
 * Ask PathPro: questions about how PathPro works, answered by a Backboard assistant from the
 * model card and docs. The server validates every answer (or sends a fixed fallback); the
 * server-signed thread token lives in this tab's sessionStorage only and is never tied to identity.
 */
export const ASK_SUGGESTIONS = [
  "Why isn't crime used for routing?",
  'How was the model tested?',
  "What does '54% less traffic risk' mean?",
] as const
export const ASK_THREAD_KEY = 'pathpro:ask-thread'
export const ASK_ERROR = "Ask PathPro can't answer right now. About PathPro has the model card."
const LOADING = "Looking through PathPro's docs…"
const MIN_CHARS = 3
const MAX_CHARS = 300

interface Turn {
  id: number
  question: string
  answer: string
}

function storage(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null // storage blocked: each question starts a new thread
  }
}

function readThread(): string | null {
  try {
    const value = storage()?.getItem(ASK_THREAD_KEY) ?? null
    return value && ASK_THREAD_TOKEN_RE.test(value) ? value : null
  } catch {
    return null
  }
}

function writeThread(threadId: string | null): void {
  try {
    if (threadId) storage()?.setItem(ASK_THREAD_KEY, threadId)
    else storage()?.removeItem(ASK_THREAD_KEY)
  } catch {
    // Blocked storage: the conversation just won't continue across questions.
  }
}

export interface AskPanelProps {
  onClose: () => void
}

export function AskPanel({ onClose }: AskPanelProps) {
  const titleId = useId()
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const nextId = useRef(0)
  const [draft, setDraft] = useState('')
  const [turns, setTurns] = useState<readonly Turn[]>([])
  const [note, setNote] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useDialog(onClose)

  const send = async (raw: string) => {
    const question = raw.trim()
    if (loading || question.length < MIN_CHARS) return
    setLoading(true)
    setError(null)
    try {
      const reply = await api.ask(question.slice(0, MAX_CHARS), readThread())
      writeThread(reply.thread_id)
      nextId.current += 1
      const turn: Turn = { id: nextId.current, question, answer: reply.answer }
      setTurns((prev) => [...prev, turn])
      setNote(reply.note)
      setDraft('')
    } catch {
      setError(ASK_ERROR)
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void send(draft)
  }

  return (
    <div className="scrim" onClick={onClose}>
      <section
        className="about ask panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="sheet-head">
          <h1 id={titleId}>Ask PathPro</h1>
          <button type="button" className="icon-btn ghost" aria-label="Close Ask PathPro" onClick={onClose}>
            <Icon name="close" />
          </button>
        </header>
        <p className="faint">Questions about how PathPro works, answered from its model card and docs.</p>
        <div className="ask-suggestions" aria-label="Suggested questions" role="group">
          {ASK_SUGGESTIONS.map((q) => (
            <button key={q} type="button" className="chip" disabled={loading} onClick={() => void send(q)}>
              {q}
            </button>
          ))}
        </div>
        <div className="ask-log" role="log" aria-live="polite" aria-label="Answers">
          {turns.map((t) => (
            <div key={t.id} className="ask-turn">
              <p className="ask-q">{t.question}</p>
              <p className="ask-a">{t.answer}</p>
            </div>
          ))}
        </div>
        <p className="ask-status" role="status">
          {loading ? LOADING : (error ?? '')}
        </p>
        {note && <p className="faint ask-note">{note}</p>}
        <form className="ask-form" onSubmit={onSubmit}>
          <label htmlFor={inputId} className="sr-only">
            Your question
          </label>
          <input
            ref={inputRef}
            id={inputId}
            type="text"
            value={draft}
            maxLength={MAX_CHARS}
            placeholder="Ask about PathPro…"
            autoComplete="off"
            onChange={(e) => setDraft(e.target.value)}
            autoFocus
          />
          <button type="submit" className="btn primary small" disabled={loading}>
            Ask
          </button>
        </form>
      </section>
    </div>
  )
}
