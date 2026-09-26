/**
 * Share my walk survives a reload: the live share session (including the owner token) is kept
 * in sessionStorage, so it stays with this tab only and is gone when the tab closes. It never
 * goes in localStorage or the URL. Every access is try/catch'd (storage can be blocked) and
 * reads are zod-validated; anything corrupt or expired is dropped.
 */

import { z } from 'zod'

export const SHARE_SESSION_KEY = 'pathpro:share-walk'
/** ~1 m: a destination read back from the URL may carry rounding noise. */
const SAME_PLACE_DEG = 1e-5

const MAX_ID_CHARS = 128
const MAX_TOKEN_CHARS = 256

export const storedShareSchema = z.object({
  walk_id: z.string().min(1).max(MAX_ID_CHARS),
  owner_token: z.string().min(1).max(MAX_TOKEN_CHARS),
  follow_path: z.string().min(1),
  expires_at: z.string().refine((s) => Number.isFinite(Date.parse(s))),
  destination: z.object({ label: z.string(), lat: z.number(), lon: z.number() }),
})
export type StoredShareSession = z.infer<typeof storedShareSchema>

type LatLon = { lat: number; lon: number }

function resolveStorage(storage?: Storage): Storage | null {
  if (storage) return storage
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage
  } catch {
    return null // storage blocked (privacy mode / sandboxed iframe)
  }
}

function readRaw(storage: Storage | null): unknown {
  if (!storage) return null
  try {
    const raw = storage.getItem(SHARE_SESSION_KEY)
    return raw == null ? null : (JSON.parse(raw) as unknown)
  } catch {
    return undefined // unreadable or corrupt
  }
}

function remove(storage: Storage | null): void {
  try {
    storage?.removeItem(SHARE_SESSION_KEY)
  } catch {
    // Blocked storage: nothing was kept.
  }
}

export function saveShareSession(session: StoredShareSession, storage?: Storage): void {
  const target = resolveStorage(storage)
  try {
    target?.setItem(SHARE_SESSION_KEY, JSON.stringify(session))
  } catch {
    // Private mode or quota: sharing still works, it just won't survive a reload.
  }
}

/** The saved share session, or null when there is none, it is corrupt, or it has expired. */
export function loadShareSession(nowMs: number = Date.now(), storage?: Storage): StoredShareSession | null {
  const target = resolveStorage(storage)
  const raw = readRaw(target)
  if (raw === null) return null
  const parsed = storedShareSchema.safeParse(raw)
  if (!parsed.success || Date.parse(parsed.data.expires_at) <= nowMs) {
    remove(target)
    return null
  }
  return parsed.data
}

/** Forget the saved session; with a walk id, only if it is that walk. */
export function clearShareSession(walkId?: string, storage?: Storage): void {
  const target = resolveStorage(storage)
  if (walkId !== undefined) {
    const parsed = storedShareSchema.safeParse(readRaw(target))
    if (parsed.success && parsed.data.walk_id !== walkId) return
  }
  remove(target)
}

/** The server extends a walk on every accepted update; keep the saved expiry in step. */
export function refreshShareExpiry(walkId: string, expiresAt: string, storage?: Storage): void {
  const target = resolveStorage(storage)
  const parsed = storedShareSchema.safeParse(readRaw(target))
  if (!parsed.success || parsed.data.walk_id !== walkId) return
  saveShareSession({ ...parsed.data, expires_at: expiresAt }, target ?? undefined)
}

export function sameDestination(a: LatLon, b: LatLon | null): boolean {
  return b != null && Math.abs(a.lat - b.lat) < SAME_PLACE_DEG && Math.abs(a.lon - b.lon) < SAME_PLACE_DEG
}
