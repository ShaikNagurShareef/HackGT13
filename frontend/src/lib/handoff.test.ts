import { describe, expect, it } from 'vitest'
import type { ModeInfo } from '../api/schemas'
import {
  HANDOFF_MIN_S,
  handoffFollowUp,
  handoffTitle,
  martaHandoff,
  nearestStation,
  rideChipLabel,
  rideSuggestion,
  stationLabel,
  stationPlace,
} from './handoff'
import { MARTA_STATIONS } from './martaStations'
import { modeOptions } from './modes'

const NORTH_AVE = { name: 'North Ave', lat: 33.7716, lon: -84.3872, lines: ['Red', 'Gold'] }
const ARTS_CENTER = { name: 'Arts Center', lat: 33.7893, lon: -84.3876 }
const FIVE_POINTS = { name: 'Five Points', lat: 33.7539, lon: -84.3916 }
const STATIONS = [NORTH_AVE, ARTS_CENTER, FIVE_POINTS]

const NEAR_NORTH_AVE = { lat: 33.7716, lon: -84.3935 } // ~580 m west
const NEAR_ARTS_CENTER = { lat: 33.7925, lon: -84.3876 } // ~360 m north
const LONG_WALK_S = 40 * 60

describe('nearestStation', () => {
  it('finds the closest station by straight line, with a rough walk time', () => {
    const near = nearestStation(NEAR_NORTH_AVE, STATIONS)

    expect(near?.station).toBe(NORTH_AVE)
    expect(near?.walkMin).toBe(10)
    expect(nearestStation(NEAR_NORTH_AVE, [])).toBeNull()
  })
})

describe('martaHandoff', () => {
  it('suggests rail when the walk is longer than 25 minutes', () => {
    const h = martaHandoff({ from: NEAR_NORTH_AVE, to: NEAR_ARTS_CENTER, walkDurationS: LONG_WALK_S, stations: STATIONS })

    expect(h?.board.station).toBe(NORTH_AVE)
    expect(h?.alight?.station).toBe(ARTS_CENTER)
    expect(handoffTitle(h!)).toBe('Faster with MARTA: walk 10 min to North Ave station')
    expect(handoffFollowUp(h!)).toBe('…then from Arts Center station, 6 min walk')
  })

  it('stays quiet for short walks, missing ends, or no stations', () => {
    const base = { from: NEAR_NORTH_AVE, to: NEAR_ARTS_CENTER, stations: STATIONS }

    expect(martaHandoff({ ...base, walkDurationS: HANDOFF_MIN_S })).toBeNull()
    expect(martaHandoff({ ...base, walkDurationS: null })).toBeNull()
    expect(martaHandoff({ ...base, to: null, walkDurationS: LONG_WALK_S })).toBeNull()
    expect(martaHandoff({ ...base, stations: [], walkDurationS: LONG_WALK_S })).toBeNull()
  })

  it('skips rail when both ends share a station or the station walks take as long as the trip', () => {
    const sameStation = { from: NEAR_NORTH_AVE, to: { lat: 33.7716, lon: -84.3810 }, stations: STATIONS }
    expect(martaHandoff({ ...sameStation, walkDurationS: LONG_WALK_S })).toBeNull()

    const far = { lat: 33.7716, lon: -84.45 }
    expect(martaHandoff({ from: far, to: NEAR_ARTS_CENTER, walkDurationS: 26 * 60, stations: STATIONS })).toBeNull()
  })

  it('labels stations once and plans a walk to them', () => {
    expect(stationLabel('North Ave')).toBe('North Ave station')
    expect(stationLabel('Midtown Station')).toBe('Midtown Station')
    expect(stationPlace(NORTH_AVE)).toEqual({ lat: 33.7716, lon: -84.3872, label: 'North Ave station' })
  })

  it('ships a bundled MARTA rail list for the offline demo', () => {
    expect(MARTA_STATIONS).toHaveLength(38)
    expect(MARTA_STATIONS.some((s) => s.name === 'North Avenue')).toBe(true)
  })
})

describe('rideSuggestion', () => {
  const BIKE: ModeInfo = { key: 'bike', label: 'Bike', available: true, speed_kmh: 15, network: 'ride', static_prefix: 'ride_' }

  it('offers the first available ride mode for long walks', () => {
    const s = rideSuggestion({ walkDurationS: LONG_WALK_S, distanceM: 3500, options: modeOptions([BIKE]) })

    expect(s).toEqual({ mode: 'bike', minutes: 14 })
    expect(rideChipLabel(s!)).toBe('Try Bike: ~14 min')
  })

  it('stays quiet for short walks or when no ride mode is available', () => {
    expect(rideSuggestion({ walkDurationS: 600, distanceM: 800, options: modeOptions([BIKE]) })).toBeNull()
    expect(rideSuggestion({ walkDurationS: LONG_WALK_S, distanceM: 3500, options: modeOptions([]) })).toBeNull()
  })
})
