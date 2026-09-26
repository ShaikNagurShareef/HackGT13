import { describe, expect, it } from 'vitest'
import { report } from '../test/fixtures'
import { CATEGORY_LABELS, REPORT_CATEGORIES } from '../api/schemas'
import { routeReportsLine } from './reports'

describe('community report copy', () => {
  it('summarises reports on a route with unique labels', () => {
    const line = routeReportsLine([
      report(),
      report({ seg_id: 12, category: 'sidewalk_blocked', label: 'Sidewalk blocked' }),
      report({ seg_id: 13 }),
    ])

    expect(line).toBe('3 community reports on this route: Construction detour, Sidewalk blocked')
  })

  it('uses the singular for one report and nothing for none', () => {
    expect(routeReportsLine([report()])).toBe('1 community report on this route: Construction detour')
    expect(routeReportsLine([])).toBeNull()
  })

  it('labels every category without alarming words', () => {
    expect(REPORT_CATEGORIES).toHaveLength(6)
    for (const c of REPORT_CATEGORIES) {
      expect(CATEGORY_LABELS[c]).toBeTruthy()
      expect(CATEGORY_LABELS[c].toLowerCase()).not.toMatch(/safe|dangerous|crime|guaranteed/)
    }
  })
})
