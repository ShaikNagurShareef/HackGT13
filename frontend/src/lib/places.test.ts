import { describe, expect, it } from 'vitest'
import { QUICK_PICKS, inBbox, searchPlaces } from './places'

describe('places', () => {
  it('surfaces MARTA stations for "MARTA" (SRCH-01)', () => {
    const labels = searchPlaces('MARTA').map((p) => p.label)

    expect(labels).toEqual(expect.arrayContaining(['Midtown MARTA', 'North Ave MARTA', 'Arts Center MARTA']))
    expect(labels.length).toBeLessThanOrEqual(5)
  })

  it('requires every term to match', () => {
    expect(searchPlaces('midtown marta').map((p) => p.label)).toEqual(['Midtown MARTA'])
    expect(searchPlaces('x')).toEqual([])
    expect(searchPlaces('starbucks')).toEqual([])
  })

  it('has the six curated quick picks (SRCH-02)', () => {
    expect(QUICK_PICKS.map((p) => p.label)).toEqual([
      'Klaus Building',
      'Tech Square',
      'Midtown MARTA',
      'North Ave MARTA',
      'Home Park',
      'Georgia Tech Hotel',
    ])
  })

  it('checks coverage bbox', () => {
    const bbox = [-84.415, 33.745, -84.37, 33.795]

    expect(inBbox(bbox, { lat: 33.7771, lon: -84.3962 })).toBe(true)
    expect(inBbox(bbox, { lat: 33.7748, lon: -84.2963 })).toBe(false)
  })
})
