import { afterEach, describe, expect, it, vi } from 'vitest'
import { deviceSpeak, speak } from './voice'

function stubSpeech() {
  const speakSpy = vi.fn()
  vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), speak: speakSpy })
  vi.stubGlobal('SpeechSynthesisUtterance', class { text: string; constructor(text: string) { this.text = text } })
  return speakSpy
}

describe('voice (VOX-01/04)', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('falls back to the device voice when the server has no voice', async () => {
    const speakSpy = stubSpeech()
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 503, headers: { 'content-type': 'application/json' } })))

    expect(await speak({ kind: 'route', route_key: 'aaaaaaaaaaaaaaaa' }, 'fallback text')).toBe('device')
    expect(speakSpy).toHaveBeenCalledTimes(1)
  })

  it('plays server audio when available', async () => {
    stubSpeech()
    const play = vi.fn(async () => undefined)
    vi.stubGlobal('Audio', class { play = play; addEventListener = vi.fn(); pause = vi.fn() })
    vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() })
    vi.stubGlobal('fetch', vi.fn(async () => new Response('mp3', { headers: { 'content-type': 'audio/mpeg' } })))

    expect(await speak({ kind: 'segment', seg_id: 1, t: 'now', cond: 'wet' }, 'x')).toBe('server')
    expect(play).toHaveBeenCalled()
  })

  it('reports none when the device has no speech synthesis', () => {
    vi.stubGlobal('speechSynthesis', undefined)
    expect(deviceSpeak('hello')).toBe(false)
  })
})
