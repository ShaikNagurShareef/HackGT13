/** Atlanta-local time helpers: every displayed time is ET regardless of device (EC-25). */

export const TZ = 'America/New_York'
export type DayGroup = 'weekday' | 'friday' | 'saturday' | 'sunday'

const partsFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: TZ,
  weekday: 'short',
  hour: 'numeric',
  hourCycle: 'h23',
  minute: '2-digit',
})

export function atlantaParts(d: Date): { weekday: string; hour: number; minute: number } {
  const parts = Object.fromEntries(partsFmt.formatToParts(d).map((p) => [p.type, p.value]))
  return { weekday: parts.weekday, hour: Number(parts.hour) % 24, minute: Number(parts.minute) }
}

export function dayGroupOf(d: Date): DayGroup {
  const { weekday } = atlantaParts(d)
  if (weekday === 'Fri') return 'friday'
  if (weekday === 'Sat') return 'saturday'
  if (weekday === 'Sun') return 'sunday'
  return 'weekday'
}

export function hourLabel(hour: number): string {
  const h = ((hour % 24) + 24) % 24
  const suffix = h < 12 ? 'AM' : 'PM'
  const twelve = h % 12 === 0 ? 12 : h % 12
  return `${twelve} ${suffix}`
}

export function formatClock(d: Date): string {
  const time = new Intl.DateTimeFormat('en-US', {
    timeZone: TZ,
    hour: 'numeric',
    minute: '2-digit',
  }).format(d)
  return `${time} ET`
}

export function formatMinutes(seconds: number): string {
  return `${Math.max(1, Math.round(seconds / 60))} min`
}

export const DAY_GROUP_LABEL: Record<DayGroup, string> = {
  weekday: 'Mon–Thu',
  friday: 'Friday',
  saturday: 'Saturday',
  sunday: 'Sunday',
}
