import { describe, expect, it } from 'vitest'
import {
  ARRIVAL_RADIUS_M,
  distanceM,
  formatDistance,
  hasArrived,
  nearestStreet,
  nextInstruction,
  projectOnRoute,
  remainingSeconds,
  startMode,
} from './navigation'
import { cumulativeDistances, type WalkAlert } from './walk'

// ~925 m east along 33.77, then ~1110 m north along -84.39.
const LINE: [number, number][] = [
  [-84.4, 33.77],
  [-84.39, 33.77],
  [-84.39, 33.78],
]
const CUM = cumulativeDistances(LINE)
const TOTAL = CUM[CUM.length - 1]

const ALERTS: WalkAlert[] = [
  { start_m: 300, end_m: 360, names: ['10th St NW'], score: 95, stretches: 1 },
  { start_m: 1400, end_m: 1520, names: ['Spring St', 'Peachtree St'], score: 98, stretches: 2 },
]

const base = { alerts: ALERTS, totalM: TOTAL, durationS: 1560, street: 'Ferst Dr', destination: 'Midtown MARTA' }

describe('distanceM', () => {
  it('measures great-circle metres', () => {
    const d = distanceM({ lat: 33.77, lon: -84.4 }, { lat: 33.77, lon: -84.39 })
    expect(d).toBeGreaterThan(900)
    expect(d).toBeLessThan(950)
    expect(distanceM({ lat: 33.77, lon: -84.4 }, { lat: 33.77, lon: -84.4 })).toBe(0)
  })
})

describe('projectOnRoute', () => {
  it('projects a point beside the first leg onto the polyline', () => {
    const p = projectOnRoute(LINE, CUM, { lat: 33.7702, lon: -84.395 })
    expect(p.alongM).toBeGreaterThan(450)
    expect(p.alongM).toBeLessThan(480)
    expect(p.offsetM).toBeGreaterThan(15)
    expect(p.offsetM).toBeLessThan(30)
  })

  it('projects onto the second leg and clamps before the start', () => {
    const second = projectOnRoute(LINE, CUM, { lat: 33.775, lon: -84.3899 })
    expect(second.alongM).toBeGreaterThan(CUM[1] + 500)
    expect(second.offsetM).toBeLessThan(15)

    const before = projectOnRoute(LINE, CUM, { lat: 33.77, lon: -84.41 })
    expect(before.alongM).toBe(0)
    expect(before.offsetM).toBeGreaterThan(900)
  })

  it('handles a degenerate one-point route', () => {
    const p = projectOnRoute([[-84.4, 33.77]], [0], { lat: 33.77, lon: -84.4 })
    expect(p).toEqual({ alongM: 0, offsetM: 0 })
  })
})

describe('nextInstruction (navigation banner)', () => {
  it('warns about the next high-risk stretch ahead with a rounded distance', () => {
    const i = nextInstruction({ ...base, alongM: 178 })
    expect(i.tone).toBe('alert')
    expect(i.headline).toBe('High traffic risk ahead')
    expect(i.detail).toBe('10th St NW in 120 m')
  })

  it('says when the walker is inside a stretch', () => {
    const i = nextInstruction({ ...base, alongM: 1450 })
    expect(i.tone).toBe('alert')
    expect(i.headline).toBe('High traffic risk here')
    expect(i.detail).toBe('Spring St and Peachtree St · take extra care crossing')
  })

  it('falls back to the current street and remaining minutes', () => {
    const i = nextInstruction({ ...base, alongM: 500 })
    expect(i.tone).toBe('info')
    expect(i.headline).toBe('Continue on Ferst Dr')
    expect(i.detail).toMatch(/^\d+ min to go$/)
  })

  it('names the route when the street is unknown', () => {
    const i = nextInstruction({ ...base, street: null, alongM: 10, alerts: [] })
    expect(i.headline).toBe('Continue on the PathPro route')
  })

  it('announces the destination near the end', () => {
    const i = nextInstruction({ ...base, alerts: [], alongM: TOTAL - 40 })
    expect(i.tone).toBe('arrive')
    expect(i.headline).toBe('Almost there')
    expect(i.detail).toBe('Midtown MARTA in 40 m')
  })

  it('never uses forbidden safety wording', () => {
    for (const along of [0, 178, 330, 500, 1450, TOTAL - 10]) {
      const i = nextInstruction({ ...base, alongM: along })
      expect(`${i.headline} ${i.detail}`).not.toMatch(/\b(safe|safest|danger|guaranteed)/i)
    }
  })
})

describe('remainingSeconds / hasArrived / formatDistance', () => {
  it('scales the route duration by the distance left', () => {
    expect(remainingSeconds(1000, 2000, 500)).toBe(750)
    expect(remainingSeconds(1000, 2000, 5000)).toBe(0)
    expect(remainingSeconds(1000, 0, 0)).toBe(0)
  })

  it('detects arrival within the radius', () => {
    const dest = { lat: 33.78, lon: -84.39 }
    expect(hasArrived({ lat: 33.7801, lon: -84.39 }, dest)).toBe(true)
    expect(hasArrived({ lat: 33.781, lon: -84.39 }, dest)).toBe(false)
    expect(ARRIVAL_RADIUS_M).toBe(30)
  })

  it('formats metres and kilometres', () => {
    expect(formatDistance(8)).toBe('10 m')
    expect(formatDistance(123)).toBe('120 m')
    expect(formatDistance(1234)).toBe('1.2 km')
  })
})

describe('nearestStreet', () => {
  it('returns the name of the closest segment', () => {
    const streets = [
      { path: LINE.slice(0, 2), name: 'Ferst Dr' },
      { path: LINE.slice(1), name: 'State St' },
    ]
    expect(nearestStreet({ lat: 33.7701, lon: -84.396 }, streets)).toBe('Ferst Dr')
    expect(nearestStreet({ lat: 33.777, lon: -84.3901 }, streets)).toBe('State St')
    expect(nearestStreet({ lat: 33.777, lon: -84.3901 }, [])).toBeNull()
  })
})

describe('startMode (GPS navigation or preview walk)', () => {
  it('follows GPS when the walker is on or near the route', () => {
    expect(startMode(LINE, { lat: 33.7702, lon: -84.395 })).toEqual({ mode: 'gps', note: null })
  })

  it('previews the walk when location is off', () => {
    expect(startMode(LINE, null)).toEqual({ mode: 'preview', note: 'Location is off, so Start previews the walk.' })
  })

  it('previews the walk when the walker is far away (e.g. at the expo)', () => {
    const far = startMode(LINE, { lat: 33.79, lon: -84.395 })
    expect(far.mode).toBe('preview')
    expect(far.note).toBe("You're 1.2 km from this route, so Start previews the walk.")
  })
})

describe('ride modes (navigation copy)', () => {
  it('keeps the same alerts and uses ride wording for the street banner', () => {
    expect(nextInstruction({ ...base, alongM: 178, mode: 'bike' }).headline).toBe('High traffic risk ahead')
    expect(nextInstruction({ ...base, alongM: 500, mode: 'bike' }).headline).toMatch(/^Keep riding on /)
  })

  it('previews the ride, not the walk', () => {
    expect(startMode(LINE, null, 'scooter').note).toBe('Location is off, so Start previews the ride.')
  })
})
