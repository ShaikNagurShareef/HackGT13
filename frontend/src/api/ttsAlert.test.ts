import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './client'

const KEY = 'aaaaaaaaaaaaaaaa'

describe('api.ttsAlert (Grok Voice navigation alerts)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    window.history.replaceState(null, '', '/')
  })

  it('names only the route, alert index, and route kind; never any text', async () => {
    const fetcher = vi.fn(async () => new Response('mp3', { headers: { 'content-type': 'audio/mpeg' } }))
    vi.stubGlobal('fetch', fetcher)

    const clip = await api.ttsAlert(KEY, 3, 'fast')

    expect(clip).toBeInstanceOf(Blob)
    const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/tts/alert')
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({ route_key: KEY, index: 3, kind: 'fast' })
  })

  it('rejects when the server has no voice, so the device voice speaks instead', async () => {
    const body = JSON.stringify({ success: false, data: null, error: { code: 'TTS_UNAVAILABLE', message: 'x' } })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(body, { status: 503, headers: { 'content-type': 'application/json' } })))

    await expect(api.ttsAlert(KEY, 0, 'pp')).rejects.toMatchObject({ code: 'TTS_UNAVAILABLE' })
  })

  it('rejects a non-audio success body', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html></html>', { headers: { 'content-type': 'text/html' } })))

    await expect(api.ttsAlert(KEY, 0, 'pp')).rejects.toMatchObject({ code: 'TTS_UNAVAILABLE' })
  })

  it('never touches the network in demo mode', async () => {
    window.history.replaceState(null, '', '/?demo=1')
    const fetcher = vi.fn()
    vi.stubGlobal('fetch', fetcher)

    await expect(api.ttsAlert(KEY, 0, 'pp')).rejects.toMatchObject({ code: 'DEMO' })
    expect(fetcher).not.toHaveBeenCalled()
  })
})
