import { describe, expect, it } from 'vitest'
import { estimateWalkMin } from './suggestion'

describe('estimateWalkMin', () => {
  it('estimates routed walking minutes from a straight line', () => {
    // Klaus -> Midtown MARTA is ~1 km straight, ~18 min routed.
    expect(estimateWalkMin({ lat: 33.7771, lon: -84.3962 }, { lat: 33.781, lon: -84.3863 })).toBe(17)
    expect(estimateWalkMin({ lat: 33.7771, lon: -84.3962 }, { lat: 33.7771, lon: -84.3962 })).toBe(1)
  })
})
