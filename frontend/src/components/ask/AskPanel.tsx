import { Fragment, useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { api } from '../../api/client'
import type { AskContext, AskSource } from '../../api/schemas'
import { useDialog } from '../../hooks/useDialog'
import { readAskThread, useAskMemory, writeAskThread } from '../../lib/askMemory'
import { Icon, type IconName } from '../ui/Icon'
import { AgentGlyph } from './AgentGlyph'
import { AskMemoryControls } from './AskMemoryControls'

export { ASK_THREAD_KEY } from '../../lib/askMemory'

/**
 * Ask PathPro: questions about how PathPro works, and about the street, route, or City Pulse area
 * on screen, answered by a Backboard assistant from the model card and docs. The browser only
 * names the context; the server builds the evidence and validates every answer (or sends a
 * fixed fallback). The server-signed thread token lives in this tab's sessionStorage only;
 * opt-in memory is a separate, browser-level token (see AskMemoryControls).
 *
 * Layout: a chat card docked bottom-right on wide screens, a tall bottom sheet on phones.
 */
export const ASK_SUGGESTIONS = ['What does the risk score mean?', 'How do I use PathPro?', 'How was the model tested?'] as const
export const ASK_CONTEXT_SUGGESTIONS: Record<AskContext['kind'], readonly string[]> = {
  segment: ['Why is this street high-risk at this hour?', 'What would lower the risk here?'],
  route: ['Why is this route longer?', 'Which stretches did it avoid?'],
  area: ['What drives traffic risk in this area?'],
}
const CONTEXT_NOUN: Record<AskContext['kind'], string> = { segment: 'street', route: 'route', area: 'area' }
const CONTEXT_ICON: Record<AskContext['kind'], IconName> = { segment: 'pin', route: 'flag', area: 'layers' }
export const ASK_ERROR = "Ask PathPro can't answer right now. About PathPro has the model card."
const INTRO = 'Questions about how PathPro works, answered from its model card and docs.'
const LOADING = "Looking through PathPro's docs…"
const MIN_CHARS = 3
const MAX_CHARS = 300

interface Turn {
  id: number
  question: string
  answer: string
  sources: readonly AskSource[]
  memory: boolean
  fallback: boolean
}

function droppedMessage(kind: AskContext['kind']): string {
  return `That ${CONTEXT_NOUN[kind]} is no longer available, so I answered in general.`
}

function Sources({ sources }: { sources: readonly AskSource[] }) {
  if (sources.length === 0) return null
  return (
    <p className="ask-sources">
      <span className="ask-sources-label">Sources:</span>{' '}
      {sources.map((s, i) => (
        <Fragment key={`${i}-${s.url}`}>
          {i > 0 && <span className="sr-only"> · </span>}
          <a className="ask-source" href={s.url} target="_blank" rel="noopener noreferrer">
            {s.label}
          </a>
        </Fragment>
      ))}
    </p>
  )
}

function Avatar() {
  return (
    <span className="ask-avatar ask-avatar-sm" aria-hidden="true">
      <AgentGlyph size={16} />
    </span>
  )
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="ask-msg ask-msg-user">
      <p className="ask-bubble ask-q">{text}</p>
    </div>
  )
}

function AnswerBubble({ turn }: { turn: Turn }) {
  return (
    <div className="ask-msg ask-msg-bot" data-variant={turn.fallback ? 'fallback' : 'answer'}>
      <Avatar />
      <div className="ask-msg-body">
        <p className="ask-bubble ask-a">{turn.answer}</p>
        {turn.memory && <span className="ask-tag">Memory on</span>}
        <Sources sources={turn.sources} />
      </div>
    </div>
  )
}

function Typing() {
  return (
    <div className="ask-msg ask-msg-bot" data-testid="ask-typing">
      <Avatar />
      <span className="ask-bubble ask-typing" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
    </div>
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
  const scrollRef = useRef<HTMLDivElement>(null)
  const nextId = useRef(0)
  const memory = useAskMemory()
  const [context, setContext] = useState<AskContext | null>(initialContext)
  const [draft, setDraft] = useState('')
  const [turns, setTurns] = useState<readonly Turn[]>([])
  const [pending, setPending] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const loading = pending !== null
  useDialog(onClose)

  // Keep the newest message in view: the typing dots while waiting, then the new answer's question.
  useEffect(() => {
    const body = scrollRef.current
    if (!body) return
    const last = body.querySelector<HTMLElement>('.ask-log > :last-child')
    if (loading || !last) body.scrollTop = body.scrollHeight
    else body.scrollTop = Math.max(0, last.offsetTop - 8) // .ask-scroll is the offsetParent
  }, [turns, loading])

  const suggestions = context ? ASK_CONTEXT_SUGGESTIONS[context.kind] : ASK_SUGGESTIONS

  const clearContext = () => {
    setContext(null)
    inputRef.current?.focus()
  }

  const send = async (raw: string) => {
    const question = raw.trim()
    if (loading || question.length < MIN_CHARS) return
    setPending(question)
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
        fallback: reply.source === 'fallback',
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
      setPending(null)
      inputRef.current?.focus()
    }
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void send(draft)
  }

  return (
    <div className="scrim ask-scrim" onClick={onClose}>
      <section
        className="ask panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <span className="ask-grip" aria-hidden="true" />
        <header className="ask-head">
          <span className="ask-avatar" aria-hidden="true">
            <AgentGlyph size={22} />
          </span>
          <div className="ask-title">
            <h1 id={titleId}>Ask PathPro</h1>
            <p className="ask-powered">Powered by Backboard</p>
          </div>
          <button type="button" className="icon-btn ghost" aria-label="Close Ask PathPro" onClick={onClose}>
            <Icon name="close" />
          </button>
        </header>
        {context && (
          <div className="ask-context">
            <Icon name={CONTEXT_ICON[context.kind]} size={15} />
            <span>About: {contextLabel}</span>
            <button
              type="button"
              className="ask-context-clear"
              aria-label={`Stop asking about ${contextLabel}`}
              onClick={clearContext}
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        )}
        <div className="ask-scroll" ref={scrollRef}>
          <div className="ask-msg ask-msg-bot ask-intro">
            <Avatar />
            <p className="ask-bubble">{INTRO}</p>
          </div>
          <div className="ask-log" role="log" aria-live="polite" aria-label="Answers">
            {turns.map((t) => (
              <div key={t.id} className="ask-turn">
                <UserBubble text={t.question} />
                <AnswerBubble turn={t} />
              </div>
            ))}
            {pending !== null && (
              <div className="ask-turn">
                <UserBubble text={pending} />
                <Typing />
              </div>
            )}
          </div>
          <p className={loading ? 'ask-status sr-only' : 'ask-status'} role="status">
            {loading ? LOADING : (message ?? '')}
          </p>
          {note && <p className="ask-note">{note}</p>}
        </div>
        <div className="ask-suggestions" aria-label="Suggested questions" role="group">
          {suggestions.map((q) => (
            <button key={q} type="button" className="chip ask-suggestion" disabled={loading} onClick={() => void send(q)}>
              {q}
            </button>
          ))}
        </div>
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
            enterKeyHint="send"
            onChange={(e) => setDraft(e.target.value)}
            autoFocus
          />
          <button type="submit" className="ask-send" aria-label="Send" disabled={loading}>
            <SendIcon />
          </button>
        </form>
        <AskMemoryControls memory={memory} onMessage={setMessage} />
      </section>
    </div>
  )
}

function SendIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M12 19V5M5.5 11.5 12 5l6.5 6.5" />
    </svg>
  )
}
