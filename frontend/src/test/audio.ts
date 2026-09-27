import { vi } from 'vitest'

/** Blob URLs are numbered in creation order so tests can follow each clip. */
export function stubBlobUrls() {
  let n = 0
  const create = vi.fn(() => `blob:clip-${n++}`)
  const revoke = vi.fn()
  vi.stubGlobal('URL', Object.assign(class extends URL {}, { createObjectURL: create, revokeObjectURL: revoke }))
  return { create, revoke }
}

/** An <audio> stand-in that records what it was asked to play; `fail` mimics a blocked autoplay. */
export function stubAudio(fail = false) {
  const sources: string[] = []
  const play = vi.fn(async () => {
    if (fail) throw new Error('NotAllowedError')
  })
  vi.stubGlobal(
    'Audio',
    class {
      play = play
      pause = vi.fn()
      addEventListener = vi.fn()
      constructor(src: string) {
        sources.push(src)
      }
    },
  )
  return { play, sources }
}

/** Device voice stand-in; returns the spy whose calls hold the spoken utterances. */
export function stubSpeech() {
  const speak = vi.fn()
  vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), speak })
  vi.stubGlobal('SpeechSynthesisUtterance', class { text: string; constructor(text: string) { this.text = text } })
  return speak
}

export const spokenTexts = (speak: ReturnType<typeof vi.fn>): string[] =>
  speak.mock.calls.map(([u]) => (u as { text: string }).text)
