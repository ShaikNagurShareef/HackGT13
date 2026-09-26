import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Hourly } from '../api/schemas'
import { hourLabel } from '../lib/time'

/** When crashes happened on this street, by hour — from Tiger Data continuous aggregates. */
export function HourlyChart({ segId, highlightHour }: { segId: number; highlightHour: number }) {
  const [data, setData] = useState<Hourly | null>(null)

  useEffect(() => {
    let cancelled = false
    setData(null)
    api
      .segmentHourly(segId)
      .then((d) => !cancelled && setData(d))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [segId])

  if (!data) return null
  const max = Math.max(1, ...data.crashes)
  const total = data.crashes.reduce((a, b) => a + b, 0)
  if (total === 0) return null
  return (
    <figure className="hourly" aria-label={`Recorded crashes on this street by hour, peak at ${hourLabel(data.crashes.indexOf(max))}`}>
      <figcaption className="faint">When crashes happened here · Tiger Data</figcaption>
      <div className="hourly-bars" aria-hidden="true">
        {data.crashes.map((c, h) => (
          <span
            key={h}
            className={`hourly-bar ${h === highlightHour ? 'now' : ''}`}
            style={{ height: `${Math.max(4, (c / max) * 100)}%` }}
            title={`${hourLabel(h)}: ${Math.round(c)} crashes`}
          />
        ))}
      </div>
      <div className="hourly-axis faint" aria-hidden="true">
        <span>12 AM</span>
        <span>6 AM</span>
        <span>12 PM</span>
        <span>6 PM</span>
      </div>
    </figure>
  )
}
