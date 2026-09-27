/**
 * Ask PathPro storage: the opt-in memory token (this browser, localStorage) and the
 * conversation thread token (this tab, sessionStorage).
 *
 * Privacy: the memory token names a private Backboard assistant that keeps only what the person
 * types into Ask PathPro; it is off by default and "Forget me" deletes it on the server.
 * Resilience: every storage read/write is try/catch + validated, so corrupt or blocked storage
 * degrades to "no memory" / "new thread" and never throws into the UI.
 */

import { useMemo, useSyncExternalStore } from 'react'
import { z } from 'zod'
import { ApiError, api } from '../api/client'
import { ASK_THREAD_TOKEN_RE } from '../api/schemas'

export const ASK_MEMORY_KEY = 'pathpro:ask-memory:v1'
export const ASK_THREAD_KEY = 'pathpro:ask-thread'

/** `on: false` pauses memory without deleting it; only Forget me deletes. */
export interface AskMemory {
  token: string
  on: boolean
}

const askMemorySchema = z.object({ token: z.string().regex(ASK_THREAD_TOKEN_RE), on: z.boolean() })

/** Failures worth a retry: the memory may still exist, so the token is kept. */
const RETRYABLE_CODES = new Set(['NETWORK', 'SERVER', 'BAD_RESPONSE', 'ASK_UNAVAILABLE', 'RATE_LIMITED'])

const listeners = new Set<() => void>()
function notify(): void {
  for (const listener of listeners) listener()
}

function localStore(storage?: Storage): Storage | null {
  if (storage) return storage
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null // storage blocked (privacy mode / sandboxed iframe)
  }
}

function sessionStore(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage
  } catch {
    return null
  }
}

function readRaw(storage?: Storage): string | null {
  try {
    return localStore(storage)?.getItem(ASK_MEMORY_KEY) ?? null
  } catch {
    return null
  }
}

function parseMemory(raw: string | null): AskMemory | null {
  if (raw == null) return null
  try {
    const parsed = askMemorySchema.safeParse(JSON.parse(raw))
    return parsed.success ? parsed.data : null
  } catch {
    return null // corrupt JSON: behave as if memory was never turned on
  }
}

export function readAskMemory(storage?: Storage): AskMemory | null {
  return parseMemory(readRaw(storage))
}

export function writeAskMemory(memory: AskMemory, storage?: Storage): void {
  const parsed = askMemorySchema.safeParse(memory)
  if (!parsed.success) return
  try {
    localStore(storage)?.setItem(ASK_MEMORY_KEY, JSON.stringify(parsed.data))
  } catch {
    // Quota exceeded or storage blocked: memory just won't carry over to the next visit.
  }
  notify()
}

export function clearAskMemory(storage?: Storage): void {
  try {
    localStore(storage)?.removeItem(ASK_MEMORY_KEY)
  } catch {
    // Blocked storage never held a token.
  }
  notify()
}

export function readAskThread(): string | null {
  try {
    const value = sessionStore()?.getItem(ASK_THREAD_KEY) ?? null
    return value && ASK_THREAD_TOKEN_RE.test(value) ? value : null
  } catch {
    return null
  }
}

export function writeAskThread(threadId: string | null): void {
  try {
    if (threadId) sessionStore()?.setItem(ASK_THREAD_KEY, threadId)
    else sessionStore()?.removeItem(ASK_THREAD_KEY)
  } catch {
    // Blocked storage: the conversation just won't continue across questions.
  }
}

/**
 * Deletes the memory on the server, then the token and the thread here. A token the server
 * rejects is cleared too (there is nothing left to delete); a retryable failure keeps it.
 */
export async function forgetAskMemory(): Promise<'deleted' | 'failed'> {
  const memory = readAskMemory()
  if (!memory) return 'deleted'
  try {
    await api.askMemoryForget(memory.token)
  } catch (err) {
    const code = err instanceof ApiError ? err.code : 'NETWORK'
    if (RETRYABLE_CODES.has(code)) return 'failed'
  }
  clearAskMemory()
  writeAskThread(null)
  return 'deleted'
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** The stored memory, kept in sync with writes from any component in this tab. */
export function useAskMemory(): AskMemory | null {
  const raw = useSyncExternalStore(subscribe, () => readRaw(), () => null)
  return useMemo(() => parseMemory(raw), [raw])
}
