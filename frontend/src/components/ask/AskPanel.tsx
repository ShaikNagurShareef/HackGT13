import { Fragment, useId, useRef, useState, type FormEvent } from 'react'
import { api } from '../../api/client'
import type { AskContext, AskSource } from '../../api/schemas'
import { useDialog } from '../../hooks/useDialog'
import { readAskThread, useAskMemory, writeAskThread } from '../../lib/askMemory'
import { Icon } from '../ui/Icon'
import { AskMemoryControls } from './AskMemoryControls'

export { ASK_THREAD_KEY } from '../../lib/askMemory'

/**
 * Ask PathPro: questions about how PathPro works, and about the street, route, or City Pulse area
 * on screen, answered by a Backboard assistant from the model card and docs. The browser only
 * names the context; the server builds the evidence and validates every answer (or sends a
 * fixed fallback). The server-signed thread token lives in this tab's sessionStorage only;
 * opt-in memory is a separate, browser-level token (see AskMemoryControls).
 */
export const ASK_SUGGESTIONS = [
  "Why isn't crime used for routing?",
  'How was the model tested?',
  "What does '54% less traffic risk' mean?",
] as const
export const ASK_CONTEXT_SUGGESTIONS: Record<AskContext['kind'], readonly string[]> = {
  segment: ['Why is this street high-risk at this hour?', 'What would lower the risk here?'],
  route: ['Why is this route longer?', 'Which stretches did it avoid?'],
  area: ['What drives traffic risk in this area?'],
}
const CONTEXT_NOUN: Record<AskContext['kind'], string> = { segment: 'street', route: 'route', area: 'area' }
export const ASK_ERROR = "Ask PathPro can't answer right now. About PathPro has the model card."
const LOADING = "Looking through PathPro's docs…"
const MIN_CHARS = 3
const MAX_CHARS = 300

interface Turn {
  id: number
  question: string
  answer: string
  sources: readonly AskSource[]
  memory: boolean
}

function droppedMessage(kind: AskContext['kind']): string {
  return `That ${CONTEXT_NOUN[kind]} is no longer available, so I answered in general.`
}

function Sources({ sources }: { sources: readonly AskSource[] }) {
  if (sources.length === 0) return null
  return (
    <p className="faint ask-sources">
      Sources:{' '}
      {sources.map((s, i) => (
        <Fragment key={`${i}-${s.url}`}>
          {i > 0 && ' · '}
          <a href={s.url} target="_blank" rel="noopener noreferrer">
            {s.label}
          </a>
        </Fragment>
      ))}
    </p>
  )
}

export interface AskPanelProps {
  onClose: () => void
  /** What is on screen; the person can clear it with the chip's × to ask in general. */
  context?: AskContext | null
  /** Chip text after "About:", e.g. "10th St NW · 9 PM" or "this route". */
  contextLabel?: string
}

export function AskPanel({ onClose, context: initialContext = null, contextLabel = 'this' }: AskPanelProps) {
  const titleId = useId()
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const nextId = useRef(0)
  const memory = useAskMemory()
  const [context, setContext] = useState<AskContext | null>(initialContext)
  const [draft, setDraft] = useState('')
  const [turns, setTurns] = useState<readonly Turn[]>([])
  const [note, setNote] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  useDialog(onClose)

  const suggestions = context ? ASK_CONTEXT_SUGGESTIONS[context.kind] : ASK_SUGGESTIONS

  const clearContext = () => {
    setContext(null)
    inputRef.current?.focus()
  }

  const send = async (raw: string) => {
    const question = raw.trim()
    if (loading || question.length < MIN_CHARS) return
    setLoading(true)
    setMessage(null)
    try {
      const memoryToken = memory?.on ? memory.token : null
      const reply = await api.ask(question.slice(0, MAX_CHARS), readAskThread(), { context, memoryToken })
      writeAskThread(reply.thread_id)
      nextId.current += 1
      const turn: Turn = {
        id: nextId.current,
        question,
        answer: reply.answer,
        sources: reply.sources,
        memory: reply.memory === 'on',
      }
      setTurns((prev) => [...prev, turn])
      setNote(reply.note)
      setDraft('')
      if (reply.context_dropped && context) {
        setMessage(droppedMessage(context.kind))
        setContext(null)
      }
    } catch {
      setMessage(ASK_ERROR)
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
        {context && (
          <div className="ask-context">
            <span>About: {contextLabel}</span>
            <button
              type="button"
              className="icon-btn ghost ask-context-clear"
              aria-label={`Stop asking about ${contextLabel}`}
              onClick={clearContext}
            >
              ×
            </button>
          </div>
        )}
        <div className="ask-suggestions" aria-label="Suggested questions" role="group">
          {suggestions.map((q) => (
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
              {t.memory && <span className="ask-tag">Memory on</span>}
              <Sources sources={t.sources} />
            </div>
          ))}
        </div>
        <p className="ask-status" role="status">
          {loading ? LOADING : (message ?? '')}
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
        <AskMemoryControls memory={memory} onMessage={setMessage} />
      </section>
    </div>
  )
}
