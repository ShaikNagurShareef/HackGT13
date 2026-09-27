/** Voice output: the server voice (Grok, then ElevenLabs), falling back to the device voice (VOX-01/03/04). */

import { apiBase } from '../api/client'
import { isDemoMode } from '../api/demo'

export type SpeakRequest =
  | { kind: 'route'; route_key: string }
  | { kind: 'segment'; seg_id: number; t: string; cond: string }

let current: HTMLAudioElement | null = null

export function deviceSpeak(text: string): boolean {
  const synth = typeof window !== 'undefined' ? window.speechSynthesis : undefined
  if (!synth || typeof SpeechSynthesisUtterance === 'undefined') return false
  synth.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.rate = 1.02
  synth.speak(utterance)
  return true
}

export function stopSpeaking(): void {
  current?.pause()
  current = null
  window.speechSynthesis?.cancel()
}

/**
 * Must be called from a user gesture (VOX-03: no autoplay). Tries the server voice first,
 * then the device voice with the same validated text. Returns which voice spoke.
 */
export async function speak(request: SpeakRequest, fallbackText: string): Promise<'server' | 'device' | 'none'> {
  stopSpeaking()
  if (!isDemoMode()) {
    try {
      const resp = await fetch(`${apiBase()}/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      })
      if (resp.ok && (resp.headers.get('content-type') ?? '').includes('audio')) {
        const url = URL.createObjectURL(await resp.blob())
        current = new Audio(url)
        current.addEventListener('ended', () => URL.revokeObjectURL(url), { once: true })
        await current.play()
        return 'server'
      }
    } catch {
      // fall through to the device voice
    }
  }
  return deviceSpeak(fallbackText) ? 'device' : 'none'
}

/**
 * A navigation alert: the prefetched server-voice clip when there is one, else the device voice
 * speaking `fallbackText` (which also carries the live distance). The clip URL stays owned by
 * its prefetch cache, so it is not revoked here.
 */
export async function playAlert(clipUrl: string | null, fallbackText: string): Promise<'server' | 'device' | 'none'> {
  stopSpeaking()
  if (clipUrl) {
    try {
      current = new Audio(clipUrl)
      await current.play()
      return 'server'
    } catch {
      // autoplay blocked or the clip failed: the device voice still speaks the alert
    }
  }
  return deviceSpeak(fallbackText) ? 'device' : 'none'
}
