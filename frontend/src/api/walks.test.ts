import { afterEach, describe, expect, it, vi } from 'vitest'
import { sharedWalk } from '../test/walkFixtures'
import { walksApi } from './walks'

function respond(body: unknown) {
  const fetcher = vi.fn(
    async () => new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } }),
  )
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

function call(fetcher: ReturnType<typeof respond>, i = 0): [string, RequestInit] {
  return fetcher.mock.calls[i] as unknown as [string, RequestInit]
}

describe('walks api', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('creates a shared walk', async () => {
    const created = { walk_id: 'w1', owner_token: 't1', follow_path: '/follow/w1', expires_at: '2026-09-27T04:30:00Z' }
    const fetcher = respond({ success: true, data: created })

    const out = await walksApi.create({
      destination: { label: 'Midtown MARTA', lat: 33.781, lon: -84.3863 },
      eta_s: 720,
      route: [[-84.39, 33.77]],
    })

    expect(out).toEqual(created)
    const [url, init] = call(fetcher)
    expect(url).toBe('/api/walks')
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toMatchObject({ eta_s: 720, route: [[-84.39, 33.77]] })
  })

  it('puts owner position updates', async () => {
    const summary = { ...sharedWalk() } as Record<string, unknown>
    delete summary.route
    const fetcher = respond({ success: true, data: summary })

    const out = await walksApi.update('w1', 'secret', { lat: 33.77, lon: -84.39, accuracy_m: 8, eta_s: 600, status: 'walking' })

    expect(out.status).toBe('walking')
    const [url, init] = call(fetcher)
    expect(url).toBe('/api/walks/w1/position')
    expect(init.method).toBe('PUT')
    expect(JSON.parse(String(init.body))).toEqual({
      owner_token: 'secret',
      lat: 33.77,
      lon: -84.39,
      accuracy_m: 8,
      eta_s: 600,
      status: 'walking',
    })
  })

  it('reads a walk for followers and validates it', async () => {
    const fetcher = respond({ success: true, data: sharedWalk() })

    const walk = await walksApi.get('w1')

    expect(walk.destination.label).toBe('Midtown MARTA')
    expect(walk.route).toHaveLength(3)
    expect(call(fetcher)[0]).toBe('/api/walks/w1')
  })

  it('escapes walk ids in paths', async () => {
    const fetcher = respond({ success: true, data: sharedWalk() })

    await walksApi.get('a/b')

    expect(call(fetcher)[0]).toBe('/api/walks/a%2Fb')
  })

  it('surfaces expired walks as WALK_NOT_FOUND', async () => {
    respond({ success: false, error: { code: 'WALK_NOT_FOUND', message: 'expired' } })

    await expect(walksApi.get('w1')).rejects.toMatchObject({ code: 'WALK_NOT_FOUND' })
  })

  describe('end', () => {
    function walkThenOk(walk: ReturnType<typeof sharedWalk>) {
      const summary = { ...walk, status: 'ended' } as Record<string, unknown>
      delete summary.route
      const fetcher = vi.fn(async (_url: string, init?: RequestInit) => {
        const data = init?.method === 'PUT' ? summary : walk
        return new Response(JSON.stringify({ success: true, data }), { headers: { 'content-type': 'application/json' } })
      })
      vi.stubGlobal('fetch', fetcher)
      return fetcher
    }

    it('marks the walk ended at the last shared position, never a new one', async () => {
      const fetcher = walkThenOk(sharedWalk())

      await walksApi.end('w1', 'secret')

      const [url, init] = fetcher.mock.calls[1] as unknown as [string, RequestInit]
      expect(url).toBe('/api/walks/w1/position')
      expect(JSON.parse(String(init.body))).toEqual({
        owner_token: 'secret',
        lat: 33.7775,
        lon: -84.395,
        accuracy_m: 9,
        status: 'ended',
      })
    })

    it('uses the destination when no position was ever shared', async () => {
      const fetcher = walkThenOk(sharedWalk({ position: null }))

      await walksApi.end('w1', 'secret')

      const body = JSON.parse(String((fetcher.mock.calls[1] as unknown as [string, RequestInit])[1].body))
      expect(body).toMatchObject({ lat: 33.781, lon: -84.3863, status: 'ended' })
    })

    it('leaves a walk that already finished alone', async () => {
      const fetcher = walkThenOk(sharedWalk({ status: 'arrived' }))

      await walksApi.end('w1', 'secret')

      expect(fetcher).toHaveBeenCalledTimes(1)
    })
  })
})
