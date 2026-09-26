/**
 * Where the API lives. Same-origin by default (VM / local Caddy).
 * Static hosting (GitHub Pages) sets VITE_LIVE_CONFIG=1: on load it reads live.json for the
 * current live API origin and checks its health; if that fails it falls back to the offline
 * demo, so the stable URL never shows a dead app.
 */

const LIVE_CONFIG = import.meta.env.VITE_LIVE_CONFIG === '1'
const PROBE_TIMEOUT_MS = 4000

let apiOrigin = ''
let fallbackDemo = false

export function getApiOrigin(): string {
  return apiOrigin
}

export function usingFallbackDemo(): boolean {
  return fallbackDemo
}

export function resetRuntimeForTests(origin = '', demo = false): void {
  apiOrigin = origin
  fallbackDemo = demo
}

async function fetchWithTimeout(url: string, fetcher: typeof fetch): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS)
  try {
    return await fetcher(url, { signal: controller.signal, cache: 'no-store' })
  } finally {
    clearTimeout(timer)
  }
}

/** Resolve the live API before the app renders. Never throws. */
export async function initRuntime(base: string, fetcher: typeof fetch = fetch, enabled = LIVE_CONFIG): Promise<void> {
  if (!enabled) return
  try {
    const config = (await (await fetchWithTimeout(`${base}live.json`, fetcher)).json()) as { api?: unknown }
    const api = typeof config.api === 'string' ? config.api.replace(/\/$/, '') : ''
    if (!/^https:\/\/[a-z0-9.-]+$/i.test(api)) throw new Error('no live api configured')
    const health = await fetchWithTimeout(`${api}/api/healthz`, fetcher)
    if (!health.ok) throw new Error('live api unhealthy')
    apiOrigin = api
  } catch {
    fallbackDemo = true
  }
}
