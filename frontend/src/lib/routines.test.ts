import { describe, expect, it } from 'vitest'
import {
  ROUTINES_STORAGE_KEY,
  clearHistory,
  recentPlaces,
  recordTrip,
  savedPlaces,
  setSavedPlace,
  suggestTrips,
  tripHistory,
  type Place,
  type RoutineSuggestion,
  type TripRecord,
} from './routines'

/** In-memory Storage fake so tests never touch the real localStorage. */
function memoryStorage(seed: Record<string, string> = {}): Storage {
  const data = new Map(Object.entries(seed))
  return {
    get length() {
      return data.size
    },
    clear: () => data.clear(),
    getItem: (k: string) => data.get(k) ?? null,
    key: (i: number) => [...data.keys()][i] ?? null,
    removeItem: (k: string) => void data.delete(k),
    setItem: (k: string, v: string) => void data.set(k, v),
  }
}

function throwingStorage(): Storage {
  const boom = () => {
    throw new Error('SecurityError: storage disabled')
  }
  return { length: 0, clear: boom, getItem: boom, key: boom, removeItem: boom, setItem: boom }
}

const KLAUS: Place = { label: 'Klaus Building', lat: 33.7771, lon: -84.3962 }
const KLAUS_NEARBY = { lat: 33.778, lon: -84.3962 } // ~100 m north of Klaus
const TECH_SQ: Place = { label: 'Tech Square', lat: 33.7765, lon: -84.3893 }
const TECH_SQ_40M: Place = { label: 'Starbucks Tech Square', lat: 33.77686, lon: -84.3893 } // ~40 m away
const HOME: Place = { label: 'Home', lat: 33.785, lon: -84.402 }
const HOME_40M: Place = { label: 'My place', lat: 33.78536, lon: -84.402 }
const MIDTOWN: Place = { label: 'Midtown MARTA', lat: 33.781, lon: -84.3863 }
const PIEDMONT = { lat: 33.7851, lon: -84.3738 } // ~2.2 km from Klaus

// Atlanta is on EDT (UTC-4) for every date used here.
const FRI_940PM = new Date('2026-09-25T21:40:00-04:00')
const FRI_7PM = new Date('2026-09-25T19:00:00-04:00')
const THU_10PM = new Date('2026-09-24T22:00:00-04:00')
const TUE_8AM = new Date('2026-09-22T08:00:00-04:00')

function trip(from: Place, to: Place, at: string): TripRecord {
  return { from, to, at }
}

function seeded(trips: ReadonlyArray<TripRecord>): Storage {
  const storage = memoryStorage()
  trips.forEach((t) => recordTrip(t, storage))
  return storage
}

/** Klaus -> Tech Square on the two previous Friday nights. */
const FRIDAY_NIGHTS = [
  trip(KLAUS, TECH_SQ, '2026-09-11T22:05:00-04:00'),
  trip(KLAUS, TECH_SQ, '2026-09-18T22:00:00-04:00'),
]

function routineTo(suggestions: ReadonlyArray<RoutineSuggestion>, label: string): RoutineSuggestion | undefined {
  return suggestions.find((s) => s.kind === 'routine' && s.to.label === label)
}

describe('trip history storage', () => {
  it('round-trips trips through the versioned storage key, oldest first', () => {
    const storage = memoryStorage()

    recordTrip(trip(KLAUS, TECH_SQ, '2026-09-18T22:00:00-04:00'), storage)
    recordTrip(trip(TECH_SQ, KLAUS, '2026-09-11T22:00:00-04:00'), storage)

    expect(storage.getItem(ROUTINES_STORAGE_KEY)).not.toBeNull()
    expect(tripHistory(storage).map((t) => t.to.label)).toEqual(['Klaus Building', 'Tech Square'])
  })

  it('keeps at most 200 trips and drops the oldest', () => {
    const storage = memoryStorage()
    const base = Date.parse('2026-09-01T12:00:00Z')
    const ats = Array.from({ length: 205 }, (_, i) => new Date(base + i * 60_000).toISOString())

    ats.forEach((at) => recordTrip(trip(KLAUS, TECH_SQ, at), storage))
    const history = tripHistory(storage)

    expect(history).toHaveLength(200)
    expect(history[0].at).toBe(ats[5])
    expect(history[199].at).toBe(ats[204])
  })

  it('ignores invalid trips instead of throwing', () => {
    const storage = memoryStorage()

    recordTrip({ from: KLAUS, to: { label: 'x', lat: Number.NaN, lon: 0 }, at: '2026-09-18T22:00:00Z' }, storage)
    recordTrip({ from: KLAUS, to: TECH_SQ, at: 'not a date' }, storage)

    expect(tripHistory(storage)).toEqual([])
  })

  it('treats corrupt JSON as empty and recovers on the next write', () => {
    const storage = memoryStorage({ [ROUTINES_STORAGE_KEY]: '{not json' })

    expect(tripHistory(storage)).toEqual([])
    expect(savedPlaces(storage)).toEqual({})
    expect(suggestTrips(FRI_940PM, null, storage)).toEqual([])

    recordTrip(FRIDAY_NIGHTS[0], storage)
    expect(tripHistory(storage)).toHaveLength(1)
  })

  it('drops malformed entries but keeps the valid ones', () => {
    const payload = {
      trips: [FRIDAY_NIGHTS[0], { from: 'nowhere' }, 42],
      saved: { home: HOME, work: { label: 'bad', lat: 'x' } },
    }
    const storage = memoryStorage({ [ROUTINES_STORAGE_KEY]: JSON.stringify(payload) })

    expect(tripHistory(storage)).toEqual([FRIDAY_NIGHTS[0]])
    expect(savedPlaces(storage)).toEqual({ home: HOME })
  })

  it('treats a wrong-shaped payload as empty', () => {
    const storage = memoryStorage({ [ROUTINES_STORAGE_KEY]: JSON.stringify(['a', 'b']) })

    expect(tripHistory(storage)).toEqual([])
    expect(savedPlaces(storage)).toEqual({})
  })

  it('never throws when storage itself is unavailable', () => {
    const storage = throwingStorage()

    expect(() => recordTrip(FRIDAY_NIGHTS[0], storage)).not.toThrow()
    expect(() => setSavedPlace('home', HOME, storage)).not.toThrow()
    expect(() => clearHistory(storage)).not.toThrow()
    expect(tripHistory(storage)).toEqual([])
    expect(recentPlaces(storage)).toEqual([])
    expect(savedPlaces(storage)).toEqual({})
    expect(suggestTrips(FRI_940PM, null, storage)).toEqual([])
  })

  it('clearHistory removes trips but keeps saved places', () => {
    const storage = seeded(FRIDAY_NIGHTS)
    setSavedPlace('home', HOME, storage)

    clearHistory(storage)

    expect(tripHistory(storage)).toEqual([])
    expect(savedPlaces(storage)).toEqual({ home: HOME })
  })

  it('sets and removes saved places', () => {
    const storage = memoryStorage()

    setSavedPlace('home', HOME, storage)
    setSavedPlace('work', TECH_SQ, storage)
    setSavedPlace('home', null, storage)

    expect(savedPlaces(storage)).toEqual({ work: TECH_SQ })
  })
})

describe('recentPlaces', () => {
  it('lists distinct destinations, most recent first, with a limit', () => {
    const storage = seeded([
      trip(KLAUS, TECH_SQ, '2026-09-20T10:00:00-04:00'),
      trip(TECH_SQ, MIDTOWN, '2026-09-21T10:00:00-04:00'),
      trip(MIDTOWN, HOME, '2026-09-22T10:00:00-04:00'),
      trip(HOME, TECH_SQ, '2026-09-23T10:00:00-04:00'),
    ])

    expect(recentPlaces(storage).map((p) => p.label)).toEqual(['Tech Square', 'Home', 'Midtown MARTA'])
    expect(recentPlaces(storage, 2).map((p) => p.label)).toEqual(['Tech Square', 'Home'])
  })

  it('clusters points within ~150 m and keeps the most recent label', () => {
    const storage = seeded([
      trip(KLAUS, TECH_SQ, '2026-09-20T10:00:00-04:00'),
      trip(KLAUS, TECH_SQ_40M, '2026-09-21T10:00:00-04:00'),
    ])

    expect(recentPlaces(storage)).toEqual([TECH_SQ_40M])
  })
})

describe('suggestTrips: routines', () => {
  it('needs at least two matching occurrences before calling it a routine', () => {
    const once = seeded([FRIDAY_NIGHTS[1]])
    const twice = seeded(FRIDAY_NIGHTS)

    expect(routineTo(suggestTrips(FRI_940PM, null, once), 'Tech Square')).toBeUndefined()
    expect(routineTo(suggestTrips(FRI_940PM, null, twice), 'Tech Square')).toMatchObject({
      from: KLAUS,
      to: TECH_SQ,
      kind: 'routine',
      reason: 'You usually walk here on Fridays around 10 PM',
    })
  })

  it('treats two nearby-but-distinct points as the same routine destination', () => {
    const storage = seeded([
      trip(KLAUS, TECH_SQ, '2026-09-11T22:05:00-04:00'),
      trip(KLAUS, TECH_SQ_40M, '2026-09-18T22:00:00-04:00'),
    ])

    const suggestions = suggestTrips(FRI_940PM, null, storage)

    expect(suggestions).toHaveLength(1)
    expect(suggestions[0].to).toEqual(TECH_SQ_40M)
  })

  it('matches hour of day and day type: Friday 9:40 PM yes, Tuesday 8 AM no', () => {
    const storage = seeded(FRIDAY_NIGHTS)

    expect(routineTo(suggestTrips(FRI_940PM, null, storage), 'Tech Square')).toBeDefined()
    expect(suggestTrips(TUE_8AM, null, storage)).toEqual([])
  })

  it('scores the same weekday above another weekday at the same hour', () => {
    const storage = seeded(FRIDAY_NIGHTS)
    const friday = routineTo(suggestTrips(new Date('2026-09-25T22:00:00-04:00'), null, storage), 'Tech Square')
    const thursday = routineTo(suggestTrips(THU_10PM, null, storage), 'Tech Square')

    expect(friday).toBeDefined()
    expect(thursday).toBeDefined()
    expect(friday!.score).toBeGreaterThan(thursday!.score)
  })

  it('reads hour and weekday in Atlanta time, not the machine time zone', () => {
    // 02:00 UTC Saturday is 10 PM Friday in Atlanta.
    const storage = seeded([
      trip(KLAUS, TECH_SQ, '2026-09-12T02:00:00Z'),
      trip(KLAUS, TECH_SQ, '2026-09-19T02:00:00Z'),
    ])

    expect(suggestTrips(FRI_940PM, null, storage)[0].reason).toBe('You usually walk here on Fridays around 10 PM')
  })

  it('describes a weekday pattern as weekday mornings', () => {
    const storage = seeded([
      trip(HOME, TECH_SQ, '2026-09-21T08:00:00-04:00'),
      trip(HOME, TECH_SQ, '2026-09-23T08:10:00-04:00'),
    ])

    const [top] = suggestTrips(new Date('2026-09-24T08:15:00-04:00'), null, storage)

    expect(top.reason).toBe('You usually walk here on weekday mornings')
  })

  it('describes a mixed-day pattern by the hour only', () => {
    const storage = seeded([
      trip(HOME, TECH_SQ, '2026-09-19T14:00:00-04:00'), // Saturday
      trip(HOME, TECH_SQ, '2026-09-22T14:00:00-04:00'), // Tuesday
    ])

    const [top] = suggestTrips(new Date('2026-09-24T14:10:00-04:00'), null, storage)

    expect(top.reason).toBe('You usually walk here around 2 PM')
  })

  it('describes a weekend pattern as weekend evenings', () => {
    const storage = seeded([
      trip(HOME, TECH_SQ, '2026-09-19T18:00:00-04:00'), // Saturday
      trip(HOME, TECH_SQ, '2026-09-13T18:00:00-04:00'), // Sunday
    ])

    const [top] = suggestTrips(new Date('2026-09-26T18:00:00-04:00'), null, storage)

    expect(top.reason).toBe('You usually walk here on weekend evenings')
  })

  it('decays older history with a ~14-day half-life', () => {
    const recent = seeded(FRIDAY_NIGHTS)
    const monthOlder = seeded([
      trip(KLAUS, TECH_SQ, '2026-08-14T22:05:00-04:00'),
      trip(KLAUS, TECH_SQ, '2026-08-21T22:00:00-04:00'),
    ])

    const recentScore = suggestTrips(FRI_940PM, null, recent)[0].score
    const olderScore = suggestTrips(FRI_940PM, null, monthOlder)[0].score

    expect(olderScore / recentScore).toBeCloseTo(0.25, 2)
  })

  it('boosts and starts from your location when you are at the origin', () => {
    const storage = seeded(FRIDAY_NIGHTS)
    const unknown = routineTo(suggestTrips(FRI_940PM, null, storage), 'Tech Square')!
    const atOrigin = routineTo(suggestTrips(FRI_940PM, KLAUS_NEARBY, storage), 'Tech Square')!

    expect(atOrigin.from).toBeNull()
    expect(atOrigin.score).toBeGreaterThan(unknown.score * 2)
  })

  it('keeps the named origin at mid distance and down-weights when far away', () => {
    const storage = seeded(FRIDAY_NIGHTS)
    const unknown = routineTo(suggestTrips(FRI_940PM, null, storage), 'Tech Square')!
    const mid = routineTo(suggestTrips(FRI_940PM, HOME, storage), 'Tech Square')!
    const far = routineTo(suggestTrips(FRI_940PM, PIEDMONT, storage), 'Tech Square')!

    expect(mid.from).toEqual(KLAUS)
    expect(mid.score).toBeCloseTo(unknown.score, 6)
    expect(far.score).toBeLessThan(unknown.score)
  })

  it('never suggests a destination within ~200 m of where you are', () => {
    const storage = seeded(FRIDAY_NIGHTS)

    expect(suggestTrips(FRI_940PM, TECH_SQ_40M, storage)).toEqual([])
  })

  it('deduplicates by destination cluster and keeps the best-scoring origin', () => {
    const storage = seeded([
      ...FRIDAY_NIGHTS,
      trip(MIDTOWN, TECH_SQ_40M, '2026-09-04T22:00:00-04:00'),
      trip(MIDTOWN, TECH_SQ_40M, '2026-08-28T22:00:00-04:00'),
    ])

    const suggestions = suggestTrips(FRI_940PM, null, storage)

    expect(suggestions).toHaveLength(1)
    expect(suggestions[0].from).toEqual(KLAUS)
  })

  it('orders by score and applies the limit (default 3)', () => {
    const storage = seeded([
      trip(KLAUS, TECH_SQ, '2026-09-11T22:00:00-04:00'),
      trip(KLAUS, TECH_SQ, '2026-09-18T22:00:00-04:00'),
      trip(KLAUS, MIDTOWN, '2026-09-04T22:00:00-04:00'),
      trip(KLAUS, MIDTOWN, '2026-09-11T21:00:00-04:00'),
      trip(KLAUS, HOME, '2026-08-28T22:00:00-04:00'),
      trip(KLAUS, HOME, '2026-09-04T21:30:00-04:00'),
      trip(HOME, piedmontPlace(), '2026-08-21T22:00:00-04:00'),
      trip(HOME, piedmontPlace(), '2026-08-28T21:00:00-04:00'),
    ])

    const all = suggestTrips(FRI_940PM, null, storage, 10)
    const top = suggestTrips(FRI_940PM, null, storage)

    expect(all).toHaveLength(4)
    expect(all.map((s) => s.score)).toEqual([...all.map((s) => s.score)].sort((a, b) => b - a))
    expect(top).toEqual(all.slice(0, 3))
    expect(all[0].to).toEqual(TECH_SQ)
    expect(suggestTrips(FRI_940PM, null, storage, 0)).toEqual([])
  })

  it('returns nothing for an invalid clock', () => {
    const storage = seeded(FRIDAY_NIGHTS)

    expect(suggestTrips(new Date(Number.NaN), null, storage)).toEqual([])
  })
})

function piedmontPlace(): Place {
  return { label: 'Piedmont Park', ...PIEDMONT }
}

describe('suggestTrips: return trips', () => {
  const OUTBOUND = trip(HOME, TECH_SQ, '2026-09-25T19:40:00-04:00')

  it('offers the reverse trip from your location when you are at the last destination', () => {
    const storage = seeded([OUTBOUND])

    const [top] = suggestTrips(FRI_940PM, TECH_SQ_40M, storage)

    expect(top).toMatchObject({ kind: 'return', from: null, to: HOME, reason: 'Heading back?' })
  })

  it('names the last destination as the start when location is unknown', () => {
    const storage = seeded([OUTBOUND])

    const [top] = suggestTrips(FRI_940PM, null, storage)

    expect(top).toMatchObject({ kind: 'return', from: TECH_SQ, to: HOME })
  })

  it('skips the return trip when the last walk is over 12 h old or you moved on', () => {
    const storage = seeded([OUTBOUND])

    expect(suggestTrips(new Date('2026-09-26T08:00:00-04:00'), null, storage)).toEqual([])
    expect(suggestTrips(FRI_940PM, PIEDMONT, storage)).toEqual([])
  })

  it('ignores trips stamped in the future', () => {
    const storage = seeded([trip(HOME, TECH_SQ, '2026-09-26T09:00:00-04:00')])

    expect(suggestTrips(FRI_940PM, null, storage)).toEqual([])
  })
})

describe('suggestTrips: saved places', () => {
  function withSaved(): Storage {
    const storage = memoryStorage()
    setSavedPlace('home', HOME, storage)
    setSavedPlace('work', TECH_SQ, storage)
    return storage
  }

  it('suggests Home in the evening when you are not already there', () => {
    const storage = withSaved()

    expect(suggestTrips(FRI_7PM, TECH_SQ, storage)).toEqual([
      expect.objectContaining({ kind: 'saved', from: null, to: HOME, reason: 'Home' }),
    ])
    expect(suggestTrips(FRI_7PM, HOME_40M, storage)).toEqual([])
  })

  it('suggests Work on weekday mornings only', () => {
    const storage = withSaved()

    expect(suggestTrips(new Date('2026-09-24T08:30:00-04:00'), HOME, storage)).toEqual([
      expect.objectContaining({ kind: 'saved', to: TECH_SQ, reason: 'Work' }),
    ])
    expect(suggestTrips(new Date('2026-09-26T08:30:00-04:00'), HOME, storage)).toEqual([])
    expect(suggestTrips(new Date('2026-09-24T13:00:00-04:00'), HOME, storage)).toEqual([])
  })

  it('ranks a strong routine above a saved place', () => {
    const storage = seeded([
      trip(KLAUS, MIDTOWN, '2026-09-11T19:00:00-04:00'),
      trip(KLAUS, MIDTOWN, '2026-09-18T19:05:00-04:00'),
    ])
    setSavedPlace('home', HOME, storage)

    const suggestions = suggestTrips(FRI_7PM, KLAUS_NEARBY, storage)

    expect(suggestions.map((s) => s.kind)).toEqual(['routine', 'saved'])
  })

  it('merges a saved place with a routine to the same spot', () => {
    const storage = seeded([
      trip(KLAUS, HOME_40M, '2026-09-11T19:00:00-04:00'),
      trip(KLAUS, HOME_40M, '2026-09-18T19:05:00-04:00'),
    ])
    setSavedPlace('home', HOME, storage)

    const suggestions = suggestTrips(FRI_7PM, null, storage)

    expect(suggestions).toHaveLength(1)
    expect(suggestions[0].kind).toBe('routine')
  })
})
