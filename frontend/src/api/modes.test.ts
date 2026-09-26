import { afterEach, describe, expect, it, vi } from 'vitest'
import { routes } from '../test/fixtures'
import { api } from './client'
import { demoResponse, fixtureKey, loadFixtures, resetFixturesForTests } from './demo'
import { envelope, metaSchema, routesSchema } from './schemas'

function respond(body: unknown) {
  const fetcher = vi.fn(
    async () => new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } }),
  )
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

const BIKE = { key: 'bike', label: 'Bike', available: true, speed_kmh: 15, network: 'ride', static_prefix: 'ride_' }
const ROUTE_BODY = {
  origin: { lat: 33.7771, lon: -84.3962 },
  destination: { lat: 33.781, lon: -84.3863 },
  cond: 'wet',
}

describe('transport modes: schemas', () => {
  const baseMeta = {
    model_version: 'v',
    data_through: '2026-09-19',
    n_segments: 3,
    coverage_bbox: [0, 0, 1, 1],
    day_groups: [],
    conditions: [],
    reference_dates: {},
    frame_light: {},
    static_base: '/static/v',
    headline: {},
    spatial_factors: [],
    temporal_factors: [],
  }

  it('parses meta without modes (old servers, recorded demo) as walk only', () => {
    const meta = metaSchema.parse(baseMeta)

    expect(meta.modes).toEqual([])
    expect(meta.ride_model).toBeNull()
  })

  it('keeps well-formed modes and drops unknown or hostile ones', () => {
    const meta = metaSchema.parse({
      ...baseMeta,
      modes: [BIKE, { ...BIKE, key: 'bus' }, { ...BIKE, key: 'scooter', static_prefix: '../x' }],
      ride_model: { version: 'r1' },
    })

    expect(meta.modes).toEqual([BIKE])
    expect(meta.ride_model).toEqual({ version: 'r1' })
  })

  it('reads the route mode, defaulting to walk', () => {
    const { mode: _omit, ...legacy } = routes()

    expect(routesSchema.parse(legacy).mode).toBe('walk')
    expect(routesSchema.parse({ ...legacy, mode: 'scooter' }).mode).toBe('scooter')
  })
})

describe('transport modes: client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sends mode only for ride modes, and the preference only for walks', async () => {
    const fetcher = respond({ success: true, data: routes() })

    await api.routes({ lat: 1, lon: 2 }, { lat: 3, lon: 4 }, 'now', 'wet', 'lit_and_busy', 'bike')
    await api.routes({ lat: 1, lon: 2 }, { lat: 3, lon: 4 }, 'now', 'wet', 'lit_and_busy', 'walk')

    const body = (i: number) => JSON.parse(String((fetcher.mock.calls[i] as unknown as [string, RequestInit])[1].body))
    expect(body(0)).toMatchObject({ mode: 'bike' })
    expect(body(0)).not.toHaveProperty('prefer')
    expect(body(1)).toMatchObject({ prefer: 'lit_and_busy' })
    expect(body(1)).not.toHaveProperty('mode')
  })

  it('asks for ride segment detail with the mode', async () => {
    const fetcher = respond({ success: false, error: { code: 'X', message: 'x' } })

    await api.segment(7, 'now', 'dry', 'scooter').catch(() => undefined)
    await api.segment(7, 'now', 'dry').catch(() => undefined)

    expect((fetcher.mock.calls[0] as unknown as [string])[0]).toBe('/api/segments/7?t=now&cond=dry&mode=scooter')
    expect((fetcher.mock.calls[1] as unknown as [string])[0]).toBe('/api/segments/7?t=now&cond=dry')
  })

  it('loads MARTA rail stations', async () => {
    const fetcher = respond({ success: true, data: [{ name: 'North Ave', lat: 33.77, lon: -84.38, lines: ['Red'] }] })

    const stations = await api.transitStations()

    expect(stations[0].name).toBe('North Ave')
    expect((fetcher.mock.calls[0] as unknown as [string])[0]).toBe('/api/transit/stations')
  })
})

describe('transport modes: offline demo', () => {
  afterEach(() => {
    resetFixturesForTests()
    vi.unstubAllGlobals()
  })

  it('keys ride routes and ride segments by mode (walk keys unchanged)', () => {
    expect(fixtureKey('POST', '/routes', JSON.stringify({ ...ROUTE_BODY, mode: 'bike' }))).toBe(
      'POST /routes 33.7771,-84.3962>33.7810,-84.3863|wet|bike',
    )
    expect(fixtureKey('POST', '/routes', JSON.stringify({ ...ROUTE_BODY, mode: 'walk' }))).toBe(
      'POST /routes 33.7771,-84.3962>33.7810,-84.3863|wet',
    )
    expect(fixtureKey('GET', '/segments/4?t=now&cond=dry&mode=ebike')).toBe('GET /segments/4|dry|ebike')
  })

  it('answers unrecorded ride routes with MODE_UNAVAILABLE', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({}))))

    const raw = await demoResponse('POST', '/routes', JSON.stringify({ ...ROUTE_BODY, mode: 'bike' }))

    expect(raw).toMatchObject({ success: false, error: { code: 'MODE_UNAVAILABLE' } })
  })

  it('serves MARTA stations from a recorded fixture, else the bundled list', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({}))))
    const bundled = (await demoResponse('GET', '/transit/stations')) as { success: boolean; data: unknown[] }
    expect(bundled.success).toBe(true)
    expect(bundled.data.length).toBeGreaterThan(10)

    resetFixturesForTests()
    const recorded = { success: true, data: [{ name: 'Midtown', lat: 1, lon: 2 }] }
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ 'GET /transit/stations': recorded }))))
    await loadFixtures()
    expect(await demoResponse('GET', '/transit/stations')).toEqual(recorded)
  })

  it('recorded demo meta still parses and offers walk only', async () => {
    const { readFileSync } = await import('node:fs')
    const fixtures = JSON.parse(readFileSync('public/demo/fixtures.json', 'utf8')) as Record<string, unknown>
    const parsed = envelope(metaSchema).parse(fixtures['GET /meta'])

    expect(Array.isArray(parsed.data?.modes)).toBe(true)
  })
})
