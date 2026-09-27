import { useId, useState } from 'react'
import { ApiError, api } from '../../api/client'
import { forgetAskMemory, writeAskMemory, writeAskThread, type AskMemory } from '../../lib/askMemory'

export const ASK_MEMORY_NOTE =
  'When on, what you type here is kept by Backboard for this browser until you tap Forget me. Your location, routes and routines are never sent.'
export const ASK_MEMORY_DELETED = 'Ask PathPro memory deleted.'
export const ASK_MEMORY_FORGET_FAILED = "Couldn't delete Ask PathPro memory right now. Please try again."
const MEMORY_LIMIT = 'Memory is full for today. Ask PathPro still answers without it.'
const MEMORY_UNAVAILABLE = "Ask PathPro can't turn on memory right now. It still answers without it."

export interface AskMemoryControlsProps {
  memory: AskMemory | null
  /** One status line for the whole panel: memory messages go there, not a second live region. */
  onMessage: (message: string | null) => void
}

/**
 * "Remember my preferences": off by default. Turning it on the first time creates this browser's
 * private memory; turning it off pauses it; Forget me deletes it. Any change starts a new thread,
 * since a thread belongs to one assistant.
 */
export function AskMemoryControls({ memory, onMessage }: AskMemoryControlsProps) {
  const noteId = useId()
  const [busy, setBusy] = useState(false)
  const on = memory?.on ?? false

  const turnOn = async () => {
    setBusy(true)
    try {
      const token = await api.askMemoryOn()
      writeAskMemory({ token, on: true })
      writeAskThread(null)
      onMessage(null)
    } catch (err) {
      onMessage(err instanceof ApiError && err.code === 'ASK_MEMORY_LIMIT' ? MEMORY_LIMIT : MEMORY_UNAVAILABLE)
    } finally {
      setBusy(false)
    }
  }

  const toggle = () => {
    if (busy) return
    if (!memory) {
      void turnOn()
      return
    }
    writeAskMemory({ ...memory, on: !memory.on })
    writeAskThread(null)
    onMessage(null)
  }

  const forget = async () => {
    setBusy(true)
    const outcome = await forgetAskMemory()
    setBusy(false)
    onMessage(outcome === 'deleted' ? ASK_MEMORY_DELETED : ASK_MEMORY_FORGET_FAILED)
  }

  return (
    <div className="ask-memory">
      <div className="options-row">
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-describedby={noteId}
          className={on ? 'chip active' : 'chip'}
          disabled={busy}
          onClick={toggle}
        >
          Remember my preferences
        </button>
        {memory && (
          <button type="button" className="link-btn" disabled={busy} onClick={() => void forget()}>
            Forget me
          </button>
        )}
      </div>
      <p id={noteId} className="faint ask-memory-note">
        {ASK_MEMORY_NOTE}
      </p>
    </div>
  )
}
