import type { SharedWalk } from '../api/walks'

/** A shared walk as GET /walks/{id} returns it: walking to Midtown MARTA, last fix 12 s ago. */
export function sharedWalk(over: Partial<SharedWalk> = {}): SharedWalk {
  return {
    walk_id: 'AbCdEfGhIjKlMnOpQrStUv',
    status: 'walking',
    destination: { label: 'Midtown MARTA', lat: 33.781, lon: -84.3863 },
    eta_s: 600,
    eta_at: '2026-09-27T02:54:00Z',
    position: { lat: 33.7775, lon: -84.395, accuracy_m: 9, at: '2026-09-27T02:44:48Z' },
    updated_at: '2026-09-27T02:44:48Z',
    expires_at: '2026-09-27T08:44:48Z',
    route: [
      [-84.3962, 33.7771],
      [-84.39, 33.779],
      [-84.3863, 33.781],
    ],
    ...over,
  }
}

/** "Now" for follow-page tests: 12 s after the fixture's last position. */
export const FOLLOW_NOW = Date.parse('2026-09-27T02:45:00Z')
