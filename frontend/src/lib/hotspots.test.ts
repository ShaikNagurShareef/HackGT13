import { describe, expect, it } from 'vitest'
import { hotspotsFor, type HotspotNode } from './hotspots'

describe('hotspotsFor', () => {
  it('scores nodes by their riskiest incident segment and keeps the top 5%', () => {
    const frame = new Uint8Array(100).map((_, i) => i) // segment i scores i
    const nodes: HotspotNode[] = Array.from({ length: 40 }, (_, i) => [
      -84.39,
      33.77,
      [i, i + 60],
    ])

    const hot = hotspotsFor(nodes, frame)

    expect(hot).toHaveLength(2) // 5% of 40
    expect(Math.min(...hot.map((h) => h.score))).toBe(98)
  })

  it('never marks nodes below the High band as hotspots', () => {
    const frame = new Uint8Array(10).fill(40)
    const nodes: HotspotNode[] = [[0, 0, [1, 2]]]

    expect(hotspotsFor(nodes, frame)).toEqual([])
    expect(hotspotsFor([], frame)).toEqual([])
  })
})
