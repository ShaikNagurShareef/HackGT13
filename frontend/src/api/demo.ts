/** Offline demo transport (PRD DEMO-01): answers API calls from recorded fixtures. */

export const DEMO_DEPART = '2026-09-25T22:30'
export const DEMO_ROUTE = {
  from: { lat: 33.7771, lon: -84.3962, label: 'Klaus Building' },
  to: { lat: 33.781, lon: -84.3863, label: 'Midtown MARTA' },
}

type Fixtures = Record<string, unknown>
let fixturesPromise: Promise<Fixtures> | null = null

/** Static hosting (GitHub Pages) builds set VITE_FORCE_DEMO=1: no backend, fixtures only. */
export const FORCE_DEMO = import.meta.env.VITE_FORCE_DEMO === '1'
const BASE = import.meta.env.BASE_URL ?? '/'

/** Prefix an absolute app path with the deploy base (e.g. /HackGT13/ on GitHub Pages). */
export function withBase(path: string): string {
  return `${BASE.replace(/\/$/, '')}${path}`
}

export function isDemoMode(search: string = window.location.search): boolean {
  return FORCE_DEMO || new URLSearchParams(search).get('demo') === '1'
}

/** Fetch every fixture up front so the demo keeps working after the network drops. */
export function loadFixtures(fetcher: typeof fetch = fetch): Promise<Fixtures> {
  fixturesPromise ??= fetcher(withBase('/demo/fixtures.json')).then(async (r) => {
    if (!r.ok) throw new Error('demo fixtures missing')
    const fixtures = (await r.json()) as Fixtures
    const meta = fixtures['GET /meta'] as { data?: { static_base?: string } } | undefined
    if (meta?.data?.static_base) meta.data.static_base = withBase(meta.data.static_base)
    return fixtures
  })
  return fixturesPromise
}

export function resetFixturesForTests(): void {
  fixturesPromise = null
}

function coordKey(p: { lat: number; lon: number }): string {
  return `${p.lat.toFixed(4)},${p.lon.toFixed(4)}`
}

/** Map a request onto its fixture key; mirrors backend/app/tools/record_demo.py. */
export function fixtureKey(method: string, path: string, body?: string): string | null {
  const [route, query = ''] = path.split('?')
  const q = new URLSearchParams(query)
  if (method === 'GET' && (route === '/meta' || route === '/conditions/live')) return `GET ${route}`
  if (method === 'GET' && route === '/areas/lookup') return `GET /areas/lookup|${q.get('cond') ?? 'live'}`
  const seg = route.match(/^\/segments\/(\d+)$/)
  if (method === 'GET' && seg) return `GET /segments/${seg[1]}|${q.get('cond') ?? 'live'}`
  if (method === 'POST' && body) {
    const b = JSON.parse(body) as Record<string, unknown>
    if (route === '/routes') {
      const o = b.origin as { lat: number; lon: number }
      const d = b.destination as { lat: number; lon: number }
      return `POST /routes ${coordKey(o)}>${coordKey(d)}|${String(b.cond ?? 'live')}`
    }
    if (route === '/explain' && b.kind === 'route') return `POST /explain route:${String(b.route_key)}`
    if (route === '/explain' && b.kind === 'segment') {
      return `POST /explain segment:${String(b.seg_id)}|${String(b.cond ?? 'live')}`
    }
  }
  return null
}

const DEMO_ONLY = {
  success: false,
  data: null,
  error: {
    code: 'DEMO_ONLY',
    message: 'Demo mode includes Klaus → Midtown MARTA and Tech Square → North Ave MARTA.',
  },
}

export async function demoResponse(method: string, path: string, body?: string): Promise<unknown> {
  if (path.startsWith('/geocode')) return { success: true, data: [], error: null }
  const fixtures = await loadFixtures()
  const key = fixtureKey(method, path, body)
  return (key && fixtures[key]) ?? DEMO_ONLY
}
