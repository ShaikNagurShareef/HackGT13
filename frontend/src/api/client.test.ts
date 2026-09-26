import { afterEach, describe, expect, it, vi } from 'vitest'
import { report, routes, segment } from '../test/fixtures'
import { ApiError, api } from './client'

function respond(body: unknown) {
  const fetcher = vi.fn(
    async () => new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } }),
  )
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

describe('api client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('posts routes and validates the envelope', async () => {
    const fetcher = respond({ success: true, data: routes(), error: null, model_version: 'v' })

    const data = await api.routes({ lat: 1, lon: 2 }, { lat: 3, lon: 4 }, 'now', 'wet')

    expect(data.exposure_reduction_pct).toBe(49)
    const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/routes')
    expect(JSON.parse(String(init.body))).toMatchObject({ depart_at: 'now', cond: 'wet' })
  })

  it('surfaces server error codes and messages', async () => {
    respond({ success: false, data: null, error: { code: 'OUT_OF_COVERAGE', message: 'PathPulse covers Midtown' } })

    await expect(api.segment(1, 'now', 'live')).rejects.toMatchObject({ code: 'OUT_OF_COVERAGE' })
  })

  it('rejects malformed payloads instead of trusting them', async () => {
    respond({ success: true, data: { score: 'high' } })

    await expect(api.segment(1, 'now', 'live')).rejects.toMatchObject({ code: 'BAD_RESPONSE' })
  })

  it('treats non-JSON gateway errors as busy, not offline', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>502</html>', { status: 502 })))

    await expect(api.meta()).rejects.toMatchObject({ code: 'SERVER' })
  })

  it('reports network failures as offline', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('failed'))))

    const err = await api.meta().catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).message).toContain("You're offline")
  })

  it('encodes explain, conditions, and geocode requests', async () => {
    const fetcher = respond({ success: true, data: { text: 'x', source: 'template' } })
    await api.explainRoute('aaaaaaaaaaaaaaaa')
    await api.explainSegment(4, 'now', 'dry')
    respond({ success: true, data: { cond: 'dry', source: 'live', label: 'Dry' } })
    expect((await api.liveConditions()).cond).toBe('dry')
    const geo = respond({ success: true, data: [] })
    await api.geocode('10th & Peachtree')

    expect(JSON.parse(String((fetcher.mock.calls[1] as unknown as [string, RequestInit])[1].body))).toEqual({
      kind: 'segment',
      seg_id: 4,
      t: 'now',
      cond: 'dry',
    })
    expect((geo.mock.calls[0] as unknown as [string])[0]).toBe('/api/geocode?q=10th%20%26%20Peachtree')
    expect(segment().score).toBe(96)
  })
})

describe('community reports client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('posts only a segment and a category', async () => {
    const fetcher = respond({ success: true, data: report({ confirmations: 1 }) })

    const saved = await api.postReport(11, 'construction')

    expect(saved.confirmations).toBe(1)
    const [url, init] = fetcher.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/reports')
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({ seg_id: 11, category: 'construction' })
  })

  it('fetches reports in a viewport and on a segment', async () => {
    const fetcher = respond({ success: true, data: [report()] })

    const inView = await api.reportsInBbox([-84.4, 33.7, -84.3, 33.8])
    const onSeg = await api.segmentReports(11)

    expect(inView).toHaveLength(1)
    expect(onSeg[0].label).toBe('Construction detour')
    expect((fetcher.mock.calls[0] as unknown as [string])[0]).toBe('/api/reports?bbox=-84.40000,33.70000,-84.30000,33.80000')
    expect((fetcher.mock.calls[1] as unknown as [string])[0]).toBe('/api/segments/11/reports')
  })

  it('routes default to no reports, and carry them when present', async () => {
    const { reports: _omit, ...legacy } = routes()
    respond({ success: true, data: legacy })
    expect((await api.routes({ lat: 1, lon: 2 }, { lat: 3, lon: 4 }, 'now', 'dry')).reports).toEqual([])

    respond({ success: true, data: routes({ reports: [report()] }) })
    expect((await api.routes({ lat: 1, lon: 2 }, { lat: 3, lon: 4 }, 'now', 'dry')).reports).toHaveLength(1)
  })

  it('surfaces REPORTS_UNAVAILABLE so the UI can hide the feature', async () => {
    respond({ success: false, error: { code: 'REPORTS_UNAVAILABLE', message: 'Community reports are unavailable' } })

    await expect(api.segmentReports(11)).rejects.toMatchObject({ code: 'REPORTS_UNAVAILABLE' })
  })
})
