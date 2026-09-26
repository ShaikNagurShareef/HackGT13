import { afterEach, describe, expect, it, vi } from 'vitest'
import { getApiOrigin, initRuntime, resetRuntimeForTests, usingFallbackDemo } from './runtime'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

describe('runtime API resolution', () => {
  afterEach(() => resetRuntimeForTests())

  it('uses a healthy live API from live.json', async () => {
    const fetcher = vi.fn(async (url: string) =>
      url.endsWith('live.json') ? json({ api: 'https://abc-def.trycloudflare.com/' }) : json({ success: true }),
    )

    await initRuntime('/PathPulse/', fetcher as unknown as typeof fetch, true)

    expect(getApiOrigin()).toBe('https://abc-def.trycloudflare.com')
    expect(usingFallbackDemo()).toBe(false)
    expect(fetcher).toHaveBeenCalledWith('https://abc-def.trycloudflare.com/api/healthz', expect.anything())
  })

  it('falls back to the demo when the live API is down or misconfigured', async () => {
    const down = vi.fn(async (url: string) => (url.endsWith('live.json') ? json({ api: 'https://x.example' }) : json({}, 502)))
    await initRuntime('/', down as unknown as typeof fetch, true)
    expect(usingFallbackDemo()).toBe(true)

    resetRuntimeForTests()
    const hostile = vi.fn(async () => json({ api: 'javascript:alert(1)' }))
    await initRuntime('/', hostile as unknown as typeof fetch, true)
    expect(usingFallbackDemo()).toBe(true)
    expect(getApiOrigin()).toBe('')
  })

  it('does nothing when live config is disabled', async () => {
    const fetcher = vi.fn()
    await initRuntime('/', fetcher as unknown as typeof fetch, false)
    expect(fetcher).not.toHaveBeenCalled()
    expect(usingFallbackDemo()).toBe(false)
  })
})
