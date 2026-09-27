/** Prefetching navigation alert clips in the server (Grok) voice, politely bounded. */

export type { AlertKind } from '../api/client'

/** Alerts past this many are spoken by the device voice; keeps a start under the paid limit. */
export const MAX_ALERT_CLIPS = 12
export const CLIP_CONCURRENCY = 2

export type ClipFetcher = (index: number, signal: AbortSignal) => Promise<Blob>

/**
 * Fetches clips 0..min(count, MAX_ALERT_CLIPS)-1, CLIP_CONCURRENCY at a time. The first failure
 * stops the rest: when the server voice is unavailable, the device voice speaks every alert.
 */
export async function prefetchClips(
  count: number,
  fetchClip: ClipFetcher,
  signal: AbortSignal,
  onClip: (index: number, clip: Blob) => void,
): Promise<void> {
  const total = Math.min(Math.max(count, 0), MAX_ALERT_CLIPS)
  let next = 0
  let failed = false
  const worker = async () => {
    while (!failed && !signal.aborted && next < total) {
      const index = next++
      try {
        const clip = await fetchClip(index, signal)
        if (!signal.aborted) onClip(index, clip)
      } catch {
        failed = true // the device voice covers this alert and the rest
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(CLIP_CONCURRENCY, total) }, worker))
}
