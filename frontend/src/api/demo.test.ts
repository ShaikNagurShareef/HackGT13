import { afterEach, describe, expect, it, vi } from 'vitest'
import { demoResponse, fixtureKey, isDemoMode, loadFixtures, resetFixturesForTests } from './demo'

describe('demo transport', () => {
  afterEach(() => {
    resetFixturesForTests()
    vi.unstubAllGlobals()
  })

  it('detects demo mode from the query string', () => {
    expect(isDemoMode('?demo=1')).toBe(true)
    expect(isDemoMode('?demo=0')).toBe(false)
  })

  it('maps requests to recorded fixture keys', () => {
    const body = JSON.stringify({
      origin: { lat: 33.7771, lon: -84.3962 },
      destination: { lat: 33.781, lon: -84.3863 },
      cond: 'wet',
    })
    expect(fixtureKey('POST', '/routes', body)).toBe('POST /routes 33.7771,-84.3962>33.7810,-84.3863|wet')
    expect(fixtureKey('GET', '/segments/42?t=now&cond=dry')).toBe('GET /segments/42|dry')
    expect(fixtureKey('GET', '/meta')).toBe('GET /meta')
    expect(fixtureKey('POST', '/explain', JSON.stringify({ kind: 'route', route_key: 'ab' }))).toBe(
      'POST /explain route:ab',
    )
    expect(fixtureKey('POST', '/explain', JSON.stringify({ kind: 'segment', seg_id: 7, cond: 'wet' }))).toBe(
      'POST /explain segment:7|wet',
    )
    expect(fixtureKey('DELETE', '/meta')).toBeNull()
  })

  it('answers from fixtures fetched once, and explains unknown requests', async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ 'GET /meta': { success: true } })))
    vi.stubGlobal('fetch', fetcher)

    await loadFixtures()
    expect(await demoResponse('GET', '/meta')).toEqual({ success: true })
    expect(await demoResponse('GET', '/segments/1?cond=wet')).toMatchObject({ error: { code: 'DEMO_ONLY' } })
    expect(await demoResponse('GET', '/geocode?q=x')).toEqual({ success: true, data: [], error: null })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
})
