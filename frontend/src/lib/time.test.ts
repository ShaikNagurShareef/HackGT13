import { describe, expect, it } from 'vitest'
import { atlantaParts, dayGroupOf, formatClock, formatMinutes, hourLabel } from './time'

// 2026-09-26T02:30Z is Friday 10:30 PM EDT in Atlanta.
const FRI_NIGHT = new Date('2026-09-26T02:30:00Z')

describe('Atlanta time', () => {
  it('reads wall-clock parts in America/New_York regardless of device zone', () => {
    expect(atlantaParts(FRI_NIGHT)).toEqual({ weekday: 'Fri', hour: 22, minute: 30 })
  })

  it('groups days like the model does', () => {
    expect(dayGroupOf(FRI_NIGHT)).toBe('friday')
    expect(dayGroupOf(new Date('2026-09-26T16:00:00Z'))).toBe('saturday')
    expect(dayGroupOf(new Date('2026-09-27T16:00:00Z'))).toBe('sunday')
    expect(dayGroupOf(new Date('2026-09-29T16:00:00Z'))).toBe('weekday')
  })

  it('labels hours in 12-hour style', () => {
    expect(hourLabel(0)).toBe('12 AM')
    expect(hourLabel(6)).toBe('6 AM')
    expect(hourLabel(12)).toBe('12 PM')
    expect(hourLabel(22)).toBe('10 PM')
    expect(hourLabel(26)).toBe('2 AM')
  })

  it('formats clock with ET suffix and minutes', () => {
    expect(formatClock(FRI_NIGHT)).toBe('10:30 PM ET')
    expect(formatMinutes(1284)).toBe('21 min')
    expect(formatMinutes(10)).toBe('1 min')
  })
})
