import { describe, expect, it } from 'vitest'
import { helpPoint, safetyHex, safetyMeta } from '../test/fixtures'
import {
  CRIME_BAND_INFO,
  FAIRNESS_NOTE,
  dayPartFor,
  dayPartName,
  formatRouteCrimes,
  formatRouteSafety,
  helpPointLabel,
  hexSummary,
  hoursLabel,
  safeHref,
  scopeLine,
} from './safety'

const SAFETY = { lit_share: 0.82, busy_share: 0.6, help_points_within_100m: 3, crimes_persons_nearby: 4, day_part: 'evening' }
const PARTS = safetyMeta().day_parts

describe('formatRouteSafety (compact route-row line)', () => {
  it('reads lighting, help points, and foot traffic', () => {
    expect(formatRouteSafety(SAFETY)).toBe('82% well-lit · 3 help points nearby · busier streets')
  })

  it('uses the singular and drops what is unknown or absent', () => {
    expect(formatRouteSafety({ ...SAFETY, help_points_within_100m: 1 })).toBe('82% well-lit · 1 help point nearby · busier streets')
    expect(formatRouteSafety({ ...SAFETY, lit_share: null, busy_share: 0.2, help_points_within_100m: 0 })).toBeNull()
    expect(formatRouteSafety({ ...SAFETY, lit_share: null, busy_share: null })).toBe('3 help points nearby')
  })

  it('is null without safety data (older bundles)', () => {
    expect(formatRouteSafety(null)).toBeNull()
  })

  it('never mentions crime in the compact line', () => {
    expect(formatRouteSafety(SAFETY)).not.toMatch(/crime/i)
  })
})

describe('formatRouteCrimes (expanded panel only)', () => {
  it('states the count with its day part and window', () => {
    expect(formatRouteCrimes(SAFETY, PARTS)).toBe('4 reported crimes against persons nearby (evening, last 12 months)')
    expect(formatRouteCrimes({ ...SAFETY, crimes_persons_nearby: 1 }, PARTS)).toBe(
      '1 reported crime against persons nearby (evening, last 12 months)',
    )
    expect(formatRouteCrimes({ ...SAFETY, crimes_persons_nearby: 0 }, PARTS)).toBe(
      'No reported crimes against persons nearby (evening, last 12 months)',
    )
  })

  it('falls back to the raw day part when the meta does not name it', () => {
    expect(formatRouteCrimes({ ...SAFETY, day_part: 'Overnight' }, [])).toContain('(overnight, last 12 months)')
    expect(formatRouteCrimes(null, PARTS)).toBeNull()
  })
})

describe('day parts', () => {
  it('finds the day part for an hour, wrapping past midnight', () => {
    expect(dayPartFor(21, PARTS)?.key).toBe('evening')
    expect(dayPartFor(2, PARTS)?.key).toBe('night')
    expect(dayPartFor(9, [])).toBeNull()
  })

  it('accepts [start, end) pairs and "18-22" strings from the API', () => {
    const pairs = [{ key: 'evening', label: 'Evening', hours: [18, 22] }]
    const text = [{ key: 'night', label: 'Night', hours: '22-6' }]
    expect(dayPartFor(20, pairs)?.key).toBe('evening')
    expect(dayPartFor(3, text)?.key).toBe('night')
    expect(dayPartFor(12, text)).toBeNull()
  })

  it('labels hours and names keys', () => {
    expect(hoursLabel(PARTS[2])).toBe('5 PM–10 PM')
    expect(hoursLabel(PARTS[3])).toBe('10 PM–6 AM')
    expect(hoursLabel({ key: 'x', label: 'X', hours: '22-6' })).toBe('10 PM–6 AM')
    expect(hoursLabel({ key: 'x', label: 'X', hours: 'whenever' })).toBe('')
    expect(dayPartName('night', PARTS)).toBe('Late night')
    expect(dayPartName('Evening', PARTS)).toBe('Evening')
  })
})

describe('hex and help-point summaries', () => {
  it('describes a hex in calm, factual terms', () => {
    const s = hexSummary(safetyHex(), 'Evening')
    expect(s.title).toBe('This area · Evening')
    expect(s.lines).toEqual([
      '6 reported crimes against persons in the last 12 months (typical for the city)',
      '78% well-lit',
      'Busier streets',
      '2 help points',
    ])
  })

  it('skips unknown signals and uses band wording, never alarm words', () => {
    const s = hexSummary(safetyHex({ crime_band: 'higher', lit_share: null, activity_band: null, help_points: 0 }), null)
    expect(s.title).toBe('This area')
    expect(s.lines).toEqual(['6 reported crimes against persons in the last 12 months (more reports than typical)'])
    expect(CRIME_BAND_INFO.higher.rgb).not.toEqual([255, 0, 0])
  })

  it('names help points by kind', () => {
    expect(helpPointLabel(helpPoint())).toBe('Blue-light emergency phone · Tech Green')
    expect(helpPointLabel(helpPoint({ kind: 'marta', name: 'North Ave' }))).toBe('MARTA station · North Ave')
  })
})

describe('copy helpers', () => {
  it('keeps the fairness note verbatim', () => {
    expect(FAIRNESS_NOTE).toBe(
      'Reported incidents, grouped by area and time of day. Reports reflect where police record incidents, not how people should feel about a neighborhood. PathPro never routes around neighborhoods based on crime.',
    )
  })

  it('states the scope honestly with and without the safety layer', () => {
    expect(scopeLine(true)).toBe(
      'Traffic risk, plus personal-safety signals: lighting, foot traffic, help points, and reported crimes against persons.',
    )
    expect(scopeLine(false)).toBe('Traffic risk from crash history.')
  })

  it('only links http(s) sources', () => {
    expect(safeHref('https://opendata.atlantapd.org/')).toBe('https://opendata.atlantapd.org/')
    expect(safeHref('javascript:alert(1)')).toBeNull()
  })
})
