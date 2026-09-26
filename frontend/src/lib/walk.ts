/** Preview walk (VOX-05): position along a route and when to speak alerts (VOX-02, EC-45). */

export interface WalkAlert {
  start_m: number
  end_m: number
  names: string[]
  score: number
  stretches: number
}

export const ALERT_LEAD_M = 60
export const MIN_ALERT_GAP_S = 45 // walk-time seconds between spoken alerts
export const WALK_SPEED_MPS = 1.3

const R = 6_371_000

function haversine([lon1, lat1]: [number, number], [lon2, lat2]: [number, number]): number {
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(lon2 - lon1)
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

export function cumulativeDistances(coords: ReadonlyArray<[number, number]>): number[] {
  const out = [0]
  for (let i = 1; i < coords.length; i++) out.push(out[i - 1] + haversine(coords[i - 1], coords[i]))
  return out
}

export function pointAlong(
  coords: ReadonlyArray<[number, number]>,
  cum: ReadonlyArray<number>,
  distance: number,
): [number, number] {
  if (distance <= 0) return coords[0]
  const total = cum[cum.length - 1]
  if (distance >= total) return coords[coords.length - 1]
  let i = 1
  while (cum[i] < distance) i++
  const t = (distance - cum[i - 1]) / Math.max(cum[i] - cum[i - 1], 1e-9)
  const [x0, y0] = coords[i - 1]
  const [x1, y1] = coords[i]
  return [x0 + t * (x1 - x0), y0 + t * (y1 - y0)]
}

export interface AlertState {
  spoken: ReadonlySet<number>
  lastSpokenS: number | null
}

/** Index of the alert to speak now, or null (once per alert, respecting the minimum gap). */
export function dueAlert(
  alerts: ReadonlyArray<WalkAlert>,
  walkedM: number,
  walkS: number,
  state: AlertState,
): number | null {
  if (state.lastSpokenS != null && walkS - state.lastSpokenS < MIN_ALERT_GAP_S) return null
  const idx = alerts.findIndex(
    (a, i) => !state.spoken.has(i) && walkedM >= a.start_m - ALERT_LEAD_M && walkedM < a.end_m,
  )
  return idx >= 0 ? idx : null
}

/** Calm wording per PRD §7.4: traffic risk, one action, no "danger"/"safe". */
export function alertText(alert: WalkAlert): string {
  if (alert.stretches > 1 || alert.names.length > 1) {
    const span = Math.round((alert.end_m - alert.start_m) / 10) * 10
    return `Next ${span} meters has ${alert.stretches} high-risk stretches for traffic: ${alert.names.join(' and ')}. Take extra care crossing.`
  }
  return `In ${ALERT_LEAD_M} meters, ${alert.names[0]} has high traffic risk. Take extra care crossing.`
}
