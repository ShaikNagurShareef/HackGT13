import { afterEach, describe, expect, it, vi } from 'vitest'
import { resetRuntimeForTests } from './runtime'
import { api } from './client'
import { demoResponse, resetFixturesForTests } from './demo'
import { routeSchema, routesSchema } from './schemas'
import { safetyApi } from './safety'
import { helpPointsSchema, safetyHexesSchema, safetyMetaSchema } from './safetySchemas'
import { helpPoint, route, routes, safetyHex, safetyMeta } from '../test/fixtures'

const JSON_HEADERS = { headers: { 'content-type': 'application/json' } }
const VIEW = [-84.4, 33.77, -84.38, 33.79] as const

function respond(body: unknown, status = 200) {
  const fetcher = vi.fn(async () => new Response(JSON.stringify(body), { ...JSON_HEADERS, status }))
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

function urlOf(fetcher: ReturnType<typeof respond>, call = 0): string {
  return (fetcher.mock.calls[call] as unknown as [string])[0]
}

describe('safety schemas', () => {
  it('parses meta, hexes, and help points from the contract', () => {
    expect(safetyMetaSchema.parse(safetyMeta()).day_parts[0].key).toBe('morning')
    expect(safetyHexesSchema.parse([safetyHex()])[0].crime_band).toBe('typical')
    expect(helpPointsSchema.parse([helpPoint()])[0].kind).toBe('blue_light')
  })

  it('fills missing lighting and activity with null', () => {
    const { lit_share: _l, activity_band: _a, ...bare } = safetyHex()
    const [hex] = safetyHexesSchema.parse([bare])
    expect(hex.lit_share).toBeNull()
    expect(hex.activity_band).toBeNull()
  })

  it('never lets a "higher" band slip through as something else', () => {
    expect(() => safetyHexesSchema.parse([safetyHex({ crime_band: 'dangerous' as never })])).toThrow()
  })

  it('drops help points of an unknown kind instead of failing the whole list', () => {
    const points = helpPointsSchema.parse([helpPoint(), { kind: 'kiosk', name: 'x', lat: 1, lon: 2 }])
    expect(points).toHaveLength(1)
  })

  it('keeps old route responses parsing: safety defaults to null', () => {
    const { safety: _s, ...old } = route()
    expect(routeSchema.parse(old).safety).toBeNull()
  })

  it('parses route safety when present, and ignores a malformed one rather than failing routing', () => {
    const withSafety = routesSchema.parse(
      routes({
        pathpro: route({
          safety: { lit_share: 0.82, busy_share: 0.6, help_points_within_100m: 3, crimes_persons_nearby: 4, day_part: 'evening' },
        }),
      }),
    )
    expect(withSafety.pathpro?.safety?.help_points_within_100m).toBe(3)
    expect(routeSchema.parse({ ...route(), safety: { lit_share: 'bright' } }).safety).toBeNull()
  })
})

describe('safety client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    resetRuntimeForTests()
    window.history.replaceState(null, '', '/')
  })

  it('fetches meta, hexes for a viewport and hour, and help points', async () => {
    const meta = respond({ success: true, data: safetyMeta() })
    expect((await safetyApi.meta()).data_through).toBe('2026-09-19')
    expect(urlOf(meta)).toBe('/api/safety/meta')

    const hexes = respond({ success: true, data: [safetyHex()] })
    expect(await safetyApi.hexes(VIEW, 21)).toHaveLength(1)
    expect(urlOf(hexes)).toBe('/api/safety/hexes?bbox=-84.40000,33.77000,-84.38000,33.79000&hour=21')

    const help = respond({ success: true, data: [helpPoint()] })
    expect(await safetyApi.helpPoints(VIEW)).toHaveLength(1)
    expect(urlOf(help)).toBe('/api/safety/help-points?bbox=-84.40000,33.77000,-84.38000,33.79000')
  })

  it('clamps the hour into 0–23', async () => {
    const fetcher = respond({ success: true, data: [] })
    await safetyApi.hexes(VIEW, 27.4)
    expect(urlOf(fetcher)).toContain('&hour=23')
  })

  it('surfaces 503 SAFETY_UNAVAILABLE from older bundles as a coded error', async () => {
    respond({ success: false, data: null, error: { code: 'SAFETY_UNAVAILABLE', message: 'No safety layer' } }, 503)
    await expect(safetyApi.meta()).rejects.toMatchObject({ code: 'SAFETY_UNAVAILABLE' })
  })

  it('treats an API without the endpoint (plain 404) as a bad response', async () => {
    respond({ detail: 'Not Found' }, 404)
    await expect(safetyApi.meta()).rejects.toMatchObject({ code: 'BAD_RESPONSE' })
  })

  it('sends a route preference only when it is not the default', async () => {
    const fetcher = respond({ success: true, data: routes() })
    await api.routes({ lat: 1, lon: 2 }, { lat: 3, lon: 4 }, 'now', 'live')
    await api.routes({ lat: 1, lon: 2 }, { lat: 3, lon: 4 }, 'now', 'live', 'lower_traffic_risk')
    await api.routes({ lat: 1, lon: 2 }, { lat: 3, lon: 4 }, 'now', 'live', 'lit_and_busy')

    const bodies = fetcher.mock.calls.map((c) => JSON.parse(String((c as unknown as [string, RequestInit])[1].body)))
    expect(bodies[0]).not.toHaveProperty('prefer')
    expect(bodies[1]).not.toHaveProperty('prefer')
    expect(bodies[2]).toMatchObject({ prefer: 'lit_and_busy' })
  })
})

describe('safety in the offline demo', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    resetFixturesForTests()
  })

  function fixtures(body: Record<string, unknown>) {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), JSON_HEADERS)))
  }

  it('answers SAFETY_UNAVAILABLE locally when no safety fixtures were recorded', async () => {
    fixtures({})
    const res = (await demoResponse('GET', '/safety/meta')) as { error: { code: string } }
    expect(res.error.code).toBe('SAFETY_UNAVAILABLE')
    const hexes = (await demoResponse('GET', '/safety/hexes?bbox=1,2,3,4&hour=9')) as { error: { code: string } }
    expect(hexes.error.code).toBe('SAFETY_UNAVAILABLE')
  })

  it('serves recorded safety fixtures by hour, ignoring the viewport', async () => {
    const meta = { success: true, data: safetyMeta() }
    const hexes = { success: true, data: [safetyHex()] }
    const help = { success: true, data: [helpPoint()] }
    fixtures({ 'GET /safety/meta': meta, 'GET /safety/hexes|21': hexes, 'GET /safety/help-points': help })

    expect(await demoResponse('GET', '/safety/meta')).toEqual(meta)
    expect(await demoResponse('GET', '/safety/hexes?bbox=1,2,3,4&hour=21')).toEqual(hexes)
    expect(await demoResponse('GET', '/safety/help-points?bbox=1,2,3,4')).toEqual(help)
  })

  it('does not pass off a default route as a lit-and-busy one', async () => {
    const recorded = { success: true, data: routes() }
    fixtures({ 'POST /routes 1.0000,2.0000>3.0000,4.0000|live': recorded })
    const body = { origin: { lat: 1, lon: 2 }, destination: { lat: 3, lon: 4 }, cond: 'live' }

    expect(await demoResponse('POST', '/routes', JSON.stringify(body))).toEqual(recorded)
    const lit = (await demoResponse('POST', '/routes', JSON.stringify({ ...body, prefer: 'lit_and_busy' }))) as {
      error: { code: string }
    }
    expect(lit.error.code).toBe('DEMO_ONLY')
  })
})
